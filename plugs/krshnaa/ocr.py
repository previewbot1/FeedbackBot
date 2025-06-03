import requests
import os
import asyncio
import time
import logging
from io import BytesIO
from datetime import datetime
import pytz
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, RPCError

OCR_API_KEY = "K88499187988957" #http://ocr.space/
STICKER_ID = "CAACAgIAAxkDAAIGgGg_EUobC_9p27y5wTzevjcg5mggAAInDwAC_aKoSeBMW_mxwQ_gHgQ"
DEFAULT_OCR_FILENAME = "nx_ocr.txt"
LOG_CHANNEL = int(os.getenv("LOG", "-1002535768083"))
MAX_TEXT_FILE_SIZE = 50 * 1024
MAX_MESSAGE_LENGTH = 4096
spam_block = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)

@Client.on_message(filters.command("ocr") & filters.reply)
async def ocr_handler(client: Client, message: Message):
    user_id = message.from_user.id
    now = time.time()
    if user_id in spam_block and now - spam_block[user_id] < 10:
        logging.info(f"Spam blocked: user {user_id}")
        return await safe_reply(message, "🛑 Please wait before using /ocr again.")
    spam_block[user_id] = now

    reply = message.reply_to_message
    if not reply or (not reply.photo and not reply.document):
        logging.info(f"Invalid reply for OCR: user {user_id}")
        return await safe_reply(message, "❌ Reply to an image or .txt file with /ocr to extract text.")

    processing, sticker, file_path = None, None, None

    try:
        processing = await safe_reply(message, "⏳ Processing, please wait...")
        sticker = await safe_sticker(message, STICKER_ID)
    except Exception as e:
        logging.warning(f"Failed to send processing or sticker: {e}")

    try:
        if reply.document and reply.document.mime_type == "text/plain":
            if reply.document.file_size > MAX_TEXT_FILE_SIZE:
                logging.info(f"Text file too large: {reply.document.file_size} bytes, user {user_id}")
                return await safe_reply(message, "❌ Text file size exceeds 50KB limit.")

            try:
                file_path = await client.download_media(reply)
                logging.info(f"TXT file downloaded: {file_path}, user {user_id}")
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        text = f.read().strip()
                except UnicodeDecodeError:
                    with open(file_path, "r", encoding="latin-1") as f:
                        text = f.read().strip()
                except Exception as e:
                    logging.error(f"Failed to read text file: {e}, user {user_id}")
                    return await safe_reply(message, f"❌ Failed to read .txt file:\n`{e}`")

                if not text:
                    logging.info(f"Empty text file: user {user_id}")
                    return await safe_reply(message, "📭 The .txt file is empty.")

                await send_extracted_text(client, message, text, user_id)
                return

            except FloodWait as fw:
                logging.warning(f"FloodWait during download: {fw.value}s, user {user_id}")
                await asyncio.sleep(fw.value)
                return await safe_reply(message, "⚠️ Flood wait triggered. Try again later.")
            except Exception as e:
                logging.error(f"Failed to process text file: {e}, user {user_id}")
                return await safe_reply(message, f"❌ Failed to process .txt file:\n`{e}`")

        if reply.photo:
            try:
                file_path = await client.download_media(reply)
                logging.info(f"Image downloaded: {file_path}, user {user_id}")
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                file_path = await client.download_media(reply)
                logging.info(f"Image downloaded after FloodWait: {file_path}, user {user_id}")
            except Exception as e:
                logging.error(f"Image download failed: {e}, user {user_id}")
                return await safe_reply(message, f"❌ Failed to download image:\n`{e}`")

            try:
                with open(file_path, "rb") as f:
                    response = requests.post(
                        "https://api.ocr.space/parse/image",
                        files={"filename": f},
                        data={"apikey": OCR_API_KEY, "language": "eng", "isOverlayRequired": False},
                        timeout=30
                    )
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logging.error(f"OCR API request failed: {e}, user {user_id}")
                return await safe_reply(message, f"❌ OCR API request failed:\n`{e}`")

            try:
                result = response.json()
            except ValueError as e:
                logging.error(f"Failed to parse OCR response: {e}, user {user_id}")
                return await safe_reply(message, "❌ Failed to parse OCR API response.")

            if result.get("IsErroredOnProcessing"):
                error_msg = result.get("ErrorMessage", ["Unknown error"])[0]
                logging.warning(f"OCR API error: {error_msg}, user {user_id}")
                return await safe_reply(message, f"❌ OCR API Error:\n`{error_msg}`")

            text = result.get("ParsedResults", [{}])[0].get("ParsedText", "").strip()
            if not text:
                logging.info(f"No text found in OCR: user {user_id}")
                return await safe_reply(message, "🔍 No readable text found in the image.")

            await send_extracted_text(client, message, text, user_id)
            return

        logging.info(f"Unsupported file type: user {user_id}")
        return await safe_reply(message, "❌ Unsupported file type. Send image or .txt only.")

    except FloodWait as fw:
        logging.warning(f"FloodWait: {fw.value}s, user {user_id}")
        await asyncio.sleep(fw.value)
        return await safe_reply(message, "⚠️ Flood wait triggered. Try again later.")
    except Exception as e:
        logging.error(f"Fatal error in OCR handler: {e}, user {user_id}")
        return await safe_reply(message, f"❌ Unexpected error:\n`{e}`")
    finally:
        try:
            if processing: await processing.delete()
            if sticker: await sticker.delete()
            if file_path and os.path.exists(file_path): os.remove(file_path)
            logging.info(f"Cleanup completed: user {user_id}")
        except Exception as e:
            logging.warning(f"Cleanup failed: {e}, user {user_id}")

async def send_extracted_text(client, message, text, user_id):
    try:
        user = message.from_user
        name = (user.first_name or "") + (f" {user.last_name}" if user.last_name else "")
        mention = f"@{user.username}" if user.username else "No username"
        india_time = datetime.utcnow().replace(tzinfo=pytz.utc).astimezone(pytz.timezone("Asia/Kolkata"))
        log_text = f"""🧾 **New Text Extracted**
👤 **User:** [{name}](tg://user?id={user.id}) (`{user.id}`)
🔗 **Username:** {mention}
🕒 **Time:** {india_time.strftime('%Y-%m-%d %I:%M:%S %p')} IST

📄 **Content:** 
`{text[:3900]}`"""

        try:
            await client.send_message(LOG_CHANNEL, log_text)
            logging.info(f"Log sent for user {user_id}")
        except Exception as e:
            logging.warning(f"Failed to send log: {e}, user {user_id}")

        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Updates ⚡", url="https://t.me/NxMirror")],
            [InlineKeyboardButton("❌ Close", callback_data="close_ocr_text")]
        ])

        if len(text) <= MAX_MESSAGE_LENGTH:
            try:
                await message.reply(f"`{text}`", reply_markup=buttons)
                logging.info(f"Sent single message to user {user_id}")
            except Exception as e:
                logging.error(f"Failed to send single message: {e}, user {user_id}")
                await safe_reply(message, f"❌ Failed to send message:\n`{e}`")
        else:
            chunks = []
            current_chunk = ""
            for word in text.split():
                if len(current_chunk) + len(word) + 1 <= MAX_MESSAGE_LENGTH - 2:
                    current_chunk += (word + " ")
                else:
                    chunks.append(f"`{current_chunk.strip()}`")
                    current_chunk = word + " "
            if current_chunk:
                chunks.append(f"`{current_chunk.strip()}`")

            for i, chunk in enumerate(chunks, 1):
                try:
                    await message.reply(chunk, reply_markup=buttons if i == len(chunks) else None)
                    logging.info(f"Sent chunk {i}/{len(chunks)} to user {user_id}")
                    await asyncio.sleep(0.5)
                except FloodWait as fw:
                    logging.warning(f"FloodWait during chunk sending: {fw.value}s, user {user_id}")
                    await asyncio.sleep(fw.value)
                    await message.reply(chunk, reply_markup=buttons if i == len(chunks) else None)
                except Exception as e:
                    logging.error(f"Failed to send chunk {i}: {e}, user {user_id}")
                    await safe_reply(message, f"❌ Failed to send chunk {i}:\n`{e}`")

    except Exception as e:
        logging.error(f"Failed in send_extracted_text: {e}, user {user_id}")
        await safe_reply(message, f"❌ Failed to process extracted text:\n`{e}`")

async def safe_reply(msg: Message, text: str):
    try:
        return await msg.reply(text)
    except RPCError as e:
        logging.warning(f"[safe_reply] RPCError: {e}")
        return None
    except Exception as e:
        logging.error(f"[safe_reply] Unexpected error: {e}")
        return None

async def safe_sticker(msg: Message, sticker_id: str):
    try:
        return await msg.reply_sticker(sticker_id)
    except RPCError as e:
        logging.warning(f"[safe_sticker] RPCError: {e}")
        return None
    except Exception as e:
        logging.error(f"[safe_sticker] Unexpected error: {e}")
        return None

@Client.on_callback_query(filters.regex("close_ocr_text"))
async def close_callback(client: Client, callback_query: CallbackQuery):
    try:
        await callback_query.message.delete()
        logging.info(f"Message deleted via close button: user {callback_query.from_user.id}")
    except Exception as e:
        logging.warning(f"Failed to delete message: {e}, user {callback_query.from_user.id}")
        try:
            await callback_query.answer("⚠️ Failed to delete message", show_alert=True)
        except Exception as e:
            logging.error(f"Failed to send callback answer: {e}, user {callback_query.from_user.id}")
