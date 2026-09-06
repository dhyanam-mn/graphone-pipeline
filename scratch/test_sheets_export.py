import sys
sys.path.insert(0, '.')
import os
import json
from dotenv import load_dotenv
load_dotenv()
from src.schemas.models import ResearchPaper, Startup, Product, Job, News, EntityMappingLog
from src.resolver.entity_resolver import EntityResolver
from src.export.sheets_export import GoogleSheetsSync, export_all

def main():
    print("Loading data from data/*.jsonl...")
    papers = []
    with open('data/papers.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            papers.append(ResearchPaper.model_validate_json(line))

    startups = []
    with open('data/startups.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            startups.append(Startup.model_validate_json(line))

    products = []
    with open('data/products.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            products.append(Product.model_validate_json(line))

    jobs = []
    with open('data/jobs.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            jobs.append(Job.model_validate_json(line))

    news = []
    with open('data/news.jsonl', 'r', encoding='utf-8') as f:
        for line in f:
            news.append(News.model_validate_json(line))

    resolver = EntityResolver()
    for s in startups:
        resolver.resolve(s.content.entityName)
    for p in products:
        resolver.resolve(p.content.startupName)
    for pap in papers:
        if pap.content.authors:
            resolver.resolve(pap.content.authors[0])

    mapping_log = [
        EntityMappingLog(
            raw_name=item['raw_name'],
            canonical_name=item['canonical_name'],
            confidence=item['confidence'],
            method=item['method']
        )
        for item in resolver.mapping_log
    ]

    print(f"Data summary:")
    print(f"  Startups: {len(startups)}")
    print(f"  Products: {len(products)}")
    print(f"  Papers: {len(papers)}")
    print(f"  Jobs: {len(jobs)}")
    print(f"  News: {len(news)}")
    print(f"  Mapping Log: {len(mapping_log)}")

    print("\nAttempting Google Sheets export...")
    try:
        results = export_all(
            startups=startups,
            products=products,
            papers=papers,
            jobs=jobs,
            news=news,
            mapping_log=mapping_log
        )
        print("\nExport successful! Results:")
        for tab, count in results.items():
            print(f"  {tab}: {count} rows")
    except Exception as e:
        print(f"\nExport failed with error: {type(e).__name__}: {e}")

if __name__ == '__main__':
    main()
