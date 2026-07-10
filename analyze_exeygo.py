import asyncio
import aiohttp
from bs4 import BeautifulSoup

async def fetch(url):
    async with aiohttp.ClientSession() as session:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        print(f'GET {url}')
        async with session.get(url, headers=headers) as response:
            print(f'Status: {response.status}')
            html = await response.text()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Check for forms
            forms = soup.find_all('form')
            for i, f in enumerate(forms):
                print(f'Form {i}: action={f.get("action")}, id={f.get("id")}')
                for inp in f.find_all('input'):
                    print(f'  Input: name={inp.get("name")}, type={inp.get("type")}, value={inp.get("value")}')
            
            print(f'Page title: {soup.title.string if soup.title else "None"}')
            with open('exeygo.html', 'w', encoding='utf-8') as f:
                f.write(html)

if __name__ == '__main__':
    asyncio.run(fetch('https://exeygo.com/dYVDPop'))
