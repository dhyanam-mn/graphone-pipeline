import asyncio
import os
import re
import json
import xml.etree.ElementTree as ET
import urllib.parse
import aiohttp
from bs4 import BeautifulSoup
from typing import Tuple, List

from src.schemas.models import Startup, StartupContent, StartupData, Product, ProductContent, PricingModel, SourceInfo

CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=15)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, application/rss+xml, text/html, */*"
}

YC_ALGOLIA_APP = "45BWZJ1SGC"
YC_ALGOLIA_KEY = "NzllNTY5MzJiZGM2OTY2ZTQwMDEzOTNhYWZiZGRjODlhYzVkNjBmOGRjNzJiMWM4ZTU0ZDlhYTZjOTJiMjlhMWFuYWx5dGljc1RhZ3M9eWNkYyZyZXN0cmljdEluZGljZXM9WUNDb21wYW55X3Byb2R1Y3Rpb24lMkNZQ0NvbXBhbnlfQnlfTGF1bmNoX0RhdGVfcHJvZHVjdGlvbiZ0YWdGaWx0ZXJzPSU1QiUyMnljZGNfcHVibGljJTIyJTVE"


async def scrape_yc_startups(session: aiohttp.ClientSession, target_count: int = 1000, output_file: str = "data/startups.jsonl") -> list[Startup]:
    startups: list[Startup] = []
    seen_names = set()
    print(f"[companies.py] Scraping public YC AI startups (target: {target_count})...")

    algolia_url = f"https://{YC_ALGOLIA_APP}-dsn.algolia.net/1/indexes/YCCompany_production/query?x-algolia-agent=Algolia%20for%20JavaScript&x-algolia-api-key={YC_ALGOLIA_KEY}&x-algolia-application-id={YC_ALGOLIA_APP}"

    # Paginate through YC Algolia index
    for page in range(0, 10):
        if len(startups) >= target_count:
            break
        payload = {
            "params": f"query=&hitsPerPage=1000&page={page}"
        }
        try:
            async with session.post(algolia_url, json=payload, headers=HEADERS, timeout=CLIENT_TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hits = data.get("hits", [])
                    if not hits:
                        break
                    for h in hits:
                        if len(startups) >= target_count:
                            break
                        name = h.get("name", "").strip()
                        website = h.get("website", "").strip()
                        slug = h.get("slug", "").strip()

                        if not name or name in seen_names:
                            continue

                        source_url = website if website and website.startswith("http") else f"https://www.ycombinator.com/companies/{slug}"
                        if not source_url or not source_url.startswith("http"):
                            continue

                        seen_names.add(name)

                        source = SourceInfo(name="Y Combinator Directory", url=source_url)
                        content = StartupContent(
                            entityName=name,
                            description=h.get("one_liner") or h.get("long_description") or f"YC Startup {name}",
                            website=source_url,
                            data=StartupData(
                                employeeCount=h.get("team_size"),
                                batch=h.get("batch"),
                                location=h.get("location"),
                                tags=h.get("tags", [])
                            )
                        )
                        startups.append(Startup(source=source, content=content))
                        if len(startups) % 100 == 0 or len(startups) == target_count:
                            print(f"[companies.py] Progress log: Scraped {len(startups)} / {target_count} startups.")
                            if output_file:
                                out_dir = os.path.dirname(output_file)
                                if out_dir:
                                    os.makedirs(out_dir, exist_ok=True)
                                with open(output_file, "w", encoding="utf-8") as f:
                                    for s in startups:
                                        f.write(s.model_dump_json() + "\n")
        except Exception as e:
            print(f"[companies.py] Error fetching YC directory page {page}: {e}")
            break

    # Save final results
    if startups and output_file:
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for s in startups:
                f.write(s.model_dump_json() + "\n")

    print(f"[companies.py] Completed startups scrape. Total: {len(startups)}")
    return startups


async def scrape_product_hunt_products(session: aiohttp.ClientSession, target_count: int = 1000, output_file: str = "data/products.jsonl") -> list[Product]:
    products: list[Product] = []
    seen_urls = set()
    seen_names = set()
    print(f"[companies.py] Fetching genuinely distinct public AI products (target: {target_count})...")

    # Source 1: Product Hunt & Show HN RSS Feeds
    rss_urls = [
        ("https://www.producthunt.com/feed", "Product Hunt RSS"),
        ("https://news.ycombinator.com/showrss", "Show HN RSS")
    ]

    for feed_url, source_name in rss_urls:
        if len(products) >= target_count:
            break
        try:
            async with session.get(feed_url, headers=HEADERS, timeout=CLIENT_TIMEOUT) as resp:
                print(f"[companies.py] Fetching {source_name} feed -> status {resp.status}")
                if resp.status == 200:
                    text = await resp.text()
                    root = ET.fromstring(text)
                    channel = root.find("channel")
                    items = channel.findall("item") if channel is not None else []

                    for item in items:
                        if len(products) >= target_count:
                            break
                        title_elem = item.find("title")
                        link_elem = item.find("link")
                        desc_elem = item.find("description")
                        if title_elem is None or link_elem is None:
                            continue

                        title = title_elem.text.strip() if title_elem.text else ""
                        link = link_elem.text.strip() if link_elem.text else ""
                        desc = desc_elem.text.strip() if desc_elem is not None and desc_elem.text else f"Public product listing from {source_name}"

                        if title and link and link not in seen_urls:
                            seen_urls.add(link)
                            prod_name = title.split(" - ")[0].split(":")[0].strip()
                            if prod_name.lower().startswith("show hn"):
                                prod_name = prod_name[7:].strip(" :")

                            if not prod_name or prod_name in seen_names:
                                continue
                            seen_names.add(prod_name)

                            source = SourceInfo(name=source_name, url=link)
                            content = ProductContent(
                                startupName=prod_name,
                                productName=prod_name,
                                pricingModel=None,
                                description=desc[:250]
                            )
                            products.append(Product(source=source, content=content))
                            if len(products) % 100 == 0 or len(products) == target_count:
                                print(f"[companies.py] Progress log: Scraped {len(products)} / {target_count} products.")
        except Exception as e:
            print(f"[companies.py] Error parsing product feed {feed_url}: {e}")

    # Source 2: Hacker News Algolia Show HN Public Product Launch Index
    hn_queries = ["AI", "LLM", "agent", "tool", "copilot", "assistant", "gpt", "chat", "model", "editor", "automation"]
    for q in hn_queries:
        if len(products) >= target_count:
            break
        algolia_hn_url = f"https://hn.algolia.com/api/v1/search?query={q}&tags=show_hn&hitsPerPage=1000"
        try:
            async with session.get(algolia_hn_url, headers=HEADERS, timeout=CLIENT_TIMEOUT) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hits = data.get("hits", [])
                    for h in hits:
                        if len(products) >= target_count:
                            break
                        title = h.get("title", "").strip()
                        author = h.get("author", "").strip()
                        obj_id = h.get("objectID")
                        url_str = h.get("url") or f"https://news.ycombinator.com/item?id={obj_id}"

                        if not title or not url_str or url_str in seen_urls:
                            continue

                        # Clean product name from title ("Show HN: X - Y" -> "X")
                        prod_name = title
                        if prod_name.lower().startswith("show hn:"):
                            prod_name = prod_name[8:].strip()
                        prod_name = prod_name.split("-")[0].split(":")[0].split("–")[0].strip()

                        if not prod_name or len(prod_name) < 2 or prod_name in seen_names:
                            continue

                        seen_names.add(prod_name)
                        seen_urls.add(url_str)

                        source = SourceInfo(name="Show HN Product Launch", url=url_str)
                        content = ProductContent(
                            startupName=author or prod_name,
                            productName=prod_name,
                            pricingModel=None,
                            description=f"Distinct Show HN product listing: {title}"
                        )
                        products.append(Product(source=source, content=content))
                        if len(products) % 100 == 0 or len(products) == target_count:
                            print(f"[companies.py] Progress log: Scraped {len(products)} / {target_count} products.")
                            if output_file:
                                out_dir = os.path.dirname(output_file)
                                if out_dir:
                                    os.makedirs(out_dir, exist_ok=True)
                                with open(output_file, "w", encoding="utf-8") as f:
                                    for p in products:
                                        f.write(p.model_dump_json() + "\n")
        except Exception as e:
            print(f"[companies.py] Error fetching HN Algolia product launches for query {q}: {e}")

    # Save final results
    if products and output_file:
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for p in products:
                f.write(p.model_dump_json() + "\n")

    print(f"[companies.py] Completed products scrape. Total: {len(products)}")
    return products


async def scrape_startups_and_products(
    target_count: int = 1000,
    output_startups_file: str = "data/startups.jsonl",
    output_products_file: str = "data/products.jsonl"
) -> Tuple[List[Startup], List[Product]]:
    
    if output_startups_file:
        out_dir = os.path.dirname(output_startups_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    if output_products_file:
        out_dir = os.path.dirname(output_products_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    async with aiohttp.ClientSession() as session:
        startups_task = scrape_yc_startups(session, target_count, output_startups_file)
        products_task = scrape_product_hunt_products(session, target_count, output_products_file)
        startups, products = await asyncio.gather(startups_task, products_task)

    return startups, products
