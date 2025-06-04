import logging
import aiohttp
import os
import re
from urllib.parse import quote
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.database import add_log_usage

class SafeUserFormatter(logging.Formatter):
    def format(self, record):
        if not hasattr(record, 'user_id'):
            record.user_id = 0
        return super().format(record)

handler = logging.StreamHandler()
handler.setFormatter(SafeUserFormatter("%(asctime)s - %(levelname)s - %(message)s - [User: %(user_id)s]"))
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)

GNEWS_KEY = os.getenv("GNEWS_KEY")

def add_user_context(user_id):
    return {"user_id": user_id}

def parse_news_date(published):
    if not published:
        return "N/A"
    for fmt in (
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%a, %d %b %Y %H:%M:%S %Z"
    ):
        try:
            return datetime.strptime(published, fmt).strftime("%b %d, %Y")
        except ValueError:
            continue
    logger.warning(f"Invalid date format: {published}", extra=add_user_context(0))
    return "N/A"

async def fetch_news(query: str, user_id: int):
    logger_context = add_user_context(user_id)
    preferred_sources = {"the-times-of-india", "hindustan-times", "bbc-news", "al-jazeera-english", "reuters"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://gnews.io/api/v4/top-headlines?q={quote(query)}&lang=en&country=in&max=10&token={GNEWS_KEY}") as response:
                if response.status == 429:
                    logger.warning(f"GNews rate limit reached for query: {query}", extra=logger_context)
                    raise Exception("Rate limit reached")
                if response.status != 200:
                    response_text = await response.text()
                    logger.info(f"No news for query: {query}, status: {response.status}, response: {response_text}", extra=logger_context)
                    raise Exception(f"HTTP {response.status}: {response_text}")
                data = await response.json()
                articles = sorted(
                    data.get("articles", []),
                    key=lambda x: x.get("source", {}).get("name", "").lower().replace(" ", "-") in preferred_sources,
                    reverse=True
                )[:3]
                if not articles:
                    raise Exception("No articles found")
                return articles, "GNews"
    except Exception as e:
        logger.warning(f"GNews failed for query: {query}: {e}", extra=logger_context)
        raise

@Client.on_message(filters.command("news") & filters.private)
async def news_fetch(client: Client, message: Message):
    user_id = message.from_user.id
    logger_context = add_user_context(user_id)

    status_msg = await message.reply_text("📰 Fetching latest news...")
    query = re.sub(r"[^\w\s]", "", " ".join(message.command[1:]).strip()) or "general"

    try:
        articles, host_name = await fetch_news(query, user_id)
        output = f"📰 Latest News: {query.title()}\n\n"
        buttons = []
        for i, article in enumerate(articles, 1):
            title = (article.get("title", "N/A")[:100] + "...") if len(article.get("title", "")) > 100 else article.get("title", "N/A")
            source = article.get("source", {}).get("name", "Unknown") or "Unknown"
            url = article.get("url", None)
            published = article.get("publishedAt", "")
            date = parse_news_date(published)
            if not url:
                continue
            output += (
                f"<blockquote>"
                f"🏷️ <b>{i}. {title}</b>\n"
                f"📝 <b>Source:</b> {source}\n"
                f"📅 <b>Date:</b> {date}\n"
                f"🔗 <a href='{url}'>Read</a>"
                f"</blockquote>\n"
            )
            buttons.append([InlineKeyboardButton(f"🌐 Read Article {i}", url=url)])
        if not buttons:
            await status_msg.edit_text("No valid articles found.")
            return
        buttons.append([InlineKeyboardButton("🔒 Close", callback_data="close_news")])
        await message.reply_text(
            output,
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=enums.ParseMode.HTML,
            quote=True
        )
        logger.info(f"News fetched successfully for query: {query} from {host_name}", extra=logger_context)
    except aiohttp.ClientResponseError as e:
        logger.error(f"GNews HTTP error for {query}: {e}", extra=logger_context, exc_info=True)
        await status_msg.edit_text(f"Failed to fetch news: HTTP {e.status}")
    except ValueError as e:
        logger.error(f"JSON parsing error for {query}: {e}", extra=logger_context, exc_info=True)
        await status_msg.edit_text("Failed to fetch news: Invalid response")
    except Exception as e:
        logger.error(f"Unexpected error for {query}: {e}", extra=logger_context, exc_info=True)
        await status_msg.edit_text(f"No news found for '{query}'. Try 'sports', 'business', 'tech', or 'general'.")
    finally:
        try:
            await status_msg.delete()
        except Exception as e:
            logger.warning(f"Failed to delete status message: {e}", extra=logger_context)
        try:
            await add_log_usage(user_id, "news")
        except Exception as e:
            logger.error(f"Failed to log usage: {e}", extra=logger_context)

@Client.on_callback_query(filters.regex("close_news"))
async def close_news_callback(client: Client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    logger_context = add_user_context(user_id)
    try:
        await callback_query.message.delete()
        await callback_query.answer("News closed")
        logger.info("News message closed", extra=logger_context)
    except Exception as e:
        logger.error(f"Failed to delete news message: {e}", extra=logger_context)
        await callback_query.answer("Failed to close news")
