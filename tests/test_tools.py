"""
Offline tests for the 4 tools. The network (requests, yfinance, DuckDuckGo)
is replaced with fake data, so these run any time without quota.
"""

from unittest import mock

import pytest

import tools
from tools import TOOL_ERROR_PREFIX


def fake_response(rows):
    response = mock.Mock()
    response.json.return_value = rows
    response.raise_for_status.return_value = None
    return response


# Frankfurter-style rows: rates against EUR
EUR_ROWS = [
    {"date": "2026-11-10", "quote": "USD", "rate": 1.10},
    {"date": "2026-11-10", "quote": "IDR", "rate": 17600.0},
    {"date": "2026-11-11", "quote": "USD", "rate": 1.00},
    {"date": "2026-11-11", "quote": "IDR", "rate": 16000.0},
]


def patch_frankfurter(rows=EUR_ROWS, **kwargs):
    if "side_effect" in kwargs:
        return mock.patch.object(tools.requests, "get", side_effect=kwargs["side_effect"])
    return mock.patch.object(tools.requests, "get", return_value=fake_response(rows))


# ---------------------------------------------------------
# EUR-pivot math
# ---------------------------------------------------------
def test_cross_rate_divides_two_eur_rates():
    with patch_frankfurter():
        cross = tools._fetch_eur_cross_series("USD", "IDR")
    # 17600 / 1.10 = 16000 and 16000 / 1.00 = 16000
    assert cross == pytest.approx({"2026-11-10": 16000.0, "2026-11-11": 16000.0})


def test_cross_rate_with_eur_as_source():
    with patch_frankfurter():
        cross = tools._fetch_eur_cross_series("EUR", "IDR")
    assert cross["2026-11-11"] == pytest.approx(16000.0)


def test_cross_rate_with_eur_as_target():
    with patch_frankfurter():
        cross = tools._fetch_eur_cross_series("IDR", "EUR")
    assert cross["2026-11-11"] == pytest.approx(1 / 16000.0)


def test_cross_rate_skips_dates_with_a_missing_quote():
    rows = [{"date": "2026-11-11", "quote": "USD", "rate": 1.0}]  # no IDR
    with patch_frankfurter(rows):
        assert tools._fetch_eur_cross_series("USD", "IDR") == {}


def test_cross_rate_empty_response():
    with patch_frankfurter([]):
        assert tools._fetch_eur_cross_series("USD", "IDR") == {}


# ---------------------------------------------------------
# Tools: success
# ---------------------------------------------------------
def test_get_exchange_rate_ok():
    with patch_frankfurter():
        out = tools.get_exchange_rate.invoke({"from_currency": "usd", "to_currency": "idr"})
    assert out == "1 USD = 16000 IDR (as of 2026-11-11)"


def test_get_average_exchange_rate_ok():
    with patch_frankfurter():
        out = tools.get_average_exchange_rate.invoke({
            "from_currency": "USD", "to_currency": "IDR",
            "start_date": "2026-11-10", "end_date": "2026-11-11"})
    assert not out.startswith(TOOL_ERROR_PREFIX)
    assert "2 days of data" in out


# ---------------------------------------------------------
# Tools: every failure starts with TOOL_ERROR_PREFIX and never raises
# ---------------------------------------------------------
RATE_ARGS = {"from_currency": "USD", "to_currency": "IDR"}
AVERAGE_ARGS = {"from_currency": "USD", "to_currency": "IDR",
                "start_date": "2026-01-01", "end_date": "2026-03-31"}


@pytest.mark.parametrize("tool, args", [
    (tools.get_exchange_rate, RATE_ARGS),
    (tools.get_average_exchange_rate, AVERAGE_ARGS),
    (tools.get_price_table, {"assets": "USD,SGD"}),
])
def test_tool_returns_error_when_network_times_out(tool, args):
    with patch_frankfurter(side_effect=TimeoutError("timed out")):
        out = tool.invoke(args)
    assert out.startswith(TOOL_ERROR_PREFIX)


@pytest.mark.parametrize("tool, args", [
    (tools.get_exchange_rate, {"from_currency": "XYZ", "to_currency": "IDR"}),
    (tools.get_average_exchange_rate, AVERAGE_ARGS),
])
def test_tool_returns_error_when_no_data(tool, args):
    with patch_frankfurter([]):
        out = tool.invoke(args)
    assert out.startswith(TOOL_ERROR_PREFIX)


def test_tool_failure_is_logged_on_one_line(temp_log_file):
    with patch_frankfurter([]):
        tools.get_exchange_rate.invoke({"from_currency": "XYZ", "to_currency": "IDR"})
    failure_lines = [line for line in temp_log_file.read_text(encoding="utf-8").splitlines()
                     if "[TOOL FAILED]" in line]
    assert len(failure_lines) == 1
    line = failure_lines[0]
    assert "get_exchange_rate(from_currency='XYZ', to_currency='IDR')" in line  # tool + args
    assert "no rate found" in line                                             # reason


def test_web_search_no_results():
    with mock.patch.object(tools, "DDGS") as ddgs:
        ddgs.return_value.text.return_value = []
        out = tools.web_search.invoke({"query": "anything"})
    assert out.startswith(TOOL_ERROR_PREFIX)


def test_web_search_shows_each_results_site(temp_log_file):
    results = [
        {"title": "Taiwan Dollar Weakens", "body": "equity inflows ebbed",
         "href": "https://www.bloomberg.com/news/articles/x"},
        {"title": "No link", "body": "text"},
    ]
    with mock.patch.object(tools, "DDGS") as ddgs:
        ddgs.return_value.text.return_value = results
        out = tools.web_search.invoke({"query": "taiwan dollar"})
    assert out.splitlines() == [
        "- [bloomberg.com] Taiwan Dollar Weakens: equity inflows ebbed",
        "- [unknown site] No link: text",
    ]
    assert "found 2 search results: bloomberg.com, unknown site" in temp_log_file.read_text(encoding="utf-8")


def test_web_search_network_error():
    with mock.patch.object(tools, "DDGS") as ddgs:
        ddgs.return_value.text.side_effect = RuntimeError("network down")
        out = tools.web_search.invoke({"query": "anything"})
    assert out.startswith(TOOL_ERROR_PREFIX)


# ---------------------------------------------------------
# Price table
# ---------------------------------------------------------
def test_price_table_still_renders_when_one_asset_fails():
    with patch_frankfurter(), \
         mock.patch.object(tools, "_get_ihsg_data", side_effect=ValueError("no data for IHSG")):
        out = tools.get_price_table.invoke({"assets": "USD,IHSG"})

    assert not out.startswith(TOOL_ERROR_PREFIX)
    lines = out.splitlines()
    assert len(lines) == 4  # header, separator, USD, IHSG
    for line in lines:
        assert line.count("|") == 5  # 4 columns
    assert "FAILED: no data for IHSG" in lines[3]


def test_price_table_shows_ihsg_in_points():
    with mock.patch.object(tools, "_get_ihsg_data", return_value=(5115.04, -0.21, "2026-11-11 16:00")):
        out = tools.get_price_table.invoke({"assets": "IHSG"})
    assert "| IHSG | 5,115.04 pts |" in out
    assert "Rp" not in out


def test_price_table_is_an_error_when_every_asset_fails():
    with patch_frankfurter(side_effect=TimeoutError("timed out")):
        out = tools.get_price_table.invoke({"assets": "USD,SGD"})
    assert out.startswith(TOOL_ERROR_PREFIX)


def test_price_table_with_no_assets():
    assert tools.get_price_table.invoke({"assets": " , "}).startswith(TOOL_ERROR_PREFIX)


# ---------------------------------------------------------
# IHSG history (yfinance, through get_average_exchange_rate)
# ---------------------------------------------------------
def fake_ticker(closes):
    """A fake yfinance Ticker whose history() returns these closing values."""
    import pandas as pd
    ticker = mock.Mock()
    ticker.history.return_value = pd.DataFrame({"Close": closes})
    return ticker


IHSG_Q1 = {"from_currency": "IHSG", "to_currency": "IDR",
           "start_date": "2026-01-01", "end_date": "2026-03-31"}


def test_ihsg_average_uses_yfinance_not_frankfurter():
    ticker = fake_ticker([8000.0, 8200.0, 8400.0])
    with mock.patch.object(tools.yf, "Ticker", return_value=ticker) as make_ticker, \
         mock.patch.object(tools.requests, "get") as frankfurter:
        out = tools.get_average_exchange_rate.invoke(IHSG_Q1)

    assert out == ("Average IHSG close = 8200.00 points from 2026-01-01 to 2026-03-31 "
                   "(3 trading days, min 8000.00, max 8400.00)")
    make_ticker.assert_called_once_with("^JKSE")
    frankfurter.assert_not_called()


def test_ihsg_history_includes_the_end_date():
    ticker = fake_ticker([8000.0])
    with mock.patch.object(tools.yf, "Ticker", return_value=ticker):
        tools.get_average_exchange_rate.invoke(IHSG_Q1)
    # yfinance's end is exclusive, so we ask for one day after end_date
    assert ticker.history.call_args.kwargs["end"] == "2026-04-01"
    assert ticker.history.call_args.kwargs["start"] == "2026-01-01"


def test_ihsg_code_is_case_insensitive():
    with mock.patch.object(tools.yf, "Ticker", return_value=fake_ticker([1.0])):
        out = tools.get_average_exchange_rate.invoke(dict(IHSG_Q1, from_currency=" ihsg "))
    assert not out.startswith(TOOL_ERROR_PREFIX)


def test_ihsg_market_closed_is_an_error_with_a_hint():
    with mock.patch.object(tools.yf, "Ticker", return_value=fake_ticker([])):
        out = tools.get_average_exchange_rate.invoke(
            dict(IHSG_Q1, start_date="2026-11-08", end_date="2026-11-08"))  # a Sunday
    assert out.startswith(TOOL_ERROR_PREFIX)
    assert "market may have been closed" in out


@pytest.mark.parametrize("problem", [
    {"start_date": "last monday"},                       # not a date
    {"_raise": TimeoutError("timed out")},               # network
])
def test_ihsg_history_failures_return_error(problem):
    args = dict(IHSG_Q1)
    ticker = fake_ticker([1.0])
    if "_raise" in problem:
        ticker.history.side_effect = problem["_raise"]
    else:
        args.update(problem)
    with mock.patch.object(tools.yf, "Ticker", return_value=ticker):
        out = tools.get_average_exchange_rate.invoke(args)
    assert out.startswith(TOOL_ERROR_PREFIX)
