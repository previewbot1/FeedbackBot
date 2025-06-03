import asyncio
import math
import os
import requests
from io import BytesIO
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
import logging

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("TOKEN")

@Client.on_message(filters.command("stickerid") & filters.private)
async def sticker_id(client: Client, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.sticker:
            await message.reply(f"Sticker ID:\n`{message.reply_to_message.sticker.file_id}`")
        else:
            await message.reply("Please reply to a sticker to get its ID.")
    except Exception as e:
        logging.error(f"Error in sticker_id: {e}")
        await message.reply("An error occurred.")

@Client.on_message(filters.command("getsticker") & filters.private)
async def get_sticker(client: Client, message: Message):
    try:
        if message.reply_to_message and message.reply_to_message.sticker:
            file_id = message.reply_to_message.sticker.file_id
            file_path = await client.download_media(file_id, file_name="sticker.png")
            await client.send_document(message.chat.id, file_path, file_name="sticker.png")
            os.remove(file_path)
        else:
            await message.reply("Please reply to a sticker to get its PNG.")
    except Exception as e:
        logging.error(f"Error in get_sticker: {e}")
        await message.reply("An error occurred.")
        if os.path.exists("sticker.png"):
            os.remove("sticker.png")

@Client.on_message(filters.command("pack") & filters.private)
async def pack_sticker(client: Client, message: Message):
    try:
        user = message.from_user
        packnum = 0
        packname = f"a{user.id}_by_{client.me.username}"
        packname_found = False
        max_stickers = 120
        sticker_emoji = "🤔"
        args = message.command[1:]

        if args:
            sticker_emoji = args[0]

        if message.reply_to_message:
            if message.reply_to_message.sticker:
                file_id = message.reply_to_message.sticker.file_id
                if message.reply_to_message.sticker.emoji and not args:
                    sticker_emoji = message.reply_to_message.sticker.emoji
            elif message.reply_to_message.photo:
                file_id = message.reply_to_message.photo[-1].file_id
            elif message.reply_to_message.document:
                file_id = message.reply_to_message.document.file_id
            else:
                await message.reply("Reply to a sticker, photo, or image to pack it.")
                return

            file_path = await client.download_media(file_id, file_name="stolensticker.png")
            im = Image.open(file_path)
            maxsize = (512, 512)
            if im.width < 512 and im.height < 512:
                if im.width > im.height:
                    scale = 512 / im.width
                    new_width = 512
                    new_height = math.floor(im.height * scale)
                else:
                    scale = 512 / im.height
                    new_width = math.floor(im.width * scale)
                    new_height = 512
                im = im.resize((new_width, new_height))
            else:
                im.thumbnail(maxsize)
            im.save(file_path, "PNG")

            while not packname_found:
                response = requests.get(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/getStickerSet",
                    params={"name": packname}
                ).json()
                if response.get("ok") and len(response["result"]["stickers"]) >= max_stickers:
                    packnum += 1
                    packname = f"a{packnum}_{user.id}_by_{client.me.username}"
                else:
                    packname_found = True

            data = {
                "user_id": user.id,
                "name": packname,
                "emojis": sticker_emoji
            }
            if message.reply_to_message.sticker:
                data["png_sticker"] = file_id
            else:
                data["png_sticker"] = open(file_path, "rb")

            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/addStickerToSet",
                files={"png_sticker": data["png_sticker"]} if not message.reply_to_message.sticker else None,
                data=data
            ).json()

            if not message.reply_to_message.sticker:
                data["png_sticker"].close()

            if response.get("ok"):
                await message.reply(
                    f"Sticker added to [pack](t.me/addstickers/{packname})\nEmoji: {sticker_emoji}",
                    disable_web_page_preview=True
                )
            elif response.get("error_code") == 400 and "STICKERSET_INVALID" in response.get("description", ""):
                name = user.first_name[:50]
                extra_version = f" {packnum}" if packnum > 0 else ""
                data["title"] = f"{name}'s Sticker Pack{extra_version}"
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/createNewStickerSet",
                    files={"png_sticker": open(file_path, "rb")} if not message.reply_to_message.sticker else None,
                    data=data
                ).json()
                if response.get("ok"):
                    await message.reply(
                        f"Sticker pack created: [pack](t.me/addstickers/{packname})\nEmoji: {sticker_emoji}",
                        disable_web_page_preview=True
                    )
                else:
                    await message.reply("Failed to create sticker pack.")
                    logging.error(f"Create sticker set failed: {response}")
            elif "Invalid sticker emojis" in response.get("description", ""):
                await message.reply("Invalid emoji.")
            elif "Stickers_too_much" in response.get("description", ""):
                await message.reply("Max pack size reached.")
            else:
                await message.reply("An error occurred.")
                logging.error(f"Add sticker failed: {response}")
        else:
            packs = "Reply to a sticker or image to pack it!\nYour packs:\n"
            if packnum > 0:
                firstpackname = f"a{user.id}_by_{client.me.username}"
                for i in range(packnum + 1):
                    pack = firstpackname if i == 0 else f"a{i}_{user.id}_by_{client.me.username}"
                    packs += f"[pack{i if i > 0 else ''}](t.me/addstickers/{pack})\n"
            else:
                packs += f"[pack](t.me/addstickers/{packname})"
            await message.reply(packs, disable_web_page_preview=True)
    except Exception as e:
        logging.error(f"Error in pack_sticker: {e}")
        await message.reply("An error occurred.")
    finally:
        if os.path.exists("stolensticker.png"):
            os.remove("stolensticker.png")
