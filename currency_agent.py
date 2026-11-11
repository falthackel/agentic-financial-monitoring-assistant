"""
Asset Price Assistant - an agentic AI example
=============================================
Stack: LangChain + Google Gemini (via Google AI Studio)

Data sources:
- Frankfurter API v2 (free, no API key): currency rates and precious metals
  (XAU/XAG are treated like currencies). Docs: https://frankfurter.dev/
  NOTE: Frankfurter data is DAILY, not real-time. So "last update" for
  these assets shows the rate date plus the time we checked, not a
  live market time.
- yfinance (free, no API key): the IHSG stock index (ticker ^JKSE),
  fetched per minute, so its time is the real market time.
- DuckDuckGo (ddgs, free): fallback search for anything the two sources
  above don't cover (for example crypto).

NOTE: the ISO code for gold is XAU ("XAUG" is not a standard code).

Log: agent_log.txt is cleared when a session starts, then every request
in that session is added to it.

Quit: press ESC while waiting for input, or type 'exit'.

How to run:
    (create a .env file with GOOGLE_API_KEY, see .env.example)
    python currency_agent.py
"""

import os
import sys
import datetime
from collections import defaultdict

import requests
import yfinance as yf
from ddgs import DDGS
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain.agents import create_agent

load_dotenv()  # read GOOGLE_API_KEY from the .env file in this folder

# Windows: avoid UnicodeEncodeError (emoji) when output is redirected to a file
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    import msvcrt  # built into Windows, used to detect the ESC key
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False  # not Windows: fall back to plain input() + Ctrl+C

API_BASE = "https://api.frankfurter.dev/v2"
GRAMS_PER_TROY_OZ = 31.1034768
LOG_FILE = "agent_log.txt"

# Every tool failure starts with this text. Code checks this prefix,
# never the wording of the message.
TOOL_ERROR_PREFIX = "ERROR:"

ASSET_LABELS = {
    "USD": "USD",
    "SGD": "SGD",
    "TWD": "TWD",
    "XAU": "Gold (XAU)",
    "XAG": "Silver (XAG, per troy oz)",
    "IHSG": "IHSG",
}


# ---------------------------------------------------------
# File log. Cleared ONCE when a session starts (_start_session_log),
# then each request in that session is added (_log_new_request + _log).
# This keeps the whole conversation readable in the log.
# ---------------------------------------------------------
def _start_session_log():
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.write(f"=== NEW SESSION STARTED: "
                f"{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")


def _log_new_request(question: str):
    _log(f"\n{'=' * 60}")
    _log(f"REQUEST: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    _log(f"Question: {question}")
    _log("-" * 60)


def _log(message: str):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def _format_call(tool_name: str, **kwargs) -> str:
    """Show a tool call as text, e.g. get_exchange_rate(from_currency='USD')."""
    args = ", ".join(f"{key}={value!r}" for key, value in kwargs.items())
    return f"{tool_name}({args})"


def _tool_error(call: str, reason: str) -> str:
    """Log a tool failure on one line and return the error text for the agent."""
    _log(f"❌ [TOOL FAILED] {call} -> {reason}")
    return f"{TOOL_ERROR_PREFIX} {reason}"


# ---------------------------------------------------------
# Time helpers
# ---------------------------------------------------------
def _now_hm() -> str:
    return datetime.datetime.now().strftime("%H:%M")


def _format_daily_update(date_str: str) -> str:
    """For daily data (Frankfurter): the rate date plus the time we checked."""
    return f"{date_str} • checked {_now_hm()}"


# ---------------------------------------------------------
# Helper: get a cross rate between two currencies, using EUR in the middle
# ---------------------------------------------------------
def _fetch_eur_cross_series(from_currency: str, to_currency: str,
                             date_or_range: dict = None) -> dict:
    """
    Return {date: rate} for from_currency -> to_currency.
    Frankfurter gives rates against EUR, so we divide two EUR rates.
    """
    from_c, to_c = from_currency.upper(), to_currency.upper()
    quotes = ",".join(sorted(set([from_c, to_c]) - {"EUR"}))

    params = {"base": "EUR"}
    if quotes:
        params["quotes"] = quotes
    if date_or_range:
        params.update(date_or_range)

    resp = requests.get(f"{API_BASE}/rates", params=params, timeout=15)
    resp.raise_for_status()
    rows = resp.json()

    by_date = defaultdict(dict)
    for row in rows:
        by_date[row["date"]][row["quote"]] = row["rate"]

    cross = {}
    for date, rates in by_date.items():
        rate_from = 1.0 if from_c == "EUR" else rates.get(from_c)
        rate_to = 1.0 if to_c == "EUR" else rates.get(to_c)
        if rate_from and rate_to:
            cross[date] = rate_to / rate_from

    return cross


def _get_price_and_change(asset: str, base_currency: str = "IDR"):
    """Latest price + % change from the previous day. -> (price, pct, date)"""
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    cross = _fetch_eur_cross_series(asset, base_currency, {"from": week_ago})

    if len(cross) < 1:
        raise ValueError(f"no data for {asset}")

    dates_sorted = sorted(cross.keys())
    latest_date = dates_sorted[-1]
    latest_rate = cross[latest_date]

    if len(dates_sorted) >= 2:
        prev_rate = cross[dates_sorted[-2]]
        pct_change = (latest_rate - prev_rate) / prev_rate * 100
    else:
        pct_change = None

    return latest_rate, pct_change, latest_date


def _get_gold_data():
    """
    Gold data: the usual reference price in USD per troy ounce (to watch
    how much it moves), plus the price in Rp per gram and per 0.01 gram.
    """
    week_ago = (datetime.date.today() - datetime.timedelta(days=7)).isoformat()
    cross_usd = _fetch_eur_cross_series("XAU", "USD", {"from": week_ago})
    cross_idr = _fetch_eur_cross_series("XAU", "IDR", {"from": week_ago})

    if not cross_usd or not cross_idr:
        raise ValueError("no data for XAU")

    dates_usd = sorted(cross_usd.keys())
    latest_date = dates_usd[-1]
    usd_per_oz = cross_usd[latest_date]
    idr_per_oz = cross_idr.get(latest_date) or cross_idr[sorted(cross_idr.keys())[-1]]

    idr_per_gram = idr_per_oz / GRAMS_PER_TROY_OZ
    idr_per_0_01_gram = idr_per_gram * 0.01

    if len(dates_usd) >= 2:
        prev_usd = cross_usd[dates_usd[-2]]
        pct_change = (usd_per_oz - prev_usd) / prev_usd * 100
    else:
        pct_change = None

    return {
        "usd_per_oz": usd_per_oz,
        "idr_per_gram": idr_per_gram,
        "idr_per_0_01_gram": idr_per_0_01_gram,
        "pct_change": pct_change,
        "date": latest_date,
    }


def _get_ihsg_data():
    """
    IHSG price during the trading day (real market time, not an estimate)
    + % change vs the previous day's close.
    """
    ticker = yf.Ticker("^JKSE")
    daily = ticker.history(period="5d")
    if daily.empty:
        raise ValueError("no data for IHSG")

    prev_close = float(daily.iloc[-2]["Close"]) if len(daily) >= 2 else None

    intraday = ticker.history(period="1d", interval="1m")
    if not intraday.empty:
        price = float(intraday.iloc[-1]["Close"])
        last_update = intraday.index[-1].strftime("%Y-%m-%d %H:%M")
    else:
        # outside market hours the 1-minute data can be empty -> use daily data
        price = float(daily.iloc[-1]["Close"])
        last_update = daily.index[-1].strftime("%Y-%m-%d %H:%M")

    pct_change = ((price - prev_close) / prev_close * 100) if prev_close else None
    return price, pct_change, last_update


# ---------------------------------------------------------
# 1. TOOL: latest rate for one pair
# ---------------------------------------------------------
@tool
def get_exchange_rate(from_currency: str, to_currency: str) -> str:
    """
    Get the LATEST exchange rate between two official FIAT currencies
    (ISO 4217), for example USD, IDR, SGD, TWD, EUR. Also supports XAU
    (gold) and XAG (silver) per troy ounce. Does NOT support crypto or
    stock indexes (use get_price_table for IHSG); use web_search for those.

    Use this tool ONLY for one specific pair. For a "price update" of
    several assets at once, use get_price_table.

    Args:
        from_currency: source currency code, for example 'USD'
        to_currency: target currency code, for example 'IDR'
    """
    call = _format_call("get_exchange_rate",
                        from_currency=from_currency, to_currency=to_currency)
    _log(f"🔧 [TOOL CALLED] {call}")
    try:
        cross = _fetch_eur_cross_series(from_currency, to_currency)
        if not cross:
            return _tool_error(
                call,
                f"no rate found for {from_currency} to {to_currency}. It may not be "
                "a standard currency or precious metal; try web_search.")
        latest_date = max(cross.keys())
        rate = cross[latest_date]
        result = f"1 {from_currency.upper()} = {rate:.6g} {to_currency.upper()} (as of {latest_date})"
        _log(f"✅ [TOOL OK] {result}")
        return result
    except Exception as e:
        return _tool_error(call, f"could not fetch exchange rate: {e}")


# ---------------------------------------------------------
# 2. TOOL: average rate over a date range
# ---------------------------------------------------------
@tool
def get_average_exchange_rate(from_currency: str, to_currency: str,
                               start_date: str, end_date: str) -> str:
    """
    Calculate the average daily exchange rate between two currencies over
    a date range. Useful for comparing periods (for example Q1 vs Q2).

    Args:
        from_currency: source currency code, for example 'USD'
        to_currency: target currency code, for example 'IDR'
        start_date: start date in YYYY-MM-DD format
        end_date: end date in YYYY-MM-DD format
    """
    call = _format_call("get_average_exchange_rate",
                        from_currency=from_currency, to_currency=to_currency,
                        start_date=start_date, end_date=end_date)
    _log(f"🔧 [TOOL CALLED] {call}")
    try:
        cross = _fetch_eur_cross_series(
            from_currency, to_currency,
            date_or_range={"from": start_date, "to": end_date},
        )
        if not cross:
            return _tool_error(
                call,
                f"no {from_currency} to {to_currency} rate data between "
                f"{start_date} and {end_date}.")

        values = list(cross.values())
        avg = sum(values) / len(values)
        result = (f"Average 1 {from_currency.upper()} = {avg:.6g} {to_currency.upper()} "
                  f"from {start_date} to {end_date} ({len(values)} days of data, "
                  f"min {min(values):.6g}, max {max(values):.6g})")
        _log(f"✅ [TOOL OK] {result}")
        return result
    except Exception as e:
        return _tool_error(call, f"could not fetch historical rates: {e}")


# ---------------------------------------------------------
# 3. TOOL: price table for many assets at once (in IDR)
# ---------------------------------------------------------
@tool
def get_price_table(assets: str = "USD,SGD,TWD,XAU,IHSG") -> str:
    """
    Build a TABLE of prices for several assets at once, with the % change
    and the last update time. This is the MAIN tool for "today's price
    update", "market summary", and similar requests. Gold (XAU) is shown
    in USD per troy oz PLUS Rp per gram and Rp per 0.01 gram.

    Do NOT call get_exchange_rate many times for this. This tool already
    calculates and formats everything in one call.

    Args:
        assets: comma-separated asset codes. ISO 4217 codes (USD, SGD,
            TWD, ...), XAU/XAG for precious metals, or IHSG. Default:
            "USD,SGD,TWD,XAU,IHSG".
    """
    asset_list = [a.strip().upper() for a in assets.split(",") if a.strip()]
    call = _format_call("get_price_table", assets=assets)
    _log(f"🔧 [TOOL CALLED] {call}")
    if not asset_list:
        return _tool_error(call, "no asset codes given.")

    rows = []
    for asset in asset_list:
        label = ASSET_LABELS.get(asset, asset)
        try:
            if asset == "XAU":
                data = _get_gold_data()
                price_str = (f"${data['usd_per_oz']:,.2f}/oz | "
                             f"Rp{data['idr_per_gram']:,.0f}/g "
                             f"(Rp{data['idr_per_0_01_gram']:,.0f}/0.01g)")
                pct = data["pct_change"]
                last_update = _format_daily_update(data["date"])
            elif asset == "IHSG":
                price, pct, last_update = _get_ihsg_data()
                price_str = f"Rp{price:,.2f}"
            else:
                price, pct, date_str = _get_price_and_change(asset, "IDR")
                price_str = f"Rp{price:,.2f}"
                last_update = _format_daily_update(date_str)
            _log(f"✅ [{asset}] {price_str} (as of {last_update})")
            rows.append((label, price_str, pct, last_update))
        except Exception as e:
            # one asset failing should not break the whole table
            _log(f"❌ [TOOL FAILED] {call} -> {asset}: {e}")
            rows.append((label, None, None, f"FAILED: {e}"))

    lines = [
        "| Asset | Price | Change (vs previous day) | Last Update |",
        "|---|---|---|---|",
    ]
    for label, price_str, pct, last_update in rows:
        if price_str is None:
            lines.append(f"| {label} | - | - | {last_update} |")
            continue
        if pct is None:
            pct_str = "n/a"
        else:
            arrow = "🔺" if pct >= 0 else "🔻"
            pct_str = f"{arrow} {pct:+.2f}%"
        lines.append(f"| {label} | {price_str} | {pct_str} | {last_update} |")
    table = "\n".join(lines)

    failed = sum(1 for row in rows if row[1] is None)
    if failed == len(rows):
        # nothing usable came back: mark the whole result as an error
        return _tool_error(call, f"could not fetch any of {asset_list}.\n{table}")

    _log(f"✅ [TOOL OK] table with {len(rows)} assets ({failed} failed)")
    return table


# ---------------------------------------------------------
# 4. TOOL: web search (fallback)
# ---------------------------------------------------------
@tool
def web_search(query: str) -> str:
    """
    Search the internet for current information using DuckDuckGo. Use it
    AS A FALLBACK when the other structured data tools fail (for example
    crypto assets or codes they don't recognize).

    Args:
        query: search keywords, for example 'bitcoin price in IDR today'
    """
    call = _format_call("web_search", query=query)
    _log(f"🔧 [TOOL CALLED] {call}")
    try:
        results = DDGS().text(query, max_results=4)
        if not results:
            return _tool_error(call, "no search results found.")

        formatted = "\n".join(f"- {r['title']}: {r['body']}" for r in results)
        _log(f"✅ [TOOL OK] found {len(results)} search results")
        return formatted
    except Exception as e:
        return _tool_error(call, f"search failed: {e}")


# ---------------------------------------------------------
# Set up the Gemini model + agent
# ---------------------------------------------------------
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0,
    api_key=os.environ.get("GOOGLE_API_KEY"),
)

TODAY = datetime.date.today().isoformat()

# v1 = the original prompt, translated to English with no rule changes.
# Kept as-is so later versions can be compared against it (see M5).
SYSTEM_PROMPT_V1 = (
    f"Today is {TODAY}. You are an assistant that helps answer questions "
    "about currency exchange rates and asset prices. ALWAYS use the "
    "available tools to get numbers. Never guess or use data from your "
    "memory.\n\n"
    "Use get_price_table when the user asks for a 'price update', a "
    "'market summary', or a list of several assets at once. Use "
    "get_exchange_rate only for one specific currency pair. Use "
    "get_average_exchange_rate for averages or comparing periods.\n\n"
    "IMPORTANT: if a structured data tool fails, do NOT give up right "
    "away. Try the web_search tool as an alternative.\n\n"
    "If the question has nothing to do with exchange rates or asset "
    "prices, answer normally without calling a tool."
)

agent = create_agent(
    llm,
    tools=[get_exchange_rate, get_average_exchange_rate, get_price_table, web_search],
    system_prompt=SYSTEM_PROMPT_V1,
)


# ---------------------------------------------------------
# Display helpers
# ---------------------------------------------------------
def _extract_text(message) -> str:
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


def _reset_conversation():
    """Clear the conversation history and start a fresh session log."""
    global _conversation_history
    _conversation_history = []
    _start_session_log()


def _run_request(question: str) -> str:
    """
    One question-and-answer turn. The earlier conversation (if any) is
    sent to the agent too, so it has CONTEXT from previous turns in the
    same session. For example, in "why did it go up?" the agent knows
    "it" means the asset from the previous turn, instead of guessing.
    """
    global _conversation_history
    _log_new_request(question)

    _conversation_history.append(("human", question))
    result = agent.invoke({"messages": _conversation_history})
    _conversation_history = result["messages"]  # keep the full history (including tool calls) for the next turn

    answer = _extract_text(_conversation_history[-1])
    _log("\n=== FINAL ANSWER ===")
    _log(answer)
    return answer


def ask(question: str) -> str:
    """Send one question (for manual testing outside chat mode)."""
    if not _conversation_history:
        _start_session_log()
    print(f"\n>> You: {question}")
    answer = _run_request(question)
    print(f"\n>> Agent:\n{answer}")
    return answer


# ---------------------------------------------------------
# Input that lets the user press ESC to quit (Windows, via msvcrt)
# ---------------------------------------------------------
def _read_line_with_esc(prompt: str = ""):
    """
    Read one line of input. Return None if the user presses ESC (meaning
    they want to quit). Outside Windows (no msvcrt), fall back to plain
    input(); use Ctrl+C to quit.
    """
    if not HAS_MSVCRT:
        try:
            return input(prompt)
        except (EOFError, KeyboardInterrupt):
            return None

    print(prompt, end="", flush=True)
    buffer = []
    while True:
        ch = msvcrt.getwch()
        if ch == "\x1b":  # ESC
            print()
            return None
        elif ch in ("\r", "\n"):
            print()
            return "".join(buffer)
        elif ch == "\x08":  # backspace
            if buffer:
                buffer.pop()
                print("\b \b", end="", flush=True)
        else:
            buffer.append(ch)
            print(ch, end="", flush=True)


# ---------------------------------------------------------
# Interactive chat mode
# ---------------------------------------------------------
def chat():
    _start_session_log()

    print("=" * 60)
    print("Asset Price Assistant")
    print("Examples: 'market summary today', 'what is the SGD to TWD rate?'")
    print("Press ESC at any time to quit (or type 'exit')")
    print("Type 'reset' to start a new conversation")
    print(f"This session's log (all requests) is saved to: {LOG_FILE}")
    print("=" * 60)

    while True:
        question = _read_line_with_esc("\nYou: ")

        if question is None:
            print("\n[ESC pressed] Closing the program. Goodbye!")
            break

        question = question.strip()
        if not question:
            continue
        if question.lower() in ("exit", "quit", "bye", "esc"):
            print("Goodbye!")
            break
        if question.lower() in ("reset", "clear"):
            _reset_conversation()
            print("[Conversation reset: earlier context is forgotten]")
            continue

        answer = _run_request(question)
        print(f"\nAgent:\n{answer}")


if __name__ == "__main__":
    chat()
