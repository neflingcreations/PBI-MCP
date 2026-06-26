"""Biała Lista (Ministry of Finance VAT whitelist) API client and NIP validator.

The Biała Lista (literally "White List") is the Polish Ministry of Finance's
register of VAT payers. It is a free, public, no-auth REST API that lets you
verify whether a company identified by its NIP (tax ID) is a registered and
active VAT payer, and look up its registered details and bank accounts.

API docs: https://wl-api.mf.gov.pl/
"""

from __future__ import annotations

import datetime

import httpx

BASE_URL = "https://wl-api.mf.gov.pl"
TIMEOUT = 10.0

# NIP checksum weights (applied to the first 9 digits).
_NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)

# Map the API's Polish statusVat values to human-readable English + Polish labels.
VAT_STATUS_MAP = {
    "Czynny": "Active (Czynny)",
    "Zwolniony": "VAT-exempt (Zwolniony)",
    "Niezarejestrowany": "Not registered (Niezarejestrowany)",
}


def validate_nip(nip: str) -> str | None:
    """Validate a Polish NIP and return the cleaned 10-digit value, or None.

    Strips spaces and dashes, requires exactly 10 digits, then applies the
    official checksum algorithm:

        weights  = [6, 5, 7, 2, 3, 4, 5, 6, 7]
        checksum = sum(digit[i] * weights[i] for i in 0..8) % 11
        valid    = checksum != 10 and checksum == digit[9]

    Returns the cleaned NIP string if valid, otherwise None.
    """
    if not nip:
        return None

    cleaned = nip.replace(" ", "").replace("-", "")
    if len(cleaned) != 10 or not cleaned.isdigit():
        return None

    checksum = sum(int(cleaned[i]) * _NIP_WEIGHTS[i] for i in range(9)) % 11
    if checksum == 10 or checksum != int(cleaned[9]):
        return None

    return cleaned


def _today() -> str:
    """Return today's date as an ISO 8601 string (YYYY-MM-DD)."""
    return datetime.date.today().isoformat()


async def lookup_nip(nip: str, date: str | None = None) -> dict | None:
    """Look up a company on the Biała Lista by NIP.

    Args:
        nip: A cleaned, validated 10-digit NIP.
        date: ISO date (YYYY-MM-DD). The API requires it; defaults to today.

    Returns:
        The ``result.subject`` dict if the company was found, otherwise None
        (not found, or HTTP 404).

    Raises:
        httpx.TimeoutException / httpx.HTTPError on network failure — callers
        (the MCP tools) are responsible for turning these into friendly text.
    """
    date = date or _today()
    url = f"{BASE_URL}/api/search/nip/{nip}"

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        response = await client.get(url, params={"date": date})

    if response.status_code == 404:
        return None
    response.raise_for_status()

    data = response.json()
    return (data.get("result") or {}).get("subject")
