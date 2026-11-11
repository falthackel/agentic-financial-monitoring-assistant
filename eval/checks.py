"""
Scoring rules for the evaluation. No LLM and no network, so these can be
unit-tested and re-run on saved results at any time.

Three separate checks:
- check_tools: did the agent call the expected tools with the expected args?
- check_answer: does the answer contain a required word (e.g. it cites a search)?
- ungrounded_numbers: numbers in the answer that appear in no tool output
"""

import datetime
import re

# ---------------------------------------------------------
# Tool choice and arguments
# ---------------------------------------------------------
def resolve_placeholders(value: str, run_date: datetime.date) -> str:
    """Replace {today}, {last_monday}, {monday_before_last} with real dates."""
    days_since_monday = run_date.weekday() or 7  # on a Monday, "last Monday" is 7 days ago
    last_monday = run_date - datetime.timedelta(days=days_since_monday)
    dates = {
        "{today}": run_date,
        "{last_monday}": last_monday,
        "{monday_before_last}": last_monday - datetime.timedelta(days=7),
    }
    for placeholder, date in dates.items():
        value = value.replace(placeholder, date.isoformat())
    return value


def _normalize(value) -> frozenset:
    """'xau, ihsg' and 'IHSG,XAU' both become {'XAU', 'IHSG'}."""
    return frozenset(part.strip().upper() for part in str(value).split(",") if part.strip())


def args_match(actual: dict, expected: dict, run_date: datetime.date) -> bool:
    """True if every expected arg is in the actual call. A list means 'any of these'."""
    for key, want in expected.items():
        if key not in actual:
            return False
        options = want if isinstance(want, list) else [want]
        allowed = {_normalize(resolve_placeholders(str(option), run_date)) for option in options}
        if _normalize(actual[key]) not in allowed:
            return False
    return True


def check_tools(case: dict, calls: list, run_date: datetime.date) -> list:
    """
    calls: [{"tool": name, "args": {...}}, ...] from the last turn.
    Returns a list of problems. An empty list means the check passed.
    """
    problems = []
    names = [call["tool"] for call in calls]
    expected = case.get("expected_tools", [])

    if not expected and names:
        problems.append(f"expected no tool, but called {', '.join(names)}")
    for tool in expected:
        if tool not in names:
            problems.append(f"{tool} was not called")
    for tool, count in case.get("expected_counts", {}).items():
        if names.count(tool) < count:
            problems.append(f"{tool} called {names.count(tool)}x, expected at least {count}x")
    for tool in case.get("forbidden_tools", []):
        if tool in names:
            problems.append(f"{tool} should not be called")
    for expected_call in case.get("expected_args", []):
        tool, args = expected_call["tool"], expected_call["args"]
        if not any(call["tool"] == tool and args_match(call["args"], args, run_date)
                   for call in calls):
            shown = ", ".join(f"{k}={resolve_placeholders(str(v), run_date)}" for k, v in args.items())
            problems.append(f"no {tool} call with {shown}")
    return problems


def check_answer(case: dict, answer: str) -> list:
    """Returns a list of problems with the answer text (empty = passed)."""
    words = case.get("answer_mentions_any")
    if words and not any(word.lower() in answer.lower() for word in words):
        return [f"answer mentions none of: {', '.join(words)}"]
    return []


# ---------------------------------------------------------
# Number grounding
# ---------------------------------------------------------
NUMBER_PATTERN = re.compile(
    r"(?:\d[\d.,]*\d|\d)"                               # 16,000.50 or 31,79 or 7
    r"(?:\s*(million|juta|billion|miliar|thousand|ribu)\b)?",
    re.IGNORECASE,
)
DATE_OR_TIME = re.compile(r"\d{4}-\d{2}-\d{2}|\b\d{1,2}:\d{2}\b")
MULTIPLIERS = {"thousand": 1e3, "ribu": 1e3, "million": 1e6, "juta": 1e6,
               "billion": 1e9, "miliar": 1e9}


def _readings(token: str) -> list:
    """
    All the ways a number token can be read, as (value, decimals shown).
    '16,000' could be sixteen thousand (English) or 16.000 (Indonesian
    decimal comma), so both readings are returned.
    """
    def as_decimal(text, decimal_sep, thousands_sep):
        whole, _, fraction = text.partition(decimal_sep)
        whole = whole.replace(thousands_sep, "")
        if not whole.isdigit() or (fraction and not fraction.isdigit()):
            return None
        return (float(f"{whole}.{fraction}" if fraction else whole), len(fraction))

    has_comma, has_dot = "," in token, "." in token
    if has_comma and has_dot:
        # the separator that comes last is the decimal one
        if token.rfind(".") > token.rfind(","):
            options = [as_decimal(token, ".", ",")]
        else:
            options = [as_decimal(token, ",", ".")]
    elif has_comma or has_dot:
        sep = "," if has_comma else "."
        other = "." if has_comma else ","
        parts = token.split(sep)
        thousands_reading = (as_decimal(token.replace(sep, ""), other, "")
                             if all(len(p) == 3 for p in parts[1:]) else None)
        decimal_reading = as_decimal(token, sep, other) if len(parts) == 2 else None
        options = [thousands_reading, decimal_reading]
    else:
        options = [(float(token), 0)]
    return [option for option in options if option is not None]


def _numbers(text: str) -> list:
    """[(token, multiplier, readings)] for every number in the text (dates and times removed)."""
    text = DATE_OR_TIME.sub(" ", text)
    found = []
    for match in NUMBER_PATTERN.finditer(text):
        token = re.match(r"[\d.,]+", match.group(0)).group(0)
        multiplier = MULTIPLIERS.get((match.group(1) or "").lower(), 1)
        found.append((match.group(0), multiplier, _readings(token)))
    return found


def _is_trivial(readings: list) -> bool:
    """Small whole numbers ('1 USD', 'Q1', '2 days') and years are not facts to check."""
    for value, decimals in readings:
        if decimals == 0 and (value < 100 or 1900 <= value <= 2100):
            return True
    return False


def ungrounded_numbers(answer: str, tool_outputs: list, question: str = "") -> list:
    """
    Numbers in the answer that don't match any number in the tool outputs.
    A match allows rounding to the decimals shown in the answer, so
    '32.88' matches a tool's '32.8793'.
    """
    tool_values = [value * multiplier
                   for output in tool_outputs
                   for _, multiplier, readings in _numbers(output)
                   for value, _ in readings]
    question_tokens = {token for token, _, _ in _numbers(question)}

    problems = []
    for token, multiplier, readings in _numbers(answer):
        if not readings or _is_trivial(readings) or token in question_tokens:
            continue
        grounded = any(
            abs(value * multiplier - tool_value) <= 0.5 * 10 ** -decimals * multiplier + 1e-9
            for value, decimals in readings
            for tool_value in tool_values
        )
        if not grounded:
            problems.append(token)
    return problems
