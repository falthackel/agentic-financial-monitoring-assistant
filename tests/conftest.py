"""
Shared test setup. Tests never call Gemini or the internet.
"""

import os

# Use a fake key so tests never touch the real one. load_dotenv() does not
# override a variable that is already set, so .env is ignored here.
os.environ["GOOGLE_API_KEY"] = "test-key-not-real"

import pytest  # noqa: E402

import trace_log  # noqa: E402


@pytest.fixture(autouse=True)
def temp_log_file(tmp_path, monkeypatch):
    """Write the trace log to a temp folder, not the real agent_log.txt."""
    log_file = tmp_path / "agent_log.txt"
    monkeypatch.setattr(trace_log, "LOG_FILE", str(log_file))
    trace_log.start_session()
    return log_file
