import argparse
import asyncio
import json
import os
import sys

# Requirement 3: load_dotenv() MUST run before any other code/imports load env vars
from dotenv import load_dotenv
load_dotenv()

from src.schemas.models import ResearchPaper, Startup, Product, Job, News, EntityMappingLog
from src.scraper.papers import scrape_papers
from src.scraper.companies import scrape_startups_and_products
from src.scraper.freshness import crawl_freshness
from src.resolver.entity_resolver import EntityResolver
from src.export.sheets_export import export_all, GoogleSheetsSync


async def run_pipeline(args):
    print("=== Starting GraphOne Intelligence Pipeline ===")
    papers: list[ResearchPaper] = []
    startups: list[Startup] = []
    products: list[Product] = []
    jobs: list[Job] = []
    news: list[News] = []
    mapping_log: list[EntityMappingLog] = []

    # Step 1 & Step 2: Papers Scraper
    if args.paper_count > 0:
        print(f"\n--- Step 2: Scraping {args.paper_count} Research Papers ---")
        papers = await scrape_papers(target_count=args.paper_count, output_file="data/papers.jsonl")
        print(f"Scraped {len(papers)} Research Paper records.")

        if args.paper_count == 1 and papers:
            print("\n=== Real ResearchPaper Record Output ===")
            paper_dict = papers[0].model_dump()
            print(json.dumps(paper_dict, indent=2, default=str))
            print(f"Verified source.url: {papers[0].source.url}")
            print("=========================================\n")

    # Step 3: Startup & Product Scraper
    if args.startup_count > 0 or args.product_count > 0:
        print(f"\n--- Step 3: Scraping Startups ({args.startup_count}) & Products ({args.product_count}) ---")
        startups, products = await scrape_startups_and_products(target_count=max(args.startup_count, args.product_count))
        print(f"Collected {len(startups)} Startups and {len(products)} Products.")

    # Step 4: Freshness Crawler & Entity Resolver
    print("\n--- Step 4: Crawling Fresh News & Jobs (Last 24h) ---")
    news, jobs = await crawl_freshness()
    print(f"Crawled {len(news)} News items and {len(jobs)} Job items.")

    print("\n--- Step 4: Running Entity Resolution Engine ---")
    resolver = EntityResolver()
    for s in startups:
        resolver.resolve(s.content.entityName)
    for p in products:
        resolver.resolve(p.content.startupName)
    for pap in papers:
        # Resolve authors or paper title references
        if pap.content.authors:
            resolver.resolve(pap.content.authors[0])
    
    mapping_log = [
        EntityMappingLog(
            raw_name=item["raw_name"],
            canonical_name=item["canonical_name"],
            confidence=item["confidence"],
            method=item["method"]
        )
        for item in resolver.mapping_log
    ]
    print(f"Generated {len(mapping_log)} entity mapping log records.")

    # Validate source.url on every single record
    all_records = list(papers) + list(startups) + list(products) + list(jobs) + list(news)
    for idx, rec in enumerate(all_records):
        url = str(rec.source.url).strip()
        if not url:
            raise ValueError(f"[CRITICAL ERROR] Record #{idx} ({rec.recordType}) missing source.url!")

    # Validate strict 24-hour freshness constraint on News and Jobs
    from datetime import datetime, timezone, timedelta
    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    for n in news:
        if n.content.published_date < cutoff_24h:
            raise ValueError(f"[CRITICAL FRESHNESS ERROR] News record '{n.content.title}' published {n.content.published_date} is older than 24h!")
    for j in jobs:
        if j.content.date < cutoff_24h:
            raise ValueError(f"[CRITICAL FRESHNESS ERROR] Job record '{j.content.role_title}' date {j.content.date} is older than 24h!")

    # Summary report before export
    print("\n=== Pipeline Scrape & Resolution Summary ===")
    print(f"Research Papers: {len(papers)} (With github_stars: {sum(1 for p in papers if p.content.github_stars is not None)})")
    print(f"Startups:        {len(startups)}")
    print(f"Products:        {len(products)}")
    print(f"Jobs (24h):      {len(jobs)}")
    print(f"News (24h):      {len(news)}")
    print(f"Mapping Log:     {len(mapping_log)}")
    print("ALL RECORDS VERIFIED: 100% contain valid source.url strings.")
    print("============================================")

    # Step 5: Sheets Export
    if not args.no_sheets:
        print("\n--- Step 5: Exporting all 6 datasets to Google Sheets ---")
        try:
            counts = export_all(
                startups=startups,
                products=products,
                papers=papers,
                jobs=jobs,
                news=news,
                mapping_log=mapping_log
            )
            print(f"Google Sheets export completed successfully. Row counts: {counts}")
        except FileNotFoundError as e:
            print(f"[Sheets Warning] Credentials file missing: {e}")
            print("To enable Google Sheets export, set GOOGLE_SHEETS_CREDENTIALS_PATH and GOOGLE_SHEET_ID in .env.")
        except Exception as e:
            print(f"[Sheets Warning] Export failed: {e}")

    return {
        "startups": startups,
        "products": products,
        "papers": papers,
        "jobs": jobs,
        "news": news,
        "mapping_log": mapping_log
    }


def main():
    parser = argparse.ArgumentParser(description="GraphOne Intelligence Pipeline")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run pipeline components")
    run_parser.add_argument("--paper-count", type=int, default=1000, help="Target number of research papers")
    run_parser.add_argument("--startup-count", type=int, default=1000, help="Target number of startups")
    run_parser.add_argument("--product-count", type=int, default=1000, help="Target number of products")
    run_parser.add_argument("--no-db", action="store_true", help="Disable DB persistence")
    run_parser.add_argument("--no-sheets", action="store_true", help="Disable Google Sheets export")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(run_pipeline(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
