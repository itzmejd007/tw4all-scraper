from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
import database
import scraper
import asyncio
import config

OWNER_ID = config.OWNER_ID
USER_STATES = {}

def create_post_buttons(posts):
    buttons = []
    for post in posts:
        buttons.append([InlineKeyboardButton(post['title'], callback_data=f"post_{str(post['_id'])}")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    return InlineKeyboardMarkup(buttons)

async def start_command(client, message):
    await database.add_or_update_user(message.from_user.id, {
        "user_id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username
    })
    await message.reply_text(
        "Welcome to ToonWorld4All Bot!\n\n"
        "Send me any keyword (e.g. 'naruto') to search for anime/cartoons.\n"
        "Use /list to see all available posts in the database.\n"
        "Use /set_lang <language> to get notifications for specific languages (e.g., /set_lang Tamil)."
    )

async def set_lang_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_lang <language>\nExample: /set_lang Tamil")
        return
    
    lang = message.command[1].capitalize()
    await database.add_or_update_user(message.from_user.id, {"language_preference": lang})
    await message.reply_text(f"Language preference set to: {lang}. You will be notified when new posts with this language are added.")

async def send_post_list(client, chat_id, page=1, lang="all", edit_msg=None):
    limit = 10
    skip = (page - 1) * limit
    
    if lang == "all":
        posts = await database.get_all_posts(skip=skip, limit=limit)
        total = await database.count_all_posts()
    else:
        posts = await database.get_posts_by_language(lang, skip=skip, limit=limit)
        total = await database.count_posts_by_language(lang)
        
    if not posts and page == 1:
        text = f"No posts found." if lang == "all" else f"No posts found for language: {lang}."
        if edit_msg:
            await edit_msg.edit_text(text)
        else:
            await client.send_message(chat_id, text)
        return
        
    text = f"📚 **Database Posts**\nTotal: {total}\n"
    if lang != "all":
        text += f"Filter: {lang}\n"
    text += f"Page {page} of {max(1, (total + limit - 1) // limit)}"
    
    buttons = []
    for post in posts:
        buttons.append([InlineKeyboardButton(post['title'], callback_data=f"post_{str(post['_id'])}")])
    
    # Pagination row
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"listpg_{page-1}_{lang}"))
    if skip + limit < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"listpg_{page+1}_{lang}"))
    if nav_row:
        buttons.append(nav_row)
        
    # Filter row
    buttons.append([InlineKeyboardButton("🔍 Filter by Language", callback_data=f"filter_{page}_{lang}")])
    if lang != "all":
        buttons.append([InlineKeyboardButton("❌ Clear Filter", callback_data=f"listpg_1_all")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
        
    markup = InlineKeyboardMarkup(buttons)
    
    if edit_msg:
        await edit_msg.edit_text(text, reply_markup=markup)
    else:
        await client.send_message(chat_id, text, reply_markup=markup)

async def list_command(client, message):
    await send_post_list(client, message.chat.id, page=1, lang="all")

async def search_handler(client, message):
    keyword = message.text.strip()
    if keyword.startswith('/'):
        return
        
    state = USER_STATES.get(message.from_user.id)
    if state and state['type'] == 'filter':
        lang = keyword.capitalize()
        try:
            await client.delete_messages(message.chat.id, [message.id, state['prompt_msg_id']])
        except:
            pass
        del USER_STATES[message.from_user.id]
        await send_post_list(client, message.chat.id, page=1, lang=lang)
        return
    
    msg = await message.reply_text("Searching database...")
    posts = await database.search_posts(keyword)
    
    if posts:
        await msg.edit_text(f"Search results for '{keyword}':", reply_markup=create_post_buttons(posts))
        return
        
    await msg.edit_text(f"'{keyword}' not found in DB.\nSearching toonworld4all.me [■■■□□□□□□]...")
    scraped_posts = await scraper.scrape_search(keyword, limit=10)
    
    if not scraped_posts:
        await msg.edit_text("No posts found on website either.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]]))
        return
        
    for p in scraped_posts:
        await database.add_or_update_post(p)
        
    posts_after_scrape = await database.search_posts(keyword)
    if not posts_after_scrape:
        await asyncio.sleep(1)
        posts_after_scrape = await database.search_posts(keyword)
        
    if posts_after_scrape:
        await msg.edit_text(f"Successfully scraped! Results for '{keyword}':", reply_markup=create_post_buttons(posts_after_scrape))
    else:
        await msg.edit_text("Scraped successfully, but error retrieving from database.")

async def callback_listpg(client, callback_query):
    parts = callback_query.data.split("_")
    page = int(parts[1])
    lang = parts[2]
    await send_post_list(client, callback_query.message.chat.id, page=page, lang=lang, edit_msg=callback_query.message)

async def callback_filter(client, callback_query):
    prompt = await callback_query.message.reply_text("Please type the language you want to filter by (e.g., Hindi, Tamil, English):")
    USER_STATES[callback_query.from_user.id] = {
        'type': 'filter',
        'prompt_msg_id': prompt.id
    }
    await callback_query.answer()

async def callback_close(client, callback_query):
    await callback_query.message.delete()

async def callback_post(client, callback_query):
    post_id = callback_query.data.split("post_")[1]
    post = await database.get_post_by_mongo_id(post_id)
    
    if not post:
        await callback_query.answer("Post not found in database.", show_alert=True)
        return
    
    if 'episodes' not in post or (len(post.get('episodes', [])) == 0 and len(post.get('zips', [])) == 0):
        await callback_query.answer("Scraping details...", show_alert=False)
        details = await scraper.scrape_post_details(post['url'])
        if details:
            post.update(details)
            await database.add_or_update_post(post)
    else:
        # Auto-update legacy titles in database silently
        needs_update = False
        for i, ep in enumerate(post.get('episodes', [])):
            if ep.get('title', '').strip() in ["Watch/Download", "Download", "Watch & Download", ""]:
                ep['title'] = f"Episode {i+1:02d}"
                needs_update = True
        for i, z in enumerate(post.get('zips', [])):
            if z.get('title', '').strip() in ["Watch/Download", "Download", "Watch & Download", ""]:
                z['title'] = f"ZIP {i+1:02d}"
                needs_update = True
        if needs_update:
            await database.add_or_update_post(post)
    
    text = f"**{post['title']}**\n\n"
    if post.get('languages'):
        text += f"🗣 **Languages:** {', '.join(post['languages'])}\n"
    
    ep_count = len(post.get('episodes', []))
    zip_count = len(post.get('zips', []))
    text += f"📺 **Episodes:** {ep_count}\n"
    text += f"📦 **ZIP Files:** {zip_count}\n\nSelect an option below:"
    
    buttons = []
    if ep_count > 0:
        buttons.append([InlineKeyboardButton("Episodes", callback_data=f"list_ep_{post_id}_0")])
    if zip_count > 0:
        buttons.append([InlineKeyboardButton("ZIP Files", callback_data=f"list_zip_{post_id}_0")])
    
    buttons.append([InlineKeyboardButton("« Back to List", callback_data=f"listpg_1_all"), InlineKeyboardButton("❌ Close", callback_data="close")])
    
    if not buttons:
        text += "\n\nNo download links found."
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def callback_list(client, callback_query):
    # list_{ptype}_{post_id}_{page}
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    page = int(parts[3]) if len(parts) > 3 else 0
    
    post = await database.get_post_by_mongo_id(post_id)
    if not post:
        await callback_query.answer("Post not found.", show_alert=True)
        return
    
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    limit = 20
    start = page * limit
    end = start + limit
    
    page_items = items[start:end]
    
    buttons = []
    row = []
    for i, item in enumerate(page_items):
        idx = start + i
        row.append(InlineKeyboardButton(item['title'], callback_data=f"sel_{ptype}_{post_id}_{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
        
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"list_{ptype}_{post_id}_{page-1}"))
    if end < len(items):
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"list_{ptype}_{post_id}_{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"post_{post_id}"), InlineKeyboardButton("❌ Close", callback_data="close")])
    
    await callback_query.message.edit_text(f"**{post['title']}**\nSelect an item:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_select(client, callback_query):
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    
    post = await database.get_post_by_mongo_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    if index >= len(items):
        await callback_query.answer("Item not found.", show_alert=True)
        return
    
    item = items[index]
    archive_url = item['url']
    
    await callback_query.answer("Fetching qualities...", show_alert=False)
    qualities = await scraper.scrape_archive_page(archive_url)
    
    # Calculate what page we were on to go back correctly
    page = index // 20
    
    if not qualities:
        await callback_query.message.edit_text("No qualities found for this link.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data=f"list_{ptype}_{post_id}_{page}")]]))
        return
    
    buttons = []
    for q_name in qualities.keys():
        short_q = q_name[:30]
        buttons.append([InlineKeyboardButton(short_q, callback_data=f"qual_{ptype}_{post_id}_{index}_{list(qualities.keys()).index(q_name)}")])
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"list_{ptype}_{post_id}_{page}"), InlineKeyboardButton("❌ Close", callback_data="close")])
    await callback_query.message.edit_text(f"**{post['title']}**\n{item['title']}\nSelect Quality:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_quality(client, callback_query):
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    q_index = int(parts[4])
    
    post = await database.get_post_by_mongo_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    item = items[index]
    archive_url = item['url']
    
    await callback_query.answer("Loading sources...", show_alert=False)
    
    qualities = await scraper.scrape_archive_page(archive_url)
    q_keys = list(qualities.keys())
    if q_index >= len(q_keys):
        await callback_query.answer("Error loading quality.", show_alert=True)
        return
    
    q_name = q_keys[q_index]
    sources = qualities[q_name]
    
    buttons = []
    for s_index, src in enumerate(sources):
        src_name = src['source'][:30]
        buttons.append([InlineKeyboardButton(src_name, callback_data=f"src_{ptype}_{post_id}_{index}_{q_index}_{s_index}")])
    
    if len(sources) > 1:
        buttons.append([InlineKeyboardButton("📜 Get All Source Links", callback_data=f"allsrc_{ptype}_{post_id}_{index}_{q_index}")])
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"sel_{ptype}_{post_id}_{index}"), InlineKeyboardButton("❌ Close", callback_data="close")])
    
    await callback_query.message.edit_text(f"**{post['title']}**\n{item['title']}\nSelected: {q_name}\n\nSelect Source:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_source(client, callback_query):
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    q_index = int(parts[4])
    s_index = int(parts[5])
    
    post = await database.get_post_by_mongo_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    item = items[index]
    archive_url = item['url']
    
    qualities = await scraper.scrape_archive_page(archive_url)
    q_name = list(qualities.keys())[q_index]
    src = qualities[q_name][s_index]
    
    redirect_url = src['url']
    shortener_link = "Could not extract final link."
    
    # Try to extract final shortener link
    try:
        import aiohttp
        import re
        import json
        async with aiohttp.ClientSession() as session:
            async with session.get(redirect_url, timeout=5) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    match = re.search(r'window\.__PROPS__\s*=\s*(\{.*?\});', html)
                    if match:
                        data = json.loads(match.group(1))
                        dest = data.get('destination')
                        if dest:
                            shortener_link = dest
    except Exception as e:
        pass
    
    text = f"**{post['title']}**\n{item['title']}\nSelected: {q_name}\n\n"
    text += f"**{src['source']}**:\n"
    text += f"Redirect Link:\n`{redirect_url}`\n\n"
    text += f"Shortener Link:\n`{shortener_link}`\n\n"
    text += "(Long press the link above to copy it)"
    
    await callback_query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back to Sources", callback_data=f"qual_{ptype}_{post_id}_{index}_{q_index}")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]))

async def callback_allsrc(client, callback_query):
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    q_index = int(parts[4])
    
    post = await database.get_post_by_mongo_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    item = items[index]
    archive_url = item['url']
    
    qualities = await scraper.scrape_archive_page(archive_url)
    q_name = list(qualities.keys())[q_index]
    sources = qualities[q_name]
    
    text = f"**{post['title']}**\n{item['title']} - {q_name}\n\n"
    for src in sources:
        text += f"**{src['source']}**: `{src['url']}`\n\n"
        
    await callback_query.message.edit_text(text, disable_web_page_preview=True, reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("« Back", callback_data=f"qual_{ptype}_{post_id}_{index}_{q_index}")],
        [InlineKeyboardButton("❌ Close", callback_data="close")]
    ]))

async def scrape_initial_command(client, message):
    if not await database.is_admin(message.from_user.id):
        await message.reply_text("Only owner/admin can use this command.")
        return
        
    msg = await message.reply_text("Scraping starting... This may take a while.")
    posts = await scraper.scrape_search("a") 
    for post in posts:
        await database.add_or_update_post(post)
        
    await msg.edit_text(f"Successfully scraped and stored {len(posts)} posts!")

async def update_db_command(client, message):
    if not await database.is_admin(message.from_user.id):
        return
        
    msg = await message.reply_text("Auto-updating all legacy post names in DB...")
    posts = await database.get_all_posts(skip=0, limit=1000)
    updated = 0
    for post in posts:
        needs_update = False
        for i, ep in enumerate(post.get('episodes', [])):
            if ep.get('title', '').strip() in ["Watch/Download", "Download", "Watch & Download", ""]:
                ep['title'] = f"Episode {i+1:02d}"
                needs_update = True
        for i, z in enumerate(post.get('zips', [])):
            if z.get('title', '').strip() in ["Watch/Download", "Download", "Watch & Download", ""]:
                z['title'] = f"ZIP {i+1:02d}"
                needs_update = True
        if needs_update:
            await database.add_or_update_post(post)
            updated += 1
            
    await msg.edit_text(f"Done! Updated {updated} posts to the new naming format.")

async def add_admin_command(client, message):
    if message.from_user.id != config.OWNER_ID:
        await message.reply_text("Only the Bot Owner can add admins.")
        return
    
    if len(message.command) < 2:
        await message.reply_text("Usage: /add_admin <user_id>")
        return
        
    try:
        new_admin_id = int(message.command[1])
        await database.add_admin(new_admin_id)
        await message.reply_text(f"User `{new_admin_id}` has been added as an admin and given full control!")
        
        try:
            await client.send_message(new_admin_id, "You have been promoted to Admin by the Owner! You now have full bot control.")
        except:
            pass
    except ValueError:
        await message.reply_text("Invalid user ID.")

async def refresh_db_task(client, msg):
    try:
        posts = await database.get_all_posts(skip=0, limit=0)
        updated = 0
        total = len(posts)
        
        for p in posts:
            details = await scraper.scrape_post_details(p['url'])
            if details:
                old_eps = len(p.get('episodes', []))
                new_eps = len(details.get('episodes', []))
                old_zips = len(p.get('zips', []))
                new_zips = len(details.get('zips', []))
                
                if new_eps > old_eps or new_zips > old_zips:
                    p.update(details)
                    await database.add_or_update_post(p)
                    updated += 1
        
        await msg.edit_text(f"🔄 **Full DB Refresh Complete!**\nChecked {total} posts.\nSuccessfully updated {updated} posts with new episodes/ZIPs.")
    except Exception as e:
        await msg.edit_text(f"Error during refresh: {e}")

async def refresh_command(client, message):
    if not await database.is_admin(message.from_user.id):
        return
        
    msg = await message.reply_text("🔄 Starting full database background refresh. This will run silently and notify you when complete.")
    asyncio.create_task(refresh_db_task(client, msg))

WEBSITE_MENU = []

async def menu_command(client, message):
    if not await database.is_admin(message.from_user.id):
        await message.reply_text("Only admins can access the scraper menu.")
        return
        
    global WEBSITE_MENU
    msg = await message.reply_text("Fetching website menu...")
    WEBSITE_MENU = await scraper.scrape_website_menu()
    
    if not WEBSITE_MENU:
        await msg.edit_text("Failed to fetch menu from website.")
        return
        
    buttons = []
    for i, m in enumerate(WEBSITE_MENU):
        buttons.append([InlineKeyboardButton(m['name'], callback_data=f"menu_{i}")])
        
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    await msg.edit_text("🗂 **Website Categories**\nSelect a category to browse or sync:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_menu(client, callback_query):
    parts = callback_query.data.split("_")
    menu_idx = int(parts[1])
    
    global WEBSITE_MENU
    if not WEBSITE_MENU:
        WEBSITE_MENU = await scraper.scrape_website_menu()
        
    if menu_idx >= len(WEBSITE_MENU):
        return await callback_query.answer("Menu expired. Send /menu again.", show_alert=True)
        
    menu = WEBSITE_MENU[menu_idx]
    
    buttons = []
    for i, sub in enumerate(menu.get('sub', [])):
        buttons.append([InlineKeyboardButton(sub['name'], callback_data=f"subm_{menu_idx}_{i}")])
        
    buttons.append([InlineKeyboardButton("« Back to Main", callback_data="menumain")])
    await callback_query.message.edit_text(f"🗂 **{menu['name']}**\nSelect a sub-category:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_menumain(client, callback_query):
    global WEBSITE_MENU
    buttons = []
    for i, m in enumerate(WEBSITE_MENU):
        buttons.append([InlineKeyboardButton(m['name'], callback_data=f"menu_{i}")])
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close")])
    await callback_query.message.edit_text("🗂 **Website Categories**\nSelect a category to browse or sync:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_submenu(client, callback_query):
    parts = callback_query.data.split("_")
    menu_idx = int(parts[1])
    sub_idx = int(parts[2])
    
    global WEBSITE_MENU
    menu = WEBSITE_MENU[menu_idx]
    sub = menu['sub'][sub_idx]
    
    url = sub['url']
    await callback_query.message.edit_text(f"Fetching posts from {sub['name']}...")
    
    # If it's a List page, trigger A-Z Sync
    if 'list_' in url or '-list' in url:
        posts = await scraper.scrape_az_list(url)
        if not posts:
            await callback_query.message.edit_text("No posts found or failed to parse A-Z list.")
            return
            
        total = len(posts)
        db_count = 0
        new_posts = []
        for p in posts:
            exists = await database.get_post_by_id(p['post_id'])
            if exists:
                db_count += 1
            else:
                new_posts.append(p)
                
        text = f"🗃 **{sub['name']} (A-Z Sync)**\n\n"
        text += f"Total Posts in List: {total}\n"
        text += f"Posts already in DB: {db_count}\n"
        text += f"New Posts to Scrape: {len(new_posts)}\n\n"
        
        # Save new posts to memory for sync callback
        global AZ_SYNC_QUEUE
        AZ_SYNC_QUEUE = new_posts
        
        buttons = []
        if len(new_posts) > 0:
            buttons.append([InlineKeyboardButton(f"🔄 Scrape New Posts ({len(new_posts)})", callback_data="azsync_new")])
        buttons.append([InlineKeyboardButton("« Back", callback_data=f"menu_{menu_idx}")])
        
        await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))
    else:
        # Just a normal category browsing (future enhancement to list them page by page)
        await callback_query.message.edit_text(f"🗃 **{sub['name']}**\nBrowsing standard categories inside the bot is coming soon. Please use search for now.\n\nLink: {url}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data=f"menu_{menu_idx}")]]))

AZ_SYNC_QUEUE = []

async def azsync_task(client, msg):
    global AZ_SYNC_QUEUE
    queue = AZ_SYNC_QUEUE.copy()
    AZ_SYNC_QUEUE = []
    
    total = len(queue)
    success = 0
    failed = []
    
    for i, p in enumerate(queue):
        if i % 5 == 0:
            try:
                bar = "█" * int((i/total)*10) + "░" * (10 - int((i/total)*10))
                await msg.edit_text(f"🔄 **Syncing Posts...**\n\nProgress: [{bar}] {i}/{total}\nScraping: {p['title']}")
            except:
                pass
                
        details = await scraper.scrape_post_details(p['url'])
        if details:
            p.update(details)
            await database.add_or_update_post(p)
            success += 1
        else:
            failed.append(p['url'])
            
    text = f"✅ **Sync Complete!**\n\nSuccessfully added: {success}/{total} posts."
    if failed:
        text += f"\n\nFailed to scrape {len(failed)} posts. Check logs."
        print("Failed posts:", failed)
        
    await msg.edit_text(text)

async def callback_azsync(client, callback_query):
    await callback_query.answer("Starting background sync...", show_alert=False)
    msg = await callback_query.message.edit_text("🔄 Preparing to scrape...")
    asyncio.create_task(azsync_task(client, msg))

async def massive_scrape_task(client, msg):
    try:
        await msg.edit_text("🔄 **Massive Scrape Started**\n\nFetching website menus to find all A-Z lists...")
        menus = await scraper.scrape_website_menu()
        
        list_urls = []
        for m in menus:
            for sub in m.get('sub', []):
                if 'list_' in sub['url'] or '-list' in sub['url']:
                    list_urls.append(sub['url'])
                    
        await msg.edit_text(f"🔄 **Massive Scrape**\n\nFound {len(list_urls)} A-Z Lists. Fetching all posts from them...")
        
        all_posts = []
        for url in list_urls:
            posts = await scraper.scrape_az_list(url)
            all_posts.extend(posts)
            
        # Deduplicate by URL
        unique_posts = {p['url']: p for p in all_posts}.values()
        total_posts = len(unique_posts)
        
        await msg.edit_text(f"🔄 **Massive Scrape**\n\nFound {total_posts} unique posts across all lists. Starting deep scrape...\nThis will run in the background. You can use the bot normally.")
        
        success = 0
        failed = []
        
        for i, p in enumerate(unique_posts):
            try:
                details = await scraper.scrape_post_details(p['url'])
                if details:
                    p.update(details)
                    await database.add_or_update_post(p)
                    success += 1
                else:
                    failed.append(p['url'])
            except Exception:
                failed.append(p['url'])
                
            # Log progress every 50 posts
            if i > 0 and i % 50 == 0:
                print(f"Massive Scrape Progress: {i}/{total_posts}...")
                
        # Scrape complete
        text = f"✅ **Massive Background Scrape Complete!**\n\nTotal Posts Found: {total_posts}\nSuccessfully Added/Updated: {success}\nFailed: {len(failed)}\n\n"
        if failed:
            text += "Some posts failed to scrape. Check the server logs for the full list."
            print("FAILED MASSIVE SCRAPE LINKS:")
            for f in failed:
                print(f)
                
        await client.send_message(config.OWNER_ID, text)
        
    except Exception as e:
        print(f"Massive scrape failed: {e}")
        await client.send_message(config.OWNER_ID, f"❌ Massive scrape crashed: {e}")

async def callback_massive_scrape_start(client, callback_query):
    if not await database.is_admin(callback_query.from_user.id):
        return
    await callback_query.answer("Starting massive scrape...", show_alert=False)
    msg = await callback_query.message.edit_text("Initializing massive scrape...")
    asyncio.create_task(massive_scrape_task(client, msg))

def register_handlers(app: Client):
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(set_lang_command, filters.command("set_lang")))
    app.add_handler(MessageHandler(list_command, filters.command("list")))
    app.add_handler(MessageHandler(scrape_initial_command, filters.command("scrape_initial")))
    app.add_handler(MessageHandler(update_db_command, filters.command("update_db_names")))
    app.add_handler(MessageHandler(add_admin_command, filters.command("add_admin")))
    app.add_handler(MessageHandler(refresh_command, filters.command("refresh")))
    app.add_handler(MessageHandler(menu_command, filters.command("menu")))
    app.add_handler(MessageHandler(search_handler, filters.text))
    
    app.add_handler(CallbackQueryHandler(callback_close, filters.regex(r"^close$")))
    app.add_handler(CallbackQueryHandler(callback_listpg, filters.regex(r"^listpg_")))
    app.add_handler(CallbackQueryHandler(callback_filter, filters.regex(r"^filter_")))
    app.add_handler(CallbackQueryHandler(callback_post, filters.regex(r"^post_")))
    app.add_handler(CallbackQueryHandler(callback_list, filters.regex(r"^list_")))
    app.add_handler(CallbackQueryHandler(callback_select, filters.regex(r"^sel_")))
    app.add_handler(CallbackQueryHandler(callback_quality, filters.regex(r"^qual_")))
    app.add_handler(CallbackQueryHandler(callback_source, filters.regex(r"^src_")))
    app.add_handler(CallbackQueryHandler(callback_allsrc, filters.regex(r"^allsrc_")))
    app.add_handler(CallbackQueryHandler(callback_menu, filters.regex(r"^menu_")))
    app.add_handler(CallbackQueryHandler(callback_menumain, filters.regex(r"^menumain$")))
    app.add_handler(CallbackQueryHandler(callback_submenu, filters.regex(r"^subm_")))
    app.add_handler(CallbackQueryHandler(callback_azsync, filters.regex(r"^azsync_new$")))
    app.add_handler(CallbackQueryHandler(callback_massive_scrape_start, filters.regex(r"^massive_scrape_start$")))
