import asyncio
import os
import logging
import re
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, MessageIdInvalid, PeerIdInvalid, UserIsBlocked, InputUserDeactivated, UserDeactivatedBan, ChatWriteForbidden, ChatAdminRequired, RPCError
from utils.database import add_log_usage, add_product, get_products, get_product, edit_product, remove_product, clear_products

logger = logging.getLogger(__name__)

ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
ADMIN_CONTACT = "t.me/MyAdmin"  # Add your admin contact

PRODUCTS_RATE_LIMIT_SECONDS = 20
SERVICE_RATE_LIMIT_SECONDS = 20
CALLBACK_RATE_LIMIT_SECONDS = 20
spam_block = {}

async def safe_reply(message: Message, text: str, reply_markup=None, parse_mode=None, quote: bool = False):
    if not message:
        return None
    try:
        return await message.reply_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            quote=quote
        )
    except RPCError as e:
        logger.warning(f"[safe_reply] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_reply] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

async def safe_edit(message: Message, text: str, parse_mode=None, reply_markup=None):
    if not message:
        return None
    try:
        return await message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except RPCError as e:
        logger.warning(f"[safe_edit] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None
    except Exception as e:
        logger.error(f"[safe_edit] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
        return None

async def safe_delete(message: Message):
    if not message:
        return
    try:
        await message.delete()
    except RPCError as e:
        logger.warning(f"[safe_delete] RPCError: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))
    except Exception as e:
        logger.error(f"[safe_delete] Unexpected error: {e}", extra=add_user_context(getattr(message.from_user, "id", 0)))

def add_user_context(user_id: int) -> dict:
    return {"user_id": user_id if user_id else "System"}

@Client.on_message(filters.command(["sale", "buy", "products", "product"]) & filters.private)
async def products_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < PRODUCTS_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for products command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /products again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Products command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "False").lower() != "true":
            await safe_reply(message, "⚖ This feature is currently disabled.", quote=True)
            return

        status_msg = None
        try:
            status_msg = await safe_reply(message, "🛒 Fetching available services...")
        except Exception as e:
            logger.error(f"Failed to send status message: {e}", extra=logger_context)

        try:
            products = await get_products()
            if not products:
                await safe_edit(status_msg, "🚫 No services available at the moment.")
                return
            output = "🛒 Available Services\n\n"
            for product in products:
                output += f"<blockquote>🏷️ {product['name']}</blockquote>\n"
            buttons = [[InlineKeyboardButton(product['name'], callback_data=f"product_detail:{product['id']}")] for product in products]
            buttons.append([InlineKeyboardButton("🔒 Close", callback_data="close_products")])
            response_msg = await safe_reply(
                message,
                output,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            if not response_msg:
                await safe_edit(status_msg, "❌ Failed to send services list.")
                return
            logger.info("Products list sent", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to fetch products: {e}", extra=logger_context)
            await safe_edit(status_msg, "❌ Failed to fetch services.")
            return
        finally:
            try:
                await safe_delete(status_msg)
                logger.info("Status message deleted", extra=logger_context)
            except Exception as e:
                logger.warning(f"Failed to delete status message: {e}", extra=logger_context)

        try:
            if user_id not in ADMINS:  # Auto-delete for non-admins
                await asyncio.sleep(60)
                try:
                    await safe_delete(response_msg)
                    await safe_delete(message)
                    logger.info("Products messages deleted after 60s", extra=logger_context)
                except Exception as e:
                    logger.warning(f"Failed to delete products messages: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

        try:
            await add_log_usage(user_id, "products")
            logger.info("Products command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in products_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for products", extra=logger_context)

@Client.on_message(filters.command("addservice") & filters.private & filters.user(ADMINS))
async def add_service_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SERVICE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for addservice command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /addservice again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Addservice command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "False").lower() != "true":
            await safe_reply(message, "⚖ This feature is currently disabled.", quote=True)
            return
        if not ADMINS:
            await safe_reply(message, "🚫 No admins configured.", quote=True)
            return

        args = message.text[len("/addservice "):].strip() if message.text.startswith("/addservice ") else ""
        if not args:
            await safe_reply(
                message,
                "📝 Please provide product details in this format:\n"
                "/addservice Name - Product Name\n"
                "Description - Product Description\n"
                "Price - Product Price\n"
                "Availability - Say Availability\n"
                "[Preview - Image URL] (optional)",
                quote=True
            )
            return

        pattern = r"Name - (.+)\nDescription - (.+)\nPrice - (.+)\nAvailability - (.+?)(?:\nPreview - (https?://[^\s]+))?$"
        match = re.match(pattern, args, re.DOTALL)
        if not match:
            await safe_reply(message, "❌ Invalid format. Please use the specified format.", quote=True)
            return
        name, description, price, availability, preview_url = match.groups()
        preview_url = preview_url.strip() if preview_url else None
        if preview_url and not preview_url.startswith(('http://', 'https://')):
            await safe_reply(message, "❌ Invalid Preview URL. Must start with http:// or https://.", quote=True)
            return

        try:
            await add_product(name.strip(), description.strip(), price.strip(), availability.strip(), preview_url)
            await safe_reply(message, f"✅ Product '{name}' added successfully!", quote=True)
            logger.info(f"Product '{name}' added", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to add product: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to add product.", quote=True)
            return

        try:
            await add_log_usage(user_id, "addservice")
            logger.info("Addservice command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in add_service_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for addservice", extra=logger_context)

@Client.on_message(filters.command("editservice") & filters.private & filters.user(ADMINS))
async def edit_service_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SERVICE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for editservice command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /editservice again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Editservice command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "False").lower() != "true":
            await safe_reply(message, "⚖ This feature is currently disabled.", quote=True)
            return
        if not ADMINS:
            await safe_reply(message, "🚫 No admins configured.", quote=True)
            return

        args = message.text[len("/editservice "):].strip() if message.text.startswith("/editservice ") else ""
        if not args:
            await safe_reply(
                message,
                "📝 Please provide product ID and details in this format:\n"
                "/editservice <ID> Name - Product Name\n"
                "Description - Product Description\n"
                "Price - Product Price\n"
                "Availability - Say Availability\n"
                "[Preview - Image URL] (optional)",
                quote=True
            )
            return

        try:
            parts = args.split(" ", 1)
            if len(parts) < 2:
                await safe_reply(message, "❌ Please include ID and details.", quote=True)
                return
            product_id = int(parts[0])
            details = parts[1].strip()
            pattern = r"Name - (.+)\nDescription - (.+?)\nPrice - (.+?)\nAvailability - (.+?)(?:\nPreview - (https?://[^\s]+))?$"
            match = re.match(pattern, details, re.DOTALL)
            if not match:
                await safe_reply(message, "❌ Invalid format. Please use the specified format.", quote=True)
                return
            name, description, price, availability, preview_url = match.groups()
            preview_url = preview_url.strip() if preview_url else None
            if preview_url and not preview_url.startswith(('http://', 'https://')):
                await safe_reply(message, "❌ Invalid Preview URL. Must start with http:// or https://.", quote=True)
                return
            if not await get_product(product_id):
                await safe_reply(message, f"❌ Product ID {product_id} not found.", quote=True)
                return
            await edit_product(product_id, name.strip(), description.strip(), price.strip(), availability.strip(), preview_url)
            await safe_reply(message, f"✅ Product '{name}' updated successfully!", quote=True)
            logger.info(f"Product ID {product_id} updated", extra=logger_context)
        except ValueError:
            await safe_reply(message, "❌ Invalid ID format. Use a number.", quote=True)
        except Exception as e:
            logger.error(f"Failed to edit product: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to update product.", quote=True)
            return

        try:
            await add_log_usage(user_id, "editservice")
            logger.info("Editservice command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in edit_service_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for editservice", extra=logger_context)

@Client.on_message(filters.command("removeservice") & filters.private & filters.user(ADMINS))
async def remove_service_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SERVICE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for removeservice command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /removeservice again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Removeservice command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "False").lower() != "true":
            await safe_reply(message, "⚖ This feature is currently disabled.", quote=True)
            return
        if not ADMINS:
            await safe_reply(message, "🚫 No admins configured.", quote=True)
            return

        args = message.text[len("/removeservice "):].strip() if message.text.startswith("/removeservice ") else ""
        if not args:
            await safe_reply(message, "📝 Please provide product ID: /removeservice <ID>", quote=True)
            return

        try:
            product_id = int(args)
            if not await get_product(product_id):
                await safe_reply(message, f"❌ Product ID {product_id} not found.", quote=True)
                return
            await remove_product(product_id)
            await safe_reply(message, f"✅ Product ID {product_id} removed successfully!", quote=True)
            logger.info(f"Product ID {product_id} removed", extra=logger_context)
        except ValueError:
            await safe_reply(message, "❌ Invalid ID format. Use a number.", quote=True)
        except Exception as e:
            logger.error(f"Failed to remove product: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to remove product.", quote=True)
            return

        try:
            await add_log_usage(user_id, "removeservice")
            logger.info("Removeservice command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in remove_service_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for removeservice", extra=logger_context)

@Client.on_message(filters.command("listservices") & filters.private & filters.user(ADMINS))
async def list_services_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SERVICE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for listservices command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /listservices again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Listservices command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "false").lower() != "true":
            await safe_reply(message, "⚖ This feature is disabled.", quote=True)
            return
        if not ADMINS:
            return await safe_reply(message, "No admins configured.", quote=True)

        try:
            products = await get_products()
            if not products:
                await safe_reply(message, "🚫 No products available.", quote=True)
                return

            output = f"🛒 Product Management\n\n"
            for product in products:
                output += (
                    f"<blockquote>"
                    f"🏷️ <b>ID:</b> {product['id']} <b>Name:</b> {product['name']}\n"
                    f"📖 <b>Description:</b> {product['description']}\n"
                    f"💰 <b>Price:</b> {product['price']}\n"
                    f"✔️ <b>Availability:</b> {product['availability']}\n"
                    f"🖼️ <b>Preview:</b> <a href=\"{product.get('preview_url', '#')}\">View</a>\n"
                    "</blockquote>\n"
                )
            buttons = [[InlineKeyboardButton("🔒 Close", callback_data="close_products")]]
            await safe_reply(
                message,
                output,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML,
                quote=True
            )
            logger.info("Product list sent successfully", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to list products: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to retrieve product list.", quote=True)
            return

        try:
            await add_log_usage(user_id, "listservices")
            logger.info("Listservices command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in list_services_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for listservices", extra=logger_context)

@Client.on_message(filters.command("cleanservices") & filters.private & filters.user(ADMINS))
async def clean_services_command(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < SERVICE_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for cleanservices command", extra=logger_context)
            await safe_reply(message, "🖐 Please wait before using /cleanservices again.", quote=True)
            return
        spam_block[user_id] = now

        logger.info("Cleanservices command triggered", extra=logger_context)
        if os.getenv("PRODUCTS", "false").lower() != "true":
            await safe_reply(message, "⚖ This feature is disabled.", quote=True)
            return
        if not ADMINS:
            await safe_reply(message, "🚫 No admins configured.", quote=True)
            return

        try:
            result = await clear_products()
            if result.deleted_count == 0:
                await safe_reply(message, "🚫 No products to delete.", quote=True)
            else:
                await safe_reply(message, f"✅ All products deleted successfully ({result.deleted_count} deleted).", quote=True)
                logger.info(f"Deleted {result.deleted_count} products", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to delete products: {e}", extra=logger_context)
            await safe_reply(message, "❌ Failed to delete products.", quote=True)
            return

        try:
            await add_log_usage(user_id, "cleanservices")
            logger.info("Cleanservices command usage logged", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in clean_services_command: {e}", extra=logger_context)
        await safe_reply(message, "❌ An unexpected error occurred.", quote=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for cleanservices", extra=logger_context)

@Client.on_callback_query(filters.regex(r"product_detail:\d+"))
async def product_detail_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < CALLBACK_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for product_detail callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before viewing more details.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info(f"Product detail callback triggered for ID {callback_query.data}", extra=logger_context)
        try:
            product_id = int(callback_query.data.split(":")[1])
            product = await get_product(product_id)
            if not product:
                logger.warning(f"No product found with ID {product_id}", extra=logger_context)
                await safe_edit(
                    callback_query.message,
                    "🚫 Service not found.",
                    parse_mode=enums.ParseMode.HTML
                )
                await callback_query.answer("Product not found.", show_alert=True)
                return

            output = (
                f"🎯 Product Details\n\n"
                f"<blockquote>"
                f"🏷️ <b>Name:</b> {product['name']}\n"
                f"📖 <b>Description:</b> {product['description']}\n"
                f"💰 <b>Price:</b> {product['price']}\n"
                f"✔️ <b>Status:</b> {product['availability']}"
            )
            if product.get('preview_url'):
                output += f"\n🖼️ <b>Preview:</b> <a href=\"{product['preview_url']}\">View</a>"
            output += "</blockquote>"

            buttons = [
                [InlineKeyboardButton("📞 Contact Admin", url=ADMIN_CONTACT)],
                [InlineKeyboardButton("🔗 Back", callback_data="back_products")],
                [InlineKeyboardButton("🔒 Close", callback_data="close_products")]
            ]

            if product.get('preview_url') and user_id in ADMINS:
                try:
                    await safe_reply_photo(
                        callback_query.message,
                        photo=product['preview_url'],
                        caption=output,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
                    await safe_delete(callback_query.message)
                    logger.info(f"Product preview image sent for ID {product_id}", extra=logger_context)
                except Exception as e:
                    logger.warning(f"Failed to send preview image: {e}", extra=logger_context)
                    await safe_edit(
                        callback_query.message,
                        output,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML
                    )
            else:
                await safe_edit(
                    callback_query.message,
                    output,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
            await callback_query.answer("✅ Details displayed!")
            logger.info(f"Product details displayed for ID {product_id}", extra=logger_context)

        except Exception as e:
            logger.error(f"Failed to display product details: {e}", extra=logger_context)
            await safe_edit(callback_query.message, "❌ Failed to load product details.", parse_mode=enums.ParseMode.HTML)
            await callback_query.answer("❌ Error loading details.", show_alert=True)

        try:
            if user_id not in ADMINS:
                await asyncio.sleep(60)
                try:
                    await safe_delete(callback_query.message)
                    logger.info("Product detail deleted after 60s", extra=logger_context)
                except Exception as e:
                    logger.warning(f"Failed to delete product detail: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in product_detail_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for product_detail", extra=logger_context)

@Client.on_callback_query(filters.regex(r"back_products"))
async def back_products_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < CALLBACK_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for back_products callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before going back.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Back_products callback triggered", extra=logger_context)
        try:
            products = await get_products()
            if not products:
                await safe_edit(
                    callback_query.message,
                    "🚫 No products available.",
                    parse_mode=enums.ParseMode.HTML
                )
                await callback_query.answer("No products found.")
                return

            output = f"🛒 Products Available\n\n"
            for product in products:
                output += f"<blockquote>{product['name']}</blockquote>\n"

            buttons = [[InlineKeyboardButton(product['name'], callback_data=f"product_detail:{product['id']}")] for product in products]
            buttons.append([InlineKeyboardButton("🔒 Close", callback_data="close_products")])

            await safe_edit(
                callback_query.message,
                output,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=enums.ParseMode.HTML
            )
            await callback_query.answer("✅ Back to products list!")
            logger.info("Back to products list successful", extra=logger_context)

        except Exception as e:
            logger.error(f"Failed to display products list: {e}", extra=logger_context)
            await safe_edit(callback_query.message, "❌ Failed to fetch products.", parse_mode=enums.ParseMode.HTML)
            await callback_query.answer("❌ Error loading products.", show_alert=True)

        try:
            if user_id not in ADMINS:
                await asyncio.sleep(60)
                try:
                    await safe_delete(callback_query.message)
                    logger.info("Products list deleted after 60s", extra=logger_context)
                except Exception as e:
                    logger.warning(f"Failed to delete products list: {e}", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to schedule deletion: {e}", extra=logger_context)

    except Exception as e:
        logger.error(f"Fatal error in back_products_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)

    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for back_products", extra=logger_context)

@Client.on_callback_query(filters.regex(r"close_products"))
async def close_products_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)

    try:
        now = asyncio.get_event_loop().time()
        if user_id in spam_block and now - spam_block[user_id] < CALLBACK_RATE_LIMIT_SECONDS:
            logger.info("Rate limit hit for close_products callback", extra=logger_context)
            await callback_query.answer("🖐 Please wait before closing.", show_alert=True)
            return
        spam_block[user_id] = now

        logger.info("Close products callback triggered", extra=logger_context)
        try:
            await safe_delete(callback_query.message)
            await callback_query.answer("✅ Closed successfully!")
            logger.info("Products message closed", extra=logger_context)
        except Exception as e:
            logger.error(f"Failed to close callback: {e}", extra=logger_context)
            await callback_query.answer("❌ Failed to close.", show_alert=True)

    except Exception as e:
        logger.error(f"Fatal error in close_products_callback: {e}", extra=logger_context)
        await callback_query.answer("❌ An unexpected error occurred.", show_alert=True)
    finally:
        if user_id in spam_block:
            spam_block.pop(user_id, None)
            logger.debug("Rate limit cleared for close_products", extra=logger_context)
