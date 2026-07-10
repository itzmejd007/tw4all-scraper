import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json

async def fetch_home():
    url = 'https://toonworld4all.me/'
    async with aiohttp.ClientSession() as session:
        headers = {'User-Agent': 'Mozilla/5.0'}
        async with session.get(url, headers=headers) as resp:
            html = await resp.text()
            match = re.search(r'window\.__PROPS__\s*=\s*(\{.*?\});', html)
            if match:
                data = json.loads(match.group(1))
                menus = data.get('data', {}).get('menus', [])
                if not menus:
                    # sometimes it's at the root or under another key
                    menus = data.get('menus', [])
                
                print(f'Found {len(menus)} menus')
                for m in menus:
                    print(f"Menu: {m.get('name')} -> {m.get('url')}")
                    for sub in m.get('sub', []):
                        print(f"  - Sub: {sub.get('name')} -> {sub.get('url')}")
            else:
                print('No PROPS found on home page')

if __name__ == "__main__":
    asyncio.run(fetch_home())
