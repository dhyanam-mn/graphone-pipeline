import asyncio
import json
import os
import re
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from src.schemas.models import ResearchPaper, ResearchPaperContent, SourceInfo

# XML Namespaces for arXiv API
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Timeout configurations
CLIENT_TIMEOUT = aiohttp.ClientTimeout(total=10)
ARXIV_TIMEOUT = aiohttp.ClientTimeout(total=30)


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=False,
)
async def fetch_arxiv_papers(session: aiohttp.ClientSession, category: str, start: int, max_results: int) -> list[dict]:
    url = f"http://export.arxiv.org/api/query?search_query=cat:{category}&start={start}&max_results={max_results}&sortBy=submittedDate&sortOrder=descending"
    print(f"[papers.py] Requesting arXiv URL: {url}")
    try:
        async with session.get(url, timeout=ARXIV_TIMEOUT) as resp:
            print(f"[papers.py] arXiv response status: {resp.status}")
            if resp.status != 200:
                print(f"[papers.py] arXiv query failed with status {resp.status}")
                return []
            text = await resp.text()
            print(f"[papers.py] Received arXiv payload length: {len(text)} bytes")
    except Exception as e:
        print(f"[papers.py] arXiv request error ({e}). Retrying...")
        raise e

    entries = []
    try:
        root = ET.fromstring(text)
        for entry in root.findall(f"{ATOM_NS}entry"):
            id_elem = entry.find(f"{ATOM_NS}id")
            title_elem = entry.find(f"{ATOM_NS}title")
            published_elem = entry.find(f"{ATOM_NS}published")

            if id_elem is None or title_elem is None:
                continue

            raw_id = id_elem.text.strip() if id_elem.text else ""
            title = title_elem.text.strip().replace("\n", " ") if title_elem.text else ""
            title = " ".join(title.split())

            # Convert arXiv ID URL to standard abstract URL (http://arxiv.org/abs/...)
            paper_url = raw_id
            if "arxiv.org/abs/" not in paper_url:
                arxiv_id_match = re.search(r"arxiv.org/abs/(\d+\.\d+|[\w\-]+)", raw_id)
                if arxiv_id_match:
                    paper_url = f"https://arxiv.org/abs/{arxiv_id_match.group(1)}"

            # Extract authors
            authors = []
            for author_node in entry.findall(f"{ATOM_NS}author"):
                name_node = author_node.find(f"{ATOM_NS}name")
                if name_node is not None and name_node.text:
                    authors.append(name_node.text.strip())

            # Extract published datetime
            pub_date = None
            if published_elem is not None and published_elem.text:
                try:
                    pub_date = datetime.fromisoformat(published_elem.text.replace("Z", "+00:00"))
                except Exception:
                    pub_date = datetime.now(timezone.utc)

            entries.append({
                "title": title,
                "authors": authors,
                "paper_url": paper_url,
                "published_date": pub_date
            })
    except Exception as e:
        print(f"[papers.py] Error parsing arXiv XML: {e}")

    return entries


PWC_RATE_LIMITED = False

async def find_github_repo_direct(session: aiohttp.ClientSession, paper_url: str) -> tuple[str | None, str | None]:
    """Primary method: Extract GitHub repo URL directly from arXiv abstract page HTML."""
    try:
        async with session.get(paper_url, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status == 200:
                html = await resp.text()
                match = re.search(r"https?://github\.com/([\w\-\.]+)/([\w\-\.]+)", html)
                if match:
                    repo_path = f"{match.group(1)}/{match.group(2)}".rstrip(".,)")
                    clean_gh_url = f"https://github.com/{repo_path}"
                    print(f"[papers.py] Direct arXiv HTML found GitHub repo: {clean_gh_url}")
                    return clean_gh_url, repo_path
    except Exception as e:
        print(f"[papers.py] Error checking arXiv abstract for GitHub URL: {e}")
    return None, None


async def find_github_repo_pwc(session: aiohttp.ClientSession, title: str) -> tuple[str | None, str | None]:
    """Secondary method: Query Papers with Code API with throttling."""
    global PWC_RATE_LIMITED
    if PWC_RATE_LIMITED:
        return None, None

    encoded_title = urllib.parse.quote(title)
    url = f"https://paperswithcode.com/api/v1/papers/?title={encoded_title}"
    try:
        async with session.get(url, timeout=CLIENT_TIMEOUT) as resp:
            if resp.status in (429, 403):
                PWC_RATE_LIMITED = True
                print(f"[papers.py] Papers with Code rate limited ({resp.status}). Short-circuiting PWC lookups.")
                return None, None
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
                                            clean_gh_url = f"https://github.com/{repo_path}"
                                            print(f"[papers.py] PWC found GitHub repo: {clean_gh_url}")
                                            return clean_gh_url, repo_path
    except Exception as e:
        print(f"[papers.py] Papers with Code lookup error: {e}")
    return None, None


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=False,
)
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


async def process_paper_entry(session: aiohttp.ClientSession, entry: dict, sem: asyncio.Semaphore) -> ResearchPaper:
    async with sem:
        paper_url = entry["paper_url"]
        
        # 1. Primary: Direct arXiv HTML lookup
        github_url, repo_path = await find_github_repo_direct(session, paper_url)
        
        # 2. Secondary: Papers with Code lookup (throttled)
        if not github_url:
            github_url, repo_path = await find_github_repo_pwc(session, entry["title"])
            await asyncio.sleep(0.1)

        github_stars = None
        if repo_path:
            try:
                github_stars = await fetch_github_stars(session, repo_path)
            except Exception:
                github_stars = None

        source = SourceInfo(name="arXiv", url=paper_url)
        content = ResearchPaperContent(
            title=entry["title"],
            authors=entry["authors"],
            paper_url=paper_url,
            github_url=github_url,
            github_stars=github_stars,
            published_date=entry["published_date"],
        )
        return ResearchPaper(source=source, content=content)



async def scrape_papers(target_count: int = 1000, output_file: str = "data/papers.jsonl") -> list[ResearchPaper]:
    if output_file:
        out_dir = os.path.dirname(output_file)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
    categories = ["cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.NE", "cs.RO", "stat.ML"]
    collected: list[ResearchPaper] = []
    seen_urls: set[str] = set()

    sem = asyncio.Semaphore(10)

    async with aiohttp.ClientSession() as session:
        for cat in categories:
            if len(collected) >= target_count:
                break
            start = 0
            batch_size = 100
            while len(collected) < target_count and start < 2000:
                needed = target_count - len(collected)
                print(f"[papers.py] Fetching arXiv batch for category {cat}, start {start}, count {min(batch_size, needed)}...")
                try:
                    raw_entries = await fetch_arxiv_papers(session, cat, start, min(batch_size, needed))
                except Exception as ex:
                    print(f"[papers.py] Exception fetching arXiv batch: {ex}")
                    raw_entries = []

                if not raw_entries:
                    print(f"[papers.py] No entries returned for category {cat} at start {start}. Retrying after delay...")
                    await asyncio.sleep(3)
                    start += batch_size
                    continue

                # Filter unique entries
                unique_entries = []
                for entry in raw_entries:
                    paper_url = entry["paper_url"]
                    if paper_url not in seen_urls:
                        seen_urls.add(paper_url)
                        unique_entries.append(entry)

                if unique_entries:
                    # Process entries concurrently in chunks
                    tasks = [process_paper_entry(session, entry, sem) for entry in unique_entries]
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    for res in results:
                        if isinstance(res, ResearchPaper):
                            collected.append(res)
                            if output_file and (len(collected) % 100 == 0 or len(collected) == target_count):
                                print(f"[papers.py] Progress log: Scraped {len(collected)} / {target_count} papers.")
                                with open(output_file, "w", encoding="utf-8") as f:
                                    for p in collected:
                                        f.write(p.model_dump_json() + "\n")

                start += batch_size
                await asyncio.sleep(3)

    # Save final results
    if collected and output_file:
        with open(output_file, "w", encoding="utf-8") as f:
            for p in collected:
                f.write(p.model_dump_json() + "\n")

    stars_count = sum(1 for p in collected if p.content.github_stars is not None)
    print(f"[papers.py] Completed scrape. Total: {len(collected)}, With GitHub Stars: {stars_count}")
    return collected
