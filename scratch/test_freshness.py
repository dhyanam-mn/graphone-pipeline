import asyncio
import aiohttp
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
import warnings
import dateparser

warnings.filterwarnings("ignore")

async def parse_rss_feed(session: aiohttp.ClientSession, feed_url: str, source_name: str) -> list[dict]:
    items = []
    print(f"[freshness.py] Crawling feed: {feed_url}")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(feed_url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status == 200:
                text = await resp.text()
                soup = BeautifulSoup(text, "html.parser")
                nodes = soup.find_all("item")
                print(f"URL: {feed_url} -> Found nodes: {len(nodes)}")
                for node in nodes:
                    title_elem = node.find("title")
                    link_elem = node.find("link")
                    pub_elem = node.find("pubdate") or node.find("dc:date")

                    title = title_elem.text.strip() if title_elem and title_elem.text else ""
                    # Note: in HTML parser, <link> tag inside <item> is self-closing or next sibling text
                    link = link_elem.text.strip() if link_elem and link_elem.text else ""
                    if not link and link_elem and link_elem.next_sibling:
                        link = str(link_elem.next_sibling).strip()
                    
                    pub_str = pub_elem.text.strip() if pub_elem and pub_elem.text else ""
                    print("Sample parsed:", title, "| Link:", link, "| Pub:", pub_str)
                    break
    except Exception as e:
        print("Error:", e)
    return items

async def main():
    async with aiohttp.ClientSession() as session:
        await parse_rss_feed(session, "https://news.ycombinator.com/rss", "HN")

asyncio.run(main())
