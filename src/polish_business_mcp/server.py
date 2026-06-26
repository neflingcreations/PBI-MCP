"""Polish Business Intelligence — FastMCP server.

Exposes five tools that wrap two free, no-auth Polish APIs:

  * Biała Lista (Ministry of Finance VAT whitelist) — company / VAT lookup
  * NBP (National Bank of Poland) — official PLN exchange rates

Every tool returns clean, human-readable plain text (never raw JSON) and never
raises — failures are turned into friendly messages so an AI agent can read the
result and act on it.
"""

from __future__ import annotations

import httpx
from mcp.server.fastmcp import FastMCP

from . import nbp, vat

mcp = FastMCP("Polish Business Intelligence")

# Message reused whenever an upstream API is unreachable or times out.
_API_UNAVAILABLE = "The API is currently unavailable. Please try again in a moment."
_COMMON_CODES = "EUR, USD, GBP, CHF, JPY, CZK"


# --------------------------------------------------------------------------- #
# Biała Lista — VAT whitelist tools
# --------------------------------------------------------------------------- #


@mcp.tool()
async def lookup_company(nip: str) -> str:
    """Look up a Polish company by NIP (tax ID) on the Ministry of Finance VAT
    whitelist (Biała Lista). Returns the company name, VAT status, registered
    address, registration date and bank account numbers.

    Args:
        nip: 10-digit Polish NIP. Spaces and dashes are fine — they are stripped.
    """
    cleaned = vat.validate_nip(nip)
    if cleaned is None:
        return (
            f"'{nip}' is not a valid Polish NIP. A NIP must be exactly 10 digits "
            "(spaces and dashes are allowed) and pass the official checksum. "
            "Please double-check the number."
        )

    try:
        subject = await vat.lookup_nip(cleaned)
    except (httpx.TimeoutException, httpx.HTTPError):
        return _API_UNAVAILABLE

    if subject is None:
        return f"No company found on the VAT whitelist for NIP {cleaned}."

    status_raw = subject.get("statusVat") or "Unknown"
    status = vat.VAT_STATUS_MAP.get(status_raw, status_raw)

    lines = [
        f"Company: {subject.get('name', 'N/A')}",
        f"NIP: {subject.get('nip', cleaned)}",
    ]
    if subject.get("regon"):
        lines.append(f"REGON: {subject['regon']}")
    lines.append(f"VAT status: {status}")
    if subject.get("workingAddress"):
        lines.append(f"Address: {subject['workingAddress']}")
    elif subject.get("residenceAddress"):
        lines.append(f"Address: {subject['residenceAddress']}")
    if subject.get("registrationLegalDate"):
        lines.append(f"Registered (legal date): {subject['registrationLegalDate']}")

    accounts = subject.get("accountNumbers") or []
    if accounts:
        lines.append("Bank accounts:")
        lines.extend(f"  - {acc}" for acc in accounts)
    else:
        lines.append("Bank accounts: none listed")

    return "\n".join(lines)


@mcp.tool()
async def check_vat_status(nip: str) -> str:
    """Quick check: is this NIP registered as an active VAT payer in Poland?
    Returns a short, definitive yes / no / exempt answer plus the company name —
    useful for fast agent decisions such as "can I trust this invoice?".

    Args:
        nip: 10-digit Polish NIP. Spaces and dashes are fine.
    """
    cleaned = vat.validate_nip(nip)
    if cleaned is None:
        return f"'{nip}' is not a valid Polish NIP (must be 10 digits with a valid checksum)."

    try:
        subject = await vat.lookup_nip(cleaned)
    except (httpx.TimeoutException, httpx.HTTPError):
        return _API_UNAVAILABLE

    if subject is None:
        return (
            f"NO — NIP {cleaned} is not on the VAT whitelist "
            "(not a registered VAT payer)."
        )

    name = subject.get("name", "this company")
    status_raw = subject.get("statusVat")

    if status_raw == "Czynny":
        return f"YES — {name} (NIP {cleaned}) is an ACTIVE VAT payer (status: Czynny)."
    if status_raw == "Zwolniony":
        return f"EXEMPT — {name} (NIP {cleaned}) is VAT-exempt (status: Zwolniony)."
    return (
        f"NO — {name} (NIP {cleaned}) is not an active VAT payer "
        f"(status: {status_raw or 'unknown'})."
    )


# --------------------------------------------------------------------------- #
# NBP — exchange-rate tools
# --------------------------------------------------------------------------- #


@mcp.tool()
async def get_all_rates(date: str | None = None) -> str:
    """Get all current PLN exchange rates from the National Bank of Poland
    (Table A — EUR, USD, GBP, CHF, JPY, CZK and ~30 others).

    Args:
        date: Optional ISO date (YYYY-MM-DD) for historical rates. NBP publishes
            rates only on banking days; a weekend date returns the most recent
            available table (the actual effective date is shown).
    """
    try:
        table = await nbp.get_table("A", date)
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return (
                f"No NBP Table A rates are available for {date}. "
                "Try a recent banking day (Mon–Fri)."
            )
        return _API_UNAVAILABLE
    except (httpx.TimeoutException, httpx.HTTPError):
        return _API_UNAVAILABLE

    header = (
        f"NBP official mid-market rates (Table {table['table']}, "
        f"no. {table['no']}, effective {table['effectiveDate']}) — PLN per 1 unit:"
    )
    rows = [
        f"  {r['code']}  {r['mid']:>10.4f}   {r['currency']}"
        for r in table["rates"]
    ]
    return header + "\n" + "\n".join(rows)


@mcp.tool()
async def get_currency_rate(currency_code: str, date: str | None = None) -> str:
    """Get the official NBP mid-market exchange rate for a single currency
    against PLN. Tries Table A first and falls back to Table B for exotic
    currencies.

    Args:
        currency_code: ISO 4217 code, e.g. "EUR", "USD", "GBP".
        date: Optional ISO date (YYYY-MM-DD) for a historical rate.
    """
    code = (currency_code or "").strip().upper()
    if not code:
        return "Please provide a currency code, e.g. EUR, USD or GBP."

    try:
        rate = await nbp.get_rate(code, date)
    except nbp.CurrencyNotFound:
        return f"Currency code {code} not found. Common codes: {_COMMON_CODES}."
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return (
                f"No NBP rate is available for {code} on {date}. "
                "Try a recent banking day (Mon–Fri)."
            )
        return _API_UNAVAILABLE
    except (httpx.TimeoutException, httpx.HTTPError):
        return _API_UNAVAILABLE

    return (
        f"{rate['code']} ({rate['currency']}): {rate['mid']:.4f} PLN per 1 {rate['code']}\n"
        f"Effective date: {rate['effectiveDate']}\n"
        "This is the official NBP mid-market rate (kurs średni)."
    )


@mcp.tool()
async def convert_currency(
    amount: float,
    from_currency: str,
    to_currency: str,
    date: str | None = None,
) -> str:
    """Convert an amount between PLN and another currency, or between two foreign
    currencies (via PLN as the pivot), using official NBP mid-market rates.

    Args:
        amount: The amount to convert.
        from_currency: Source currency ISO code (e.g. "PLN", "EUR").
        to_currency: Target currency ISO code (e.g. "GBP", "PLN").
        date: Optional ISO date (YYYY-MM-DD) for historical rates.
    """
    src = (from_currency or "").strip().upper()
    dst = (to_currency or "").strip().upper()
    if not src or not dst:
        return "Please provide both a source and a target currency code."
    if src == dst:
        return f"{amount:.2f} {src} = {amount:.2f} {dst} (same currency)."

    try:
        conv = await nbp.convert(amount, src, dst, date)
    except nbp.CurrencyNotFound as exc:
        bad = str(exc)
        return f"Currency code {bad} not found. Common codes: {_COMMON_CODES}."
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return (
                f"No NBP rate is available for {date}. "
                "Try a recent banking day (Mon–Fri)."
            )
        return _API_UNAVAILABLE
    except (httpx.TimeoutException, httpx.HTTPError):
        return _API_UNAVAILABLE

    lines = [
        f"{conv['amount']:.2f} {conv['from']} = {conv['result']:.2f} {conv['to']}",
    ]
    if conv["from"] != "PLN":
        lines.append(f"  {conv['from']} rate: {conv['from_rate']:.4f} PLN per 1 {conv['from']}")
    if conv["to"] != "PLN":
        lines.append(f"  {conv['to']} rate: {conv['to_rate']:.4f} PLN per 1 {conv['to']}")
    if conv["effective_date"]:
        lines.append(f"  Effective date: {conv['effective_date']}")
    lines.append("Rates are official NBP mid-market rates (kurs średni).")
    return "\n".join(lines)


def main() -> None:
    """Console-script entry point — runs the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
