import asyncio
from pyrogram import Client
from pyrogram.handlers import RawUpdateHandler
import config
import logging

logging.basicConfig(level=logging.INFO)

app = Client("test_session_local", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

async def dump_update(client, update, users, chats):
    print("GOT UPDATE:", update)

app.add_handler(RawUpdateHandler(dump_update))

async def main():
    await app.start()
    print("Bot listening for raw updates...")
    import pyrogram
    await pyrogram.idle()
    await app.stop()

asyncio.run(main())
