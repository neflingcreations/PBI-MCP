"""Tests for the Biała Lista VAT client and NIP validator (HTTP fully mocked)."""

import httpx
import respx

from polish_business_mcp import server, vat

# A real, checksum-valid NIP (Booksy International) used throughout the spec.
VALID_NIP = "5270103391"


# --------------------------------------------------------------------------- #
# NIP validation
# --------------------------------------------------------------------------- #


def test_valid_nip_passes_checksum():
    assert vat.validate_nip(VALID_NIP) == VALID_NIP


def test_valid_nip_strips_spaces_and_dashes():
    assert vat.validate_nip("527-010-33-91") == VALID_NIP
    assert vat.validate_nip(" 527 010 3391 ") == VALID_NIP


def test_invalid_nip_wrong_checksum():
    assert vat.validate_nip("5270103392") is None


def test_invalid_nip_wrong_length():
    assert vat.validate_nip("12345") is None
    assert vat.validate_nip("12345678901") is None


def test_invalid_nip_non_numeric():
    assert vat.validate_nip("52701O3391") is None  # letter O instead of zero
    assert vat.validate_nip("") is None


# --------------------------------------------------------------------------- #
# lookup_nip client
# --------------------------------------------------------------------------- #


def _subject_response(status_vat="Czynny"):
    return {
        "result": {
            "subject": {
                "name": "BOOKSY INTERNATIONAL SP. Z O.O.",
                "nip": VALID_NIP,
                "regon": "363777164",
                "statusVat": status_vat,
                "workingAddress": "UL. PROSTA 67, 00-838 WARSZAWA",
                "registrationLegalDate": "2015-07-01",
                "accountNumbers": ["12345678901234567890123456"],
            },
            "requestDateTime": "2026-06-26T10:00:00.000+02:00",
        }
    }


@respx.mock
async def test_lookup_nip_found():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(200, json=_subject_response())
    )
    subject = await vat.lookup_nip(VALID_NIP)
    assert subject is not None
    assert subject["statusVat"] == "Czynny"


@respx.mock
async def test_lookup_nip_not_found_null_subject():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(
            200, json={"result": {"subject": None, "requestDateTime": "x"}}
        )
    )
    assert await vat.lookup_nip(VALID_NIP) is None


@respx.mock
async def test_lookup_nip_404_returns_none():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(404)
    )
    assert await vat.lookup_nip(VALID_NIP) is None


# --------------------------------------------------------------------------- #
# Tool-level behaviour
# --------------------------------------------------------------------------- #


async def test_lookup_company_rejects_invalid_nip_without_calling_api():
    # No respx mock registered: if the tool hit the network, respx (not active
    # here) would let it fail — but validation must short-circuit first.
    out = await server.lookup_company("123")
    assert "not a valid Polish NIP" in out


@respx.mock
async def test_lookup_company_formats_active_payer():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(200, json=_subject_response("Czynny"))
    )
    out = await server.lookup_company(VALID_NIP)
    assert "BOOKSY INTERNATIONAL" in out
    assert "Active (Czynny)" in out
    assert "UL. PROSTA 67" in out
    assert "12345678901234567890123456" in out


@respx.mock
async def test_lookup_company_not_found():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(404)
    )
    out = await server.lookup_company(VALID_NIP)
    assert "No company found" in out
    assert VALID_NIP in out


@respx.mock
async def test_check_vat_status_active():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(200, json=_subject_response("Czynny"))
    )
    out = await server.check_vat_status(VALID_NIP)
    assert out.startswith("YES")
    assert "ACTIVE" in out


@respx.mock
async def test_check_vat_status_exempt():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(200, json=_subject_response("Zwolniony"))
    )
    out = await server.check_vat_status(VALID_NIP)
    assert out.startswith("EXEMPT")


@respx.mock
async def test_check_vat_status_not_registered():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        return_value=httpx.Response(404)
    )
    out = await server.check_vat_status(VALID_NIP)
    assert out.startswith("NO")


@respx.mock
async def test_lookup_company_handles_timeout():
    respx.get(f"{vat.BASE_URL}/api/search/nip/{VALID_NIP}").mock(
        side_effect=httpx.TimeoutException("timeout")
    )
    out = await server.lookup_company(VALID_NIP)
    assert "unavailable" in out.lower()
