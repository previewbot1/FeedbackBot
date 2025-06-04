import logging
import aiohttp
from aiohttp import FormData
import asyncio
import math
import os
import tempfile
import traceback
from io import BytesIO
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
import emoji

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TOKEN")
if not BOT_TOKEN:
    logging.error("Bot token not found in environment", extra={"user_id": 0})
    raise ValueError("TOKEN environment variable is required")

async def validate_emoji(emoji_str: str):
    return emoji.is_emoji(emoji_str)

async def resize_image(file_path: str):
    im = Image.open(file_path)
    maxsize = (512, 512)
    if im.width < 512 and im.height < 512:
        scale = 512 / max(im.width, im.height)
        new_width = math.floor(im.width * scale)
        new_height = math.floor(im.height * scale)
        im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
    else:
        im.thumbnail(maxsize, Image.Resampling.LANCZOS)
    im.save(file_path, "PNG")

async def telegram_api(method: str, data=None, files=None, retry=0):
    async with aiohttp.ClientSession() as session:
        try:
            form = FormData()
            if data:
                for k, v in data.items():
                    form.add_field(k, str(v))
            if files:
                for k, f in files.items():
                    form.add_field(k, f, filename=getattr(f, 'name', 'file.png'), content_type='application/octet-stream')

            async with session.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", data=form) as response:
                if response.status == 429 and retry < 3:
                    wait = 2 ** retry
                    logging.warning(f"Rate limit hit, retrying after {wait}s")
                    await asyncio.sleep(wait)
                    return await telegram_api(method, data, files, retry + 1)
                return await response.json()
        except aiohttp.ClientError as e:
            logging.error(f"API request failed: {e}")
            raise

@Client.on_message(filters.command("stickerid") & filters.private)
async def sticker_id(client: Client, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.sticker:
            await message.reply(f"Sticker ID:\n`{message.reply_to_message.sticker.file_id}`")
        else:
            await message.reply("Please reply to a sticker to get its ID.")
    except Exception as e:
        logging.error(f"Error in sticker_id: {traceback.format_exc()}", extra={"user_id": message.from_user.id})
        await message.reply("An error occurred.")

@Client.on_message(filters.command("getsticker") & filters.private)
async def get_sticker(client: Client, message: Message):
    file_path = None
    try:
        if message.reply_to_message and message.reply_to_message.sticker:
            sticker = message.reply_to_message.sticker
            if sticker.is_animated or sticker.is_video:
                await message.reply("Can’t download animated or video stickers as PNG.")
                return
            file_id = sticker.file_id
            with tempfile.NamedTemporaryFile(delete=False, suffix=".webp") as tmp:
                file_path = await client.download_media(file_id, file_name=tmp.name)
            im = Image.open(file_path)
            if im.format not in ["PNG", "WEBP"]:
                await message.reply("Unsupported sticker format.")
                return
            output_path = "sticker.png"
            im.convert("RGBA").save(output_path, "PNG")
            await client.send_document(message.chat.id, output_path, file_name="sticker.png")
        else:
            await message.reply("Please reply to a sticker to get its PNG.")
    except Exception as e:
        logging.error(f"Error in get_sticker: {traceback.format_exc()}", extra={"user_id": message.from_user.id})
        await message.reply("An error occurred.")
    finally:
        for path in filter(None, [file_path, "sticker.png"]):
            if os.path.exists(path):
                os.remove(path)

@Client.on_message(filters.command("pack") & filters.private)
async def pack_sticker(client: Client, message: Message):
    user = message.from_user
    packnum = 0
    packname = f"a{user.id}_by_{client.me.username}"
    max_stickers = 120
    sticker_emoji = "🤔"
    args = message.command[1:]

    try:
        if args and await validate_emoji(args[0]):
            sticker_emoji = args[0]

        if message.reply_to_message:
            if message.reply_to_message.sticker:
                file_id = message.reply_to_message.sticker.file_id
                if message.reply_to_message.sticker.emoji and not args:
                    sticker_emoji = message.reply_to_message.sticker.emoji
                use_file = False
            elif message.reply_to_message.photo:
                file_id = message.reply_to_message.photo[-1].file_id
                use_file = True
            elif message.reply_to_message.document:
                file_id = message.reply_to_message.document.file_id
                use_file = True
            else:
                await message.reply("Reply to a sticker, photo, or image to pack it.")
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                file_path = await client.download_media(file_id, file_name=tmp.name)

            if use_file:
                await resize_image(file_path)

            while True:
                response = await telegram_api("getStickerSet", {"name": packname})
                if response.get("ok") and len(response["result"]["stickers"]) >= max_stickers:
                    packnum += 1
                    packname = f"a{packnum}_{user.id}_by_{client.me.username}"
                else:
                    break

            data = {"user_id": user.id, "name": packname, "emojis": sticker_emoji}
            files = None
            if not use_file:
                data["png_sticker"] = file_id
            else:
                files = {"png_sticker": open(file_path, "rb")}

            response = await telegram_api("addStickerToSet", data, files)
            if response.get("ok"):
                await message.reply(
                    f"Sticker added to [pack](t.me/addstickers/{packname})\nEmoji: {sticker_emoji}",
                    disable_web_page_preview=True
                )
            elif response.get("error_code") == 400 and "STICKERSET_INVALID" in response.get("description", ""):
                name = user.first_name[:50]
                data["title"] = f"{name}'s Sticker Pack{' ' + str(packnum) if packnum > 0 else ''}"
                response = await telegram_api("createNewStickerSet", data, files)
                if response.get("ok"):
                    await message.reply(
                        f"Sticker pack created: [pack](t.me/addstickers/{packname})\nEmoji: {sticker_emoji}",
                        disable_web_page_preview=True
                    )
                else:
                    await message.reply("Failed to create sticker pack.")
                    logging.error(f"Create sticker set failed: {response}", extra={"user_id": user.id})
            elif "Invalid sticker emojis" in response.get("description", ""):
                await message.reply("Invalid emoji.")
            elif "Stickers_too_much" in response.get("description", ""):
                await message.reply("Max pack size reached.")
            else:
                await message.reply("An error occurred.")
                logging.error(f"Add sticker failed: {response}", extra={"user_id": user.id})
        else:
            packs = "Reply to a sticker or image to pack it!\nYour packs:\n"
            valid_packs = []
            for i in range(packnum + 1):
                pack = f"a{user.id}_by_{client.me.username}" if i == 0 else f"a{i}_{user.id}_by_{client.me.username}"
                response = await telegram_api("getStickerSet", {"name": pack})
                if response.get("ok"):
                    valid_packs.append(f"[pack{i if i > 0 else ''}](t.me/addstickers/{pack})")
            packs += "\n".join(valid_packs) if valid_packs else "No packs found."
            await message.reply(packs, disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Error in pack_sticker: {traceback.format_exc()}", extra={"user_id": user.id})
        await message.reply("An error occurred.")
    finally:
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
