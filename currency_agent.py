"""
Asset Price Assistant - an agentic AI example
=============================================
Stack: LangChain + Google Gemini (via Google AI Studio)

Start the terminal chat:
    (create a .env file with GOOGLE_API_KEY, see .env.example)
    python currency_agent.py

The code is split into:
    tools.py      the 4 tools + data helpers (Frankfurter, yfinance, DuckDuckGo)
    prompts.py    system prompt versions
    agent.py      Gemini + create_agent + conversation history
    cli.py        terminal input/output
    trace_log.py  the agent_log.txt file log
"""

import sys

# Windows: avoid UnicodeEncodeError (emoji) when output is redirected to a file
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from cli import chat  # noqa: E402  (import after the stdout fix)

if __name__ == "__main__":
    chat()
