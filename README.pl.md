# 🇵🇱 Polish Business Intelligence MCP

> **Język:** [🇬🇧 English](./README.md) · **Polski**

Serwer [MCP (Model Context Protocol)](https://modelcontextprotocol.io), który daje dowolnemu agentowi AI — Claude, Cursor, Copilot — natychmiastowy dostęp w czasie rzeczywistym do dwóch oficjalnych polskich źródeł danych: **Białej Listy podatników VAT (Ministerstwo Finansów)** oraz **kursów walut Narodowego Banku Polskiego (NBP)**. Bez kluczy API, bez rejestracji, bez scrapowania.

[![CI](https://github.com/neflingcreations/PBI-MCP/actions/workflows/ci.yml/badge.svg)](https://github.com/neflingcreations/PBI-MCP/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Po co to powstało

Duże modele językowe nie mają dostępu do aktualnego rejestru VAT ani do oficjalnych kursów walut — te dane są dynamiczne, zmieniają się codziennie i znajdują się w rządowych API, na których model nigdy nie był trenowany. Ten serwer MCP wypełnia tę lukę. Po podłączeniu do agenta pozwala zweryfikować, czy polska firma jest czynnym podatnikiem VAT, pobrać jej adres rejestrowy i rachunki bankowe oraz przeliczać waluty po oficjalnym kursie średnim banku centralnego — wszystko na żywo.

Serwer opakowuje dwa darmowe, publiczne API bez autoryzacji:

| Źródło | Co udostępnia |
| --- | --- |
| [**Biała Lista**](https://wl-api.mf.gov.pl/) — wykaz podatników VAT Ministerstwa Finansów | Wyszukiwanie firmy po **NIP**: nazwa, status VAT, adres, data rejestracji, rachunki bankowe |
| [**NBP**](https://api.nbp.pl/) — Narodowy Bank Polski | Oficjalne kursy średnie PLN dla ok. 40 walut |

> **Dlaczego liczą się dane na żywo**
> Modele AI z przekonaniem generują dane, które wyglądają wiarygodnie — poprawny NIP, właściwy format — a mimo to bywają błędne. Jedynym rozwiązaniem jest zapytanie wiarygodnego źródła. Dokładnie to robi ten serwer, przy każdym wywołaniu.

---

## Narzędzia

| Narzędzie | Co robi | Główne dane wejściowe |
| --- | --- | --- |
| `lookup_company` | Pełne wyszukiwanie firmy na Białej Liście — nazwa, status VAT, adres, data rejestracji, rachunki bankowe | `nip` |
| `check_vat_status` | Szybka odpowiedź tak / nie / zwolniony — czy ten NIP to czynny podatnik VAT? Idealne do pytania „czy mogę zaufać tej fakturze?” | `nip` |
| `get_all_rates` | Wszystkie aktualne kursy PLN z Tabeli A NBP (EUR, USD, GBP, CHF, JPY, CZK, …) | _opcjonalnie_ `date` |
| `get_currency_rate` | Oficjalny kurs średni NBP dla jednej waluty (Tabela A, z przejściem do Tabeli B dla walut egzotycznych) | `currency_code`, _opcjonalnie_ `date` |
| `convert_currency` | Przeliczanie między PLN a dowolną walutą lub kurs krzyżowy dwóch walut przez PLN | `amount`, `from_currency`, `to_currency`, _opcjonalnie_ `date` |

Każde narzędzie zwraca czytelny tekst (nigdy surowy JSON) i nigdy nie zgłasza wyjątku — błędy wracają jako przyjazne komunikaty, na które agent może zareagować.

---

## Szybka instalacja

Wymaga [**uv**](https://docs.astral.sh/uv/) oraz Pythona 3.11+.

```bash
git clone https://github.com/neflingcreations/PBI-MCP.git
cd PBI-MCP
uv sync
```

### Konfiguracja Claude Desktop / Claude Code

Dodaj poniższe do konfiguracji MCP (Claude Desktop: `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "polish-business": {
      "command": "uv",
      "args": ["run", "polish-business-mcp"],
      "cwd": "/sciezka/do/PBI-MCP"
    }
  }
}
```

Po ponownym uruchomieniu klienta pięć narzędzi pojawi się automatycznie.

---

## Przykładowe interakcje z agentem

Po podłączeniu agent może odpowiadać na pytania, na które wcześniej nie potrafił:

> **„Czy firma o NIP 951-238-16-07 jest czynnym podatnikiem VAT?”**
> → wywołuje `check_vat_status("9512381607")` →
> `YES — BOOKSY INTERNATIONAL SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ (NIP 9512381607) is an ACTIVE VAT payer (status: Czynny).`

> **„Wyszukaj NIP 9512381607 i podaj adres oraz rachunki bankowe.”**
> → wywołuje `lookup_company("9512381607")` → nazwa firmy, status VAT, adres rejestrowy (UL. PROSTA 67, Warszawa), data rejestracji oraz lista rachunków z wykazu.

> **„Jaki jest dzisiejszy kurs EUR/PLN według NBP?”**
> → wywołuje `get_currency_rate("EUR")` →
> `EUR (euro): 4.2531 PLN za 1 EUR · data: 2026-06-26 · oficjalny kurs średni NBP.`

> **„Przelicz 1500 PLN na GBP po oficjalnym kursie.”**
> → wywołuje `convert_currency(1500, "PLN", "GBP")` → przeliczona kwota, użyty kurs GBP oraz data obowiązywania.

---

## Źródła API

- **Biała Lista** (wykaz podatników VAT) — Ministerstwo Finansów: https://wl-api.mf.gov.pl/
- **NBP** — kursy walut, Narodowy Bank Polski: https://api.nbp.pl/

Oba są darmowe, publiczne i nie wymagają autoryzacji. Zapytanie do Białej Listy zawsze przekazuje dzisiejszą datę (wymaganą przez API); NBP publikuje kursy tylko w dni robocze, więc zapytanie z weekendu zwraca ostatni dostępny kurs, a narzędzie pokazuje rzeczywistą datę obowiązywania.

---

## Praca lokalna

```bash
uv sync                                              # instalacja zależności (z grupą dev)
uv run pytest                                        # testy (HTTP w pełni zamockowane — bez sieci)
uv run ruff check .                                  # lint
uv run mcp dev src/polish_business_mcp/server.py     # MCP Inspector — ręczne wywołanie narzędzi
uv run polish-business-mcp                           # serwer przez stdio (czeka na stdin — to normalne)
```

Zestaw testów mockuje każde wywołanie HTTP biblioteką [`respx`](https://lundberg.github.io/respx/), więc działa offline i deterministycznie.

---

## Plany rozwoju

- `lookup_by_regon` — API Białej Listy przyjmuje też **REGON** (9- lub 14-cyfrowy identyfikator firmy).
- `lookup_companies_batch` — endpoint zbiorczy (`/api/search/nips/`) weryfikuje do 30 numerów NIP w jednym wywołaniu.
- Historyczne sprawdzanie statusu VAT na wskazaną datę.

---

## Licencja

MIT — zobacz [`LICENSE`](./LICENSE).
