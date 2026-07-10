from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
import database
import scraper
import asyncio
import config

OWNER_ID = config.OWNER_ID

def create_post_buttons(posts):
    buttons = []
    for post in posts:
        buttons.append([InlineKeyboardButton(post['title'], callback_data=f"post_{post['post_id'][:40]}")])
    return InlineKeyboardMarkup(buttons)

async def start_command(client, message):
    print("Received /start command!")
    await database.add_or_update_user(message.from_user.id, {
        "user_id": message.from_user.id,
        "first_name": message.from_user.first_name,
        "username": message.from_user.username
    })
    await message.reply_text(
        "Welcome to ToonWorld4All Bot!\n\n"
        "Send me any keyword (e.g. 'naruto') to search for anime/cartoons.\n"
        "Use /set_lang <language> to get notifications for specific languages (e.g., /set_lang Tamil)."
    )

async def set_lang_command(client, message):
    if len(message.command) < 2:
        await message.reply_text("Usage: /set_lang <language>\nExample: /set_lang Tamil")
        return
    
    lang = message.command[1].capitalize()
    await database.add_or_update_user(message.from_user.id, {"language_preference": lang})
    await message.reply_text(f"Language preference set to: {lang}. You will be notified when new posts with this language are added.")

async def search_handler(client, message):
    keyword = message.text.strip()
    if keyword.startswith('/'):
        return
    
    msg = await message.reply_text("Searching...")
    posts = await database.search_posts(keyword)
    
    if not posts:
        await msg.edit_text("No posts found in database. Trying to scrape latest as fallback...")
        latest = await database.get_latest_posts(5)
        if latest:
            await msg.edit_text("No exact match. Here are latest posts:", reply_markup=create_post_buttons(latest))
        else:
            await msg.edit_text("No posts found.")
        return
    
    await msg.edit_text(f"Search results for '{keyword}':", reply_markup=create_post_buttons(posts))

async def callback_post(client, callback_query):
    post_id = callback_query.data.split("post_")[1]
    post = await database.get_post_by_id(post_id)
    
    if not post:
        await callback_query.answer("Post not found in database.", show_alert=True)
        return
    
    # Check if episodes/zips exist, if not scrape details live
    if 'episodes' not in post or ('episodes' in post and len(post['episodes']) == 0 and len(post['zips']) == 0):
        await callback_query.message.edit_text("Loading details from website...")
        details = await scraper.scrape_post_details(post['url'])
        if details:
            post.update(details)
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
        buttons.append([InlineKeyboardButton("Episodes", callback_data=f"list_ep_{post_id}")])
    if zip_count > 0:
        buttons.append([InlineKeyboardButton("ZIP Files", callback_data=f"list_zip_{post_id}")])
    
    if not buttons:
        text += "\n\nNo download links found."
    
    await callback_query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons))

async def callback_list(client, callback_query):
    action, ptype, post_id = callback_query.data.split("_")
    post = await database.get_post_by_id(post_id)
    
    if not post:
        await callback_query.answer("Post not found.", show_alert=True)
        return
    
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    
    # If too many items, just show first 90 to fit in telegram button limits (max 100)
    buttons = []
    for i, item in enumerate(items[:90]):
        # Pass index and ptype to fetch url later
        buttons.append([InlineKeyboardButton(item['title'], callback_data=f"sel_{ptype}_{post_id}_{i}")])
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"post_{post_id}")])
    
    await callback_query.message.edit_text("Select:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_select(client, callback_query):
    # Data: sel_ep_postid_index
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    
    post = await database.get_post_by_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    if index >= len(items):
        await callback_query.answer("Item not found.", show_alert=True)
        return
    
    item = items[index]
    archive_url = item['url']
    
    await callback_query.message.edit_text("Fetching available qualities...")
    
    qualities = await scraper.scrape_archive_page(archive_url)
    
    if not qualities:
        await callback_query.message.edit_text("No qualities found for this link.", 
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Back", callback_data=f"list_{ptype}_{post_id}")]]))
        return
    
    # Store qualities temporarily or in cache. For simplicity, we can just list them and map them.
    # To keep state simple, we will scrape again on quality select if we don't store it.
    # Let's save them to the DB under a temporary cache collection or just in the post object?
    # No, we can just pass the index and let the next callback re-scrape, it's fast enough or use a global dict (cache).
    
    buttons = []
    for q_name in qualities.keys():
        # q_name might be long, let's limit it
        short_q = q_name[:20]
        # We need a way to identify this specific item and quality.
        buttons.append([InlineKeyboardButton(short_q, callback_data=f"qual_{ptype}_{post_id}_{index}_{list(qualities.keys()).index(q_name)}")])
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"list_{ptype}_{post_id}")])
    
    await callback_query.message.edit_text("Select Quality:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_quality(client, callback_query):
    # Data: qual_ep_postid_index_qindex
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    q_index = int(parts[4])
    
    post = await database.get_post_by_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    item = items[index]
    archive_url = item['url']
    
    await callback_query.message.edit_text("Loading sources...")
    
    qualities = await scraper.scrape_archive_page(archive_url)
    q_keys = list(qualities.keys())
    if q_index >= len(q_keys):
        await callback_query.answer("Error loading quality.", show_alert=True)
        return
    
    q_name = q_keys[q_index]
    sources = qualities[q_name]
    
    buttons = []
    for i, src in enumerate(sources):
        src_name = src['source'][:20]
        buttons.append([InlineKeyboardButton(src_name, callback_data=f"src_{ptype}_{post_id}_{index}_{q_index}_{i}")])
    
    if len(sources) > 1:
        buttons.append([InlineKeyboardButton("All Sources", callback_data=f"src_{ptype}_{post_id}_{index}_{q_index}_all")])
    
    buttons.append([InlineKeyboardButton("« Back", callback_data=f"sel_{ptype}_{post_id}_{index}")])
    
    await callback_query.message.edit_text(f"Selected: {q_name}\n\nSelect Source:", reply_markup=InlineKeyboardMarkup(buttons))

async def callback_source(client, callback_query):
    parts = callback_query.data.split("_")
    ptype = parts[1]
    post_id = parts[2]
    index = int(parts[3])
    q_index = int(parts[4])
    s_index = parts[5] # can be 'all'
    
    post = await database.get_post_by_id(post_id)
    items = post.get('episodes' if ptype == 'ep' else 'zips', [])
    item = items[index]
    archive_url = item['url']
    
    qualities = await scraper.scrape_archive_page(archive_url)
    q_name = list(qualities.keys())[q_index]
    sources = qualities[q_name]
    
    text = f"**{post['title']}**\n{item['title']} - {q_name}\n\n"
    
    if s_index == 'all':
        for src in sources:
            text += f"**{src['source']}**: {src['url']}\n"
    else:
        src = sources[int(s_index)]
        text += f"**{src['source']}**: {src['url']}\n"
        
    await callback_query.message.edit_text(text)
    
async def scrape_initial_command(client, message):
    if message.from_user.id != OWNER_ID:
        await message.reply_text("Only owner can use this command.")
        return
    
    msg = await message.reply_text("Scraping initial 20 posts from homepage... This might take a minute.")
    
    posts = await scraper.scrape_homepage(limit=20)
    for p in posts:
        # Get details
        details = await scraper.scrape_post_details(p['url'])
        if details:
            p.update(details)
        await database.add_or_update_post(p)
        
    await msg.edit_text(f"Successfully scraped and stored {len(posts)} posts!")

def register_handlers(app: Client):
    app.add_handler(MessageHandler(start_command, filters.command("start")))
    app.add_handler(MessageHandler(set_lang_command, filters.command("set_lang")))
    app.add_handler(MessageHandler(scrape_initial_command, filters.command("scrape_initial")))
    app.add_handler(MessageHandler(search_handler, filters.text))
    
    app.add_handler(CallbackQueryHandler(callback_post, filters.regex(r"^post_")))
    app.add_handler(CallbackQueryHandler(callback_list, filters.regex(r"^list_")))
    app.add_handler(CallbackQueryHandler(callback_select, filters.regex(r"^sel_")))
    app.add_handler(CallbackQueryHandler(callback_quality, filters.regex(r"^qual_")))
    app.add_handler(CallbackQueryHandler(callback_source, filters.regex(r"^src_")))
