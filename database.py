import motor.motor_asyncio
from datetime import datetime
import config

DB_URL = config.DB_URL
DB_NAME = config.DB_NAME

client = motor.motor_asyncio.AsyncIOMotorClient(DB_URL)
db = client[DB_NAME]
posts_collection = db["posts"]
users_collection = db["users"]
admins_collection = db["admins"]

async def init_db():
    # Create indexes for faster search
    await posts_collection.create_index([("title", "text")])
    await posts_collection.create_index("post_id", unique=True)
    await users_collection.create_index("user_id", unique=True)
    print("Database initialized")

async def add_or_update_post(post_data):
    post_data['updated_at'] = datetime.utcnow()
    if 'created_at' not in post_data:
        post_data['created_at'] = datetime.utcnow()
        
    await posts_collection.update_one(
        {"post_id": post_data["post_id"]},
        {"$set": post_data},
        upsert=True
    )

async def get_post_by_id(post_id):
    return await posts_collection.find_one({"post_id": post_id})

from bson.objectid import ObjectId

async def get_post_by_mongo_id(oid_str):
    try:
        return await posts_collection.find_one({"_id": ObjectId(oid_str)})
    except:
        return None

async def get_all_posts(skip=0, limit=10):
    cursor = posts_collection.find().sort("created_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)
    
async def get_posts_by_language(language, skip=0, limit=10):
    cursor = posts_collection.find({"languages": language}).sort("created_at", -1).skip(skip).limit(limit)
    return await cursor.to_list(length=limit)

async def count_all_posts():
    return await posts_collection.count_documents({})
    
async def count_posts_by_language(language):
    return await posts_collection.count_documents({"languages": language})

async def search_posts(keyword, limit=10):
    # Regex search for partial matching
    regex_pattern = f".*{keyword}.*"
    cursor = posts_collection.find({"title": {"$regex": regex_pattern, "$options": "i"}}).limit(limit)
    return await cursor.to_list(length=limit)

async def get_latest_posts(limit=10):
    cursor = posts_collection.find().sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=limit)

async def add_or_update_user(user_id, data):
    data['updated_at'] = datetime.utcnow()
    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": data},
        upsert=True
    )

async def get_user(user_id):
    return await users_collection.find_one({"user_id": user_id})

async def get_all_users():
    cursor = users_collection.find()
    return await cursor.to_list(length=None)

async def get_users_by_language(language):
    cursor = users_collection.find({"language_preference": language})
    return await cursor.to_list(length=None)

async def add_admin(user_id):
    await admins_collection.update_one(
        {"user_id": int(user_id)},
        {"$set": {"user_id": int(user_id), "added_at": datetime.utcnow()}},
        upsert=True
    )

async def remove_admin(user_id):
    await admins_collection.delete_one({"user_id": int(user_id)})

async def is_admin(user_id):
    if int(user_id) == config.OWNER_ID:
        return True
    admin = await admins_collection.find_one({"user_id": int(user_id)})
    return admin is not None

async def get_all_admins():
    cursor = admins_collection.find()
    admins = await cursor.to_list(length=None)
    return [a['user_id'] for a in admins]
