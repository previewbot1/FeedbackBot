import logging
import aiohttp
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.database import add_log_usage

@Client.on_message(filters.command("news") & filters.private)
async def news_fetch(client: Client, message: Message):
    status_msg = await message.reply_text("📰 Fetching latest news...")
    query = " ".join(message.command[1:]) if len(message.command) > 1 else "general"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://newsapi.org/v2/top-headlines?q={query}&apiKey=515092a872c348209fa34e623d14591b") as response:
                if response.status != 200:
                    await status_msg.edit_text("No news found for this topic")
                    return
                data = await response.json()
                articles = data.get("articles", [])[:5]
                if not articles:
                    await status_msg.edit_text("No news found for this topic")
                    return
                output = f"📰 Latest News: {query.title()}\n\n"
                buttons = []
                for i, article in enumerate(articles, 1):
                    title = article.get("title", "N/A")
                    source = article.get("source", {}).get("name", "Unknown")
                    url = article.get("url", "N/A")
                    output += (
                        f"<blockquote>"
                        f"🏷️ <b>{i}. {title}</b>\n"
                        f"📝 <b>Source:</b> {source}\n"
                        f"🔗 <a href='{url}'>Read</a>"
                        f"</blockquote>\n"
                    )
                    buttons.append([InlineKeyboardButton(f"🌐 Read Article {i}", url=url)])
                buttons.append([InlineKeyboardButton("🔒 Close", callback_data="close_news")])
                await message.reply_text(
                    output,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML,
                    quote=True
                )
    except Exception as e:
        logging.error(f"News fetch error for {query}: {e}", exc_info=True)
        await status_msg.edit_text("Failed to fetch news")
    finally:
        await status_msg.delete()
    await add_log_usage(message.from_user.id, "news")

@Client.on_callback_query(filters.regex("close_news"))
async def close_news_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.message.delete()
    await callback_query.answer()
