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
    
    text = f"**{post['title']}**\n{item['title']}\nSelected: {q_name}\n\n"
    text += f"**{src['source']}**:\n`{src['url']}`\n\n(Long press the link above to copy it)"
    
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
    if message.from_user.id != OWNER_ID:
        await message.reply_text("Only owner can use this command.")
        return
    
    msg = await message.reply_text("Scraping initial 20 posts from homepage [■■■□□□□□□]... This might take a minute.")
    
    posts = await scraper.scrape_homepage(limit=20)
    for p in posts:
        details = await scraper.scrape_post_details(p['url'])
        if details:
            p.update(details)
        await database.add_or_update_post(p)
        
    await msg.edit_text(f"Successfully scraped and stored {len(posts)} posts!")

async def update_db_command(client, message):
    if message.from_user.id != OWNER_ID:
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

def register_handlers(app: Client):
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(set_lang_command, filters.command("set_lang")))
    app.add_handler(MessageHandler(list_command, filters.command("list")))
    app.add_handler(MessageHandler(scrape_initial_command, filters.command("scrape_initial")))
    app.add_handler(MessageHandler(update_db_command, filters.command("update_db_names")))
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
