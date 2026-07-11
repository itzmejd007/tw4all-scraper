import aiohttp
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, parse_qs

BASE_URL = "https://toonworld4all.me/"

async def fetch_html(url):
    async with aiohttp.ClientSession() as session:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                return await response.text()
            return None

def extract_post_id(url):
    parsed = urlparse(url)
    path = parsed.path.strip('/')
    return path

def extract_languages_from_title(title):
    langs = []
    title_lower = title.lower()
    common_langs = ["hindi", "tamil", "telugu", "malayalam", "english", "japanese", "bengali", "marathi"]
    for lang in common_langs:
        if lang in title_lower:
            langs.append(lang.capitalize())
    if "multi audio" in title_lower or "dual audio" in title_lower:
        langs.append("Multi")
    return langs

async def scrape_homepage(limit=10):
    html = await fetch_html(BASE_URL)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    posts = []
    
    # Typically, posts are in article tags or div with class 'post'
    # We will look for h2 containing links
    for h2 in soup.find_all('h2'):
        a_tag = h2.find('a')
        if a_tag and a_tag.get('href'):
            url = a_tag.get('href')
            title = a_tag.get_text(strip=True)
            if "toonworld4all.me" in url and "/tag/" not in url and "/category/" not in url:
                post_id = extract_post_id(url)
                if post_id and len(posts) < limit:
                    posts.append({
                        "post_id": post_id,
                        "title": title,
                        "url": url,
                        "languages": extract_languages_from_title(title)
                    })
    return posts

async def scrape_search(keyword, limit=5):
    search_url = f"{BASE_URL}?s={keyword.replace(' ', '+')}"
    html = await fetch_html(search_url)
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    posts = []
    
    for h2 in soup.find_all('h2'):
        a_tag = h2.find('a')
        if a_tag and a_tag.get('href'):
            url = a_tag.get('href')
            title = a_tag.get_text(strip=True)
            if "toonworld4all.me" in url and "/tag/" not in url and "/category/" not in url:
                post_id = extract_post_id(url)
                if post_id and len(posts) < limit:
                    posts.append({
                        "post_id": post_id,
                        "title": title,
                        "url": url,
                        "languages": extract_languages_from_title(title)
                    })
    return posts

async def scrape_post_details(url, deep_scrape=False):
    html = await fetch_html(url)
    if not html:
        return None
    
    soup = BeautifulSoup(html, 'html.parser')
    
    title_tag = soup.find('h1') or soup.find('h2')
    title = title_tag.get_text(strip=True) if title_tag else "Unknown Title"
    
    episodes = []
    zips = []
    
    content = soup.find(class_='entry-content')
    if content:
        for a_tag in content.find_all('a'):
            href = a_tag.get('href', '')
            if 'archive.toonworld4all.me/episode' in href:
                ep_num = len(episodes) + 1
                episodes.append({
                    "title": f"Episode {ep_num:02d}",
                    "url": href
                })
            elif 'archive.toonworld4all.me/zip' in href:
                zip_num = len(zips) + 1
                zips.append({
                    "title": f"ZIP {zip_num:02d}",
                    "url": href
                })
                
    post_details = {
        "title": title,
        "languages": extract_languages_from_title(title),
        "episodes": episodes,
        "zips": zips
    }
    
    if deep_scrape:
        import asyncio
        async def fetch_qualities(item):
            q = await scrape_archive_page(item['url'])
            if q:
                item['qualities'] = q
            return item
            
        tasks = []
        for ep in post_details['episodes']:
            tasks.append(fetch_qualities(ep))
        for z in post_details['zips']:
            tasks.append(fetch_qualities(z))
            
        if tasks:
            await asyncio.gather(*tasks)
            
    return post_details

async def scrape_archive_page(url):
    html = await fetch_html(url)
    if not html:
        return {}
    
    soup = BeautifulSoup(html, 'html.parser')
    
    qualities = {}
    
    # 1. Try React JSON parser (window.__PROPS__)
    import re
    import json
    props_match = re.search(r'window\.__PROPS__\s*=\s*(\{.*?\});', html)
    if props_match:
        try:
            data = json.loads(props_match.group(1))
            encodes = data.get('data', {}).get('data', {}).get('encodes', [])
            for encode in encodes:
                q_name = encode.get('readable', {}).get('codec', encode.get('resolution', 'Unknown'))
                files = encode.get('files', [])
                if files:
                    if q_name not in qualities:
                        qualities[q_name] = []
                    for f in files:
                        qualities[q_name].append({
                            'source': f.get('host', 'Unknown'),
                            'url': f"https://archive.toonworld4all.me{f.get('link', '')}"
                        })
            if qualities:
                return qualities
        except Exception:
            pass
            
    # 2. Legacy parser fallback
    current_quality = "Available Links"
    for tag in soup.find_all(['h3', 'h4', 'a']):
        if tag.name == 'h3':
            current_quality = tag.get_text(strip=True)
            if current_quality not in qualities:
                qualities[current_quality] = []
        elif tag.name == 'a':
            href = tag.get('href', '')
            if href.startswith('/redirect/'):
                parent_text = tag.parent.get_text(strip=True).replace('DOWNLOAD', '').strip()
                source_name = parent_text if parent_text else "Direct Link"
                
                full_redirect_url = f"https://archive.toonworld4all.me{href}"
                if current_quality not in qualities:
                    qualities[current_quality] = []
                qualities[current_quality].append({
                    "source": source_name,
                    "url": full_redirect_url
                })
                
    # 3. React App HTML parser fallback (if __PROPS__ is missing)
    if len(qualities) <= 1 and (current_quality not in qualities or not qualities[current_quality]):
        react_sources = []
        for a_tag in soup.find_all('a'):
            href = a_tag.get('href', '')
            if href.startswith('/redirect/'):
                parent = a_tag.parent
                h4 = parent.find('h4')
                source_name = h4.get_text(strip=True) if h4 else 'Direct Link'
                react_sources.append({
                    'source': source_name,
                    'url': 'https://archive.toonworld4all.me' + href
                })
        if react_sources:
            qualities = {"Available Links": react_sources}
            
    return qualities

async def scrape_website_menu():
    html = await fetch_html(BASE_URL)
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    menus = []
    
    for nav in soup.find_all('nav', class_='main-navigation'):
        main_item = {"name": "Website Navigation", "url": BASE_URL, "sub": []}
        seen_urls = set()
        for a in nav.find_all('a'):
            href = a.get('href', '')
            name = a.get_text(strip=True)
            if href and href != '#' and name and href not in seen_urls:
                main_item["sub"].append({
                    "name": name,
                    "url": href
                })
                seen_urls.add(href)
        if main_item["sub"]:
            menus.append(main_item)
            
    return menus

async def scrape_az_list(url):
    html = await fetch_html(url)
    if not html:
        return []
        
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.find('div', class_='entry-content')
    posts = []
    
    if content:
        for a_tag in content.find_all('a'):
            href = a_tag.get('href', '')
            title = a_tag.get_text(strip=True)
            if "toonworld4all.me" in href and "/tag/" not in href and "/category/" not in href and href != url:
                post_id = extract_post_id(href)
                if post_id and len(title) > 2:
                    posts.append({
                        "post_id": post_id,
                        "title": title,
                        "url": href,
                        "languages": extract_languages_from_title(title)
                    })
    return posts
