import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import database
import scraper
import datetime
import io
import config

LOG_CHANNEL_ID = config.LOG_CHANNEL_ID

async def check_new_posts(client):
    try:
        latest = await scraper.scrape_homepage(limit=5)
        for p in latest:
            existing = await database.get_post_by_id(p['post_id'])
            if not existing:
                # New post found!
                print(f"New post found: {p['title']}")
                details = await scraper.scrape_post_details(p['url'])
                if details:
                    p.update(details)
                await database.add_or_update_post(p)
                
                # Notify users based on language
                langs = p.get('languages', [])
                if langs:
                    for lang in langs:
                        users = await database.get_users_by_language(lang)
                        for u in users:
                            try:
                                await client.send_message(
                                    u['user_id'], 
                                    f"**New Post Alert!**\n\nTitle: {p['title']}\nLanguages: {', '.join(langs)}\n\nSearch for it to download!"
                                )
                            except Exception as e:
                                print(f"Failed to notify user {u['user_id']}: {e}")
    except Exception as e:
        print(f"Error checking new posts: {e}")

async def send_weekly_logs(client):
    if not LOG_CHANNEL_ID:
        return
    
    users = await database.get_all_users()
    total_users = len(users)
    
    log_content = f"Weekly Log - {datetime.datetime.now().strftime('%Y-%m-%d')}\n"
    log_content += f"Total Users: {total_users}\n"
    
    file = io.BytesIO(log_content.encode('utf-8'))
    file.name = "weekly_log.txt"
    
    try:
        await client.send_document(
            chat_id=LOG_CHANNEL_ID,
            document=file,
            caption="Weekly Bot Log Data"
        )
    except Exception as e:
        print(f"Failed to send weekly log: {e}")

def setup_scheduler(client):
    scheduler = AsyncIOScheduler()
    
    # Check for new posts every 30 minutes
    scheduler.add_job(check_new_posts, "interval", minutes=30, args=[client])
    
    # Weekly logs (run every 7 days)
    scheduler.add_job(send_weekly_logs, "interval", days=7, args=[client])
    
    scheduler.start()
    return scheduler
