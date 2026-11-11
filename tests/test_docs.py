"""
Offline checks on the docs, for mistakes GitHub only shows after a push.
"""

import re
from pathlib import Path

DEV_LOG = Path(__file__).resolve().parent.parent / "docs" / "dev_log.md"


def gantt_task_lines() -> list:
    """Task lines inside the ```mermaid gantt block of the dev log."""
    text = DEV_LOG.read_text(encoding="utf-8")
    block = re.search(r"```mermaid\s*\ngantt\n(.*?)```", text, re.S).group(1)
    keywords = ("title", "dateFormat", "axisFormat", "section", "excludes", "todayMarker")
    return [line.strip() for line in block.splitlines()
            if line.strip() and not line.strip().startswith(keywords)]


def test_gantt_task_names_have_no_colon():
    # Mermaid splits a task line at its FIRST colon: "Fix F1: IHSG history :done, ..."
    # breaks the chart on GitHub ("Cannot read properties of undefined").
    for line in gantt_task_lines():
        assert line.count(":") == 1, f"task name must not contain ':' -> {line}"


def test_gantt_task_data_looks_valid():
    # ":[tags,] id, start, end-or-duration", e.g. ":done, t01, 2026-07-29, 1d"
    pattern = re.compile(r"^[^:]+:\s*((done|active|crit|milestone),\s*)*t\d+,\s*"
                         r"\d{4}-\d{2}-\d{2},\s*(\d+d|\d{4}-\d{2}-\d{2})$")
    for line in gantt_task_lines():
        assert pattern.match(line), f"unexpected task format -> {line}"
