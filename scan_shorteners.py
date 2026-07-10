import asyncio
import aiohttp
import re
import json
import database
import scraper
from urllib.parse import urlparse

async def extract_shortener(url, session):
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                html = await response.text()
                match = re.search(r'window\.__PROPS__\s*=\s*(\{.*?\});', html)
                if match:
                    data = json.loads(match.group(1))
                    return data.get('destination')
    except Exception as e:
        pass
    return None

async def test():
    await database.init_db()
    posts = await database.get_all_posts(limit=10)
    
    shorteners = set()
    
    async with aiohttp.ClientSession(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}) as session:
        for post in posts:
            if post.get('episodes'):
                print(f"Checking post: {post['title']}")
                ep = post['episodes'][0]
                q_dict = await scraper.scrape_archive_page(ep['url'])
                
                for q, sources in q_dict.items():
                    for src in sources[:2]:
                        redirect_url = src['url']
                        dest = await extract_shortener(redirect_url, session)
                        if dest:
                            domain = urlparse(dest).netloc
                            shorteners.add(domain)
                            print(f"  - {src['source']}: {domain} ({dest})")
                
    print('\nAll unique shortener domains found:')
    for s in shorteners:
        print(s)

if __name__ == "__main__":
    asyncio.run(test())
