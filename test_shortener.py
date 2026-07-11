import asyncio
from scraper import extract_shortener_link

import database
import scraper
import json

async def test():
    await database.init_db()
    posts = await database.get_all_posts(limit=10)
    print(f"Found {len(posts)} posts")
    
    for p in posts:
        if p.get('episodes'):
            ep = p['episodes'][0]
            if ep.get('qualities'):
                q_name = list(ep['qualities'].keys())[0]
                src = ep['qualities'][q_name][0]
                url = src['url']
                print(f"Testing URL: {url}")
                res = await scraper.extract_shortener_link(url)
                print(f"Result: {res}")
                return
            else:
                print(f"Post {p['title']} has episodes but NO qualities!")
        else:
            print(f"Post {p['title']} has NO episodes!")


if __name__ == "__main__":
    asyncio.run(test())
