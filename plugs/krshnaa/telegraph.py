import os
import asyncio
import logging
import aiofiles
import requests
from secrets import token_urlsafe
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from telegraph.aio import Telegraph
from telegraph.exceptions import RetryAfterError, TelegraphException
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, RPCError
from requests.exceptions import RequestException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

TELEGRAPH_AUTHOR_NAME = os.getenv("TELEGRAPH_AUTHOR_NAME", "@NxMirror")
TELEGRAPH_AUTHOR_URL = os.getenv("TELEGRAPH_AUTHOR_URL", "https://t.me/NxMirror")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY")
IMG_CLOUD = os.getenv("IMG_CLOUD", "False").lower() == "true"
MAX_FILE_SIZE = 5 * 1024 * 1024
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/bmp"}
RATE_LIMIT_SECONDS = 10
MAX_RETRIES = 3
spam_block = {}

def add_user_context(user_id):
    return {"user_id": user_id}

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RequestException),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying ImgBB API call: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
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

class TelegraphHelper:
    def __init__(self, author_name=TELEGRAPH_AUTHOR_NAME, author_url=TELEGRAPH_AUTHOR_URL):
        self._telegraph = Telegraph(domain="graph.org")
        self._author_name = author_name
        self._author_url = author_url
        self._account_created = False

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(TelegraphException),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying create_account: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
            extra=add_user_context(retry_state.kwargs.get("user_id", 0))
        )
    )
    async def create_account(self, user_id: int):
        if self._account_created:
            return
        try:
            await self._telegraph.create_account(
                short_name=token_urlsafe(8),
                author_name=self._author_name,
                author_url=self._author_url
            )
            self._account_created = True
            logger.info("Telegraph account created", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to create Telegraph account: {e}", extra=add_user_context(user_id))
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RetryAfterError),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying create_page: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
            extra=add_user_context(retry_state.kwargs.get("user_id", 0))
        )
    )
    async def create_page(self, title: str, content: str, user_id: int):
        try:
            result = await self._telegraph.create_page(
                title=title,
                author_name=self._author_name,
                author_url=self._author_url,
                html_content=content
            )
            logger.info(f"Telegraph page created: {result['url']}", extra=add_user_context(user_id))
            return result
        except RetryAfterError as st:
            logger.warning(f"Telegraph flood control exceeded, sleeping for {st.retry_after}s", extra=add_user_context(user_id))
            await asyncio.sleep(st.retry_after)
            raise
        except Exception as e:
            logger.error(f"Failed to create Telegraph page: {e}", extra=add_user_context(user_id))
            raise

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(RetryAfterError),
        before_sleep=lambda retry_state: logger.warning(
            f"Retrying edit_page: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
            extra=add_user_context(retry_state.kwargs.get("user_id", 0))
        )
    )
    async def edit_page(self, path: str, title: str, content: str, user_id: int):
        try:
            result = await self._telegraph.edit_page(
                path=path,
                title=title,
                author_name=self._author_name,
                author_url=self._author_url,
                html_content=content
            )
            logger.info(f"Telegraph page edited: {result['url']}", extra=add_user_context(user_id))
            return result
        except RetryAfterError as st:
            logger.warning(f"Telegraph flood control exceeded, sleeping for {st.retry_after}s", extra=add_user_context(user_id))
            await asyncio.sleep(st.retry_after)
            raise
        except Exception as e:
            logger.error(f"Failed to edit Telegraph page: {e}", extra=add_user_context(user_id))
            raise

    async def edit_telegraph(self, paths: list, contents: list, user_id: int):
        try:
            if len(paths) != len(contents):
                logger.error("Mismatched paths and contents length", extra=add_user_context(user_id))
                raise ValueError("Paths and contents lists must have equal length")
            nxt_page = 1
            prev_page = 0
            num_of_path = len(paths)
            for content in contents:
                modified_content = content
                if nxt_page == 1 and num_of_path > 1:
                    modified_content += f'<b><a href="https://telegra.ph/{paths[nxt_page]}">Next</a></b>'
                    nxt_page += 1
                else:
                    if prev_page < num_of_path:
                        modified_content += f'<b><a href="https://telegra.ph/{paths[prev_page]}">Prev</a></b>'
                        prev_page += 1
                    if nxt_page < num_of_path:
                        modified_content += f'<b> | <a href="https://telegra.ph/{paths[nxt_page]}">Next</a></b>'
                        nxt_page += 1
                await self.edit_page(
                    path=paths[prev_page - 1],
                    title="@Nxleech Search Engine",
                    content=modified_content,
                    user_id=user_id
                )
            logger.info("Telegraph pages updated with navigation", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to update Telegraph pages: {e}", extra=add_user_context(user_id))
            raise

telegraph = TelegraphHelper()

@Client.on_message(filters.command("telegraphtxt") & filters.text & filters.private)
async def publish_to_telegraph(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    now = asyncio.get_event_loop().time()
    if user_id in spam_block and now - spam_block[user_id] < RATE_LIMIT_SECONDS:
        logger.info("Rate limit hit", extra=logger_context)
        await safe_reply(message, "🛑 Please wait before using /publish again.")
        return
    spam_block[user_id] = now

    if not message.text or len(message.text.strip()) <= len("/publish "):
        logger.info("No content provided for publishing", extra=logger_context)
        await safe_reply(message, "❌ Please provide text to publish to Telegraph.")
        return

    processing = None
    try:
        processing = await safe_reply(message, "⏳ Creating Telegraph page...")

        try:
            await telegraph.create_account(user_id)
        except Exception as e:
            await safe_edit(processing, f"❌ Failed to initialize Telegraph: {e}")
            return

        content = message.text.strip().replace("/publish ", "", 1)
        if len(content) > 65536:
            logger.info("Content exceeds Telegraph limit", extra=logger_context)
            await safe_edit(processing, "❌ Content too large for Telegraph (max 64KB).")
            return

        try:
            result = await telegraph.create_page(
                title="@NxMirror",
                content=content,
                user_id=user_id
            )
            url = result["url"]
            logger.info(f"Published to Telegraph: {url}", extra=logger_context)
            await safe_edit(
                processing,
                f"<blockquote>Published to Telegraph:</blockquote>\n\n{url}\n\n<blockquote>Made By @NxMirror</blockquote>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("View Page", url=url)],
                    [InlineKeyboardButton("Updates ⚡", url="https://t.me/NxMirror")]
                ])
            )
        except Exception as e:
            logger.error(f"Telegraph publishing failed: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ Failed to publish to Telegraph: {e}")

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
        await asyncio.sleep(fw.value)
        await safe_edit(processing, "⚠️ Flood wait triggered. Try again later.")
    except Exception as e:
        logger.error(f"Fatal error in publish_to_telegraph: {e}", extra=logger_context)
        await safe_edit(processing, f"❌ Unexpected error: {e}")
    finally:
        if processing:
            logger.info("Processing message cleanup attempted", extra=logger_context)

@Client.on_message(filters.command("telegraph") & filters.reply & filters.private)
async def publish_image_to_telegraph(client: Client, message: Message):
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
        await safe_reply(message, "🛑 Please wait before using /publishimg again.")
        return
    spam_block[user_id] = now

    reply = message.reply_to_message
    if not reply or not reply.media or (not reply.photo and not reply.document):
        logger.info("No valid image in reply", extra=logger_context)
        await safe_reply(message, "❌ Reply to an image to publish to Telegraph.")
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

    title = message.text.strip().replace("@NxMirror ", "", 1) or "@NxMirror"
    processing = None
    file_path = None
    try:
        processing = await safe_reply(message, "⏳ Processing image for Telegraph...")

        try:
            file_path = await reply.download()
            if not file_path or not os.path.exists(file_path):
                logger.error("Download failed or file not found", extra=logger_context)
                await safe_edit(processing, "❌ Download failed.")
                return
            logger.info(f"Image downloaded: {file_path}", extra=logger_context)
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
            imgbb_url = result["data"]["url"]
            logger.info(f"Image uploaded to ImgBB: {imgbb_url}", extra=logger_context)
        except RequestException as e:
            logger.error(f"ImgBB API error: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ ImgBB API error: {e}")
            return

        try:
            await telegraph.create_account(user_id)
        except Exception as e:
            logger.error(f"Telegraph account creation failed: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ Failed to initialize Telegraph: {e}")
            return

        content = f'<figure><img src="{imgbb_url}"></figure>'
        if len(content) > 65536:
            logger.info("Content exceeds Telegraph limit", extra=logger_context)
            await safe_edit(processing, "❌ Content too large for Telegraph (max 64KB).")
            return

        try:
            result = await telegraph.create_page(
                title=title,
                content=content,
                user_id=user_id
            )
            url = result["url"]
            logger.info(f"Published image to Telegraph: {url}", extra=logger_context)
            await safe_edit(
                processing,
                f"<blockquote>Published to Telegraph:</blockquote>\n\n{url}\n\n<blockquote>Made By @NxMirror</blockquote>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("View Image", url=url)],
                    [InlineKeyboardButton("Updates ⚡", url="https://t.me/NxMirror")]
                ])
            )
        except Exception as e:
            logger.error(f"Telegraph publishing failed: {e}", extra=logger_context)
            await safe_edit(processing, f"❌ Failed to publish to Telegraph: {e}")

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
        await asyncio.sleep(fw.value)
        await safe_edit(processing, "⚠️ Flood wait triggered. Try again later.")
    except Exception as e:
        logger.error(f"Fatal error in publish_image_to_telegraph: {e}", extra=logger_context)
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
