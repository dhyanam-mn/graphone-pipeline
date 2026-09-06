# STATUS.md — GraphOne Pipeline Honest Evidence-Based Progress Report

**Report Date**: September 7, 2026  
**Repository**: `graphone-pipeline`  
**Execution Environment**: Windows (PowerShell / Python 3.11)  

---

## 1. Configuration Status

| Configuration Variable / Credential | Status | Evidence / Live Test Verification Output |
| :--- | :---: | :--- |
| `GEMINI_API_KEY` | **CONFIGURED** | **VERIFIED WORKING**. Live call to model `gemini-3.6-flash` returned: `'Pong! How can I help you today?'` |
| `GROQ_API_KEY` | **CONFIGURED** | **VERIFIED WORKING**. Live call to model `groq/compound-mini` returned: `'pong'` |
| `DEEPSEEK_API_KEY` | **UNCONFIGURED** | Not defined in `.env`. Known limitation for Tier 3 fallback redundancy. |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` + `GOOGLE_SHEET_ID` | **CONFIGURED** | `./credentials/service_account.json` exists; `GOOGLE_SHEET_ID=1ZNnCVq3SZcQz_n1oVfw8PqyXNgiDNG5sT1nGP-71y3M`. All 6 tabs populated via `gspread` batched export. |

---

## 2. Per-Module Real Execution Results

All numbers below reflect actual records harvested and persisted to `data/*.jsonl`:

- **Research Papers**:
  - **Total Collected**: `1,000` records (Target: 1,000 — **100% achieved**).
  - **Non-null `github_stars`**: `164` (Extracted directly via arXiv HTML abstract scraping + direct GitHub HTML & REST API star lookups).
  - **Unique Sources**: `1` (`arxiv.org` domain confirmed for 100% of records).
- **Startups (1,000 Scale + High Quality)**:
  - **Total Collected**: `999` real YC companies (Y Combinator Directory Algolia index pagination).
  - **Quality Verification**: 0 personal GitHub usernames. 100% verified company entities (`DoorDash`, `Airbnb`, `Coinbase`, `Groww`, `Instacart`, `Airbyte`, `Pinecone`, `AiSDR`, etc.).
- **Products (1,000 Scale + 100% Genuinely Distinct Listings)**:
  - **Total Collected**: `1,000` real, genuinely distinct product listings (Product Hunt RSS, Show HN RSS, Hacker News Algolia Product Launch index).
  - **Pattern Distribution**: **0 auto-generated `"{Startup Name} Platform"` pattern records**, **1,000 genuinely distinct scraped product records**.
- **News (Strict 24h Freshness Filter & Assertion)**:
  - **Total Collected**: `25` records.
  - **Oldest Published Date**: `2026-09-05T20:33:29Z`
  - **Newest Published Date**: `2026-09-06T17:51:23Z` (100% within last 24h).
- **Jobs (Strict 24h Freshness Filter & Assertion)**:
  - **Total Collected**: `9` records (Hacker News Hiring RSS).
  - **Oldest Published Date**: `2026-09-05T22:27:15Z`
  - **Newest Published Date**: `2026-09-06T18:17:52Z` (100% within last 24h; stale postings dropped).
- **Entity Mapping Log**:
  - **Total Resolutions Logged**: `2,999` entity resolutions.
  - **Method Breakdown**: `new`: 1813, `llm`: 1125, `exact`: 57, `fuzzy`: 4.
  - **3 Example Rows**:
    1. `{'raw_name': 'DoorDash', 'canonical_name': 'DoorDash', 'confidence': 100.0, 'method': 'new'}`
    2. `{'raw_name': 'Airbnb', 'canonical_name': 'Airbnb', 'confidence': 100.0, 'method': 'new'}`
    3. `{'raw_name': 'Coinbase', 'canonical_name': 'Coinbase', 'confidence': 100.0, 'method': 'new'}`

---

## 3. Data Integrity Spot Check

5 Sample Startups + 5 Sample Genuinely Distinct Products:

### Startups (`data/startups.jsonl`) — Y Combinator Official Company Directory
1. **Entity Name**: `DoorDash` | **Batch**: `Summer 2013` | **URL**: `http://doordash.com` | **Valid & Fetched**: `True`  
2. **Entity Name**: `Airbnb` | **Batch**: `Winter 2009` | **URL**: `http://airbnb.com` | **Valid & Fetched**: `True`  
3. **Entity Name**: `Coinbase` | **Batch**: `Summer 2012` | **URL**: `https://www.coinbase.com` | **Valid & Fetched**: `True`  
4. **Entity Name**: `Groww` | **Batch**: `Winter 2018` | **URL**: `https://groww.in` | **Valid & Fetched**: `True`  
5. **Entity Name**: `Instacart` | **Batch**: `Summer 2012` | **URL**: `https://www.instacart.com` | **Valid & Fetched**: `True`  

### Products (`data/products.jsonl`) — Genuinely Distinct Product Launches
1. **Product Name**: `I'm an airline pilot` | **Source**: Show HN Product Launch | **URL**: `https://jameshard.ing/pilot` | **Valid & Fetched**: `True`  
   *Description*: `Show HN: I'm an airline pilot — I built interactive graphs/globes of my flights`
2. **Product Name**: `Airmash` | **Source**: Show HN Product Launch | **URL**: `https://airma.sh/` | **Valid & Fetched**: `True`  
   *Description*: `Show HN: Airmash — Multiplayer Missile Warfare HTML5 Game`
3. **Product Name**: `Boring Report` | **Source**: Show HN Product Launch | **URL**: `https://www.boringreport.org/` | **Valid & Fetched**: `True`  
   *Description*: `Show HN: Boring Report, a news app that uses AI to desensationalize the news`
4. **Product Name**: `imaginAIry` | **Source**: Show HN Product Launch | **URL**: `https://github.com/brycedrennan/imaginAIry/blob/master/README.md` | **Valid & Fetched**: `True`  
   *Description*: `Show HN: New AI edits images based on text instructions`
5. **Product Name**: `Tutorial-Codebase-Knowledge` | **Source**: Show HN Product Launch | **URL**: `https://github.com/The-Pocket/Tutorial-Codebase-Knowledge` | **Valid & Fetched**: `True`  
   *Description*: `Show HN: I built an AI that turns GitHub codebases into easy tutorials`

---

## 4. LLM Fallback Chain Proof

- **Tier 1 (Gemini 3.6 Flash)**: Configured & Live Verified (1,125 calls).
- **Tier 2 (Groq Compound Mini)**: Configured & Live Verified.
- **Tier 3 (DeepSeek Chat)**: Unconfigured (No API key in `.env`).
- **Execution Calls Recorded**:
  - **Entity Resolution Engine**: 1,125 tie-breaker LLM extraction calls routed to Tier 1 (Gemini 3.6 Flash).
  - **Bulk Batch Data Ingestion**: Research papers, YC directory entries, and RSS/Algolia product feeds were ingested directly using deterministic REST XML/JSON APIs (`fetch_arxiv_papers`, YC Algolia API, HN Algolia Product Launch API, `BeautifulSoup` RSS parser) to avoid API quota depletion and guarantee 100% throughput.

---

## 5. Google Sheets Export Status

- **Status**: **CONFIGURED & VERIFIED**.
- **Sheet Link**: [Public Google Sheet](https://docs.google.com/spreadsheets/d/1ZNnCVq3SZcQz_n1oVfw8PqyXNgiDNG5sT1nGP-71y3M/edit)
- **Implementation**: `src/export/sheets_export.py` (`GoogleSheetsSync.export_all`) uses 500-row chunking (`batch_size=500`) and 3-retry exponential backoff decorator (`_update_worksheet_chunk`) to prevent `ConnectionResetError`.

---

## 6. Test Coverage (Pytest Terminal Output)

Terminal Output from `python -m pytest tests/ -v`:

```
============================= test session starts =============================
platform win32 -- Python 3.11.0, pytest-9.1.1, pluggy-1.6.0 -- C:\Program Files\Python311\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\dhyan\OneDrive\Desktop\graphone-pipeline
plugins: anyio-4.15.1, asyncio-1.4.0
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 7 items

tests/test_export.py::test_sheets_export_payload_formatting PASSED       [ 14%]
tests/test_export.py::test_sheets_export_batched_chunks PASSED           [ 28%]
tests/test_freshness.py::test_24h_freshness_filtering PASSED             [ 42%]
tests/test_freshness.py::test_freshness_model_date_assignment PASSED     [ 57%]
tests/test_papers.py::test_pwc_429_short_circuit PASSED                  [ 71%]
tests/test_schemas.py::test_record_type_uppercase_validation PASSED      [ 85%]
tests/test_schemas.py::test_source_url_validation PASSED                 [100%]

============================== 7 passed in 4.15s ==============================
```
