"""NBP (National Bank of Poland) exchange-rate API client.

The NBP publishes official mid-market ("kurs średni") exchange rates for PLN.
Table A covers the major / common currencies, Table B covers exotic ones.
The API is free, public and requires no authentication.

Note: rates are published only on banking days. Requesting a weekend or
holiday date returns the most recent available rate, so always surface the
actual ``effectiveDate`` returned to the user.

API docs: https://api.nbp.pl/
"""

from __future__ import annotations

import httpx

BASE_URL = "https://api.nbp.pl"
TIMEOUT = 10.0


class CurrencyNotFound(Exception):
    """Raised when a currency code is not found in Table A or Table B."""


async def get_table(table: str = "A", date: str | None = None) -> dict:
    """Fetch a full NBP rate table (A or B).

    Args:
        table: "A" or "B".
        date: Optional ISO date (YYYY-MM-DD) for historical rates.

    Returns:
        A dict with keys ``table``, ``no``, ``effectiveDate`` and ``rates``
        (a list of ``{"currency", "code", "mid"}`` entries).
    """
    table = table.upper()
    if date:
        url = f"{BASE_URL}/api/exchangerates/tables/{table}/{date}/"
    else:
        url = f"{BASE_URL}/api/exchangerates/tables/{table}/"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params={"format": "json"})

    response.raise_for_status()
    # The tables endpoint returns a list with a single table object.
    return response.json()[0]


async def _get_rate_from_table(
    table: str, code: str, date: str | None
) -> dict | None:
    """Fetch a single currency rate from a specific table, or None on 404."""
    code = code.upper()
    if date:
        url = f"{BASE_URL}/api/exchangerates/rates/{table}/{code}/{date}/"
    else:
        url = f"{BASE_URL}/api/exchangerates/rates/{table}/{code}/"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params={"format": "json"})

    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.json()


async def get_rate(code: str, date: str | None = None) -> dict:
    """Get the official NBP mid rate for a single currency.

    Tries Table A first, then falls back to Table B for exotic currencies.

    Returns:
        A dict ``{"code", "currency", "mid", "effectiveDate"}``.

    Raises:
        CurrencyNotFound: if the code is in neither table.
    """
    code = code.upper()

    for table in ("A", "B"):
        data = await _get_rate_from_table(table, code, date)
        if data is not None:
            rate_entry = data["rates"][0]
            return {
                "code": data["code"],
                "currency": data["currency"],
                "mid": rate_entry["mid"],
                "effectiveDate": rate_entry["effectiveDate"],
            }

    raise CurrencyNotFound(code)


async def convert(
    amount: float,
    from_currency: str,
    to_currency: str,
    date: str | None = None,
) -> dict:
    """Convert an amount between currencies using official NBP rates.

    PLN is supported as either source or target. For cross-rates between two
    foreign currencies (e.g. EUR -> GBP), PLN is used as the pivot.

    Returns:
        A dict with the conversion result and the rates / effective date used:
        ``{"amount", "from", "to", "result", "from_rate", "to_rate",
           "effective_date"}``. Rates are expressed as PLN per 1 unit of the
        currency (PLN itself has an implicit rate of 1.0).

    Raises:
        CurrencyNotFound: if either currency code is unknown.
    """
    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    effective_dates: list[str] = []

    # PLN per 1 unit of the source currency.
    if from_currency == "PLN":
        from_rate = 1.0
    else:
        rate = await get_rate(from_currency, date)
        from_rate = rate["mid"]
        effective_dates.append(rate["effectiveDate"])

    # PLN per 1 unit of the target currency.
    if to_currency == "PLN":
        to_rate = 1.0
    else:
        rate = await get_rate(to_currency, date)
        to_rate = rate["mid"]
        effective_dates.append(rate["effectiveDate"])

    # amount (from) -> PLN -> (to)
    amount_in_pln = amount * from_rate
    result = amount_in_pln / to_rate

    return {
        "amount": amount,
        "from": from_currency,
        "to": to_currency,
        "result": result,
        "from_rate": from_rate,
        "to_rate": to_rate,
        "effective_date": max(effective_dates) if effective_dates else None,
    }
