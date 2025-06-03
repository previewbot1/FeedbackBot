import asyncio
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, RPCError, ChatWriteForbidden, PeerIdInvalid
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from run import ADMINS
from utils.database import get_all_users, del_user

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

BROADCAST_RATE_LIMIT_SECONDS = 10
MAX_RETRIES = 3
BATCH_SIZE = 10
broadcast_status = {"running": False}
spam_block = {}

def add_user_context(user_id):
    return {"user_id": user_id}

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(RPCError),
    before_sleep=lambda retry_state: logger.warning(
        f"Retrying message copy: attempt {retry_state.attempt_number}/{MAX_RETRIES}",
        extra=add_user_context(retry_state.kwargs.get("user_id", 0))
    )
)
async def send_message_to_user(client: Client, message: Message, user_id: int):
    try:
        await message.copy(user_id)
        logger.info(f"Message sent to user {user_id}", extra=add_user_context(user_id))
        return True, None
    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s for user {user_id}", extra=add_user_context(user_id))
        await asyncio.sleep(fw.value)
        await message.copy(user_id)
        logger.info(f"Message sent to user {user_id} after FloodWait", extra=add_user_context(user_id))
        return True, None
    except UserIsBlocked:
        logger.info(f"User {user_id} blocked the bot", extra=add_user_context(user_id))
        try:
            await del_user(user_id)
            logger.info(f"User {user_id} removed from database", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to delete blocked user {user_id}: {e}", extra=add_user_context(user_id))
        return False, "blocked"
    except InputUserDeactivated:
        logger.info(f"User {user_id} account deactivated", extra=add_user_context(user_id))
        try:
            await del_user(user_id)
            logger.info(f"Deactivated user {user_id} removed from database", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to delete deactivated user {user_id}: {e}", extra=add_user_context(user_id))
        return False, "deactivated"
    except PeerIdInvalid:
        logger.warning(f"Invalid peer ID for user {user_id}", extra=add_user_context(user_id))
        try:
            await del_user(user_id)
            logger.info(f"Invalid user {user_id} removed from database", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to delete invalid user {user_id}: {e}", extra=add_user_context(user_id))
        return False, "invalid"
    except ChatWriteForbidden:
        logger.warning(f"Write permission denied for user {user_id}", extra=add_user_context(user_id))
        try:
            await del_user(user_id)
            logger.info(f"User {user_id} with denied permissions removed from database", extra=add_user_context(user_id))
        except Exception as e:
            logger.error(f"Failed to delete user {user_id} with denied permissions: {e}", extra=add_user_context(user_id))
        return False, "forbidden"
    except RPCError as e:
        logger.error(f"Telegram RPC error for user {user_id}: {e}", extra=add_user_context(user_id))
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending message to user {user_id}: {e}", extra=add_user_context(user_id))
        try:
            await del_user(user_id)
            logger.info(f"User {user_id} removed from database due to error", extra=add_user_context(user_id))
        except Exception as de:
            logger.error(f"Failed to delete user {user_id} after send error: {de}", extra=add_user_context(user_id))
        return False, "failed"

@Client.on_message(filters.private & filters.command("broadcast") & filters.user(ADMINS))
async def send_broadcast(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < BROADCAST_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for broadcast", extra=logger_context)
            await safe_reply(message, "🛑 Please wait before starting another broadcast.")
            return
        spam_block[user_id] = now

        if not message.reply_to_message:
            logger.info("No reply message provided for broadcast", extra=logger_context)
            msg = await safe_reply(message, "❌ Reply to a message to broadcast.")
            try:
                await asyncio.sleep(5)
                await safe_delete(msg)
            except Exception as e:
                logger.warning(f"Failed to delete reply message: {e}", extra=logger_context)
            return

        if broadcast_status["running"]:
            logger.info("Another broadcast is already running", extra=logger_context)
            await safe_reply(message, "❌ Another broadcast is in progress. Please wait.")
            return

        broadcast_status["running"] = True
        try:
            users = await get_all_users()
        except Exception as e:
            logger.error(f"Failed to fetch users from database: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to access user database. Please try again later.")
            broadcast_status["running"] = False
            spam_block.pop(user_id, None)
            return

        total_users = len(users)
        if total_users == 0:
            logger.info("No users found in database", extra=logger_context)
            await safe_reply(message, "❌ No users found to broadcast to.")
            broadcast_status["running"] = False
            spam_block.pop(user_id, None)
            return
        logger.info(f"Starting broadcast to {total_users} users", extra=logger_context)

        total = successful = blocked = deactivated = invalid = forbidden = failed = 0
        cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("Cancel Broadcast", callback_data="cancel_bcast")]])
        progress_msg = None
        try:
            progress_msg = await safe_reply(message, "<i>Broadcasting message...</i>", reply_markup=cancel_btn)
            if not progress_msg:
                logger.error("Failed to send progress message", extra=logger_context)
                await safe_reply(message, "❌ Failed to initialize broadcast progress.")
                broadcast_status["running"] = False
                spam_block.pop(user_id, None)
                return

            for i in range(0, total_users, BATCH_SIZE):
                if not broadcast_status["running"]:
                    logger.info("Broadcast cancelled by admin", extra=logger_context)
                    break
                batch = users[i:i + BATCH_SIZE]
                tasks = [send_message_to_user(client, message.reply_to_message, uid) for uid in batch]
                try:
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                except Exception as e:
                    logger.error(f"Batch processing failed: {e}", extra=logger_context)
                    continue

                for result in results:
                    if isinstance(result, tuple):
                        success, reason = result
                        if success:
                            successful += 1
                        elif reason == "blocked":
                            blocked += 1
                        elif reason == "deactivated":
                            deactivated += 1
                        elif reason == "invalid":
                            invalid += 1
                        elif reason == "forbidden":
                            forbidden += 1
                        elif reason == "failed":
                            failed += 1
                    else:
                        failed += 1
                    total += 1

                    if total % 5 == 0 or total == total_users:
                        status = (
                            f"<b><u>📢 Broadcast In Progress...</u></b>\n\n"
                            f"<b>👥 Total:</b> <code>{total}</code>\n"
                            f"<b>✅ Sent:</b> <code>{successful}</code>\n"
                            f"<b>🚫 Blocked:</b> <code>{blocked}</code>\n"
                            f"<b>🗑️ Deactivated:</b> <code>{deactivated}</code>\n"
                            f"<b>🔍 Invalid:</b> <code>{invalid}</code>\n"
                            f"<b>🚷 Forbidden:</b> <code>{forbidden}</code>\n"
                            f"<b>⚠️ Failed:</b> <code>{failed}</code>"
                        )
                        try:
                            await safe_edit(progress_msg, status, reply_markup=cancel_btn)
                            await asyncio.sleep(1)
                        except Exception as e:
                            logger.warning(f"Failed to update progress message: {e}", extra=logger_context)

        except Exception as e:
            logger.error(f"Fatal error in broadcast: {e}", extra=logger_context)
            await safe_edit(progress_msg, f"❌ Broadcast failed: {e}")
            broadcast_status["running"] = False
            spam_block.pop(user_id, None)
            return
        finally:
            broadcast_status["running"] = False
            spam_block.pop(user_id, None)
            if progress_msg:
                try:
                    await safe_delete(progress_msg)
                    logger.info("Progress message deleted", extra=logger_context)
                except Exception as e:
                    logger.warning(f"Failed to delete progress message: {e}", extra=logger_context)

        result = (
            f"<b><u>✅ Broadcast Completed</u></b>\n\n"
            f"<b>👥 Total:</b> <code>{total}</code>\n"
            f"<b>✅ Sent:</b> <code>{successful}</code>\n"
            f"<b>🚫 Blocked:</b> <code>{blocked}</code>\n"
            f"<b>🗑️ Deactivated:</b> <code>{deactivated}</code>\n"
            f"<b>🔍 Invalid:</b> <code>{invalid}</code>\n"
            f"<b>🚷 Forbidden:</b> <code>{forbidden}</code>\n"
            f"<b>⚠️ Failed:</b> <code>{failed}</code>"
        )
        try:
            await safe_reply(
                message,
                result,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Close", callback_data="close")]])
            )
            logger.info(f"Broadcast completed: {successful}/{total} successful", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send final broadcast result: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to send broadcast results.")

    except Exception as e:
        logger.error(f"Unexpected error in send_broadcast: {e}", extra=logger_context)
        await safe_reply(message, "❌ Unexpected error during broadcast initialization.")
        broadcast_status["running"] = False
        spam_block.pop(user_id, None)

@Client.on_callback_query(filters.regex("cancel_bcast"))
async def cancel_broadcast(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        if callback_query.from_user.id not in ADMINS:
            logger.warning("Non-admin attempted to cancel broadcast", extra=logger_context)
            await callback_query.answer("❌ Only admins can cancel broadcasts.", show_alert=True)
            return

        broadcast_status["running"] = False
        try:
            await safe_edit(callback_query.message, "❌ Broadcast cancelled by admin.")
            logger.info("Broadcast cancelled", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to update cancellation message: {e}", extra=logger_context)
            await callback_query.answer("❌ Broadcast cancelled, but failed to update message.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in cancel_broadcast: {e}", extra=logger_context)
        await callback_query.answer("❌ Failed to process cancellation request.", show_alert=True)

@Client.on_callback_query(filters.regex("close"))
async def close_broadcast(client: Client, callback_query):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        await callback_query.message.delete()
        logger.info("Broadcast message closed", extra=logger_context)
    except RPCError as e:
        logger.warning(f"RPCError in close_broadcast: {e}", extra=logger_context)
        await callback_query.answer("❌ Failed to close message due to Telegram error.", show_alert=True)
    except Exception as e:
        logger.error(f"Unexpected error in close_broadcast: {e}", extra=logger_context)
        await callback_query.answer("❌ Failed to close message.", show_alert=True)

async def safe_reply(message: Message, text: str, reply_markup=None):
    try:
        return await message.reply_text(text, reply_markup=reply_markup)
    except RPCError as e:
        logger.warning(f"[safe_reply] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

async def safe_edit(message: Message, text: str, reply_markup=None):
    if not message:
        return
    try:
        await message.edit_text(text, reply_markup=reply_markup)
    except RPCError as e:
        logger.warning(f"[safe_edit] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_edit] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

async def safe_delete(message: Message):
    if not message:
        return
    try:
        await message.delete()
        logger.info("Message deleted", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except RPCError as e:
        logger.warning(f"[safe_delete] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_delete] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
