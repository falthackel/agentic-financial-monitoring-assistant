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


def test_price_table_is_an_error_when_every_asset_fails():
    with patch_frankfurter(side_effect=TimeoutError("timed out")):
        out = tools.get_price_table.invoke({"assets": "USD,SGD"})
    assert out.startswith(TOOL_ERROR_PREFIX)


def test_price_table_with_no_assets():
    assert tools.get_price_table.invoke({"assets": " , "}).startswith(TOOL_ERROR_PREFIX)
