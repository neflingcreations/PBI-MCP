# AGENTS.md

Guidance for AI coding agents (and humans) working **on** this repository.
If you are an AI *using* the running server, read the server `instructions`
instead — see `SERVER_INSTRUCTIONS` in `src/polish_business_mcp/server.py`.

## What this project is

An MCP (Model Context Protocol) server that exposes five tools wrapping two
free, no-auth Polish APIs:

- **Biała Lista** (Ministry of Finance VAT whitelist) — company lookup by NIP
- **NBP** (National Bank of Poland) — official PLN exchange rates

It runs locally over **stdio**, launched on demand by an MCP client (Claude
Desktop, Cursor, etc.). There is no hosted server and no database.

## ⛔ Hard rule: never commit or push `Private/`

`Private/` holds the internal project brief and is **git-ignored on purpose**.
Never `git add -f` it, never reference its contents in committed files, and
never push it. This repo is **public**. Before any commit, confirm:

```bash
git ls-files | grep -i private   # must return nothing
```

## Setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.11+.

```bash
uv sync          # install runtime + dev dependencies
```

## Everyday commands

```bash
uv run pytest                                        # tests (HTTP fully mocked; offline)
uv run ruff check .                                  # lint — must pass with zero warnings
uv run ruff check . --fix                            # auto-fix what's fixable
uv run mcp dev src/polish_business_mcp/server.py     # MCP Inspector — call tools by hand
uv run polish-business-mcp                           # run the server (stdio; waits on stdin)
```

`uv run polish-business-mcp` appears to "hang" — that is correct. A stdio
server blocks waiting for a client on stdin; it is not frozen.

## Layout

```
src/polish_business_mcp/
  vat.py      # Biała Lista client + NIP validator + VAT_STATUS_MAP. No MCP code.
  nbp.py      # NBP client: get_table / get_rate (A->B fallback) / convert. No MCP code.
  server.py   # FastMCP instance, SERVER_INSTRUCTIONS, the 5 @mcp.tool()s, main().
tests/
  test_vat.py # respx-mocked vat client + lookup_company / check_vat_status tools
  test_nbp.py # respx-mocked nbp client + rate / convert tools
```

**Separation of concerns:** `vat.py` and `nbp.py` are pure API clients with no
knowledge of MCP. `server.py` is the only file that imports `FastMCP`, does
input validation, formats plain-text output, and maps errors to messages. Keep
new business logic in the client modules; keep presentation in `server.py`.

## Conventions (follow these — they are load-bearing)

- **Tools must never raise.** Every `@mcp.tool()` returns a `str`, even on
  failure. Wrap network calls and translate `httpx` errors / not-found /
  unknown-currency into a friendly message. A crash is unusable to an AI client.
- **Plain text out, never JSON.** Format output like a helpful assistant would
  write it. The AI reads it and the human sees it in chat.
- **Validate before the network.** Reject a malformed NIP with `validate_nip`
  before making any HTTP call.
- **Async + httpx.** All I/O is `async`; use `httpx.AsyncClient(timeout=10)`.
- **Tests mock HTTP with `respx`** — no real network in the suite. `pytest`
  runs in `asyncio_mode = "auto"` (set in `pyproject.toml`), so async test
  functions need no decorator.
- **Keep `ruff` clean.** Run it before committing; CI fails otherwise.
- **Commits:** small and logical, imperative subject (e.g. `feat: ...`,
  `test: ...`, `docs: ...`), one concern each.

## How to add a new tool

1. Put the API/business logic in `vat.py` or `nbp.py` (or a new client module)
   as an `async` function returning structured data — no MCP imports there.
2. Add a thin `@mcp.tool()` wrapper in `server.py`: validate inputs, call the
   client, format plain text, and handle every error path to a string.
3. Write `respx`-mocked tests in the matching `tests/test_*.py`: happy path,
   not-found/invalid input, and a timeout (`side_effect=httpx.TimeoutException`).
4. If it changes how an agent should choose tools, update `SERVER_INSTRUCTIONS`.
5. Add a row to the tools table in **both** `README.md` and `README.pl.md`.
6. Run `uv run ruff check .` and `uv run pytest` — both green before committing.

## Known gotchas

- **NBP banking days:** rates publish only Mon–Fri. A weekend/holiday date
  returns the most recent rate; always surface the actual `effectiveDate`.
- **Table A vs B:** common currencies are in Table A, exotic ones in Table B.
  `get_rate` tries A then falls back to B before raising `CurrencyNotFound`.
- **Biała Lista date param is required** — defaults to today's date.
- **NIP checksum:** if `checksum == 10` the NIP is invalid (not "digit 10").
- The spec's example API responses (in the ignored `Private/` brief) use
  placeholder field values — verify field names against the live API, not the
  example, when extending the clients.
