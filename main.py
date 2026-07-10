import asyncio
from pyrogram import Client
import database
import bot_handlers
import scheduler
import config

if not config.BOT_TOKEN:
    print("WARNING: BOT_TOKEN is not set in config.py!")

app = Client(
    "toonworld_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN
)

async def main():
    print("Initializing Database...")
    await database.init_db()
    
    print("Registering Handlers...")
    bot_handlers.register_handlers(app)
    
    print("Starting Scheduler...")
    scheduler.setup_scheduler(app)
    
    print("Starting Bot...")
    await app.start()
    
    print("Bot is running. Press Ctrl+C to stop.")
    import pyrogram
    await pyrogram.idle()
    
    await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
