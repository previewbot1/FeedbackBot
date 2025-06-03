import os
import asyncio
import logging
import aiofiles
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError
from requests.exceptions import RequestException
import requests
from utils.database import add_upload_log

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

IMG_CLOUD = os.getenv("IMG_CLOUD", "False").lower() == "true"
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/bmp"}
MAX_RETRIES = 3
RATE_LIMIT_SECONDS = 10
spam_block = {}

def add_user_context(user_id):
    return {"user_id": user_id}

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RequestException),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying API call: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
        extra=add_user_context(retry_state.kwargs.get("user_id", 0))
    )
)
async def upload_to_imgbb(file_path: str, user_id: int) -> dict:
    async with aiofiles.open(file_path, "rb") as f:
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY},
            files={"image": await f.read()},
            timeout=30
        )
    resp.raise_for_status()
    return resp.json()

@Client.on_message(filters.command(["img", "cup", "cloud"]) & filters.reply & filters.private)
async def c_upload(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)
    
    if not IMG_CLOUD:
        logger.info("Cloud upload feature disabled", extra=logger_context)
        await safe_reply(message, "❌ Cloud upload feature is disabled.")
        return

    if not IMGBB_API_KEY:
        logger.error("ImgBB API key not configured", extra=logger_context)
        await safe_reply(message, "❌ Server configuration error. Please try again later.")
        return

    now = asyncio.get_event_loop().time()
    if user_id in spam_block and now - spam_block[user_id] < RATE_LIMIT_SECONDS:
        logger.info("Rate limit hit", extra=logger_context)
        await safe_reply(message, "🛑 Please wait before using this command again.")
        return
    spam_block[user_id] = now

    reply = message.reply_to_message
    if not reply or not reply.media:
        logger.info("No media in reply", extra=logger_context)
        await safe_reply(message, "❌ Reply to an image to upload it to Cloud.")
        return

    if reply.document:
        if reply.document.file_size > MAX_FILE_SIZE:
            logger.info(f"File too large: {reply.document.file_size} bytes", extra=logger_context)
            await safe_reply(message, "❌ File size limit is 5 MB.")
            return
        if reply.document.mime_type not in ALLOWED_MIME_TYPES:
            logger.info(f"Unsupported MIME type: {reply.document.mime_type}", extra=logger_context)
            await safe_reply(message, "❌ Only image files (JPEG, PNG, GIF, BMP) are supported.")
            return

    processing = None
    file_path = None
    try:
        processing = await safe_reply(message, "⏳ Processing...")

        try:
            file_path = await reply.download()
            if not file_path or not os.path.exists(file_path):
                logger.error("Download failed or file not found", extra=logger_context)
                await safe_edit(processing, "❌ Download failed.")
                return
            logger.info(f"Media downloaded: {file_path}", extra=logger_context)
        except FloodWait as fw:
            logger.warning(f"FloodWait during download: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            file_path = await reply.download()
            if not file_path:
                await safe_edit(processing, "❌ Download failed after retry.")
                return

        try:
            result = await upload_to_imgbb(file_path, user_id)
            if not result.get("success"):
                error_msg = result.get("error", {}).get("message", "Unknown error")
                logger.warning(f"ImgBB upload failed: {error_msg}", extra=logger_context)
                await safe_edit(processing, f"❌ Upload failed: {error_msg}")
                return

            url = result["data"]["url"]
            try:
                await add_upload_log(user_id, url)
                logger.info(f"Upload logged: {url}", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to log upload: {e}", extra=logger_context)

            await safe_edit(
                processing,
                f"<blockquote>Successfully Uploaded:</blockquote>\n\n{url}\n\n<blockquote>Made By @NxMirror</blockquote>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Updates ⚡", url="https://t.me/NxMirror")]
                ])
            )
            logger.info("Upload successful", extra=logger_context)

        except RequestException as e:
            logger.error(f"ImgBB API error: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ ImgBB API error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during upload: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ Error: {e}")

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
        await asyncio.sleep(fw.value)
        await safe_edit(processing, "⚠️ Flood wait triggered. Try again later.")
    except Exception as e:
        logger.error(f"Fatal error in c_upload: {e}", extra=logger_context)
        await safe_edit(processing, f"❌ Unexpected error: {e}")
    finally:
        try:
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info("File cleaned up", extra=logger_context)
            if processing:
                logger.info("Processing message cleanup attempted", extra=logger_context)
        except Exception as e:
            logger.warning(f"Cleanup failed: {e}", extra=logger_context)

async def safe_reply(message: Message, text: str):
    try:
        return await message.reply_text(text)
    except RPCError as e:
        logger.warning(f"[safe_reply] RPCError: {e}", extra=add_user_context(message.from_user.id))
        return None
    except Exception as e:
        logger.error(f"[safe_reply] Unexpected error: {e}", extra=add_user_context(message.from_user.id))
        return None

async def safe_edit(message: Message, text: str, reply_markup=None):
    if not message:
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except RPCError as e:
        logger.warning(f"[safe_edit] RPCError: {e}", extra=add_user_context(message.from_user.id))
    except Exception as e:
        logger.error(f"[safe_edit] Unexpected error: {e}", extra=add_user_context(message.from_user.id))
