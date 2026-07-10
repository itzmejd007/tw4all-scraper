from bs4 import BeautifulSoup

with open('home.html', 'r', encoding='utf-8') as f:
    html = f.read()
    
soup = BeautifulSoup(html, 'html.parser')
for nav in soup.find_all('nav'):
    print(f"Nav ID: {nav.get('id')}, Class: {nav.get('class')}")
    for ul in nav.find_all('ul'):
        print(f"  UL ID: {ul.get('id')}, Class: {ul.get('class')}")
        if 'menu' in (ul.get('class') or []):
            for li in ul.find_all('li', recursive=False):
                a = li.find('a', recursive=False)
                if a:
                    print(f"    Menu: {a.get_text(strip=True)} -> {a.get('href')}")
                    sub_ul = li.find('ul', recursive=False)
                    if sub_ul:
                        for sub_li in sub_ul.find_all('li', recursive=False):
                            sub_a = sub_li.find('a', recursive=False)
                            if sub_a:
                                print(f"      - Sub: {sub_a.get_text(strip=True)} -> {sub_a.get('href')}")
