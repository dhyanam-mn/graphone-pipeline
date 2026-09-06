import sys
sys.path.insert(0, ".")
import asyncio
import json
from src.scraper.companies import scrape_startups_and_products

async def run_test():
    startups, products = await scrape_startups_and_products(target_count=1000)
    print(f"Final Count: {len(startups)} Startups, {len(products)} Products")

    # Analyze Product distribution
    platform_pattern = [p for p in products if p.content.productName.endswith(" Platform")]
    distinct_products = [p for p in products if not p.content.productName.endswith(" Platform")]

    print(f"Auto-generated Pattern ('{{Startup}} Platform') Records: {len(platform_pattern)}")
    print(f"Genuinely Distinct Scraped Product Records: {len(distinct_products)}")

    print("\n--- 10 SAMPLE GENUINELY DISTINCT PRODUCTS ---")
    for i, p in enumerate(distinct_products[:10], 1):
        print(f"[{i}] Product Name: {p.content.productName} | Source: {p.source.name} | URL: {p.source.url}")
        print(f"    Description: {p.content.description[:100]}")

if __name__ == "__main__":
    asyncio.run(run_test())
