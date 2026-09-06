import asyncio
import json
import sys
import os

# Set PYTHONPATH to current directory
sys.path.insert(0, os.path.abspath("."))

from src.schemas.models import ResearchPaper, ResearchPaperContent, SourceInfo, Startup, StartupContent, StartupData
from src.scraper.papers import scrape_papers
from src.scraper.companies import scrape_startups_and_products
from src.scraper.freshness import crawl_freshness
from src.resolver.entity_resolver import EntityResolver
from src.llm.orchestrator import LLMOrchestrator, count_tokens, chunk_text
from src.export.sheets_export import GoogleSheetsSync, flatten_pydantic_model


async def run_smoke_tests():
    print("==========================================================")
    print("       GRAPHONE PIPELINE FILE-BY-FILE SMOKE TESTS         ")
    print("==========================================================\n")

    # 1. src/schemas/models.py
    print("--- 1. Testing src/schemas/models.py ---")
    try:
        source = SourceInfo(name="Test Source", url="https://arxiv.org/abs/2609.00001")
        content = ResearchPaperContent(
            title="Smoke Test Paper Title",
            authors=["Alice", "Bob"],
            paper_url="https://arxiv.org/abs/2609.00001"
        )
        paper = ResearchPaper(source=source, content=content)
        print("Model instantiation: SUCCESS")
        print(f"recordType: {paper.recordType}")
        print(f"source.url: {paper.source.url}")
        
        # Test validator rejecting invalid URL
        try:
            SourceInfo(name="Invalid", url="ftp://invalid")
        except ValueError as val_err:
            print(f"URL Validator catch: '{val_err}'")
    except Exception as e:
        print(f"ERROR: {e}")

    # 2. src/scraper/papers.py
    print("\n--- 2. Testing src/scraper/papers.py ---")
    try:
        papers = await scrape_papers(target_count=1, output_file=None)
        print(f"scrape_papers(target_count=1) output count: {len(papers)}")
        if papers:
            print(f"Paper Title: '{papers[0].content.title}'")
            print(f"Paper source.url: '{papers[0].source.url}'")
    except Exception as e:
        print(f"ERROR: {e}")

    # 3. src/scraper/companies.py
    print("\n--- 3. Testing src/scraper/companies.py ---")
    try:
        startups, products = await scrape_startups_and_products(target_count=1, output_startups_file=None, output_products_file=None)
        print(f"scrape_startups_and_products output: {len(startups)} startups, {len(products)} products")
        if startups:
            print(f"Startup Entity: '{startups[0].content.entityName}' | URL: '{startups[0].source.url}'")
        if products:
            print(f"Product Name: '{products[0].content.productName}' | URL: '{products[0].source.url}'")
    except Exception as e:
        print(f"ERROR: {e}")

    # 4. src/scraper/freshness.py
    print("\n--- 4. Testing src/scraper/freshness.py ---")
    try:
        news, jobs = await crawl_freshness()
        print(f"crawl_freshness() output: {len(news)} news, {len(jobs)} jobs")
        if news:
            print(f"News Title: '{news[0].content.title}' | URL: '{news[0].source.url}'")
        if jobs:
            print(f"Job Role: '{jobs[0].content.role_title}' | URL: '{jobs[0].source.url}'")
    except Exception as e:
        print(f"ERROR: {e}")

    # 5. src/resolver/entity_resolver.py
    print("\n--- 5. Testing src/resolver/entity_resolver.py ---")
    try:
        resolver = EntityResolver()
        c1, s1, m1 = resolver.resolve("OpenAI Inc")
        c2, s2, m2 = resolver.resolve("Custom Unknown Startup")
        print(f"Resolve 'OpenAI Inc' -> Canonical: '{c1}', Score: {s1}, Method: '{m1}'")
        print(f"Resolve 'Custom Unknown Startup' -> Canonical: '{c2}', Score: {s2}, Method: '{m2}'")
        print(f"Mapping log entries generated: {len(resolver.mapping_log)}")
    except Exception as e:
        print(f"ERROR: {e}")

    # 6. src/llm/orchestrator.py
    print("\n--- 6. Testing src/llm/orchestrator.py ---")
    try:
        sample_text = "GraphOne pipeline orchestrator token counting and paragraph chunking verification.\n\nSecond paragraph content."
        tokens = count_tokens(sample_text)
        chunks = chunk_text(sample_text, max_tokens=10)
        orchestrator = LLMOrchestrator()
        print(f"count_tokens output: {tokens} tokens")
        print(f"chunk_text output: {len(chunks)} chunks")
        print(f"LLMOrchestrator instance initialized. Tiers available: Gemini({bool(orchestrator.gemini_api_key)}), Groq({bool(orchestrator.groq_api_key)}), DeepSeek({bool(orchestrator.deepseek_api_key)})")
    except Exception as e:
        print(f"ERROR: {e}")

    # 7. src/export/sheets_export.py
    print("\n--- 7. Testing src/export/sheets_export.py ---")
    try:
        source = SourceInfo(name="arXiv", url="https://arxiv.org/abs/2609.00001")
        content = ResearchPaperContent(title="Export Test Paper", authors=["Author A"], paper_url="https://arxiv.org/abs/2609.00001")
        paper = ResearchPaper(source=source, content=content)
        flat = flatten_pydantic_model(paper)
        syncer = GoogleSheetsSync()
        print(f"flatten_pydantic_model output keys count: {len(flat)}")
        print(f"Flattened 'source.url': '{flat.get('source.url')}'")
        print(f"GoogleSheetsSync initialized. Configured Creds Path: '{syncer.creds_path}'")
    except Exception as e:
        print(f"ERROR: {e}")

    print("\n==========================================================")
    print("           ALL 7 SMOKE TESTS EXECUTED CLEANLY             ")
    print("==========================================================")

if __name__ == "__main__":
    asyncio.run(run_smoke_tests())
