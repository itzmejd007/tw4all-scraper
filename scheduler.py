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
                details = await scraper.scrape_post_details(p['url'], deep_scrape=True)
                if details:
                    p.update(details)
                    await database.add_or_update_post(p)
                    new_count += 1
                    
                    # Notify about new post
                    admins = await database.get_all_admins()
                    admins.append(config.OWNER_ID)
                    for user in list(set(admins)):
                        try:
                            from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 View Post", callback_data=f"post_{p['post_id']}")]])
                            await client.send_message(user, f"🆕 **New Post Added!**\n\n**{p['title']}**\nAdded: {len(p.get('episodes', []))} Episodes, {len(p.get('zips', []))} ZIPs.", reply_markup=btn)
                        except:
                            pass
            else:
                # Post exists, check if new episodes were added by doing a shallow scrape first
                shallow_details = await scraper.scrape_post_details(p['url'], deep_scrape=False)
                if shallow_details:
                    old_eps = len(existing.get('episodes', []))
                    new_eps = len(shallow_details.get('episodes', []))
                    
                    if new_eps > old_eps:
                        # New episodes added! Now do a deep scrape to get all links
                        details = await scraper.scrape_post_details(p['url'], deep_scrape=True)
                        if details:
                            p.update(details)
                            await database.add_or_update_post(p)
                            update_count += 1
                            
                            # Notify about update
                            admins = await database.get_all_admins()
                            admins.append(config.OWNER_ID)
                            for user in list(set(admins)):
                                try:
                                    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                                    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🎬 View Update", callback_data=f"post_{p['post_id']}")]])
                                    await client.send_message(user, f"🔄 **Post Updated!**\n\n**{p['title']}**\nAdded {new_eps - old_eps} new Episodes.", reply_markup=btn)
                                except:
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
    
    # Run massive scrape every night at 12 AM
    import bot_handlers
    scheduler.add_job(bot_handlers.run_nightly_massive_scrape, "cron", hour=0, minute=0, args=[client])
    
    scheduler.start()
    return scheduler
