"""
Web page for the agent (Streamlit). It uses the same agent, tools and
prompt as the terminal chat. Only the display is different: each tool
step is shown live in a box above the answer.

Run (from the repo folder, with the virtual env active):
    streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="Asset Price Assistant", page_icon="💱")

try:
    import agent  # stops with SystemExit if GOOGLE_API_KEY is missing
except SystemExit as e:
    st.error(str(e))
    st.stop()

import cli  # shared step text and error messages, so the page matches the terminal
import trace_log

EXAMPLES = [
    "Give me a market summary for today.",
    "How much is 1 gram of gold in rupiah?",
    "Compare today's IHSG with its Q1 2026 average.",
    "Why did the Taiwan dollar get weaker recently?",
]


# ---------------------------------------------------------
# Session: each browser tab keeps its own conversation
# ---------------------------------------------------------
def _start_conversation():
    st.session_state.history = []  # messages sent to the agent (including tool calls)
    st.session_state.turns = []    # what the page shows: question, steps, answer or error
    trace_log.start_session()


def _ask_example(question: str):
    st.session_state.pending = question


if "history" not in st.session_state:
    _start_conversation()


# ---------------------------------------------------------
# Display helpers
# ---------------------------------------------------------
def _md(text: str) -> str:
    """Make model text safe for st.markdown."""
    # "$4,072 ... $2,370" would be read as a math formula; "<br>" would show as text
    return text.replace("$", "\\$").replace("<br>", " ")


def _step_md(step: dict) -> str:
    return "`" + cli.format_step(step).replace("`", "'") + "`"


def _steps_label(steps: list) -> str:
    calls = sum(step["type"] == "tool_call" for step in steps)
    failed = sum(step["type"] == "tool_result" and not step["ok"] for step in steps)
    if not calls:
        return "No tool needed"
    label = f"🔧 {calls} tool call{'s' if calls > 1 else ''}"
    return label + (f" · ❌ {failed} failed" if failed else "")


def _show_turn(turn: dict):
    """Show one earlier question and answer (steps folded away)."""
    with st.chat_message("user"):
        st.markdown(_md(turn["question"]))
    with st.chat_message("assistant"):
        if turn["steps"]:
            with st.expander(_steps_label(turn["steps"])):
                for step in turn["steps"]:
                    st.markdown(_step_md(step))
        if turn["error"]:
            st.error(turn["error"])
        else:
            st.markdown(_md(turn["answer"]))


def _run_question(question: str):
    """Run one turn and show its steps live, then the answer."""
    with st.chat_message("user"):
        st.markdown(_md(question))
    with st.chat_message("assistant"):
        steps = []
        status = st.status("Working...", expanded=True)

        def on_step(step):
            steps.append(step)
            status.markdown(_step_md(step))

        turn = {"question": question, "steps": steps, "answer": None, "error": None}
        try:
            answer, st.session_state.history = agent.run_turn(
                st.session_state.history, question, on_step=on_step)
            turn["answer"] = answer
            status.update(label=_steps_label(steps), state="complete", expanded=False)
            st.markdown(_md(answer))
        except agent.AgentRunError as e:
            turn["error"] = (cli.ERROR_MESSAGES.get(e.kind, cli.ERROR_MESSAGES["other"])
                             + " This question was not saved to the conversation.")
            status.update(label="Failed", state="error", expanded=True)
            st.error(turn["error"])
        except Exception as e:
            # last safety net: should not happen, but never break the page
            trace_log.log(f"[UI ERROR] {type(e).__name__}: {e}")
            turn["error"] = f"Unexpected error: {e}"
            status.update(label="Failed", state="error", expanded=True)
            st.error(turn["error"])
        st.session_state.turns.append(turn)


# ---------------------------------------------------------
# Page
# ---------------------------------------------------------
with st.sidebar:
    st.header("💱 Asset Price Assistant")
    st.caption("Exchange rates, gold, and the IHSG index in rupiah. "
               "The agent chooses which data tool to use for each question.")
    st.subheader("Try a question")
    for example in EXAMPLES:
        st.button(example, on_click=_ask_example, args=(example,), width="stretch")
    st.divider()
    st.button("🔄 Reset conversation", on_click=_start_conversation, width="stretch")
    st.markdown("🔧 tool chosen · ✅ result OK · ❌ tool failed")
    st.caption(f"Prompt {agent.PROMPT_VERSION} · {agent.MODEL_NAME}\n\n"
               "Data: Frankfurter (daily FX and gold), yfinance (IHSG), DuckDuckGo (search). "
               "Not financial advice.")

st.title("Asset Price Assistant")

for earlier_turn in st.session_state.turns:
    _show_turn(earlier_turn)

typed = st.chat_input("Ask about exchange rates, gold, or IHSG...")
question = typed or st.session_state.pop("pending", None)
if question:
    _run_question(question)
