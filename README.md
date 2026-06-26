# 🇵🇱 Polish Business Intelligence MCP

> **Language:** **English** · [🇵🇱 Polski](./README.pl.md)

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that gives any AI agent — Claude, Cursor, Copilot — instant, live access to two official Polish data sources: the **Ministry of Finance VAT whitelist (Biała Lista)** and the **National Bank of Poland (NBP) exchange rates**. No API keys, no signup, no scraping.

[![CI](https://github.com/neflingcreations/PBI-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/neflingcreations/PBI-MCP/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why this exists

Large language models have no live access to the Polish VAT registry or to official FX rates — that data is dynamic, changes daily, and lives behind government APIs the model was never trained on. This MCP server closes that gap. Plug it into your agent and it can verify whether a Polish company is a registered VAT payer, pull its registered address and bank accounts, and convert money at the official central-bank mid rate — all in real time.

It wraps two free, public, no-auth APIs:

| Source | What it provides |
| --- | --- |
| [**Biała Lista**](https://wl-api.mf.gov.pl/) — Ministry of Finance VAT whitelist | Look up a company by **NIP** (tax ID): name, VAT status, address, registration date, bank accounts |
| [**NBP**](https://api.nbp.pl/) — National Bank of Poland | Official PLN exchange rates (kurs średni) for ~40 currencies |

---

## Tools

| Tool | What it does | Key inputs |
| --- | --- | --- |
| `lookup_company` | Full company lookup on the VAT whitelist — name, VAT status, address, registration date, bank accounts | `nip` |
| `check_vat_status` | Quick yes / no / exempt — is this NIP an active VAT payer? Good for "can I trust this invoice?" | `nip` |
| `get_all_rates` | All current PLN rates from NBP Table A (EUR, USD, GBP, CHF, JPY, CZK, …) | _optional_ `date` |
| `get_currency_rate` | Official NBP mid rate for one currency (Table A, falls back to Table B for exotics) | `currency_code`, _optional_ `date` |
| `convert_currency` | Convert between PLN and any currency, or cross-rate two currencies via PLN | `amount`, `from_currency`, `to_currency`, _optional_ `date` |

Every tool returns clean, human-readable text (never raw JSON) and never throws — errors come back as friendly messages the agent can act on.

---

## Quick install

Requires [**uv**](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
git clone https://github.com/neflingcreations/PBI-MCP.git
cd PBI-MCP
uv sync
```

### Claude Desktop / Claude Code config

Add this to your MCP config (Claude Desktop: `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "polish-business": {
      "command": "uv",
      "args": ["run", "polish-business-mcp"],
      "cwd": "/path/to/PBI-MCP"
    }
  }
}
```

Restart the client and the five tools appear automatically.

---

## Example agent interactions

Once connected, your agent can answer questions it previously couldn't:

> **"Is the company with NIP 527-010-33-91 a registered VAT payer?"**
> → calls `check_vat_status("5270103391")` →
> `YES — BOOKSY INTERNATIONAL SP. Z O.O. (NIP 5270103391) is an ACTIVE VAT payer (status: Czynny).`

> **"Look up NIP 5270103391 and give me their address and bank accounts."**
> → calls `lookup_company("5270103391")` → company name, VAT status, registered address, registration date, and the list of whitelisted bank accounts.

> **"What's today's EUR/PLN rate from the NBP?"**
> → calls `get_currency_rate("EUR")` →
> `EUR (euro): 4.2531 PLN per 1 EUR · Effective date: 2026-06-26 · official NBP mid-market rate.`

> **"Convert 1500 PLN to GBP at the official rate."**
> → calls `convert_currency(1500, "PLN", "GBP")` → the converted amount, the GBP rate used, and the effective date.

---

## API sources

- **Biała Lista** (VAT whitelist) — Ministry of Finance: https://wl-api.mf.gov.pl/
- **NBP** exchange rates — National Bank of Poland: https://api.nbp.pl/

Both are free, public and require no authentication. The Biała Lista lookup always passes today's date as required by the API; NBP publishes rates only on banking days, so a weekend request returns the most recent rate and the tool shows the actual effective date.

---

## Local development

```bash
uv sync                                              # install deps (incl. dev group)
uv run pytest                                        # run tests (HTTP fully mocked — no network)
uv run ruff check .                                  # lint
uv run mcp dev src/polish_business_mcp/server.py     # open the MCP Inspector and call tools by hand
uv run polish-business-mcp                           # run the server over stdio (waits on stdin — that's normal)
```

The test suite mocks every HTTP call with [`respx`](https://lundberg.github.io/respx/), so it runs offline and deterministically.

---

## Roadmap

- `lookup_by_regon` — the Biała Lista API also accepts **REGON** (9/14-digit company ID).
- `lookup_companies_batch` — the batch endpoint (`/api/search/nips/`) verifies up to 30 NIPs in one call.
- Historical VAT-status checks for a given date.

---

## License

MIT — see [`LICENSE`](./LICENSE).
