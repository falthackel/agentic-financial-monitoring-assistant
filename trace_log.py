"""
File log of what the agent did (agent_log.txt).

The file is cleared ONCE when a session starts (start_session), then each
request in that session is added (log_request + log). This keeps the
whole conversation readable in the log.
"""

import datetime

LOG_FILE = "agent_log.txt"


def start_session():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== NEW SESSION STARTED: "
                f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")


def log_request(question: str):
    log(f"\n{'=' * 60}")
    log(f"REQUEST: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"Question: {question}")
    log("-" * 60)


def log(message: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")
