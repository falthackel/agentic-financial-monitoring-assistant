"""
Offline tests for the evaluation: the scoring rules (eval/checks.py) and a
full run of eval/run_eval.py with a fake model instead of Gemini.
"""

import datetime
import json
import sys
from pathlib import Path
from unittest import mock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain.agents import create_agent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "eval"))
import checks  # noqa: E402
import run_eval  # noqa: E402

import agent  # noqa: E402
import tools  # noqa: E402

WEDNESDAY = datetime.date(2026, 11, 11)


# ---------------------------------------------------------
# Tool and argument checks
# ---------------------------------------------------------
def test_placeholders_resolve_from_run_date():
    assert checks.resolve_placeholders("{last_monday}", WEDNESDAY) == "2026-11-09"
    assert checks.resolve_placeholders("{monday_before_last}", WEDNESDAY) == "2026-11-02"
    monday = datetime.date(2026, 11, 9)
    assert checks.resolve_placeholders("{last_monday}", monday) == "2026-11-02"


def test_args_match_ignores_case_and_list_order():
    assert checks.args_match({"assets": "ihsg, xau"}, {"assets": "XAU,IHSG"}, WEDNESDAY)
    assert not checks.args_match({"assets": "XAU"}, {"assets": "XAU,IHSG"}, WEDNESDAY)
    assert checks.args_match({"start_date": "2026-11-02"},
                             {"start_date": ["{last_monday}", "{monday_before_last}"]}, WEDNESDAY)


def test_check_tools_pass_and_failures():
    case = {"expected_tools": ["get_price_table"], "forbidden_tools": ["get_exchange_rate"]}
    good = [{"tool": "get_price_table", "args": {"assets": "USD"}}]
    bad = [{"tool": "get_exchange_rate", "args": {}}]
    assert checks.check_tools(case, good, WEDNESDAY) == []
    problems = checks.check_tools(case, bad, WEDNESDAY)
    assert "get_price_table was not called" in problems
    assert "get_exchange_rate should not be called" in problems


def test_check_tools_counts_and_no_tool_case():
    case = {"expected_tools": ["get_average_exchange_rate"],
            "expected_counts": {"get_average_exchange_rate": 2}}
    one_call = [{"tool": "get_average_exchange_rate", "args": {}}]
    assert checks.check_tools(case, one_call, WEDNESDAY)
    assert checks.check_tools({"expected_tools": []}, one_call, WEDNESDAY)
    assert checks.check_tools({"expected_tools": []}, [], WEDNESDAY) == []


def test_check_answer_requires_a_word():
    case = {"answer_mentions_any": ["search", "according"]}
    assert checks.check_answer(case, "According to news reports...") == []
    assert checks.check_answer(case, "Because of exports.")


# ---------------------------------------------------------
# Number grounding
# ---------------------------------------------------------
@pytest.mark.parametrize("answer, tool_output", [
    ("1 USD = 32.88 TWD", "1 USD = 32.8793 TWD (as of 2026-11-11)"),        # rounded
    ("about Rp16.000", "1 USD = 16000 IDR"),                                # Indonesian thousands
    ("Rp16,000.00 today", "| USD | Rp16,000.00 | ..."),                      # same format
    ("1 USD = 31,79 TWD", "1 USD = 31.7929 TWD"),                           # decimal comma
    ("gold is Rp1.31 million per gram", "Rp1,310,450/g"),                   # word multiplier
    ("up 0.12% today", "🔺 +0.12%"),                                         # percent
    ("about Rp 1,339,000,000 per BTC", "rate is Rp 1,339,621,582"),          # rounded to millions
    ("XYZ is not an ISO 4217 code", "ERROR: no rate"),                       # standard name, not a value
])
def test_grounded_numbers(answer, tool_output):
    assert checks.ungrounded_numbers(answer, [tool_output]) == []


def test_invented_number_is_flagged():
    assert checks.ungrounded_numbers("1 XYZ = 1,234.5 IDR", ["ERROR: no rate found"]) == ["1,234.5"]


def test_round_numbers_with_few_digits_stay_strict():
    assert checks.ungrounded_numbers("about 16,000", ["1 USD = 16900 IDR"]) == ["16,000"]


def test_difference_and_percent_change_are_marked_computed():
    outputs = ["Average 1 TWD = 533.77 IDR", "Average 1 TWD = 554.962 IDR"]
    answer = "It rose by about 21.19 IDR (about a 3.97% increase)."
    result = checks.classify_numbers(answer, outputs, structured_outputs=outputs)
    assert result == {"ungrounded": [], "computed": ["21.19", "3.97"]}


def test_computed_numbers_ignore_search_text():
    outputs = ["Average 1 TWD = 533.77 IDR", "Average 1 TWD = 554.962 IDR"]
    result = checks.classify_numbers("rose by 21.19", outputs, structured_outputs=[])
    assert result["ungrounded"] == ["21.19"]


def test_dates_years_small_numbers_and_question_numbers_are_ignored():
    answer = "On 2026-11-09 at 16:00, in Q1 2026, 1 USD for 2 days, as asked: 550"
    assert checks.ungrounded_numbers(answer, [], question="is it below 550?") == []


# ---------------------------------------------------------
# Full eval run with a fake model (no Gemini)
# ---------------------------------------------------------
class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def test_run_eval_end_to_end(tmp_path, monkeypatch):
    cases_file = tmp_path / "cases.yaml"
    cases_file.write_text(
        "cases:\n"
        "  - id: single_pair\n"
        "    question: USD to IDR?\n"
        "    expected_tools: [get_exchange_rate]\n"
        "  - id: off_topic\n"
        "    question: What is an agent?\n"
        "    expected_tools: []\n", encoding="utf-8")
    monkeypatch.setattr(run_eval, "CASES_FILE", cases_file)
    monkeypatch.setattr(run_eval, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(run_eval, "RESULTS_FILE", tmp_path / "results.md")
    monkeypatch.setattr(run_eval, "REPO_ROOT", tmp_path)

    replies = iter([
        AIMessage(content="", tool_calls=[{"name": "get_exchange_rate", "id": "c1",
                                           "args": {"from_currency": "USD", "to_currency": "IDR"}}]),
        AIMessage(content="1 USD = 16,000 IDR."),
        AIMessage(content="An agent uses tools. It invented 123.45 here."),
    ])
    fake = create_agent(FakeToolModel(messages=replies), tools=tools.ALL_TOOLS, system_prompt="t")
    monkeypatch.setattr(agent, "build_agent", lambda version: fake)

    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"date": "2026-11-11", "quote": "USD", "rate": 1.0},
                                  {"date": "2026-11-11", "quote": "IDR", "rate": 16000.0}]
    with mock.patch.object(tools.requests, "get", return_value=response):
        run_eval.run_cases("v1", only=[], rerun_all=False, delay=0)
    run_eval.write_report()

    saved = json.loads((tmp_path / "runs" / "v1.json").read_text(encoding="utf-8"))
    assert set(saved["cases"]) == {"single_pair", "off_topic"}
    report = (tmp_path / "results.md").read_text(encoding="utf-8")
    assert "| v1 | gemini-3.5-flash-lite |" in report
    assert "2/2 | 1/2 | 0 |" in report          # both pass tool checks, one has an invented number
    assert "123.45" in report
    assert (tmp_path / "runs" / "v1.log").exists()  # eval has its own log
