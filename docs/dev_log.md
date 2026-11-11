# Development Log

How this project was built, step by step. Updated after every step.

- **Task table**: one row per task, ready to copy into a spreadsheet or Gantt tool.
- **Gantt chart**: the same tasks as a picture (GitHub draws it).
- **Technical log**: what was done each day, why, and how it was checked.

Dates marked *(inferred)* come from file timestamps, not written notes. Correct them if you remember better.

---

## 1. Task table

Status: `done`, `in progress`, `planned`, `dropped`.

| ID | Phase | Task | Start | End | Status | Evidence |
|---|---|---|---|---|---|---|
| T01 | Setup | Create Python 3.10 virtual env (`.venv`) | 2026-07-29 | 2026-07-29 | done | `.venv` created *(inferred)* |
| T02 | Setup | Get Gemini API key, create `.env` | 2026-07-29 | 2026-07-29 | done | `.env` created *(inferred)* |
| T03 | Build v0 | First working agent run (LangChain + Gemini + tools) | 2026-07-30 | 2026-07-30 | done | first `agent_log.txt` *(inferred)* |
| T04 | Build v0 | Build 4 tools, conversation memory, file log, CLI | 2026-07-30 | 2026-09-16 | done | baseline commit `8a68834` |
| T05 | Build v0 | Prototype TWD/IDR price-alert script | 2026-08-12 | 2026-08-18 | dropped | `twd_idr_history.csv`, `.env` edit *(inferred)*; removed in `bf66fd4` |
| T06 | Build v0 | Architecture diagram (`flowchart.svg`) | 2026-09-16 | 2026-09-16 | done | file date *(inferred)* |
| T07 | Review | Code review, write improvement plan (local project notes, not in the repo) | 2026-11-11 | 2026-11-11 | done | local notes |
| T08 | Safety rails | `.gitignore`, `git init`, baseline commit | 2026-11-11 | 2026-11-11 | done | `8a68834` |
| T09 | Safety rails | Pin dependency versions | 2026-11-11 | 2026-11-11 | done | `9ab2213` |
| T10 | Cleanup | Delete unused alert script, choose English | 2026-11-11 | 2026-11-11 | done | `bf66fd4` |
| T11 | Cleanup | `.env.example` (K2) | 2026-11-11 | 2026-11-11 | done | `8695e98` |
| T12 | Cleanup | Remove false "why" line from log (K3) | 2026-11-11 | 2026-11-11 | done | `7628b4e` |
| T13 | Safety rails | UTF-8 console fix for Windows | 2026-11-11 | 2026-11-11 | done | `60e2164` |
| T14 | Refactor | Translate to English + `ERROR:` prefix for tool failures | 2026-11-11 | 2026-11-11 | done | `ae9cd9e` |
| T15 | Refactor | Split into `tools` / `prompts` / `agent` / `cli` / `trace_log` | 2026-11-11 | 2026-11-11 | done | `2f7a611` |
| T16 | Docs | Simple main README + detailed `docs/README.md` | 2026-11-11 | 2026-11-11 | done | `3edd883` |
| T17 | M2 | Show tool calls and results live in terminal | 2026-11-11 | 2026-11-11 | done | `f91fc58` |
| T18 | Docs | Start this development log | 2026-11-11 | 2026-11-11 | done | `38b66ab` |
| T19 | M3 | Graceful error handling (Gemini 429, timeouts, missing key) | 2026-11-11 | 2026-11-11 | done | `5d5f706` |
| T20 | M4b | Offline unit tests (pytest, mocked network): 32 tests | 2026-11-11 | 2026-11-11 | done | `f0d02fa` |
| T28 | M3 | First live smoke test after the changes (1 question) | 2026-11-11 | 2026-11-11 | done | technical log, Nov 11 |
| T29 | Cleanup | Remove `temperature` (ignored by the model) | 2026-11-11 | 2026-11-11 | done | `a74f78d` |
| T21 | M4 | Evaluation set (13 cases) + `run_eval.py`, run v1: 12/13 | 2026-11-11 | 2026-11-11 | done | `eb3aa8d`, `eval/results.md` |
| T22 | M5 | Prompt v2 from eval failures, re-run (13/13), write iteration log | 2026-11-11 | 2026-11-11 | done | `f325e8a`, `0a658bf`, `docs/prompt_iterations.md` |
| T30 | M5 | Make prompt v2 the default for the chat | 2026-11-11 | 2026-11-11 | done | see technical log |
| T23 | M1 | README with real session + eval results; secret check; push to GitHub | 2026-11-11 | 2026-11-11 | done | `e5de560`, GitHub `main` |
| T31 | M6 | Write `demo_script.md` | 2026-11-11 | 2026-11-11 | done | see technical log |
| T24 | M6 | Clean run + backup recording (Farrel) | 2026-11-15 | 2026-11-15 | planned | |
| T32 | Rehearsal | Partial rehearsal by Farrel; found F1: no IHSG history | 2026-11-11 | 2026-11-11 | done | see technical log |
| T33 | Fix | F1: IHSG history (average / compare periods), v2 re-run 15/15 | 2026-11-11 | 2026-11-11 | done | `78aeebb`, `eval/results.md` |
| T34 | Fix | F2: web_search gives no source names, so the agent invented one | 2026-11-12 | 2026-11-12 | done | `d74f257`, repeated runs 6/6 |
| T35 | UI | Streamlit UI (nice-to-have #7) | 2026-11-12 | 2026-11-12 | done | `f816011` + UI commit; live test pending |
| T25 | Release | Feature freeze, tag `demo-v1` | 2026-11-15 | 2026-11-15 | planned | |
| T26 | Release | Rehearsal, bug fixes only | 2026-11-16 | 2026-11-16 | planned | |
| T27 | Release | Demo day | 2026-11-17 | 2026-11-17 | planned | |

## 2. Gantt chart

```mermaid
gantt
    title Currency Agent - development timeline
    dateFormat YYYY-MM-DD
    axisFormat %b %d

    section Setup
    Virtual env + API key (T01-T02)          :done, t01, 2026-07-29, 1d

    section Build v0
    First agent run (T03)                    :done, t03, 2026-07-30, 1d
    Tools, memory, log, CLI (T04)            :done, t04, 2026-07-30, 2026-09-16
    Alert script prototype, dropped (T05)    :done, t05, 2026-08-12, 2026-08-18
    Architecture diagram (T06)               :done, t06, 2026-09-16, 1d

    section Review and safety rails
    Review + plan, git baseline, pins (T07-T13) :done, t07, 2026-11-11, 1d

    section Improvements
    English + error prefix + split (T14-T15) :done, t14, 2026-11-11, 1d
    README + dev log (T16, T18)              :done, t16, 2026-11-11, 1d
    M2 live tool display (T17)               :done, t17, 2026-11-11, 1d
    M3 error handling (T19)                  :done, t19, 2026-11-11, 1d
    M4b unit tests (T20)                     :done, t20, 2026-11-11, 1d
    Live smoke test (T28)                    :done, t28, 2026-11-11, 1d
    Remove temperature (T29)                 :done, t29, 2026-11-11, 1d
    M4 evaluation, v1 (T21)                  :done, t21, 2026-11-11, 1d
    M5 prompt v2 (T22)                       :done, t22, 2026-11-11, 1d

    section Release
    README final + GitHub push (T23)         :done, t23, 2026-11-11, 1d
    Demo script written (T31)                :done, t31, 2026-11-11, 1d
    Partial rehearsal, finding F1 (T32)      :done, t32, 2026-11-11, 1d
    Fix F1: IHSG history (T33)               :done, t33, 2026-11-11, 1d
    Fix F2: source names in search (T34)     :done, t34, 2026-11-12, 1d
    Streamlit UI (T35)                       :done, t35, 2026-11-12, 1d
    Clean run + recording (T24)              :t24, 2026-11-15, 1d
    Freeze, tag demo-v1 (T25)                :milestone, t25, 2026-11-15, 0d
    Rehearsal (T26)                          :t26, 2026-11-16, 1d
    Demo day (T27)                     :milestone, t27, 2026-11-17, 0d
```

## 3. Technical log

### 2026-07-29 · Setup *(inferred)*
- Created the Python 3.10.11 virtual environment on Windows.
- Got a Gemini API key from Google AI Studio and stored it in `.env`.

### 2026-07-30 → 2026-09-16 · Build v0 *(inferred)*
- First agent run on Jul 30 (first `agent_log.txt`).
- Built one file, `currency_agent.py` (~550 lines), with:
  - 4 tools: `get_exchange_rate`, `get_average_exchange_rate`, `get_price_table`, `web_search`
  - EUR-pivot math, because Frankfurter only gives rates against EUR
  - gold per gram / per 0.01 gram, IHSG from yfinance
  - conversation memory within a session, `reset` command, ESC to quit
  - a trace of every tool call in `agent_log.txt`
- Aug 12–18: tried a separate TWD/IDR price-alert script. Not connected to the agent. Later dropped.
- Sep 16: drew `flowchart.svg`. Last logged session before the review.

### 2026-11-11 · Review, safety rails, first improvements
**Review.** Wrote the project plan (local project notes, not in the repo): the goal (a live demo on Nov 17), working rules, known issues K1–K7, and must-haves M1–M6.

**Safety rails** (so nothing breaks the working demo):
- `8a68834` Added `.gitignore` first (`.env`, `.venv/`, logs), then `git init`. Checked `.env` is ignored and scanned for key patterns before the first commit.
- `9ab2213` Pinned all packages to the exact versions in `.venv` (`==` instead of `>=`).
- `60e2164` `sys.stdout.reconfigure(encoding="utf-8")` so emoji don't crash when output goes to a file. Checked by redirecting output to a file.

**Decisions**
- Demo language: **English** (the audience may not read Indonesian).
- `twd_idr_alert.py`: **delete**, it was unused (`bf66fd4`).

**Cleanup**
- `8695e98` `.env.example` with a placeholder key (K2).
- `7628b4e` Removed a hard-coded log line that always said "the structured tools could not answer" whenever web search ran. It was often false (K3). This is also the first known failure for the prompt log (M5).

**Refactor**
- `ae9cd9e` Translated everything user-facing to plain English. The prompt kept the same meaning and moved to `SYSTEM_PROMPT_V1`. Every tool failure now starts with `ERROR:`, so code checks one prefix instead of the wording. Failure log lines hold tool, arguments, and reason on one line.
- `2f7a611` Split the single file into `tools.py`, `prompts.py`, `agent.py`, `cli.py`, `trace_log.py`. `currency_agent.py` is now only the entry point. Reason: the CLI, the eval, and a future UI all need the same "run one turn" logic, so it lives in `agent.py`.
- Check after each step: compile, import (no chat, no LLM call), and an offline script with fake network data covering the EUR math, every tool's error path, and the price table with one or all assets failing.

**Docs**
- `3edd883` Main README cut down to 4 sections (background, directory, setup, run). The detail moved to `docs/README.md`. Removed the invented example session (K4). Folded in and deleted `read.md`.

**M2: live tool display**
- `f91fc58` `agent.run_request` now uses `agent.stream(..., stream_mode="values")` and reports each step through an `on_step` callback. `cli.py` prints `🔧 tool(args)` and `✅/❌ tool → first line (+N lines)`.
- History is saved only after the turn finishes, so a crash halfway doesn't leave a half-finished turn in memory.
- Check: ran the real `create_agent` loop offline with a scripted fake model (instead of Gemini) that calls two tools, one good and one bad. Both calls and both results printed before the final answer.

**M3: error handling**
- `5d5f706` In `agent.py`:
  - The program stops at startup with a one-line message if `GOOGLE_API_KEY` is missing or still the placeholder. Before, the Gemini library crashed with a long stack trace as soon as the program started.
  - Gemini now has `timeout=30, max_retries=2`. The library default is 6 retries, which uses up the free quota quickly.
  - Any failure in a turn becomes `AgentRunError` with a kind: `quota` (429 / RESOURCE_EXHAUSTED), `timeout`, `auth`, or `other`. Logged as `[AGENT ERROR] kind: reason`.
  - A turn with no final answer is an error. An answer with no text gets a fallback message.
- In `cli.py`: `_answer()` shows a clear message per error kind and never lets the loop crash. Ctrl+C cancels only the current question.
- In `tools.py`: yfinance timeout set explicitly (`YF_TIMEOUT = 10`).
- History rollback was already done in M2 (history is saved only after a turn succeeds).

**M4b: offline unit tests**
- Installed `pytest==9.2.0` (Farrel's OK), listed in `requirements-dev.txt` so the main requirements stay small.
- `f0d02fa` 32 tests in `tests/`, none of them use Gemini or the internet:
  - `test_tools.py`: EUR-pivot math (EUR as source or target, missing quote, empty response), `ERROR:` prefix on every tool failure, one-line failure log, price table with one or all assets failing.
  - `test_agent.py`: runs the real `create_agent` loop with a scripted fake model. Checks M2 step events and CLI output, error kinds, history rollback (also when a turn fails halfway), empty answer fallback, the CLI continuing after an error, and the clear message for a placeholder API key.
  - `conftest.py` sets a fake API key and sends the log to a temp folder, so tests never touch the real key or `agent_log.txt`.

**Live smoke test** (Farrel's OK, 2 Gemini requests)
- Saved the old `agent_log.txt` (Sep 16 session, K3 evidence) to `docs/evidence/` first, because a new session overwrites it.
- Question "USD to TWD rate":
  ```
  🔧 get_exchange_rate(to_currency='TWD', from_currency='USD')
  ✅ get_exchange_rate → 1 USD = 32.8793 TWD (as of 2026-11-11)
  Agent: The current exchange rate is 1 USD = 32.8793 TWD (as of November 11, 2026).
  ```
  English prompt, split code, live steps, and the log all worked.
- **Finding:** Gemini warned `Model 'gemini-3.5-flash-lite' uses fixed sampling defaults; temperature will be ignored`. So `temperature=0` has no effect on this model. Answers can vary between runs, and the eval must allow for that.

**Lost log (mistake).** The Sep 16 session in `agent_log.txt` was overwritten at 19:49 by a scratch test script that called `reset_conversation()` without sending the log elsewhere. The backup copy was made too late, so it held only test output and was deleted. K3 is still proven by the baseline code (`8a68834`), which logged the false reason on every web search. Since then, tests and the eval always write to their own log file.

**Remove temperature**
- `a74f78d` Removed `temperature=0`, because the model ignores it. Updated the local project notes.

**M4: evaluation**
- `eb3aa8d` Built the eval in two stages, so quota is only spent when needed:
  - *run*: asks Gemini each case in a fresh conversation (6 s pause, one retry after 60 s on a 429), saves every tool call, result and answer to `eval/runs/<version>.json` after each case. Resumes where it stopped. `--only` re-runs single cases.
  - *score*: `eval/checks.py` checks tool choice, arguments (with date placeholders like `{last_monday}`), required words, and number grounding (handles `16,000` / `16.000` / `31,79` / "million", rounding). Writes `eval/results.md`. `--report-only` rescores for free.
  - Prompt versions: `prompts.PROMPTS`, `agent.build_agent(version)`, env var `PROMPT_VERSION`.
  - 13 cases, see `eval/eval_cases.yaml`. Offline tests for the checks and a full fake-model run: 48 tests in total.
- **v1 run** (Farrel's OK, about 35 Gemini requests, 19 tool calls, 0 quota errors): **12/13 tool choice pass.**
  - `causal_why` **failed**: 3 searches, and only 1 result was relevant (the others were converter pages and a 2008 article). The answer still listed 3 causes as facts, with no attribution, and one (TSMC / AI demand) appears in no search result. This is the known M5 failure.
  - `compare_q1_q2` was first flagged for numbers 21.19 and 3.97. A manual check showed they are correct: Q2 − Q1 and the % change. Changed the checker to mark such numbers "computed" instead of "ungrounded", but only for structured tools (search text has too many numbers). After rescoring: 13/13 grounded.
  - `relative_date` passed but made one extra, unneeded `get_exchange_rate` call first.
  - Fixed the report to show arguments in the tool's parameter order.

**M5: prompt v2**
- `f325e8a` `SYSTEM_PROMPT_V2` = v1 + two rules, one per observed failure:
  - Rule A (`causal_why`): only give reasons found in the search results, name the source, say so if the search doesn't explain the move.
  - Rule B (`relative_date`): for one past date, use `get_average_exchange_rate` with start = end.
  - Not added, since the eval showed no failure for them: "never state an ungrounded number", "say data is unavailable", "answer in the user's language".
- **v2 run** (about 35 Gemini requests, 0 quota errors; about 70 for the day): **13/13 tool choice.**
  - `causal_why`: the searches returned The Walking Dead ("TWD") and CNN's front page. v2 still didn't invent a cause: it said the results show the TWD *weakened*, and every claim was found word for word in the search results (hand check). It named sources only loosely ("market reports").
  - `relative_date`: one call instead of two. Read "last Monday" as Nov 2 (v1: Nov 9). Both accepted, and the date was stated.
- `0a658bf` Checker fixes after hand checks, applied to both versions: large round numbers count as rounded (only with 3+ significant digits), "ISO 4217" is not a value. 51 tests.
- Wrote `docs/prompt_iterations.md`: K3, v1 failures with evidence, v2 change, result, checker fixes, limits (one run per case, the word check can be gamed), and v3 ideas.
- **Gemini quota:** no 429 in either run. The free daily quota resets at midnight US Pacific = 08:00 UTC = **16:00 Taiwan time** (Google docs). Limits are per Google Cloud project, not per key.
- Commit messages: PowerShell 5.1 strips double quotes from `git commit -m`, so messages with quotes now go through `git commit -F <file>`.
- Made v2 the default prompt for the chat (`DEFAULT_PROMPT_VERSION = "v2"`), Farrel's decision. v1 is still available with `PROMPT_VERSION=v1`.

**Publish to GitHub** (done 3 days ahead of the Nov 14 plan)
- Sample session: 3 live questions in one conversation (prompt v2, about 8 Gemini requests): market summary table, a follow-up comparing SGD to its Q1 average (memory + average tool), and "why did the Taiwan dollar get weaker?" (web search, one search failed, answer cited Bloomberg). Repeated the search without Gemini to confirm the Bloomberg quote. Added to `docs/README.md` with notes on what it shows (`e5de560`).
- Fresh-clone test: cloned to a temp folder. All 51 tests passed with only committed files, and the app without `.env` stopped with the one-line key message. Not tested: `pip install` into a brand-new venv (large download).
- Secret scan of **all** commits: `.env` never committed, no Google key pattern in any diff.
- The repo is public, so the local project plan and the learning notes were removed from **all** commits before the first push (`git filter-branch`, backup bundle kept). Personal details in old versions of this log were neutralized at the same time. Commit hashes changed, so every hash in this log and in `prompt_iterations.md` was updated to the new ones. Both files are now in `.gitignore` and stay on disk.
- Branch renamed `master` → `main`. Pushed to https://github.com/falthackel/agentic-financial-monitoring-assistant.

**M6: demo script**
- Wrote `demo_script.md`: a checklist for before the demo (quota reset time, terminal, test question), 6 questions in one conversation (table → follow-up → gold per gram → unknown code with fallback → "why" with source → off-topic), what to point at and say for each, a closing tour of the eval and the prompt log, a 2–3 minute recording plan, and what to do if something fails live.
- Order chosen so each question shows one new thing, the follow-up comes right after the question it depends on, and the error case comes before the prompt-fix story.
- Not yet rehearsed live: the full script uses about 15–20 Gemini requests.

### 2026-11-11 · Rehearsal finding F1: no IHSG history
- **Found by:** Farrel, during a partial rehearsal (pushed `f82df48` first).
- **Symptom:** the agent can give today's IHSG, but not IHSG history: no average over a period, and no comparison of today with the past.
- **Cause (checked without Gemini):**
  - The only history tool, `get_average_exchange_rate`, gets its data from Frankfurter, which only has currencies. With IHSG it returns `ERROR: ... 422 Unprocessable Entity`.
  - IHSG comes from yfinance (`^JKSE`), and `_get_ihsg_data()` only fetches the last 5 days, for today's price and % change.
  - yfinance **does** have the history: for Q1 2026 it returned 55 trading days (2026-01-02 to 2026-03-31, average close 8,184.86). So the data source exists, but no tool asks it for a date range.
- **Effect:** the agent can only fall back to `web_search`, which can't reliably compute an average over a date range.
- **Why the eval missed it:** none of the 13 cases asks for IHSG history. A case will be added with the fix, so this stays covered.
- **Status:** recorded, fix planned (T33). Fix options are listed in the next entry once chosen.

### 2026-11-11 · Fix F1: IHSG history
- **Chosen (Farrel): option A**, extend `get_average_exchange_rate` instead of adding a 5th tool. This keeps the 4-tool design, and fewer tools means fewer wrong choices for the model.
- **Data check first:** today's IHSG (5,115) is about 37% below the Q1 average (8,185). The monthly yfinance data showed a steady fall all year with no gaps (largest day −11.6% on Oct 16), so the comparison is valid.
- `78aeebb` in `tools.py`:
  - `from_currency="IHSG"` uses yfinance `^JKSE` daily closes (`_get_index_history`), with both dates included (yfinance's end date is exclusive, so +1 day). No data → `ERROR:` with "the market may have been closed".
  - Tool descriptions say the history tool covers IHSG. The model only sees descriptions, so this is how it learns the new ability.
  - The price table shows IHSG in **index points** (`5,115.04 pts`), not `Rp`, which was a wrong unit.
  - yfinance's "possibly delisted" message for days without trading is hidden (it was false and alarming on screen).
  - 7 new unit tests (58 total), 2 new eval cases: `ihsg_average`, `ihsg_today_vs_history`.
- **v2 re-run, all 15 cases** (about 40 Gemini requests, 0 errors): **15/15 tool choice, 15/15 numbers grounded**, no regressions. v1 was not re-run, so its column shows "–" for the 2 new cases and was measured with the old tool descriptions.
  - `ihsg_average`: 8,184.86 points, 55 trading days, min and max. Correct.
  - `ihsg_today_vs_history`: called both tools (history + table) and compared 5,115.04 with 8,184.86 points. Correct.

### 2026-11-11 · Finding F2: invented source name
- **Found by:** hand check of `causal_why` in the v2 re-run (the eval passed it).
- **Symptom:** the answer said "According to recent reports (such as from *Focus Taiwan* or similar financial news updates)". Both causes it gave (a stock rally, trade-deal speculation) are in the search results. But "Focus Taiwan" and "key psychological levels" appear **nowhere** in them.
- **Cause:** `web_search` returns each result as `- title: text` and drops the site/URL that DuckDuckGo provides. Prompt v2 Rule A asks the model to "say which source each reason comes from", but the tool never tells it the source. The first v2 run fell back on "market reports". This run guessed a plausible name. The sample session's "Bloomberg" was correct only because it was in a title.
- **Why the eval missed it:** the checks look for the word "according" and for grounded *numbers*, not for grounded *source names*.
- **Planned fix (T34):** add each result's site to the `web_search` output (e.g. `[bloomberg.com]`) and an eval check that every source named in an answer appears in the search results.

### 2026-11-12 · Fix F2: source names in search results
- `d74f257`, a tool fix (the prompt is unchanged; Rule A was fine, it just couldn't be followed):
  - `web_search` lines now start with the site from the result URL: `- [bloomberg.com] title: text`. The log line lists the sites too, so the log now shows where answers came from.
  - New eval check `check_sources` (turned on for `causal_why` and `crypto`): a capitalized name after "according to", "such as (from)", "reported by", or "citing" must appear in the search results (text or site). Vague phrases ("according to recent reports") are skipped.
  - Re-scoring the saved runs (no Gemini) flagged the old "Focus Taiwan" answer: v2 went from 15/15 to **14/15**. The eval now catches what only the hand check caught before.
  - New `--repeat N` in `run_eval.py`, which runs a case N times and reports k/N.
  - 7 new tests (65 total).
- **Verification** (about 20 Gemini requests, 0 errors): `causal_why` and `crypto` on v2, 3 runs each → **3/3 and 3/3**. v2 back to 15/15.
  - `causal_why`: all 3 runs named *The Edge Malaysia*, and `theedgemalaysia.com` was in every result. Run 3 also cited *The Helper* (`thehelper.net`), which is real and matches the text, but is a forum, not a news site.
  - `crypto`: run 3 labelled a price "Indodax" with `[binance.com]`. Hand check: DuckDuckGo returned one binance.com result whose title merges several sites, including Indodax, and the price is in that text. A data quirk, not an invention.
  - **Hand check: no invented source in 6 of 6 runs.**
- **Open (v3 idea):** source *quality*. The agent treats a forum like a newspaper.
- Small fix in `run_eval.py`: the "prompt changed since the saved run" warning fired because the prompt starts with today's date. It now ignores the date.

### 2026-11-12 · Streamlit UI (nice-to-have #7)
- Installed `streamlit==1.65.0` (Farrel's OK). No other package changed (`pip check` clean). Pinned in `requirements.txt`.
- `f816011` refactor, no behavior change:
  - `agent.run_turn(history, question, on_step)` returns `(answer, new_history)`. `run_request()` (CLI, eval) wraps it with the shared history. This lets each browser tab keep its own conversation.
  - `cli.format_step(step)` gives the 🔧/✅/❌ text, shared by the terminal and the page, so the formatting isn't copied.
- `app.py`: chat, a live status box that fills with each step and then folds to "🔧 N tool calls", example question buttons, a reset button, and the same error messages as the CLI. A missing key shows a clear message instead of a stack trace. **No agent logic in the page**: it only calls `agent.run_turn`.
- Display details found while building:
  - `$` in answers is escaped, because Streamlit reads text between two `$` as a math formula ("$4,072/oz … $2,370" would be garbled).
  - `<br>` in tables (Gemini writes it, see the sample session) is replaced with a space.
  - `use_container_width` is deprecated in Streamlit 1.65, so `width="stretch"` is used (avoids a warning on screen).
- **Security:** the first server start showed a *Network URL* (`140.112.x.x`), so anyone on the university network could have used the page, and with it the API key and quota. `.streamlit/config.toml` now binds to `127.0.0.1` only (not `localhost`: PowerShell resolved that to IPv6 first and failed). Checked: reachable on 127.0.0.1, not reachable on the network address. Usage statistics are off.
- **Checks:** 5 offline page tests with Streamlit's `AppTest` and the fake model (page loads, live steps + answer with `$` escaped, example button, quota error keeps history, reset). 72 tests in total. Real server started and stopped (health `ok`, HTTP 200) without asking a question, so no Gemini call.
- **Not yet done:** a live question through the page (needs Gemini quota, Farrel's OK). Added an optional "bonus" section to `demo_script.md`.
