"""
The agent: Gemini model + LangChain create_agent + the 4 tools, and the
conversation history for one chat session.

Used by the CLI (cli.py). The evaluation and a future UI can import it too.
"""

import os

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import create_agent

import trace_log
from prompts import SYSTEM_PROMPT_V1
from tools import ALL_TOOLS

load_dotenv()  # read GOOGLE_API_KEY from the .env file in this folder

# ---------------------------------------------------------
# Set up the Gemini model + agent
# ---------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
    api_key=os.environ.get("GOOGLE_API_KEY"),
)

agent = create_agent(
    llm,
    tools=ALL_TOOLS,
    system_prompt=SYSTEM_PROMPT_V1,
)


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


def reset_conversation():
    """Clear the conversation history and start a fresh session log."""
    global _conversation_history
    _conversation_history = []
    trace_log.start_session()


def run_request(question: str) -> str:
    """
    One question-and-answer turn. The earlier conversation (if any) is
    sent to the agent too, so it has CONTEXT from previous turns in the
    same session. For example, in "why did it go up?" the agent knows
    "it" means the asset from the previous turn, instead of guessing.
    """
    global _conversation_history
    trace_log.log_request(question)

    _conversation_history.append(("human", question))
    result = agent.invoke({"messages": _conversation_history})
    _conversation_history = result["messages"]  # keep the full history (including tool calls) for the next turn

    answer = extract_text(_conversation_history[-1])
    trace_log.log("\n=== FINAL ANSWER ===")
    trace_log.log(answer)
    return answer
