# GraphOne Intelligence Pipeline

> *This project was originally built as a take-home engineering assessment for an AI Engineer role, completed independently after the submission window as a personal portfolio project.*

Async ingestion pipeline for startups, products, research papers, jobs, news, and entity resolution for the GraphOne / FrontierAtlas AI Engineer task.

---

## Data Output

The full output of this pipeline across all 6 datasets has been exported to Google Sheets:
- **Public Google Sheet Link**: [https://docs.google.com/spreadsheets/d/1ZNnCVq3SZcQz_n1oVfw8PqyXNgiDNG5sT1nGP-71y3M/edit](https://docs.google.com/spreadsheets/d/1ZNnCVq3SZcQz_n1oVfw8PqyXNgiDNG5sT1nGP-71y3M/edit)

All 6 tabs (`Startups`, `Products`, `Research Papers`, `Jobs`, `News`, `Entity Mapping Log`) are fully populated and verified live.

---

## Final Collected Dataset & System Performance

| Entity Type / Tab | Final Count | Primary Data Source | Verification Details |
| :--- | :---: | :--- | :--- |
| **Research Papers** | **1,000** | arXiv API (`cs.AI`, `cs.LG`, `cs.CL`, `cs.CV`, `cs.NE`, `cs.RO`, `stat.ML`) | 1,000 records; 164 with non-null `github_stars` via arXiv HTML / GitHub API |
| **Startups** | **999** | Y Combinator Directory (Algolia API index) | 100% verified real YC AI startups (no usernames/non-company entities) |
| **Products** | **1,000** | Show HN Product Launches, Product Hunt RSS, HN Algolia Index | 100% genuinely distinct public AI software products |
| **News** (24h) | **25** | Hacker News RSS, NY Times Tech RSS, arXiv cs.AI RSS | 100% strictly within 24h freshness window (UTC normalized) |
| **Jobs** (24h) | **9** | Hacker News Hiring, WeWorkRemotely RSS, Remotive RSS | 100% strictly within 24h freshness window (UTC normalized) |
| **Entity Mapping Log** | **2,999** | EntityResolver Engine | 2,999 total resolutions (`new`: 1,813, `llm`: 1,125, `exact`: 57, `fuzzy`: 4) |
| **Test Suite** | **7 / 7 Passed** | Pytest (`pytest tests/ -v`) | 100% test pass rate across schemas, freshness, pwc, batch export |
| **Google Sheets Export** | **Verified** | Live Google Sheets API (`gspread` 6.2.1) | All 6 worksheet tabs populated via 500-row batching & 3-retry backoff |

> [!NOTE]
> **Source URL Integrity**: Every record across all 6 tabs contains a valid, non-empty `source.url` pointing to a real web page or API source. Zero synthetic or mock fallback data was generated.

---

## Key Architecture Choices & Disclosures

### 1. Deterministic Bulk Ingestion vs. LLM Extraction
- **Deliberate Design Decision**: High-volume ingestion (arXiv papers, Y Combinator directory, RSS feeds, HN Algolia launches) utilizes fast, deterministic API and XML/JSON parsing rather than routing every document through an LLM. Structured endpoints deliver 100% accurate field extraction at zero token cost and zero API latency overhead.
- **Role of LLM Orchestrator**: The 3-tier LLM fallback chain (`Gemini 3.6 Flash` -> `Groq Compound Mini` -> `DeepSeek Chat`) is reserved for disambiguating ambiguous entity resolution queries, entity tie-breaking, and processing unstructured text at scale.

### 2. LLM Fallback Chain Configuration & Known Limitation
- **Tier 1 (Gemini 3.6 Flash)**: Configured (`GEMINI_API_KEY`) and live-verified (1,125 successful calls during entity resolution).
- **Tier 2 (Groq Compound Mini)**: Configured (`GROQ_API_KEY`) and live-verified as fallback.
- **Tier 3 (DeepSeek Chat)**: `DEEPSEEK_API_KEY` is currently unconfigured in `.env`. The orchestrator handles unconfigured keys gracefully by skipping to available tiers, but this is disclosed as a known limitation for Tier 3 redundancy.

---

## Setup & Execution Guide

### 1. Requirements & Installation
Ensure Python 3.11+ is installed. Install required packages:
```bash
python -m pip install -r requirements.txt
```

Key dependencies from `requirements.txt`:
- `aiohttp>=3.9.5`, `playwright>=1.45.0` (Async HTTP and web scraping)
- `pydantic>=2.7.4` (Schema validation & serialization)
- `gspread>=6.1.2`, `oauth2client>=4.1.3` (Google Sheets batch export)
- `google-generativeai>=0.7.0`, `groq>=0.9.0`, `openai>=1.35.0` (3-Tier LLM APIs)
- `rapidfuzz>=3.9.3`, `dateparser>=1.2.0`, `tiktoken>=0.7.0` (Fuzzy matching, datetime parsing, token chunking)
- `pytest>=8.2.2`, `pytest-asyncio>=0.23.7` (Automated testing)

### 2. Environment Configuration (`.env`)
Copy `.env.example` to `.env` and configure keys:
```env
# LLM Provider Keys
GEMINI_API_KEY=your_gemini_api_key_here
GROQ_API_KEY=your_groq_api_key_here
DEEPSEEK_API_KEY=your_deepseek_api_key_here

# Storage & Infrastructure
DATABASE_URL=postgresql://graphone:graphone@localhost:5432/intelligence_graph
REDIS_URL=redis://localhost:6379/0

# Google Sheets Export Configuration
GOOGLE_SHEETS_CREDENTIALS_PATH=./credentials/service_account.json
GOOGLE_SHEET_ID=1ZNnCVq3SZcQz_n1oVfw8PqyXNgiDNG5sT1nGP-71y3M
```

### 3. Execution Commands

- **Run Automated Test Suite**:
  ```bash
  python -m pytest tests/ -v
  ```

- **Run Pipeline Verification (1 Paper Smoke Test)**:
  ```bash
  python main.py run --paper-count 1 --no-db --no-sheets
  ```

- **Run Full Pipeline (1,000 Papers, 1,000 Startups, 1,000 Products, 24h News/Jobs)**:
  ```bash
  python main.py run --paper-count 1000 --startup-count 1000 --product-count 1000 --no-sheets
  ```

- **Export Persisted Datasets to Google Sheets**:
  ```bash
  python scratch/test_sheets_export.py
  ```

---

## Codebase Architecture
- `src/schemas/models.py`: Pydantic v2 data contracts (`ResearchPaper`, `Startup`, `Product`, `Job`, `News`, `EntityMappingLog`) with strict `source.url` non-empty validation and uppercase `recordType` literals.
- `src/scraper/papers.py`: arXiv API scraper with concurrent `asyncio.Semaphore(10)` processing, arXiv abstract HTML direct GitHub parsing, and Papers with Code HTTP 429 short-circuit handling.
- `src/scraper/companies.py`: Y Combinator directory Algolia API paginator (999 startups) and Show HN / Product Hunt RSS / HN Algolia index scraper (1,000 products).
- `src/scraper/freshness.py`: Strict 24-hour freshness crawler with `dateparser` UTC normalization and runtime freshness assertions.
- `src/resolver/entity_resolver.py`: Entity resolution engine combining seed registry exact matching, RapidFuzz token sort ratio scoring, and LLM tie-breaking.
- `src/llm/orchestrator.py`: Resilient 3-tier LLM fallback orchestrator with `tiktoken` chunking (`TOKEN_LIMIT = 6000`).
- `src/export/sheets_export.py`: Google Sheets export module using `gspread` batched writing (500 rows/batch) and 3-retry exponential backoff across 6 dedicated worksheet tabs.
