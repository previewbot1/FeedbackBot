import logging
import os
from os import getenv
from dotenv import load_dotenv
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(
    level=logging.INFO,
    filename=os.getenv("LOG_FILE", "bot.log"),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
load_dotenv('config.env')
LOGGER = logging.getLogger(__name__)

try:
    client = AsyncIOMotorClient(getenv('MONGO'))
    db = client[getenv('DB_NAME')]
    users_collection = db['users']
    uploads_collection = db['uploads']
    logs_collection = db['logs']
    keywords_collection = db['keywords']
    callbacks_collection = db['callbacks']  # New collection for callback data
except Exception as e:
    LOGGER.error(f"Failed to connect to MongoDB: {e}", exc_info=True)
    raise

async def get_all_users():
    try:
        user_ids = [str(user["user_id"]) async for user in users_collection.find({}, {"user_id": 1, "_id": 0})]
        return user_ids
    except Exception as e:
        LOGGER.error(f"Error getting all users: {e}", exc_info=True)
        return []

async def user_exists(user_id: int) -> bool:
    try:
        return await users_collection.count_documents({"user_id": user_id}) > 0
    except Exception as e:
        LOGGER.error(f"Error checking user {user_id}: {e}", exc_info=True)
        return False

async def del_user(user_id: int):
    try:
        await users_collection.delete_one({"user_id": user_id})
    except Exception as e:
        LOGGER.error(f"Error deleting user {user_id}: {e}", exc_info=True)

async def add_user(user_id: int):
    try:
        await users_collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id}},
            upsert=True
        )
    except Exception as e:
        LOGGER.error(f"Error adding user {user_id}: {e}", exc_info=True)

async def add_upload_log(user_id: int, url: str):
    try:
        await uploads_collection.insert_one({
            "user_id": user_id,
            "url": url,
            "timestamp": int(datetime.now().timestamp())
        })
    except Exception as e:
        LOGGER.error(f"Error logging upload for user {user_id}: {e}", exc_info=True)

async def add_log_usage(user_id: int, command: str):
    try:
        await logs_collection.insert_one({
            "user_id": user_id,
            "command": command,
            "timestamp": int(datetime.now().timestamp())
        })
    except Exception as e:
        LOGGER.error(f"Error logging command {command} for user {user_id}: {e}", exc_info=True)

async def add_keyword_response(keyword: str, response: str):
    try:
        await keywords_collection.update_one(
            {"keyword": keyword.lower()},
            {"$set": {"keyword": keyword.lower(), "response": response}},
            upsert=True
        )
    except Exception as e:
        LOGGER.error(f"Error adding keyword {keyword}: {e}", exc_info=True)

async def get_keyword_response_map():
    try:
        return {
            doc["keyword"]: doc["response"]
            async for doc in keywords_collection.find({"response": {"$exists": True}}, {"_id": 0})
        }
    except Exception as e:
        LOGGER.error(f"Error getting keyword response map: {e}", exc_info=True)
        return {}

async def clear_keywords():
    try:
        result = await keywords_collection.delete_many({})
        LOGGER.info(f"Cleared {result.deleted_count} keywords")
        return result
    except Exception as e:
        LOGGER.error(f"Error clearing keywords: {e}", exc_info=True)

async def delete_keyword(keyword: str) -> bool:
    try:
        result = await keywords_collection.delete_one({"keyword": keyword.lower()})
        LOGGER.info(f"Deleted keyword {keyword}: {result.deleted_count > 0}")
        return result.deleted_count > 0
    except Exception as e:
        LOGGER.error(f"Error deleting keyword {keyword}: {e}", exc_info=True)
        return False

async def get_all_keywords_with_responses():
    try:
        return [doc async for doc in keywords_collection.find({}, {"_id": 0})]
    except Exception as e:
        LOGGER.error(f"Error getting all keywords: {e}", exc_info=True)
        return []

async def add_callback_response(data: str, response: str):
    """Store callback data and associated response text."""
    try:
        await callbacks_collection.update_one(
            {"data": data.lower()},
            {"$set": {"data": data.lower(), "response": response}},
            upsert=True
        )
        LOGGER.info(f"Added callback response for data: {data}")
    except Exception as e:
        LOGGER.error(f"Error adding callback response {data}: {e}", exc_info=True)

async def get_callback_response(data: str) -> str | None:
    """Retrieve response text for given callback data."""
    try:
        doc = await callbacks_collection.find_one({"data": data.lower()}, {"response": 1, "_id": 0})
        return doc["response"] if doc else None
    except Exception as e:
        LOGGER.error(f"Error getting callback response for {data}: {e}", exc_info=True)
        return None

async def delete_callback(callback_data: str) -> bool:
    result = await callbacks_collection.delete_one({"data": callback_data.lower()})
    return result.deleted_count > 0

async def get_all_callbacks():
    return [doc async for doc in callbacks_collection.find({}, {"_id": 0})]

async def clear_callbacks():
    result = await callbacks_collection.delete_many({})
    return result

async def add_product(name, description, price, availability, preview_url=None):
    max_id = await db.products.find_one(sort=[("id", -1)])
    new_id = (max_id["id"] + 1) if max_id else 1
    return await db.products.insert_one({
        "id": new_id,
        "name": name,
        "description": description,
        "price": price,
        "availability": availability,
        "preview_url": preview_url
    })

async def get_products():
    return await db.products.find().to_list(None)

async def get_product(product_id):
    return await db.products.find_one({"id": product_id})

async def edit_product(product_id, name, description, price, availability, preview_url=None):
    return await db.products.update_one(
        {"id": product_id},
        {"$set": {
            "name": name,
            "description": description,
            "price": price,
            "availability": availability,
            "preview_url": preview_url
        }}
    )

async def remove_product(product_id):
    return await db.products.delete_one({"id": product_id})

async def clear_products():
    return await db.products.delete_many({})
