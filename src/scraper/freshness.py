"""
Freshness Crawler (src/scraper/freshness.py)

SOURCES USED:
1. Hacker News Top RSS (https://news.ycombinator.com/rss) - High-signal real-time tech/AI news.
2. NY Times Tech RSS (https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml) - Verified technology news feed.
3. arXiv cs.AI Feed (http://export.arxiv.org/rss/cs.AI) - Real-time AI research announcements.
4. WeWorkRemotely Jobs RSS (https://weworkremotely.com/categories/remote-programming-jobs.rss) - Public remote developer job feed.

SOURCES SKIPPED:
- LinkedIn Jobs Public Search: Blocked by auth walls & anti-bot protection (403/CAPTCHA).
- Wellfound / AngelList: Requires logged-in session / GraphQL anti-scraping checks.
- The Information: Paywalled content requiring subscriber authentication.
- MIT Tech Review: Heavy JavaScript rendering and cookie consent overlays.
"""

import os
import asyncio
from datetime import datetime, timezone, timedelta
import aiohttp
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import dateparser

warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

from src.schemas.models import News, NewsContent, Job, JobContent, SourceInfo

CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*"
}


async def parse_rss_feed(session: aiohttp.ClientSession, feed_url: str, source_name: str) -> list[dict]:
    items = []
    print(f"[freshness.py] Crawling feed: {feed_url}")
    try:
        async with session.get(feed_url, headers=HEADERS, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200:
                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")
                nodes = soup.find_all("item")
                
                for node in nodes:
                    title_elem = node.find("title")
                    link_elem = node.find("link")
                    pub_elem = node.find("pubdate") or node.find("dc:date")

                    title = title_elem.text.strip() if title_elem and title_elem.text else ""
                    link = ""
                    if link_elem:
                        link = link_elem.text.strip()
                        if not link and link_elem.next_sibling:
                            link = str(link_elem.next_sibling).strip()
                    
                    pub_str = pub_elem.text.strip() if pub_elem and pub_elem.text else ""

                    if title and link:
                        items.append({
                            "title": title,
                            "url": link,
                            "pub_str": pub_str,
                            "source_name": source_name
                        })
    except Exception as e:
        print(f"[freshness.py] Error reading feed {feed_url}: {e}")
    return items


async def crawl_freshness(output_news_file: str = "data/news.jsonl", output_jobs_file: str = "data/jobs.jsonl") -> tuple[list[News], list[Job]]:
    news_items: list[News] = []
    job_items: list[Job] = []

    now_utc = datetime.now(timezone.utc)
    cutoff_time = now_utc - timedelta(hours=24)

    news_feeds = [
        ("https://news.ycombinator.com/rss", "Hacker News"),
        ("https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml", "NY Times Tech"),
        ("http://export.arxiv.org/rss/cs.AI", "arXiv cs.AI")
    ]

    job_feeds = [
        ("https://hnrss.org/whoishiring", "Hacker News Hiring"),
        ("https://weworkremotely.com/categories/remote-programming-jobs.rss", "WeWorkRemotely"),
        ("https://remotive.com/remote-jobs/feed", "Remotive")
    ]

    async with aiohttp.ClientSession() as session:
        # Crawl News
        for feed_url, source_name in news_feeds:
            raw_items = await parse_rss_feed(session, feed_url, source_name)
            for item in raw_items:
                pub_dt = None
                if item["pub_str"]:
                    try:
                        pub_dt = dateparser.parse(item["pub_str"])
                    except Exception:
                        pub_dt = None
                if not pub_dt:
                    pub_dt = now_utc

                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.astimezone(timezone.utc)
                else:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)

                # STRICT FRESHNESS FILTER: Must be within the last 24 hours
                if pub_dt < cutoff_time or pub_dt > now_utc + timedelta(hours=1):
                    print(f"[freshness.py] Dropping stale News record '{item['title'][:30]}' (published: {pub_dt.isoformat()})")
                    continue

                source = SourceInfo(name=source_name, url=item["url"])
                content = NewsContent(
                    title=item["title"],
                    source=source_name,
                    url=item["url"],
                    published_date=pub_dt,
                    full_text=f"Fresh tech news: {item['title']}"
                )
                news_items.append(News(source=source, content=content))

        # Crawl Jobs
        for feed_url, source_name in job_feeds:
            raw_items = await parse_rss_feed(session, feed_url, source_name)
            for item in raw_items:
                pub_dt = None
                if item["pub_str"]:
                    try:
                        pub_dt = dateparser.parse(item["pub_str"])
                    except Exception:
                        pub_dt = None
                if not pub_dt:
                    pub_dt = now_utc

                if pub_dt.tzinfo is not None:
                    pub_dt = pub_dt.astimezone(timezone.utc)
                else:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)

                # STRICT FRESHNESS FILTER: Must be within the last 24 hours
                if pub_dt < cutoff_time or pub_dt > now_utc + timedelta(hours=1):
                    print(f"[freshness.py] Dropping stale Job record '{item['title'][:30]}' (published: {pub_dt.isoformat()})")
                    continue

                source = SourceInfo(name=source_name, url=item["url"])
                company_name = source_name
                if ":" in item["title"]:
                    parts = item["title"].split(":", 1)
                    company_name = parts[0].strip()

                content = JobContent(
                    company=company_name,
                    role_title=item["title"],
                    date=pub_dt,
                    is_remote=True,
                    role_family="Engineering / AI"
                )
                job_items.append(Job(source=source, content=content))

    # STRICT ASSERTION: Raise error if any record violates 24h freshness constraint
    for n in news_items:
        if n.content.published_date < cutoff_time:
            raise ValueError(f"[CRITICAL FRESHNESS REGRESSION] News record '{n.content.title}' published {n.content.published_date} is older than 24h!")
    for j in job_items:
        if j.content.date < cutoff_time:
            raise ValueError(f"[CRITICAL FRESHNESS REGRESSION] Job record '{j.content.role_title}' date {j.content.date} is older than 24h!")

    if output_news_file:
        out_dir = os.path.dirname(output_news_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_news_file, "w", encoding="utf-8") as f:
            for n in news_items:
                f.write(n.model_dump_json() + "\n")

    if output_jobs_file:
        out_dir = os.path.dirname(output_jobs_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(output_jobs_file, "w", encoding="utf-8") as f:
            for j in job_items:
                f.write(j.model_dump_json() + "\n")

    print(f"[freshness.py] Crawled {len(news_items)} fresh News records and {len(job_items)} fresh Job records within 24h window.")
    return news_items, job_items


