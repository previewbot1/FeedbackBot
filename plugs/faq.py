import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.errors import RPCError, FloodWait, MessageNotModified
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from formats import script
from run import FAQ_ENABLED

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

FAQ_RATE_LIMIT_SECONDS = 5
spam_block = {}

def add_user_context(user_id):
    return {"user_id": user_id}

if FAQ_ENABLED:
    try:
        from formats import faq_format
    except ImportError as e:
        logger.error(f"Failed to import faq_format: {e}")
        FAQ_ENABLED = False

@Client.on_callback_query(filters.regex("faq"))
async def faq_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < FAQ_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for FAQ callback", extra=logger_context)
            await callback_query.answer("🛑 Please wait before accessing FAQ again.", show_alert=True)
            return
        spam_block[user_id] = now

        if not FAQ_ENABLED:
            logger.info("FAQ feature disabled", extra=logger_context)
            await callback_query.answer("❌ FAQ feature is disabled.", show_alert=True)
            return

        logger.info("FAQ callback triggered", extra=logger_context)
        user_name = (
            callback_query.from_user.first_name or
            callback_query.from_user.username or
            "User"
        )

        try:
            faq_text = faq_format.faq_script.FAQ_TXT.format(user_name)
        except (AttributeError, KeyError) as e:
            logger.error(f"Invalid FAQ format configuration: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to load FAQ content.", show_alert=True)
            return

        try:
            await callback_query.message.edit_text(
                faq_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="back_start")],
                    [InlineKeyboardButton("Close", callback_data="close")]
                ])
            )
            await callback_query.answer()
            logger.info("FAQ message displayed", extra=logger_context)
        except MessageNotModified:
            logger.warning("FAQ message unchanged", extra=logger_context)
            await callback_query.answer("ℹ️ FAQ content already displayed.", show_alert=False)
        except FloodWait as fw:
            logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            await callback_query.message.edit_text(
                faq_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="back_start")],
                    [InlineKeyboardButton("Close", callback_data="close")]
                ])
            )
            await callback_query.answer()
        except RPCError as e:
            logger.warning(f"Telegram RPC error in FAQ edit: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to display FAQ due to Telegram error.", show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in FAQ edit: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to display FAQ.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in faq_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for FAQ", extra=logger_context)

@Client.on_callback_query(filters.regex("back_start"))
async def back_start_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < FAQ_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for back_start callback", extra=logger_context)
            await callback_query.answer("🛑 Please wait before navigating back.", show_alert=True)
            return
        spam_block[user_id] = now

        if not FAQ_ENABLED:
            logger.info("FAQ feature disabled", extra=logger_context)
            await callback_query.answer("❌ FAQ feature is disabled.", show_alert=True)
            return

        logger.info("Back callback triggered", extra=logger_context)
        user_name = (
            callback_query.from_user.first_name or
            callback_query.from_user.username or
            "User"
        )

        try:
            start_text = script.script.START_TXT.format(user_name)
        except (AttributeError, KeyError) as e:
            logger.error(f"Invalid start script configuration: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to load start content.", show_alert=True)
            return

        buttons = []
        if FAQ_ENABLED:
            buttons.append(InlineKeyboardButton("FAQ", callback_data="faq"))
        if os.getenv("SOURCE_BUTTON", "False").lower() == "true":
            source_url = os.getenv("SOURCE", "https://github.com/")
            try:
                if not source_url.startswith(("http://", "https://")):
                    raise ValueError("Invalid source URL")
                buttons.append(InlineKeyboardButton("SOURCE", url=source_url))
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid SOURCE environment variable: {e}", extra=logger_context)

        reply_markup = InlineKeyboardMarkup([buttons]) if buttons else None

        try:
            await callback_query.message.edit_text(
                start_text,
                reply_markup=reply_markup
            )
            await callback_query.answer()
            logger.info("Start message displayed", extra=logger_context)
        except MessageNotModified:
            logger.warning("Start message unchanged", extra=logger_context)
            await callback_query.answer("ℹ️ Start content already displayed.", show_alert=False)
        except FloodWait as fw:
            logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
            await asyncio.sleep(fw.value)
            await callback_query.message.edit_text(
                start_text,
                reply_markup=reply_markup
            )
            await callback_query.answer()
        except RPCError as e:
            logger.warning(f"Telegram RPC error in back_start edit: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to return to start due to Telegram error.", show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in back_start edit: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to return to start.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in back_start_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for back_start", extra=logger_context)

@Client.on_callback_query(filters.regex("close"))
async def close_callback(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < FAQ_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close callback", extra=logger_context)
            await callback_query.answer("🛑 Please wait before closing.", show_alert=True)
            return
        spam_block[user_id] = now

        if not FAQ_ENABLED:
            logger.info("FAQ feature disabled", extra=logger_context)
            await callback_query.answer("❌ FAQ feature is disabled.", show_alert=True)
            return

        logger.info("Close callback triggered", extra=logger_context)
        try:
            await callback_query.message.delete()
            logger.info("Message closed", extra=logger_context)
        except RPCError as e:
            logger.warning(f"Telegram RPC error in close: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message due to Telegram error.", show_alert=True)
        except Exception as e:
            logger.error(f"Unexpected error in close: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close message.", show_alert=True)
        else:
            await callback_query.answer("✅ Message closed.", show_alert=False)

    except Exception as e:
        logger.error(f"Fatal error in close_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close", extra=logger_context)

async def safe_edit(message, text: str, reply_markup=None):
    if not message:
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except RPCError as e:
        logger.warning(f"[safe_edit] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_edit] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

async def safe_reply(message: Message, text: str, reply_markup=None):
    try:
        return await message.reply_text(text, reply_markup=reply_markup)
    except RPCError as e:
        logger.warning(f"[safe_reply] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
