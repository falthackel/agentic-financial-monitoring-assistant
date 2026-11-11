"""
Run the evaluation cases against the real agent and write eval/results.md.

Two stages:
1. RUN: ask Gemini each case and save the raw results to eval/runs/<version>.json.
   Only this stage uses quota. Cases already saved are skipped (resume).
2. SCORE: check the saved results (eval/checks.py) and write eval/results.md
   for every version found in eval/runs/. No quota.

Usage (from the repo root):
    python eval/run_eval.py                       # run missing v1 cases, then score
    python eval/run_eval.py --prompt v2           # same for prompt v2
    python eval/run_eval.py --only crypto,follow_up   # re-run only these cases
    python eval/run_eval.py --rerun-all           # re-run every case for this version
    python eval/run_eval.py --report-only         # only rescore saved runs, no Gemini calls
"""

import argparse
import datetime
import json
import sys
import time
from pathlib import Path

# Windows: avoid UnicodeEncodeError (emoji) when output is redirected to a file
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EVAL_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVAL_DIR.parent
RUNS_DIR = EVAL_DIR / "runs"
CASES_FILE = EVAL_DIR / "eval_cases.yaml"
RESULTS_FILE = EVAL_DIR / "results.md"
sys.path.insert(0, str(REPO_ROOT))  # so we can import agent, cli, prompts
sys.path.insert(0, str(EVAL_DIR))   # so we can import checks

import yaml  # noqa: E402

import checks  # noqa: E402

DEFAULT_DELAY_SECONDS = 6     # pause between cases (free-tier per-minute limit)
QUOTA_RETRY_WAIT_SECONDS = 60  # wait once after a 429, then give up on the case


def load_cases() -> list:
    with open(CASES_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f)["cases"]


def load_run(version: str) -> dict:
    path = RUNS_DIR / f"{version}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"version": version, "cases": {}}


def save_run(run: dict):
    RUNS_DIR.mkdir(exist_ok=True)
    path = RUNS_DIR / f"{run['version']}.json"
    path.write_text(json.dumps(run, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------
# Stage 1: run cases against Gemini
# ---------------------------------------------------------
def _ask(agent, question: str, steps: list):
    """One turn, with one retry after a quota error. Returns (answer, error)."""
    for attempt in (1, 2):
        steps.clear()
        try:
            return agent.run_request(question, on_step=steps.append), None
        except agent.AgentRunError as e:
            if e.kind == "quota" and attempt == 1:
                print(f"  ⏳ quota limit hit, waiting {QUOTA_RETRY_WAIT_SECONDS}s and retrying once...")
                time.sleep(QUOTA_RETRY_WAIT_SECONDS)
                continue
            return None, f"ERROR ({e.kind}): {e}"


def run_case(agent, cli, case: dict) -> dict:
    """Run one case in a fresh conversation and return the raw record."""
    agent.reset_conversation(new_log=False)
    record = {
        "run_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "run_date": datetime.date.today().isoformat(),
        "turns": [],
        "error": None,
    }
    for question in case.get("turns") or [case["question"]]:
        print(f"  You: {question}")
        steps = []
        answer, error = _ask(agent, question, steps)
        for step in steps:
            cli.print_step(step)
        record["turns"].append({"question": question, "steps": steps, "answer": answer})
        if error:
            record["error"] = error
            print(f"  ⚠️  {error}")
            break
        print(f"  Agent: {checks_preview(answer)}")
    return record


def checks_preview(text: str, limit: int = 120) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[:limit] + "..."


def run_cases(version: str, only: list, rerun_all: bool, delay: float, repeat: int = 1):
    import agent  # imported here so --report-only works without an API key
    import cli
    import trace_log
    from prompts import PROMPTS

    if version not in PROMPTS:
        raise SystemExit(f"Unknown prompt version {version!r}. Choose one of: {', '.join(PROMPTS)}")

    # the eval has its own log, so it never overwrites agent_log.txt
    RUNS_DIR.mkdir(exist_ok=True)
    trace_log.LOG_FILE = str(RUNS_DIR / f"{version}.log")
    trace_log.start_session()
    agent.agent = agent.build_agent(version)

    run = load_run(version)
    if run.get("prompt_text") and run["prompt_text"] != PROMPTS[version]:
        print(f"⚠️  The {version} prompt changed since the saved run. "
              "Use --rerun-all so all cases use the same prompt.")
    run.update({"model": agent.MODEL_NAME, "prompt_text": PROMPTS[version]})

    cases = load_cases()
    if only:
        unknown = set(only) - {case["id"] for case in cases}
        if unknown:
            raise SystemExit(f"Unknown case id(s): {', '.join(sorted(unknown))}")
        todo = [case for case in cases if case["id"] in only]
    elif rerun_all:
        todo = cases
    else:
        # resume: skip cases that already ran without an error
        todo = [case for case in cases
                if case["id"] not in run["cases"] or run["cases"][case["id"]]["error"]]

    print(f"Prompt {version}: running {len(todo)} of {len(cases)} cases"
          f"{f', {repeat} times each' if repeat > 1 else ''} ({delay:.0f}s pause between runs)\n")
    first = True
    for number, case in enumerate(todo, start=1):
        records = []
        for attempt in range(1, repeat + 1):
            if not first:
                time.sleep(delay)
            first = False
            label = f" (run {attempt}/{repeat})" if repeat > 1 else ""
            print(f"[{number}/{len(todo)}] {case['id']}{label}")
            records.append(run_case(agent, cli, case))
            run["cases"][case["id"]] = records[-1]  # the main table shows the latest run
            if repeat > 1:
                run.setdefault("repeats", {})[case["id"]] = records
            else:
                run.get("repeats", {}).pop(case["id"], None)  # old repeats no longer match
            save_run(run)  # save after every run, so a crash loses nothing
            print()


# ---------------------------------------------------------
# Stage 2: score saved runs and write results.md
# ---------------------------------------------------------
def score_case(case: dict, record: dict) -> dict:
    """Apply the checks to one saved case."""
    if record is None:
        return {"status": "not run"}
    if record["error"]:
        return {"status": "error", "problems": [record["error"].split(":")[0]], "calls": []}

    last_turn = record["turns"][-1]
    calls = [s for s in last_turn["steps"] if s["type"] == "tool_call"]
    results = [s for turn in record["turns"] for s in turn["steps"] if s["type"] == "tool_result"]
    tool_outputs = [s["content"] for s in results]
    structured_outputs = [s["content"] for s in results if s["tool"] != "web_search"]
    search_outputs = [s["content"] for s in results if s["tool"] == "web_search"]
    questions = " ".join(turn["question"] for turn in record["turns"])
    run_date = datetime.date.fromisoformat(record["run_date"])
    answer = last_turn["answer"] or ""

    problems = (checks.check_tools(case, calls, run_date)
                + checks.check_answer(case, answer)
                + checks.check_sources(case, answer, search_outputs))
    numbers = checks.classify_numbers(last_turn["answer"] or "", tool_outputs, questions,
                                      structured_outputs)
    return {
        "status": "pass" if not problems else "fail",
        "problems": problems,
        "calls": calls,
        "ungrounded": numbers["ungrounded"],
        "computed": numbers["computed"],
        "answer": last_turn["answer"] or "",
    }


def _cell(text: str) -> str:
    """Make text safe inside a markdown table cell."""
    return " ".join(str(text).split()).replace("|", "\\|")


def _short_call(call: dict) -> str:
    """get_average_exchange_rate(TWD, IDR, 2026-01-01, 2026-03-31), args in the tool's own order."""
    from tools import ALL_TOOLS
    order = {t.name: list(t.args) for t in ALL_TOOLS}.get(call["tool"], [])
    keys = sorted(call["args"], key=lambda k: order.index(k) if k in order else len(order))
    return f"{call['tool']}({', '.join(str(call['args'][k]) for k in keys)})"


def _status_cell(score: dict) -> str:
    return {"pass": "✅ pass", "fail": "❌ fail", "error": "⚠️ error", "not run": "–"}[score["status"]]


def _grounding_cell(score: dict) -> str:
    if score["status"] not in ("pass", "fail"):
        return "–"
    if score["ungrounded"]:
        return "⚠️ " + ", ".join(score["ungrounded"])
    if score["computed"]:
        return "✅ (computed: " + ", ".join(score["computed"]) + ")"
    return "✅"


def write_report():
    cases = load_cases()
    versions = sorted(path.stem for path in RUNS_DIR.glob("*.json"))
    if not versions:
        raise SystemExit("No saved runs in eval/runs/. Run the eval first.")
    runs = {version: load_run(version) for version in versions}
    scores = {version: {case["id"]: score_case(case, runs[version]["cases"].get(case["id"]))
                        for case in cases}
              for version in versions}

    lines = [
        "# Evaluation Results",
        "",
        f"Generated {datetime.datetime.now():%Y-%m-%d %H:%M} by `python eval/run_eval.py`. "
        f"Cases: [eval_cases.yaml](eval_cases.yaml). Raw runs: [runs/](runs/).",
        "",
        "**How to read this**",
        "- **Result** checks tool choice and arguments (plus a required word in the answer for some cases).",
        "- **Numbers** is a separate check: ✅ means every number in the answer appears in a tool output. "
        "\"computed\" marks numbers that are a difference or % change of two tool numbers "
        "(correct arithmetic, not copied). ⚠️ lists numbers found nowhere: possibly invented, "
        "so they need a human look.",
        "- The model ignores temperature, so results can change between runs. "
        "One run per case is a sample, not a guarantee.",
        "",
        "## Summary",
        "",
        "| Prompt | Model | Run | Result pass | Numbers grounded | Errors |",
        "|---|---|---|---|---|---|",
    ]
    for version in versions:
        version_scores = list(scores[version].values())
        ran = [s for s in version_scores if s["status"] in ("pass", "fail")]
        passed = sum(s["status"] == "pass" for s in ran)
        grounded = sum(not s["ungrounded"] for s in ran)
        errors = sum(s["status"] == "error" for s in version_scores)
        run_dates = sorted({r["run_date"] for r in runs[version]["cases"].values()})
        lines.append(f"| {version} | {runs[version].get('model', '?')} | {', '.join(run_dates)} | "
                     f"{passed}/{len(ran)} | {grounded}/{len(ran)} | {errors} |")

    header = "| Case | Question | Expected tools |"
    divider = "|---|---|---|"
    for version in versions:
        header += f" {version} called | {version} result | {version} numbers |"
        divider += "---|---|---|"
    lines += ["", "## Per case", "", header, divider]
    for case in cases:
        question = " → ".join(case.get("turns") or [case["question"]])
        expected = ", ".join(case.get("expected_tools", [])) or "(no tool)"
        row = f"| `{case['id']}` | {_cell(question)} | {_cell(expected)} |"
        for version in versions:
            score = scores[version][case["id"]]
            called = ", ".join(_short_call(c) for c in score.get("calls", [])) or "(none)"
            if score["status"] in ("error", "not run"):
                called = "–"
            row += f" {_cell(called)} | {_status_cell(score)} | {_cell(_grounding_cell(score))} |"
        lines.append(row)

    lines += ["", "## Problems found", ""]
    any_problem = False
    for version in versions:
        for case in cases:
            score = scores[version][case["id"]]
            if score["status"] in ("fail", "error") or score.get("ungrounded"):
                any_problem = True
                lines.append(f"### {version} · `{case['id']}`")
                for problem in score.get("problems", []):
                    lines.append(f"- {problem}")
                if score.get("ungrounded"):
                    lines.append(f"- numbers not found in any tool output: {', '.join(score['ungrounded'])}")
                if score.get("answer"):
                    lines.append(f"- answer: \"{checks_preview(score['answer'], 300)}\"")
                lines.append("")
    if not any_problem:
        lines.append("None.")

    lines += _repeat_section(cases, versions, runs)
    RESULTS_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {RESULTS_FILE.relative_to(REPO_ROOT)}")


def _repeat_section(cases: list, versions: list, runs: dict) -> list:
    """Table for cases run several times (--repeat): how often each passed."""
    rows = []
    for version in versions:
        for case in cases:
            records = runs[version].get("repeats", {}).get(case["id"])
            if not records:
                continue
            scores = [score_case(case, record) for record in records]
            passed = sum(score["status"] == "pass" for score in scores)
            seen = sorted({problem for score in scores for problem in score.get("problems", [])})
            rows.append(f"| {version} | `{case['id']}` | {passed}/{len(scores)} | "
                        f"{_cell('; '.join(seen)) or '–'} |")
    if not rows:
        return []
    return ["", "## Repeated runs", "",
            "Some cases were run several times (`--repeat`), because one run of a model "
            "that ignores temperature is only a sample.", "",
            "| Prompt | Case | Passed | Problems seen |", "|---|---|---|---|", *rows]


def main():
    parser = argparse.ArgumentParser(description="Run the agent evaluation.")
    parser.add_argument("--prompt", default="v1", help="prompt version to run (default: v1)")
    parser.add_argument("--only", default="", help="comma-separated case ids to (re)run")
    parser.add_argument("--rerun-all", action="store_true", help="re-run every case")
    parser.add_argument("--report-only", action="store_true", help="only rescore saved runs")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY_SECONDS,
                        help="seconds to wait between runs")
    parser.add_argument("--repeat", type=int, default=1,
                        help="run each selected case this many times (e.g. for flaky cases)")
    args = parser.parse_args()

    if not args.report_only:
        only = [case_id.strip() for case_id in args.only.split(",") if case_id.strip()]
        run_cases(args.prompt, only, args.rerun_all, args.delay, max(1, args.repeat))
    write_report()


if __name__ == "__main__":
    main()
