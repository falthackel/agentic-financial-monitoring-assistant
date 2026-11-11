"""
The agent: Gemini model + LangChain create_agent + the 4 tools, and the
conversation history for one chat session.

Used by the CLI (cli.py). The evaluation and a future UI can import it too.
"""

import os

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

import trace_log
from prompts import DEFAULT_PROMPT_VERSION, PROMPTS
from tools import ALL_TOOLS, TOOL_ERROR_PREFIX

load_dotenv()  # read GOOGLE_API_KEY from the .env file in this folder

API_KEY = os.environ.get("GOOGLE_API_KEY", "").strip()
if not API_KEY or API_KEY == "your-key-here":
    # stop with a clear message instead of a long error from the Gemini library
    raise SystemExit("GOOGLE_API_KEY not set — copy .env.example to .env and add your key.")

EMPTY_ANSWER_MESSAGE = "(The model returned no text answer. Please try again or rephrase the question.)"

# ---------------------------------------------------------
# Set up the Gemini model + agent
# ---------------------------------------------------------
# No temperature setting: this model uses fixed sampling and ignores it
# (Gemini prints a warning if we set it). See docs/learning_notes.md.
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    api_key=API_KEY,
    timeout=30,      # seconds per Gemini request
    max_retries=2,   # library default is 6, which uses up the free quota fast
)

MODEL_NAME = llm.model

# which system prompt to use: set PROMPT_VERSION=v2 to try another version
PROMPT_VERSION = os.environ.get("PROMPT_VERSION", DEFAULT_PROMPT_VERSION)
if PROMPT_VERSION not in PROMPTS:
    raise SystemExit(f"Unknown PROMPT_VERSION {PROMPT_VERSION!r}. Choose one of: {', '.join(PROMPTS)}")


def build_agent(prompt_version: str):
    """Create the agent with the given system prompt version."""
    return create_agent(llm, tools=ALL_TOOLS, system_prompt=PROMPTS[prompt_version])


agent = build_agent(PROMPT_VERSION)


# ---------------------------------------------------------
# Errors
# ---------------------------------------------------------
class AgentRunError(Exception):
    """A turn failed. kind is 'quota', 'timeout', 'auth' or 'other'."""

    def __init__(self, kind: str, reason: str):
        super().__init__(reason)
        self.kind = kind


def _classify_error(error: Exception) -> str:
    """Guess the kind of failure from the error type and message."""
    text = f"{type(error).__name__} {error}".lower()
    if any(word in text for word in ("429", "resource_exhausted", "quota", "rate limit")):
        return "quota"
    if any(word in text for word in ("timeout", "timed out", "deadline")):
        return "timeout"
    if any(word in text for word in ("api key", "api_key", "permission_denied", "unauthenticated")):
        return "auth"
    return "other"


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------
def extract_text(message) -> str:
    """Keep only the text parts of a Gemini 3.x reply (a list of blocks)."""
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts).strip()
    return str(content)


_conversation_history = []  # all messages from earlier turns in this chat session


def has_history() -> bool:
    return bool(_conversation_history)


def reset_conversation(new_log: bool = True):
    """Clear the conversation history. By default also start a fresh session log."""
    global _conversation_history
    _conversation_history = []
    if new_log:
        trace_log.start_session()


def _steps_from_message(message) -> list:
    """
    Turn one new message into step events:
    - AIMessage with tool_calls -> the agent chose a tool
    - ToolMessage               -> a tool result came back
    """
    if isinstance(message, AIMessage):
        return [{"type": "tool_call", "tool": call["name"], "args": call["args"]}
                for call in message.tool_calls]
    if isinstance(message, ToolMessage):
        content = str(message.content)
        ok = message.status != "error" and not content.startswith(TOOL_ERROR_PREFIX)
        return [{"type": "tool_result", "tool": message.name, "ok": ok, "content": content}]
    return []


def run_request(question: str, on_step=None) -> str:
    """
    One question-and-answer turn. The earlier conversation (if any) is
    sent to the agent too, so it has CONTEXT from previous turns in the
    same session. For example, in "why did it go up?" the agent knows
    "it" means the asset from the previous turn, instead of guessing.

    on_step: optional function called with each step (a dict) as soon as
    it happens, so the caller can show it live. See _steps_from_message.

    Raises AgentRunError if the turn fails. The history is then unchanged,
    as if the question was never asked.
    """
    global _conversation_history
    trace_log.log_request(question)

    messages = _conversation_history + [("human", question)]
    seen = len(messages)
    final_state = None
    try:
        # stream_mode="values" gives the full state after every agent step
        for state in agent.stream({"messages": messages}, stream_mode="values"):
            final_state = state
            for message in state["messages"][seen:]:
                for step in _steps_from_message(message):
                    if on_step:
                        on_step(step)
            seen = len(state["messages"])
    except Exception as e:
        kind = _classify_error(e)
        trace_log.log(f"[AGENT ERROR] {kind}: {type(e).__name__}: {e}")
        raise AgentRunError(kind, f"{type(e).__name__}: {e}") from e

    if final_state is None or not isinstance(final_state["messages"][-1], AIMessage):
        reason = "the agent stopped without a final answer"
        trace_log.log(f"[AGENT ERROR] other: {reason}")
        raise AgentRunError("other", reason)

    # save history only after the turn finished, so a failure leaves it unchanged
    _conversation_history = final_state["messages"]  # full history (including tool calls) for the next turn

    answer = extract_text(_conversation_history[-1])
    if not answer:
        # Gemini 3 can reply with only non-text blocks
        trace_log.log("[AGENT WARNING] final answer had no text")
        answer = EMPTY_ANSWER_MESSAGE
    trace_log.log("\n=== FINAL ANSWER ===")
    trace_log.log(answer)
    return answer
