import asyncio
from pyrogram import Client
from pyrogram.types import Message, User, Chat
import bot_handlers
import config
import database

app = Client("test", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

async def mock_test():
    await database.init_db()
    bot_handlers.register_handlers(app)
    
    # Manually start
    await app.start()
    print("Bot started!")
    
    # Mock an incoming message
    user = User(id=123, first_name="Test", is_bot=False)
    chat = Chat(id=123, type="private")
    msg = Message(id=1, from_user=user, chat=chat, text="/start", date=0)
    
    # Process through dispatcher
    print("Processing message...")
    try:
        # In Pyrogram, you can process an update manually, but let's just await the handler to see if it works.
        await bot_handlers.start_command(app, msg)
        print("Start handler executed!")
    except Exception as e:
        print("Handler error:", e)
        
    await app.stop()

asyncio.run(mock_test())
