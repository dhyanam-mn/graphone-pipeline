# Gemini / Antigravity Prompt Pack — GraphOne Pipeline

Paste these one at a time, in order. Each is self-contained (includes schema +
constraints) so the agent doesn't need back-and-forth. Run each in its own
Antigravity agent task if you're parallelizing; otherwise feed sequentially.

---

## Prompt 1 — Pydantic Schemas

```
Create src/schemas/models.py with Pydantic v2 models for these 4 entity types.
Every model must include: schemaVersion (str, default "1.0"), recordType (Literal,
fixed per type), source (nested model with name: str, url: str — url is REQUIRED,
non-empty), collectedAt (datetime, default factory = now, ISO-8601).

1. Startup: content.entityName (str), content.data.employeeCount (int | None)
2. Product: content.startupName (str), content.pricingModel (Enum: FREE, FREEMIUM, PAID, ENTERPRISE)
3. ResearchPaper: content.title (str), content.authors (list[str]), content.paper_url (str),
   content.github_url (str | None), content.github_stars (int | None), content.published_date (datetime)
4. Job: content.company (str), content.date (datetime), content.is_remote (bool), content.role_family (str)

Add a validator on every model: reject construction if source.url is empty or not a valid URL.
Include __init__.py exports.
```

---

## Prompt 2 — Research Paper Scraper (do this vertical first — most structured)

```
Build src/scraper/papers.py: an async scraper using aiohttp that:
1. Queries the arXiv API (export.arxiv.org/api/query) for AI/ML categories
   (cs.AI, cs.LG, cs.CL) — paginate to collect 1000+ unique papers.
2. For each paper, attempts to find an associated GitHub repo via the
   Papers with Code API (paperswithcode.com/api/v1/papers/) matching by title.
3. If a GitHub repo is found, fetches current star count via the GitHub REST API
   (api.github.com/repos/{owner}/{repo}) — handle 403 rate limits with exponential
   backoff (use tenacity).
4. Maps every result into the ResearchPaper Pydantic model from src/schemas/models.py.
   source.url must be the actual arxiv abstract URL for that paper — never fabricate it.
5. Use asyncio.Semaphore(10) to cap concurrency. Log progress every 100 records.
6. Skip any paper where a GitHub repo can't be confidently matched — leave
   github_url/github_stars as None rather than guessing.
Output: a function `async def scrape_papers(target_count: int) -> list[ResearchPaper]`.
```

---

## Prompt 3 — Startup & Product Scraper

```
Build src/scraper/companies.py: an async scraper targeting public, non-paywalled
AI startup directories (e.g. Y Combinator's public company directory at
ycombinator.com/companies, Product Hunt's public listing pages) to collect
1000+ unique Startup records and 1000+ Product records matching the schemas
in src/schemas/models.py.

Requirements:
- Use aiohttp for static pages; fall back to Playwright Async only if a page
  requires JS rendering to load listings.
- Every record's source.url must be the actual page it was scraped from.
- content.data.employeeCount: extract if shown, else None — do not estimate.
- content.pricingModel: infer FREE/FREEMIUM/PAID/ENTERPRISE only from explicit
  pricing page text, default to None/skip the field logic if ambiguous — flag
  ambiguous ones for the LLM extraction layer to resolve instead of guessing here.
- Respect robots.txt. Use asyncio.Semaphore(8) for concurrency control.
Output: `async def scrape_startups_and_products(target_count: int) -> tuple[list[Startup], list[Product]]`.
```

---

## Prompt 4 — LLM Fallback + Chunking Orchestrator

```
Build src/llm/orchestrator.py implementing a multi-tier LLM extraction fallback chain:
Tier 1: Gemini Flash (google-generativeai SDK, model "gemini-1.5-flash" or latest flash)
Tier 2: Groq Llama 3 (groq SDK)
Tier 3: DeepSeek (openai SDK pointed at DeepSeek's OpenAI-compatible endpoint)

Requirements:
1. `async def extract_structured(raw_text: str, target_schema: type[BaseModel]) -> BaseModel`
   — tries Tier 1, on failure (429, 5xx, timeout) falls to Tier 2, then Tier 3.
   Raise only if all 3 fail.
2. Exponential backoff with jitter on 429s within each tier (use tenacity,
   max 3 retries per tier before falling through).
3. Chunking: before sending raw_text, use tiktoken to count tokens. If over
   6000 tokens, split at paragraph boundaries (never mid-sentence), send the
   highest-information-density chunks first (headings + first paragraphs),
   and merge partial extractions if the schema has list fields (e.g. authors).
   Never let a request exceed 8000 tokens (avoid 413s).
4. Prompt each tier to return ONLY valid JSON matching target_schema.model_json_schema(),
   parse with target_schema.model_validate_json(), retry with a stricter prompt
   once per tier if parsing fails.
5. Log which tier succeeded for each call (for the architecture doc's metrics).
```

---

## Prompt 5 — News/Jobs Freshness Crawler

```
Build src/scraper/freshness.py: an async crawler that monitors 5 AI news sources
(e.g. TechCrunch AI, VentureBeat AI, The Information AI, MIT Tech Review AI,
Ars Technica AI) and 5 AI job boards (e.g. Wellfound/AngelList jobs, LinkedIn
jobs — public search results only, RemoteOK, WeWorkRemotely AI filter, Hacker
News "Who's Hiring").

Requirements:
1. For each source, extract full-text article/job content.
2. Use the `dateparser` library to normalize publication dates — handle both
   explicit dates and relative strings ("2 hours ago", "yesterday").
3. Filter: only keep items published within the last 24 hours (datetime.now(UTC) - published_date <= timedelta(hours=24)).
4. If a source has no reliable date (missing meta tags), implement a heuristic:
   track previously-seen URLs in a Redis set (key: "seen_urls"); anything not
   in the set on this run is treated as new/fresh, then add it to the set.
5. Map news into a simple News schema (title, source, url, published_date,
   full_text) and jobs into the Job model from src/schemas/models.py.
Output: `async def crawl_freshness() -> tuple[list[dict], list[Job]]` (news, jobs).
```

---

## Prompt 6 — Entity Resolution Engine

```
Build src/resolver/entity_resolver.py:
1. Hardcode a seed list of 50 canonical AI startup names (e.g. "OpenAI",
   "Anthropic", "Google DeepMind", "Mistral AI", ... — generate a reasonable
   list of 50 well-known AI companies).
2. `def resolve(raw_name: str) -> tuple[str, float, str]` returns
   (canonical_name, confidence_score, method) where method is "exact",
   "fuzzy", or "llm".
   - Use rapidfuzz.fuzz.token_sort_ratio against the seed list.
   - Score >= 90: auto-match to canonical name, method="fuzzy".
   - Score 60-89: call the LLM orchestrator (src/llm/orchestrator.py) with a
     prompt asking "is X the same company as Y?" for the top-3 fuzzy candidates,
     method="llm".
   - Score < 60: treat as a new canonical entity (add to a runtime registry,
     not the hardcoded seed list), method="new".
3. Log every resolution to a list of dicts: {raw_name, canonical_name, confidence,
   method} — this becomes the "Entity Mapping Log" sheet tab.
Output: `class EntityResolver` with the above `resolve` method and a
`.mapping_log` property.
```

---

## Prompt 7 — Google Sheets Export

```
Build src/export/sheets_export.py using gspread:
1. Authenticate via service account JSON at path from GOOGLE_SHEETS_CREDENTIALS_PATH env var.
2. Open the sheet by GOOGLE_SHEET_ID env var.
3. Create/overwrite 6 tabs: Startups, Products, Research Papers, Jobs, News, Entity Mapping Log.
4. `def export_all(startups, products, papers, jobs, news, mapping_log)` —
   converts each list of Pydantic models to rows (flatten nested fields with
   dot notation for headers, e.g. "content.entityName"), writes headers + rows
   to the corresponding tab using batch_update (not cell-by-cell, to avoid
   Google Sheets API rate limits).
5. Before writing, assert every row has a non-empty source_url — raise if any
   record is missing one (this is the hard requirement from the brief).
```

---

## After all 7 prompts

Wire them together in a `main.py` at repo root that runs the phases in order,
persists intermediate results to Postgres, then calls the Sheets export.
Ask Codex CLI for this final integration step — it's a good fit for
straightforward glue code across files you already have.
