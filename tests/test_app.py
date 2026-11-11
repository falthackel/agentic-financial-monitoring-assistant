"""
Offline tests for the Streamlit page (app.py), using Streamlit's own test
runner. Gemini is replaced by the same scripted fake model as in
test_agent.py, so no API call is made.
"""

from pathlib import Path
from unittest import mock

import pytest
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langchain.agents import create_agent
from streamlit.testing.v1 import AppTest

import agent
import tools

APP = str(Path(__file__).resolve().parent.parent / "app.py")


class FakeToolModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def fake_agent(*replies):
    return create_agent(FakeToolModel(messages=iter(replies)), tools=tools.ALL_TOOLS,
                        system_prompt="test")


@pytest.fixture
def frankfurter_usd_idr():
    response = mock.Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"date": "2026-11-11", "quote": "USD", "rate": 1.0},
                                  {"date": "2026-11-11", "quote": "IDR", "rate": 16000.0}]
    with mock.patch.object(tools.requests, "get", return_value=response):
        yield


def all_markdown(app) -> str:
    return "\n".join(element.value for element in app.markdown)


def test_page_loads_with_examples():
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert app.title[0].value == "Asset Price Assistant"
    labels = [button.label for button in app.sidebar.button]
    assert "Give me a market summary for today." in labels
    assert "🔄 Reset conversation" in labels


def test_question_shows_steps_and_answer(frankfurter_usd_idr):
    script = fake_agent(
        AIMessage(content="", tool_calls=[{"name": "get_exchange_rate", "id": "c1",
                                           "args": {"from_currency": "USD", "to_currency": "IDR"}}]),
        AIMessage(content="1 USD = 16,000 IDR, about $1 = Rp16,000."),
    )
    with mock.patch.object(agent, "agent", script):
        app = AppTest.from_file(APP).run()
        app.chat_input[0].set_value("USD to IDR?").run()

    assert not app.exception
    text = all_markdown(app)
    assert "🔧 get_exchange_rate(from_currency='USD', to_currency='IDR')" in text
    assert "✅ get_exchange_rate → 1 USD = 16000 IDR (as of 2026-11-11)" in text
    assert "about \\$1 = Rp16,000" in text  # $ escaped, so it isn't read as math
    assert len(app.session_state["history"]) == 4  # question, tool call, tool result, answer


def test_example_button_asks_the_question():
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="Here is the summary."))):
        app = AppTest.from_file(APP).run()
        app.sidebar.button[0].click().run()
    assert app.session_state["turns"][0]["question"] == "Give me a market summary for today."
    assert "Here is the summary." in all_markdown(app)


def test_quota_error_shows_message_and_keeps_history():
    broken = mock.Mock()
    broken.stream.side_effect = Exception("429 RESOURCE_EXHAUSTED")
    with mock.patch.object(agent, "agent", broken):
        app = AppTest.from_file(APP).run()
        app.chat_input[0].set_value("anything").run()
    assert not app.exception
    assert "quota or rate limit" in app.error[0].value
    assert app.session_state["history"] == []


def test_reset_clears_the_conversation():
    with mock.patch.object(agent, "agent", fake_agent(AIMessage(content="first"))):
        app = AppTest.from_file(APP).run()
        app.chat_input[0].set_value("question").run()
        assert len(app.session_state["turns"]) == 1
        reset = next(b for b in app.sidebar.button if b.label == "🔄 Reset conversation")
        reset.click().run()
    assert app.session_state["turns"] == []
    assert app.session_state["history"] == []
