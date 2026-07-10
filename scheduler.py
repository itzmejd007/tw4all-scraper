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
        latest = await scraper.scrape_homepage(limit=20)
        new_count = 0
        update_count = 0
        
        for p in latest:
            existing = await database.get_post_by_id(p['post_id'])
            if not existing:
                # New post found
                details = await scraper.scrape_post_details(p['url'])
                if details:
                    p.update(details)
                    await database.add_or_update_post(p)
                    new_count += 1
            else:
                # Check for updates (e.g. new episodes)
                details = await scraper.scrape_post_details(p['url'])
                if details:
                    old_eps = len(existing.get('episodes', []))
                    new_eps = len(details.get('episodes', []))
                    old_zips = len(existing.get('zips', []))
                    new_zips = len(details.get('zips', []))
                    
                    if new_eps > old_eps or new_zips > old_zips:
                        p.update(details)
                        await database.add_or_update_post(p)
                        update_count += 1
                        
        if new_count > 0 or update_count > 0:
            admins = await database.get_all_admins()
            admins.append(config.OWNER_ID)
            admins = list(set(admins)) # deduplicate
            
            for admin_id in admins:
                try:
                    await client.send_message(
                        admin_id, 
                        f"🔄 **Auto-Update Complete**\n\nNew Posts Added: {new_count}\nExisting Posts Updated: {update_count}"
                    )
                except Exception:
                    pass
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
    
    # Check for new posts every 10 minutes
    scheduler.add_job(check_new_posts, "interval", minutes=10, args=[client])
    
    # Weekly logs (run every 7 days)
    scheduler.add_job(send_weekly_logs, "interval", days=7, args=[client])
    
    scheduler.start()
    return scheduler
