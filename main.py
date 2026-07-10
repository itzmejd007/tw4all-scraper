import asyncio
from pyrogram import Client
import database
import bot_handlers
import scheduler
import config

if not config.BOT_TOKEN:
    print("WARNING: BOT_TOKEN is not set in config.py!")

async def main():
    app = Client(
        "tw4all_scraper_bot_session",
        api_id=config.API_ID,
        api_hash=config.API_HASH,
        bot_token=config.BOT_TOKEN
    )
    
    print("Initializing Database...")
    await database.init_db()
    
    print("Registering Handlers...")
    bot_handlers.register_handlers(app)
    
    print("Starting Scheduler...")
    scheduler.setup_scheduler(app)
    
    print("Starting Bot...")
    await app.start()
    
    print("Bot is running. Press Ctrl+C to stop.")
    
    # Send startup prompt to owner
    try:
        from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        await app.send_message(
            config.OWNER_ID,
            "🚀 **Bot Started Successfully!**\n\nDo you want to run a massive background scrape of the entire website (all A-Z lists) tonight?\n\nThis will take a long time but will run safely in the background.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Start Massive Scrape", callback_data="massive_scrape_start")],
                [InlineKeyboardButton("❌ Skip", callback_data="close")]
            ])
        )
    except Exception as e:
        print(f"Could not send startup message to owner: {e}")
        
    import pyrogram
    await pyrogram.idle()
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
