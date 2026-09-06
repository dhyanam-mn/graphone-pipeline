import json
import re
import aiohttp
import asyncio

async def run_extract_gh():
    with open("data/papers.jsonl", encoding="utf-8") as f:
        papers = [json.loads(line) for line in f if line.strip()][:50]

    found = 0
    async with aiohttp.ClientSession() as session:
        for p in papers:
            url = p["source"]["url"]
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        match = re.search(r"https?://github\.com/([\w\-\.]+)/([\w\-\.]+)", html)
                        if match:
                            repo_path = f"{match.group(1)}/{match.group(2)}".rstrip(".,)")
                            gh_url = f"https://github.com/{repo_path}"
                            found += 1
                            print(f"Found GitHub repo in abstract: {p['content']['title'][:40]}... -> {gh_url}")
            except Exception as e:
                pass
    print(f"Found {found} / 50 GitHub repos directly in arXiv HTML!")

if __name__ == "__main__":
    asyncio.run(run_extract_gh())
