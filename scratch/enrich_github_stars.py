import sys
sys.path.insert(0, ".")
import json
import os
import re
import asyncio
import aiohttp
import urllib.parse
from src.schemas.models import ResearchPaper

CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)

async def fetch_github_stars(session: aiohttp.ClientSession, repo_path: str) -> int | None:
    # Method 1: Try GitHub REST API
    url = f"https://api.github.com/repos/{repo_path}"
    headers = {"User-Agent": "GraphOne-Pipeline/1.0"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with session.get(url, headers=headers, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200:
                data = await resp.json()
                stars = data.get("stargazers_count")
                if stars is not None:
                    return int(stars)
    except Exception:
        pass

    # Method 2: Fallback to direct GitHub HTML page scrape (bypasses REST API 403 rate limits)
    try:
        gh_page_url = f"https://github.com/{repo_path}"
        html_headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with session.get(gh_page_url, headers=html_headers, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200:
                html = await resp.text()
                match = re.search(r'stargazers_count":\s*(\d+)', html) or re.search(r'id="repo-stars-counter-star"[^>]*title="([\d,]+)"', html) or re.search(r'id="repo-stars-counter-star"[^>]*>([\d\.\,kKmM]+)<', html)
                if match:
                    raw_stars = match.group(1).replace(",", "")
                    if raw_stars.endswith("k") or raw_stars.endswith("K"):
                        return int(float(raw_stars[:-1]) * 1000)
                    return int(raw_stars)
    except Exception:
        pass
    return None

async def find_github_repo_direct(session: aiohttp.ClientSession, paper_url: str) -> tuple[str | None, str | None]:
    try:
        async with session.get(paper_url, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200:
                html = await resp.text()
                match = re.search(r"https?://github\.com/([\w\-\.]+)/([\w\-\.]+)", html)
                if match:
                    repo_path = f"{match.group(1)}/{match.group(2)}".rstrip(".,)")
                    return f"https://github.com/{repo_path}", repo_path
    except Exception:
        pass
    return None, None

async def find_github_repo_pwc(session: aiohttp.ClientSession, title: str) -> tuple[str | None, str | None]:
    encoded_title = urllib.parse.quote(title)
    url = f"https://paperswithcode.com/api/v1/papers/?title={encoded_title}"
    try:
        async with session.get(url, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200 and "application/json" in resp.headers.get("Content-Type", ""):
                data = await resp.json(content_type=None)
                results = data.get("results", [])
                if results:
                    paper_id = results[0].get("id")
                    if paper_id:
                        repo_url = f"https://paperswithcode.com/api/v1/papers/{paper_id}/repositories/"
                        async with session.get(repo_url, timeout=CLIENT_TIMEOUT) as repo_resp:
                            if repo_resp.status == 200 and "application/json" in repo_resp.headers.get("Content-Type", ""):
                                repo_data = await repo_resp.json(content_type=None)
                                repo_results = repo_data.get("results", [])
                                for r in repo_results:
                                    url_str = r.get("url", "")
                                    if "github.com" in url_str:
                                        match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", url_str)
                                        if match:
                                            repo_path = f"{match.group(1)}/{match.group(2)}"
                                            return f"https://github.com/{repo_path}", repo_path
    except Exception:
        pass
    return None, None

async def enrich_papers():
    with open("data/papers.jsonl", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"Enriching {len(records)} papers with GitHub stars...")
    sem = asyncio.Semaphore(20)
    updated_records = []
    star_count = 0

    async with aiohttp.ClientSession() as session:
        async def process_one(r):
            nonlocal star_count
            async with sem:
                paper_url = r["content"]["paper_url"]
                title = r["content"]["title"]
                gh_url = r["content"].get("github_url")
                stars = r["content"].get("github_stars")

                if stars is None:
                    # Method 1: Direct arXiv page scrape
                    if not gh_url:
                        gh_url, repo_path = await find_github_repo_direct(session, paper_url)
                    else:
                        match = re.search(r"github\.com/([\w\-\.]+)/([\w\-\.]+)", gh_url)
                        repo_path = f"{match.group(1)}/{match.group(2)}" if match else None

                    # Method 2: Papers with Code fallback (throttled)
                    if not gh_url:
                        gh_url, repo_path = await find_github_repo_pwc(session, title)
                        await asyncio.sleep(0.05)

                    # Fetch stars if repo path found
                    if repo_path:
                        stars = await fetch_github_stars(session, repo_path)
                        r["content"]["github_url"] = gh_url
                        r["content"]["github_stars"] = stars

                if r["content"].get("github_stars") is not None:
                    star_count += 1
                return r

        tasks = [process_one(r) for r in records]
        updated_records = await asyncio.gather(*tasks)

    # Persist updated papers
    with open("data/papers.jsonl", "w", encoding="utf-8") as f:
        for r in updated_records:
            f.write(json.dumps(r) + "\n")

    print(f"Enrichment completed! Papers with non-null github_stars: {star_count} / {len(updated_records)}")

if __name__ == "__main__":
    asyncio.run(enrich_papers())
