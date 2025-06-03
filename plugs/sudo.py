import asyncio
import os
import shutil
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import Message, User, BotCommand, BotCommandScopeDefault, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, RPCError
from pymongo.errors import PyMongoError
from utils.database import add_log_usage, user_exists, add_keyword_response, get_keyword_response_map, delete_keyword, get_all_keywords_with_responses, clear_keywords, add_callback_response, get_callback_response, get_all_callbacks, delete_callback, clear_callbacks
from utils.buttons import parse_buttons

logging.basicConfig(
    level=logging.INFO,
    filename=os.getenv("LOG_FILE", "bot.log"),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]

spam_block = {}
LOGS_RATE_LIMIT_SECONDS = 30
SEND_RATE_LIMIT_SECONDS = 30
COMMANDS_RATE_LIMIT_SECONDS = 30
USERS_RATE_LIMIT_SECONDS = 30

Bot_cmds = {
    "start": "Start the bot",
    "help": "Get Help Guild",
    "buy": "Checkout Available Services",
    "alive": "Check if bot is alive",
    "ping": "Check bot latency",
    "system": "Show system info",
    "id": "Get user ID details",
    "info": "Get user profile info",
    "img": "Upload image to cloud",
    "ocr": "IMAGE to TEXT & txt to TEXT",
    "telegraphtxt": "Upload Text on Telegraph",
    "telegraph": "Upload Images on Telegraph",
    "stickerid": "Get sticker ID",
    "getsticker": "Get sticker details",
    "addservice": "Add a Product in selling list (admin)",
    "editservice": "Edit Prodects Details (admin)",
    "removeservice": "Remove Products From List (admin)",
    "listservices": "List All Products (admin)",
    "cleanservices": "Remove All Products (admin)",
    "wiki": "Search on Wikipedia",
    "news": "Get Trading News",
    "users": "Get total number of users (admin)",
    "send": "Send message to user (admin)",
    "broadcast": "Broadcast message (admin)",
    "logs": "Get bot logs (admin)",
    "commands": "Update bot commands (admin)",
    "getcmds": "Get List of Available Commands (admin)",
    "keyword": "Add keyword auto-reply (admin)",
    "keywords": "List all keywords (admin)",
    "delkeyword": "Delete a keyword (admin)",
    "clearkeywords": "Clear all keywords (admin)",
    "save": "Save callback data and response (admin)",
    "listcallbacks": "List all callbacks (admin)",
    "delcallback": "Delete a callback (admin)",
    "clearcallbacks": "Clear all callbacks (admin)"
}

def add_user_context(user_id: int) -> dict:
    return {"user_id": user_id if user_id else "System"}

async def safe_reply(message, text: str, reply_markup=None, parse_mode=None, quote: bool = False):
    if not message:
        return
    try:
        return await message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode, quote=quote)
    except Exception as e:
        try:
            logger.error(f"[safe_reply] Error replying: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        except:
            logger.error(f"[safe_reply] Error replying and logging failed")

async def safe_reply_document(message, document: str, caption: str = None, quote: bool = False):
    if not message:
        return
    try:
        return await message.reply_document(document=document, caption=caption, quote=quote)
    except FloodWait as fw:
        try:
            await asyncio.sleep(fw.value)
            return await message.reply_document(document=document, caption=caption, quote=quote)
        except Exception as e:
            try:
                logger.error(f"[safe_reply_document] Retry after FloodWait failed: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
            except:
                logger.error("[safe_reply_document] Logging failure in FloodWait retry")
    except Exception as e:
        try:
            logger.error(f"[safe_reply_document] Error sending document: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        except:
            logger.error("[safe_reply_document] Logging failure")

@Client.on_message(filters.command("logs") & filters.user(ADMINS) & filters.private)
async def log_file(client, message):
    user_id = getattr(message.from_user, "id", 0)
    context = add_user_context(user_id)
    now = asyncio.get_event_loop().time()

    try:
        if user_id in spam_block and now - spam_block[user_id] < LOGS_RATE_LIMIT_SECONDS:
            await safe_reply(message, "🖐 Please wait before using /logs again.", quote=True)
            return
        spam_block[user_id] = now
    except Exception as e:
        try:
            logger.error(f"Rate-limit check failed: {e}", extra=context)
        except:
            logger.error("Rate-limit check and logging both failed")
        return

    log_path = os.getenv("LOG_FILE", "bot.log")
    try:
        if not os.path.exists(log_path):
            await safe_reply(message, "🚫 Log file not found.", quote=True)
            return
    except Exception as e:
        try:
            logger.error(f"Log existence check failed: {e}", extra=context)
        except:
            logger.error("Log existence check and logging both failed")
        return

    try:
        if os.path.getsize(log_path) > 50 * 1024 * 1024:
            await safe_reply(message, "⚠️ Log file too large to send.", quote=True)
            return
    except Exception as e:
        try:
            logger.error(f"Log size check failed: {e}", extra=context)
        except:
            logger.error("Log size check and logging both failed")
        return

    temp_log = f"nxmirror_{user_id}_{int(now)}.log"
    try:
        shutil.copy(log_path, temp_log)
    except Exception as e:
        try:
            logger.error(f"Copy to temp failed: {e}", extra=context)
        except:
            logger.error("Temp copy and logging both failed")
        await safe_reply(message, "❌ Failed to prepare log file.", quote=True)
        return

    response_msg = None
    try:
        response_msg = await safe_reply_document(message, document=temp_log, caption="📜 Bot log file", quote=True)
        if not response_msg:
            await safe_reply(message, "❌ Failed to send log file.", quote=True)
            return
    except Exception as e:
        try:
            logger.error(f"Document send failed: {e}", extra=context)
        except:
            logger.error("Document send and logging both failed")
        await safe_reply(message, "❌ Failed to send log file.", quote=True)
        return

    try:
        await add_log_usage(user_id, "logs")
    except Exception as e:
        try:
            logger.error(f"Logging usage failed: {e}", extra=context)
        except:
            logger.error("Logging usage and logging itself both failed")

    try:
        await asyncio.sleep(60)
        try:
            await safe_delete(response_msg)
            await safe_delete(message)
        except Exception as e:
            try:
                logger.warning(f"Post-send deletion failed: {e}", extra=context)
            except:
                logger.warning("Post-send deletion and logging failed")
    except Exception as e:
        try:
            logger.error(f"Sleep and delete scheduling failed: {e}", extra=context)
        except:
            logger.error("Sleep/delete scheduling and logging failed")

    try:
        if os.path.exists(temp_log):
            os.remove(temp_log)
    except Exception as e:
        try:
            logger.warning(f"Temp file removal failed: {e}", extra=context)
        except:
            logger.warning("Temp file removal and logging both failed")

    try:
        spam_block.pop(user_id, None)
    except Exception as e:
        try:
            logger.debug(f"Rate-limit map cleanup failed: {e}", extra=context)
        except:
            logger.debug("Rate-limit cleanup and logging failed")

async def user_exists(user_id: int) -> bool:
    return True  # Mock;
    
async def safe_copy(message: Message, chat_id: int):
    if not message:
        return None
    try:
        return await message.copy(chat_id=chat_id)
    except RPCError as e:
        logger.warning(f"[safe_copy] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_copy] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

@Client.on_message(filters.command("send") & filters.user(ADMINS) & filters.private)
async def send_message(client: Client, message: Message):
    user_id = getattr(message.from_user, "id", 0)
    logger_context = add_user_context(user_id)
    response_msg = None

    try:
        try:
            now = asyncio.get_event_loop().time()
        except Exception as e:
            logger.critical(f"Failed to get current time: {e}", extra=logger_context)
            await safe_reply(message, "❌ Internal time failure. Try again.", quote=True)
            return

        if user_id in spam_block:
            try:
                last_time = spam_block[user_id]
                if now - last_time < SEND_RATE_LIMIT_SECONDS:
                    logger.info("Rate limit triggered", extra=logger_context)
                    await safe_reply(message, "🖐 Please wait before using /send again.", quote=True)
                    return
            except Exception as e:
                logger.error(f"Rate limit check failed: {e}", extra=logger_context)
        spam_block[user_id] = now

        try:
            if not message.reply_to_message:
                await safe_reply(
                    message,
                    "📨 <b>Please reply to a message and provide a target user ID. Example: /send user_id</b>",
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
                return
        except Exception as e:
            logger.error(f"Failed to check reply message: {e}", extra=logger_context)
            await safe_reply(message, "❌ Internal message context error.", quote=True)
            return

        try:
            target_text = message.text.split()[1]
            target_id = int(target_text)
        except IndexError:
            await safe_reply(
                message,
                "❌ <b>Missing user ID. Usage: /send user_id</b>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return
        except ValueError:
            await safe_reply(
                message,
                "❌ <b>Invalid user ID format. Use a number.</b>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return
        except Exception as e:
            logger.error(f"Failed to parse user ID: {e}", extra=logger_context)
            await safe_reply(message, "❌ Unknown user ID error.", quote=True)
            return

        try:
            exists = await user_exists(target_id)
            if not exists:
                await safe_reply(
                    message,
                    "🚫 <b>This user has not started the bot yet!</b>",
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
                return
        except Exception as e:
            logger.error(f"user_exists check failed: {e}", extra=logger_context)
            await safe_reply(message, "❌ Error checking user presence.", quote=True)
            return

        copied_msg = None
        try:
            copied_msg = await safe_copy(message.reply_to_message, target_id)
        except FloodWait as fw:
            try:
                logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
                await asyncio.sleep(fw.value)
                copied_msg = await safe_copy(message.reply_to_message, target_id)
            except Exception as e:
                logger.error(f"Retry after FloodWait failed: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"safe_copy exception: {e}", extra=logger_context)

        if copied_msg is None:
            await safe_reply(
                message,
                "❌ Failed to deliver the message to the target user.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return

        user_mention = f"User {target_id}"
        try:
            user = await client.get_users(target_id)
            if isinstance(user, User):
                user_mention = user.mention
        except Exception as e:
            logger.warning(f"Failed to get user mention: {e}", extra=logger_context)

        try:
            response_msg = await safe_reply(
                message,
                f"✅ <b>Message sent successfully to {user_mention}.</b>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info(f"Message delivered to {target_id}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to send success reply: {e}", extra=logger_context)

        try:
            await add_log_usage(user_id, "send")
            logger.info("Usage log added", extra=logger_context)
        except Exception as e:
            logger.error(f"Logging usage failed: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                if response_msg:
                    await safe_delete(response_msg)
                await safe_delete(message)
                logger.info("Cleanup complete", extra=logger_context)
            except Exception as e:
                logger.warning(f"Cleanup failed: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Sleep or delete wrapper failed: {e}", extra=logger_context)

    except Exception as e:
        logger.critical(f"Unhandled error in send_message: {e}", extra=logger_context)
        try:
            await safe_reply(message, "❌ A critical error occurred while handling your request.", quote=True)
        except:
            pass
    finally:
        try:
            if user_id in spam_block:
                spam_block.pop(user_id, None)
                logger.debug("Rate limiter cleared", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to clear rate limit: {e}", extra=logger_context)

async def safe_set_bot_commands(client: Client, commands: list) -> bool:
    try:
        if not isinstance(commands, list):
            logger.error("[safe_set_bot_commands] 'commands' is not a list", extra=add_user_context(0))
            return False
        if not all(isinstance(cmd, BotCommand) for cmd in commands):
            logger.error("[safe_set_bot_commands] One or more invalid BotCommand objects", extra=add_user_context(0))
            return False

        await client.set_bot_commands(commands)
        return True

    except FloodWait as fw:
        logger.warning(f"[safe_set_bot_commands] FloodWait: {fw.value}s", extra=add_user_context(0))
        try:
            await asyncio.sleep(fw.value)
            await client.set_bot_commands(commands)
            return True
        except Exception as e:
            logger.error(f"[safe_set_bot_commands] Retry after FloodWait failed: {e}", extra=add_user_context(0))
            return False

    except RPCError as e:
        logger.warning(f"[safe_set_bot_commands] RPCError: {e}", extra=add_user_context(0))
        return False

    except Exception as e:
        logger.error(f"[safe_set_bot_commands] Unexpected error: {e}", extra=add_user_context(0))
        return False


@Client.on_message(filters.command("commands") & filters.user(ADMINS) & filters.private)
async def set_commands(client: Client, message: Message):
    user_id = getattr(message.from_user, "id", 0)
    logger_context = add_user_context(user_id)
    response_msg = None

    try:
        try:
            now = asyncio.get_event_loop().time()
        except Exception as e:
            logger.critical(f"Failed to get current time: {e}", extra=logger_context)
            await safe_reply(message, "❌ Internal error: time failed.", quote=True)
            return

        if user_id in spam_block:
            try:
                if now - spam_block[user_id] < COMMANDS_RATE_LIMIT_SECONDS:
                    logger.info("Rate limit hit for /commands", extra=logger_context)
                    await safe_reply(message, "🖐 Please wait before using /commands again.", quote=True)
                    return
            except Exception as e:
                logger.warning(f"Rate limit check failed: {e}", extra=logger_context)

        spam_block[user_id] = now
        logger.info("Commands command triggered", extra=logger_context)

        try:
            commands = []
            for cmd, desc in Bot_cmds.items():
                try:
                    if not (1 <= len(cmd) <= 32 and 1 <= len(desc) <= 256):
                        logger.warning(f"Invalid command or description: {cmd}", extra=logger_context)
                        continue
                    commands.append(BotCommand(cmd.lower().lstrip("/"), desc))
                except Exception as e:
                    logger.warning(f"Command prep error [{cmd}]: {e}", extra=logger_context)
            if not commands:
                await safe_reply(
                    message,
                    "❌ No valid commands found to set.",
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
                return
        except Exception as e:
            logger.error(f"Command list creation failed: {e}", extra=logger_context)
            await safe_reply(
                message,
                "❌ Failed to prepare bot commands.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return

        try:
            success = await safe_set_bot_commands(client, commands)
        except Exception as e:
            logger.error(f"safe_set_bot_commands call failed: {e}", extra=logger_context)
            success = False

        if not success:
            await safe_reply(
                message,
                "❌ Failed to update bot commands.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return

        try:
            response_msg = await safe_reply(
                message,
                "✅ <b>Bot commands updated successfully</b>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info("Bot commands updated successfully", extra=logger_context)
        except Exception as e:
            logger.error(f"Confirmation reply failed: {e}", extra=logger_context)

        try:
            await add_log_usage(user_id, "commands")
            logger.info("Usage log recorded for /commands", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log command usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                if response_msg:
                    try:
                        await safe_delete(response_msg)
                    except Exception as e:
                        logger.warning(f"Failed to delete response_msg: {e}", extra=logger_context)
                try:
                    await safe_delete(message)
                except Exception as e:
                    logger.warning(f"Failed to delete original message: {e}", extra=logger_context)
                logger.info("Messages deleted after 60s", extra=logger_context)
            except Exception as e:
                logger.warning(f"Delete wrapper failed: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Sleep and delete failed: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal exception in set_commands: {e}", extra=logger_context)
        try:
            await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
        except:
            pass
    finally:
        try:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for /commands", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to clear rate limit: {e}", extra=logger_context)

async def safe_mongo_count(collection, query: dict):
    try:
        return await collection.count_documents(query)
    except PyMongoError as e:
        logger.error(f"[safe_mongo_count] MongoDB error: {e}", extra=add_user_context(0))
        return None
    except Exception as e:
        logger.error(f"[safe_mongo_count] Unexpected error: {e}", extra=add_user_context(0))
        return None 


async def safe_get_bot_commands(client: Client, scope=BotCommandScopeDefault()):
    try:
        return await client.get_bot_commands(scope=scope)
    except RPCError as e:
        logger.warning(f"[safe_get_bot_commands] RPCError: {e}", extra=add_user_context(0))
        return None
    except Exception as e:
        logger.error(f"[safe_get_bot_commands] Unexpected error: {e}", extra=add_user_context(0))
        return None

@Client.on_message(filters.command("getcmds") & filters.user(ADMINS) & filters.private)
async def get_commands(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)
    response_msg = None

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < COMMANDS_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for getcmds command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /getcmds again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Get commands command triggered", extra=logger_context)
        commands = await safe_get_bot_commands(client)
        if commands is None:
            response_msg = await safe_reply(
                message,
                "❌ Failed to fetch bot commands.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return
        if not commands:
            response_msg = await safe_reply(
                message,
                "⚠️ <b>No commands found for this bot.</b>",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info("No bot commands present", extra=logger_context)
            return

        try:
            formatted = "\n".join([f"• <code>/{cmd.command}</code> - {cmd.description}" for cmd in commands])
        except Exception as e:
            logger.error(f"Command formatting error: {e}", extra=logger_context)
            formatted = "⚠️ Failed to format command list."

        buttons = [[InlineKeyboardButton("🔒 Close", callback_data="close_getcmds")]]
        response_msg = await safe_reply(
            message,
            f"🤖 <b>Current Bot Commands:</b>\n\n{formatted}",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        if not response_msg:
            await safe_reply(message, "❌ Failed to send command list.", parse_mode=enums.ParseMode.HTML, quote=True)
            return

        logger.info("Commands list sent", extra=logger_context)

        try:
            await add_log_usage(user_id, "getcmds")
            logger.info("Get commands usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                if response_msg:
                    await safe_delete(response_msg)
                await safe_delete(message)
                logger.info("Get commands messages deleted after 60s", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete messages: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Sleep block failed: {e}", extra=logger_context)

    except FloodWait as fw:
        logger.warning(f"FloodWait: {fw.value}s", extra=logger_context)
        try:
            await asyncio.sleep(fw.value)
            commands = await safe_get_bot_commands(client)
            if commands is None or not commands:
                await safe_reply(
                    message,
                    "❌ Failed to fetch commands after retry.",
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
                return
            try:
                formatted = "\n".join([f"• <code>/{cmd.command}</code> - {cmd.description}" for cmd in commands])
            except Exception as e:
                logger.error(f"Formatting after retry failed: {e}", extra=logger_context)
                formatted = "⚠️ Failed to format command list after retry."

            buttons = [[InlineKeyboardButton("🔒 Close", callback_data="close_getcmds")]]
            response_msg = await safe_reply(
                message,
                f"🤖 <b>Current Bot Commands:</b>\n\n{formatted}",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info("Commands sent after FloodWait", extra=logger_context)

            try:
                await add_log_usage(user_id, "getcmds")
            except Exception as e:
                logger.error(f"Failed to log usage after retry: {e}", extra=logger_context)

            try:
                await asyncio.sleep(60)
                if response_msg:
                    await safe_delete(response_msg)
                await safe_delete(message)
            except Exception as e:
                logger.warning(f"Failed to delete messages after retry: {e}", extra=logger_context)

        except Exception as e:
            logger.error(f"FloodWait handling block failed: {e}", extra=logger_context)
            await safe_reply(message, "❌ An unexpected retry failure occurred.", quote=True)

    except Exception as e:
        logger.error(f"Fatal error in get_commands: {e}", extra=logger_context)
        try:
            await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
        except:
            pass
    finally:
        try:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for getcmds", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to clear rate limit: {e}", extra=logger_context)


@Client.on_callback_query(filters.regex(r"close_getcmds"))
async def close_getcmds_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < COMMANDS_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close_getcmds callback", extra=logger_context)
            try:
                await callback_query.answer("🖐 Please wait before closing.", show_alert=True)
            except:
                pass
            return
        spam_block[user_id] = now

        logger.info("Close getcmds callback triggered", extra=logger_context)
        try:
            await safe_delete(callback_query.message)
        except Exception as e:
            logger.warning(f"Failed to delete getcmds message: {e}", extra=logger_context)

        try:
            await callback_query.answer("✅ Closed successfully!")
        except Exception as e:
            logger.warning(f"Callback answer failed: {e}", extra=logger_context)

        logger.info("Getcmds message closed", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in close_getcmds_callback: {e}", extra=logger_context)
        try:
            await callback_query.answer("❌ Failed to close.", show_alert=True)
        except:
            pass
    finally:
        try:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close_getcmds", extra=logger_context)
        except Exception as e:
            logger.warning(f"Failed to clear rate limit: {e}", extra=logger_context)
            

@Client.on_message(filters.command("users") & filters.user(ADMINS) & filters.private)
async def get_users_count(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < USERS_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for users command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /users again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Users command triggered", extra=logger_context)
        from utils.database import users_collection

        try:
            total_users = await safe_mongo_count(users_collection, {})
            if total_users is None:
                await safe_reply(
                    message,
                    "❌ Failed to retrieve user statistics.",
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
                return
        except Exception as e:
            logger.error(f"Failed to access users_collection: {e}", extra=logger_context)
            await safe_reply(
                message,
                "❌ Failed to access user database.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return

        output = (
            f"<blockquote>👥 User Statistics</blockquote>\n\n"
            f"📊 <b>Total Users:</b> {total_users}"
        )
        buttons = [[InlineKeyboardButton("🔒 Close", callback_data="close_users")]]
        response_msg = await safe_reply(
            message,
            output,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        if not response_msg:
            await safe_reply(
                message,
                "❌ Failed to send user statistics.",
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            return
        logger.info(f"User statistics sent: {total_users} users", extra=logger_context)

        try:
            await add_log_usage(user_id, "users")
            logger.info("Users command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

        try:
            await asyncio.sleep(60)
            try:
                await safe_delete(response_msg)
                await safe_delete(message)
                logger.info("Users messages deleted after 60s", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete users messages: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in get_users_count: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for users", extra=logger_context)

async def safe_delete(message: Message):
    if not message:
        return
    try:
        await message.delete()
    except RPCError as e:
        logger.warning(f"[safe_delete] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_delete] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

@Client.on_callback_query(filters.regex(r"close_users")) #if don't want duplicate then- from basics import safe_delet💯
async def close_users_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < USERS_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close_users callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before closing.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Close users callback triggered", extra=logger_context)
        try:
            await safe_delete(callback_query.message)
            await callback_query.answer("✅ Closed successfully!")
            logger.info("Users message closed", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to close callback: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in close_users_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close_users", extra=logger_context)

@Client.on_message(filters.command("save") & filters.user(ADMINS) & filters.private)
async def save_callback_cmd(client: Client, message: Message):
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        return await message.reply_text(
            "❗ Usage:\n/save <data> <response text>\n\n"
            "Saves a response to be shown when a callback button with the specified data is clicked.\n"
            "To add buttons, include lines in the format:\n"
            "`Button Text - https://example.com`\n"
            "For buttons on the same row, use `&&`:\n"
            "`Button Text - https://example.com && Button Text - https://example.com`\n"
            "For callback buttons, use:\n"
            "`Button Text - callback:data`\n"
            "Example:\n/save hello Hey There What's up?\n"
            "Visit Site - https://example.com && Show Info - callback:info",
            parse_mode=enums.ParseMode.MARKDOWN
        )
    data = args[1]
    response = args[2]
    await add_callback_response(data, response)
    clean_text, reply_markup = parse_buttons(response)
    await message.reply_text(
        f"✅ Callback response saved:\n\nData: `{data}`\nResponse:\n{clean_text}",
        reply_markup=reply_markup,
        parse_mode=enums.ParseMode.MARKDOWN
    )
    await add_log_usage(message.from_user.id, "save")

@Client.on_message(filters.command("keyword") & filters.user(ADMINS) & filters.private)
async def add_keyword_cmd(client: Client, message: Message):
    try:
        logging.info(f"Received /keyword from user {message.from_user.id}")
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            return await message.reply_text(
                "❗ Usage:\n/keyword <trigger> <auto reply text>\n\n"
                "To add URL buttons, include lines in the format:\n"
                "`Button Text - https://example.com`\n"
                "For buttons on the same row, use `&&`:\n"
                "`Button Text - https://example.com && Button Text - https://example.com`\n"
                "To add callback buttons, use:\n"
                "`Button Text - callback:data`\n"
                "Example:\n/keyword hello Welcome to my bot!\n"
                "Visit Site - https://example.com && Learn More - https://example.com/more\n"
                "Show Info - callback:hello",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        keyword = args[1]
        response = args[2]
        await add_keyword_response(keyword, response)
        # Parse buttons to display in confirmation
        clean_text, reply_markup = parse_buttons(response)
        await message.reply_text(
            f"✅ Auto-reply added:\n\nTrigger: `{keyword}`\nReply:\n{clean_text}",
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )
    except Exception as e:
        logging.error(f"Error in add_keyword_cmd: {e}", exc_info=True)
        await message.reply_text(f"❌ Failed to add keyword: {str(e)}")

@Client.on_message(filters.private & filters.text & ~filters.command(list(Bot_cmds.keys())))
async def keyword_autoreply(client: Client, message: Message):
    try:
        logger.info(f"Received message from user {message.from_user.id}")
        if message.from_user and message.from_user.is_bot:
            return
        user_text = (message.text or message.caption or "").lower().strip()
        if user_text:
            keyword_map = await get_keyword_response_map()
            for keyword, response in keyword_map.items():
                if keyword in user_text:
                    clean_text, reply_markup = parse_buttons(response)
                    logger.info(f"Sending reply to {message.from_user.id}: text='{clean_text}', markup={reply_markup}")
                    await message.reply_text(
                        clean_text,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    await message.forward(LOG_CHANNEL)
                    await message.react(random.choice(script.script.EMOJIS))
                    return
            # Fallback if no keyword matches
            await message.reply_text(script.script.REPLY_MSG)
            await message.forward(LOG_CHANNEL)
            await message.react(random.choice(script.script.EMOJIS))
    except FloodWait as e:
        logger.error(f"FloodWait: Sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        await message.react(random.choice(script.script.EMOJIS))
    except ReactionInvalid as e:
        logger.error(f"Invalid reaction emoji: {e}")
    except Exception as e:
        logger.error(f"Error in keyword_autoreply: {e}", exc_info=True)
        await message.reply_text(f"Error processing your message: {str(e)}", parse_mode=enums.ParseMode.MARKDOWN)

@Client.on_message(filters.command("clearkeywords") & filters.user(ADMINS) & filters.private)
async def clear_keywords_cmd(client: Client, message: Message):
    try:
        logging.info(f"Received /clearkeywords from user {message.from_user.id}")
        await clear_keywords()
        await message.reply_text("🗑️ All keywords cleared.", parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Error clearing keywords: {e}", exc_info=True)
        await message.reply_text(f"❌ Failed to clear keywords: {str(e)}", parse_mode=enums.ParseMode.MARKDOWN)

@Client.on_message(filters.command("delkeyword") & filters.user(ADMINS) & filters.private)
async def delete_keyword_cmd(client: Client, message: Message):
    try:
        logging.info(f"Received /delkeyword from user {message.from_user.id}")
        if len(message.command) < 2:
            await message.reply_text("⚠️ Usage: `/delkeyword <keyword>`", parse_mode=enums.ParseMode.MARKDOWN)
            return
        keyword = message.command[1].lower()
        success = await delete_keyword(keyword)
        if success:
            await message.reply_text(f"✅ Keyword `{keyword}` deleted.", parse_mode=enums.ParseMode.MARKDOWN)
        else:
            await message.reply_text(f"❌ Keyword `{keyword}` not found.", parse_mode=enums.ParseMode.MARKDOWN)
        logging.info(f"Deleted keyword: {keyword}")
    except Exception as e:
        logging.error(f"Error in delete_keyword_cmd: {e}", exc_info=True)
        await message.reply_text(f"❌ Failed to delete keyword: {str(e)}", parse_mode=enums.ParseMode.MARKDOWN)

@Client.on_message(filters.command("keywords") & filters.user(ADMINS) & filters.private)
async def list_keywords(client: Client, message: Message):
    try:
        logging.info(f"Received /keywords from user {message.from_user.id}")
        keywords = await get_all_keywords_with_responses()
        if not keywords:
            return await message.reply_text("ℹ️ No keywords found.", parse_mode=enums.ParseMode.MARKDOWN)
        text = "📃 **Stored Keywords:**\n\n"
        for i, entry in enumerate(keywords, 1):
            clean_text, reply_markup = parse_buttons(entry.get('response', 'No response'))
            text += f"{i}. `{entry['keyword']}` → {clean_text}\n"
            if reply_markup:
                text += "   **Buttons:**\n"
                for row in reply_markup.inline_keyboard:
                    row_text = " && ".join(
                        [f"{button.text} - {button.url if button.url else f'callback:{button.callback_data}'}" 
                         for button in row]
                    )
                    text += f"   - `{row_text}`\n"
        await message.reply_text(text, parse_mode=enums.ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Error in list_keywords: {e}", exc_info=True)
        await message.reply_text(f"❌ Failed to fetch keyword list: {str(e)}", parse_mode=enums.ParseMode.MARKDOWN)

@Client.on_callback_query(filters.regex(r".+"))
async def handle_callback_buttons(client: Client, callback_query: CallbackQuery):
    data = callback_query.data
    logger.info(f"Handling callback: {data} by user {callback_query.from_user.id}")

    if data.startswith("product_detail:") or data in ("back_products", "close_products"):
        logger.debug(f"Skipping products callback: {data}")
        return

    if data.startswith("popup:") or data.startswith("alert:"):
        await callback_query.answer(data.split(":", 1)[1], show_alert=True)
        return

    response = await get_callback_response(data)
    if response:
        clean_text, reply_markup = parse_buttons(response)
        await callback_query.message.edit_text(
            clean_text,
            reply_markup=reply_markup,
            parse_mode=enums.ParseMode.MARKDOWN
        )
        await callback_query.answer("Message updated!")
    else:
        logger.warning(f"No response found for callback: {data}")
        await callback_query.answer("No response found for this button.", show_alert=True)

@Client.on_message(filters.command("listcallbacks") & filters.user(ADMINS) & filters.private)
async def list_callbacks(client: Client, message: Message):
    callbacks = await get_all_callbacks()
    if not callbacks:
        return await message.reply_text("ℹ️ No callbacks found.", parse_mode=enums.ParseMode.MARKDOWN)
    text = "📃 **Stored Callbacks:**\n\n"
    for i, entry in enumerate(callbacks, 1):
        clean_text, reply_markup = parse_buttons(entry.get('response', 'No response'))
        text += f"{i}. `{entry['data']}` → {clean_text}\n"
        if reply_markup:
            text += "   **Buttons:**\n"
            for row in reply_markup.inline_keyboard:
                row_text = " && ".join(
                    [f"{button.text} - {button.url if button.url else f'callback:{button.callback_data}'}" 
                     for button in row]
                )
                text += f"   - `{row_text}`\n"
    await message.reply_text(text, parse_mode=enums.ParseMode.MARKDOWN)

@Client.on_message(filters.command("delcallback") & filters.user(ADMINS) & filters.private)
async def delete_callback_cmd(client: Client, message: Message):
    if len(message.command) < 2:
        await message.reply_text("⚠️ Usage: `/delcallback <callback_data>`", parse_mode=enums.ParseMode.MARKDOWN)
        return
    callback_data = message.command[1].lower()
    success = await delete_callback(callback_data)
    if success:
        await message.reply_text(f"✅ Callback `{callback_data}` deleted.", parse_mode=enums.ParseMode.MARKDOWN)
    else:
        await message.reply_text(f"❌ Callback `{callback_data}` not found.", parse_mode=enums.ParseMode.MARKDOWN)


@Client.on_message(filters.command("clearcallbacks") & filters.user(ADMINS) & filters.private)
async def clear_callbacks_cmd(client: Client, message: Message):
    await clear_callbacks()
    await message.reply_text("🗑️ All callbacks cleared.", parse_mode=enums.ParseMode.MARKDOWN)
