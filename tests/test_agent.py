"""
Offline tests for one agent turn (M2 live steps, M3 error handling).
Gemini is replaced by a fake model that replies from a fixed script, so
the real LangChain create_agent loop runs without any API call.
"""

import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain.agents import create_agent

import agent
import cli
import tools

REPO_ROOT = Path(__file__).resolve().parent.parent


class FakeToolModel(GenericFakeChatModel):
    """Fake chat model that accepts tools (the base class does not)."""

    def bind_tools(self, tools, **kwargs):
        return self


def fake_agent(*replies):
    """A real create_agent loop whose model answers with the given messages."""
    model = FakeToolModel(messages=iter(replies))
    return create_agent(model, tools=tools.ALL_TOOLS, system_prompt="test")


def tool_call(name, args, call_id):
    return {"name": name, "args": args, "id": call_id}


@pytest.fixture(autouse=True)
def fresh_conversation():
    agent.reset_conversation()
    yield
    agent.reset_conversation()


@pytest.fixture
def frankfurter_usd_idr():
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"date": "2026-11-11", "quote": "USD", "rate": 1.0},
                                  {"date": "2026-11-11", "quote": "IDR", "rate": 16000.0}]
    with mock.patch.object(tools.requests, "get", return_value=response):
        yield


# ---------------------------------------------------------
# M2: each tool call and result is reported live
# ---------------------------------------------------------
def test_two_tool_calls_are_reported_in_order(frankfurter_usd_idr):
    script = fake_agent(
        AIMessage(content="", tool_calls=[
            tool_call("get_exchange_rate", {"from_currency": "USD", "to_currency": "IDR"}, "c1"),
            tool_call("get_exchange_rate", {"from_currency": "XYZ", "to_currency": "IDR"}, "c2"),
        ]),
        AIMessage(content="USD is 16000 IDR. XYZ is not available."),
    )
    steps = []
    with mock.patch.object(agent, "agent", script):
        answer = agent.run_request("USD and XYZ to IDR?", on_step=steps.append)

    assert answer == "USD is 16000 IDR. XYZ is not available."
    assert [(s["type"], s.get("ok")) for s in steps] == [
        ("tool_call", None), ("tool_call", None),
        ("tool_result", True), ("tool_result", False),
    ]
    assert steps[0]["args"] == {"from_currency": "USD", "to_currency": "IDR"}


def test_cli_prints_tool_steps(frankfurter_usd_idr, capsys):
    script = fake_agent(
        AIMessage(content="", tool_calls=[
            tool_call("get_exchange_rate", {"from_currency": "USD", "to_currency": "IDR"}, "c1")]),
        AIMessage(content="done"),
    )
    with mock.patch.object(agent, "agent", script):
        cli.ask("USD to IDR?")
    out = capsys.readouterr().out
    assert "🔧 get_exchange_rate(from_currency='USD', to_currency='IDR')" in out
    assert "✅ get_exchange_rate → 1 USD = 16000 IDR (as of 2026-11-11)" in out


def test_summary_of_multi_line_result():
    assert cli._summarize("| a | b |\n|---|---|\n| 1 | 2 |") == "| a | b | (+2 lines)"


def test_run_turn_keeps_each_conversation_separate():
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="A"), AIMessage(content="B"))):
        answer_a, history_a = agent.run_turn([], "question A")
        answer_b, history_b = agent.run_turn([], "question B")
    assert (answer_a, answer_b) == ("A", "B")
    assert len(history_a) == len(history_b) == 2
    assert agent._conversation_history == []  # the shared CLI history is untouched


def test_format_step_matches_the_terminal_lines():
    call = {"type": "tool_call", "tool": "get_exchange_rate",
            "args": {"from_currency": "USD", "to_currency": "IDR"}}
    result = {"type": "tool_result", "tool": "web_search", "ok": False, "content": "ERROR: down"}
    assert cli.format_step(call) == "🔧 get_exchange_rate(from_currency='USD', to_currency='IDR')"
    assert cli.format_step(result) == "❌ web_search → ERROR: down"


def test_history_is_kept_between_turns():
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="first"))):
        agent.run_request("question 1")
    assert len(agent._conversation_history) == 2  # question + answer


# ---------------------------------------------------------
# M3: failures give a clear error and leave history unchanged
# ---------------------------------------------------------
@pytest.mark.parametrize("error, kind", [
    (Exception("429 RESOURCE_EXHAUSTED: quota exceeded"), "quota"),
    (TimeoutError("Request timed out"), "timeout"),
    (Exception("400 API key not valid"), "auth"),
    (ValueError("something else"), "other"),
])
def test_errors_are_classified(error, kind):
    assert agent._classify_error(error) == kind


def test_failed_turn_rolls_back_history(temp_log_file):
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="first"))):
        agent.run_request("question 1")
    history_before = list(agent._conversation_history)

    broken = mock.Mock()
    broken.stream.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    with mock.patch.object(agent, "agent", broken):
        with pytest.raises(agent.AgentRunError) as error:
            agent.run_request("question 2")

    assert error.value.kind == "quota"
    assert agent._conversation_history == history_before
    assert "[AGENT ERROR] quota:" in temp_log_file.read_text(encoding="utf-8")


def test_error_in_the_middle_of_a_turn_rolls_back_history():
    def stream_then_fail(*args, **kwargs):
        yield {"messages": [AIMessage(content="", tool_calls=[
            tool_call("web_search", {"query": "x"}, "c1")])]}
        raise TimeoutError("timed out")

    broken = mock.Mock()
    broken.stream.side_effect = stream_then_fail
    with mock.patch.object(agent, "agent", broken):
        with pytest.raises(agent.AgentRunError):
            agent.run_request("question")
    assert agent._conversation_history == []


def test_stream_without_final_answer_is_an_error():
    broken = mock.Mock()
    broken.stream.return_value = iter([])  # no state at all
    with mock.patch.object(agent, "agent", broken):
        with pytest.raises(agent.AgentRunError):
            agent.run_request("question")
    assert agent._conversation_history == []


def test_empty_answer_gets_fallback_text():
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content=""))):
        answer = agent.run_request("question")
    assert answer == agent.EMPTY_ANSWER_MESSAGE


def test_cli_keeps_running_after_an_error(capsys):
    broken = mock.Mock()
    broken.stream.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    with mock.patch.object(agent, "agent", broken):
        assert cli.ask("question") is None  # no crash
    out = capsys.readouterr().out
    assert "quota or rate limit" in out

    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="works again"))):
        assert cli.ask("next question") == "works again"


def test_placeholder_api_key_stops_with_clear_message(tmp_path):
    env = dict(os.environ, GOOGLE_API_KEY="your-key-here", PYTHONPATH=str(REPO_ROOT))
    result = subprocess.run([sys.executable, "-c", "import agent"], cwd=tmp_path,
                            env=env, capture_output=True, text=True)
    assert result.returncode == 1
    assert "GOOGLE_API_KEY not set" in result.stderr
    assert "Traceback" not in result.stderr
