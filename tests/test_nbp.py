"""Tests for the NBP exchange-rate client and tools (HTTP fully mocked)."""

import httpx
import pytest
import respx

from polish_business_mcp import nbp, server


def _table_a():
    return [
        {
            "table": "A",
            "no": "123/A/NBP/2026",
            "effectiveDate": "2026-06-26",
            "rates": [
                {"currency": "euro", "code": "EUR", "mid": 4.2531},
                {"currency": "dolar amerykański", "code": "USD", "mid": 3.8920},
                {"currency": "funt szterling", "code": "GBP", "mid": 4.9801},
            ],
        }
    ]


def _single_rate(code, currency, mid, date="2026-06-26"):
    return {
        "table": "A",
        "currency": currency,
        "code": code,
        "rates": [{"no": "123/A/NBP/2026", "effectiveDate": date, "mid": mid}],
    }


# --------------------------------------------------------------------------- #
# get_table
# --------------------------------------------------------------------------- #


@respx.mock
async def test_get_table_parses_rates():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/tables/A/").mock(
        return_value=httpx.Response(200, json=_table_a())
    )
    table = await nbp.get_table("A")
    assert table["effectiveDate"] == "2026-06-26"
    assert {r["code"] for r in table["rates"]} == {"EUR", "USD", "GBP"}


# --------------------------------------------------------------------------- #
# get_rate — Table A hit, and A->B fallback
# --------------------------------------------------------------------------- #


@respx.mock
async def test_get_rate_found_in_table_a():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/EUR/").mock(
        return_value=httpx.Response(200, json=_single_rate("EUR", "euro", 4.2531))
    )
    rate = await nbp.get_rate("EUR")
    assert rate["code"] == "EUR"
    assert rate["mid"] == 4.2531
    assert rate["effectiveDate"] == "2026-06-26"


@respx.mock
async def test_get_rate_falls_back_to_table_b():
    # Not in A (404), found in B.
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/UAH/").mock(
        return_value=httpx.Response(404)
    )
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/B/UAH/").mock(
        return_value=httpx.Response(
            200, json=_single_rate("UAH", "hrywna (Ukraina)", 0.0934)
        )
    )
    rate = await nbp.get_rate("UAH")
    assert rate["code"] == "UAH"
    assert rate["mid"] == 0.0934


@respx.mock
async def test_get_rate_unknown_raises_currency_not_found():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/XYZ/").mock(
        return_value=httpx.Response(404)
    )
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/B/XYZ/").mock(
        return_value=httpx.Response(404)
    )
    with pytest.raises(nbp.CurrencyNotFound):
        await nbp.get_rate("XYZ")


# --------------------------------------------------------------------------- #
# convert — math, PLN as source/target, and cross-rate
# --------------------------------------------------------------------------- #


@respx.mock
async def test_convert_pln_to_foreign():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/GBP/").mock(
        return_value=httpx.Response(200, json=_single_rate("GBP", "funt", 4.9801))
    )
    conv = await nbp.convert(1500, "PLN", "GBP")
    # 1500 PLN / 4.9801 PLN-per-GBP
    assert conv["result"] == pytest.approx(1500 / 4.9801)
    assert conv["from_rate"] == 1.0
    assert conv["to_rate"] == 4.9801


@respx.mock
async def test_convert_foreign_to_pln():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/EUR/").mock(
        return_value=httpx.Response(200, json=_single_rate("EUR", "euro", 4.2531))
    )
    conv = await nbp.convert(100, "EUR", "PLN")
    assert conv["result"] == pytest.approx(100 * 4.2531)


@respx.mock
async def test_convert_cross_rate_via_pln_pivot():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/EUR/").mock(
        return_value=httpx.Response(200, json=_single_rate("EUR", "euro", 4.2531))
    )
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/GBP/").mock(
        return_value=httpx.Response(200, json=_single_rate("GBP", "funt", 4.9801))
    )
    conv = await nbp.convert(100, "EUR", "GBP")
    # 100 EUR -> PLN -> GBP
    assert conv["result"] == pytest.approx(100 * 4.2531 / 4.9801)


# --------------------------------------------------------------------------- #
# Tool-level behaviour
# --------------------------------------------------------------------------- #


@respx.mock
async def test_get_all_rates_tool_formats_table():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/tables/A/").mock(
        return_value=httpx.Response(200, json=_table_a())
    )
    out = await server.get_all_rates()
    assert "2026-06-26" in out
    assert "EUR" in out and "4.2531" in out


@respx.mock
async def test_get_currency_rate_tool_unknown_currency():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/XYZ/").mock(
        return_value=httpx.Response(404)
    )
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/B/XYZ/").mock(
        return_value=httpx.Response(404)
    )
    out = await server.get_currency_rate("XYZ")
    assert "not found" in out.lower()
    assert "EUR" in out  # suggests common codes


@respx.mock
async def test_convert_currency_tool_output():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/rates/A/GBP/").mock(
        return_value=httpx.Response(200, json=_single_rate("GBP", "funt", 4.9801))
    )
    out = await server.convert_currency(1500, "PLN", "GBP")
    assert "1500.00 PLN" in out
    assert "GBP" in out
    assert "NBP" in out


@respx.mock
async def test_get_all_rates_tool_handles_timeout():
    respx.get(f"{nbp.BASE_URL}/api/exchangerates/tables/A/").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    out = await server.get_all_rates()
    assert "unavailable" in out.lower()
