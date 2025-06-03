import logging
import aiohttp
from rapidfuzz import process
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from utils.database import add_log_usage

@Client.on_message(filters.command("wiki") & filters.private)
async def wiki_search(client: Client, message: Message):
    status_msg = await message.reply_text("🔎 Fetching Wikipedia results...")
    if len(message.command) < 2:
        await status_msg.edit_text("Please provide a search query (e.g., /wiki Times of India)")
        return
    query = " ".join(message.command[1:])
    google_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}") as response:
                if response.status == 200:
                    data = await response.json()
                    title = data.get("title", "N/A")
                    extract = data.get("extract", "No summary available")
                    url = data.get("content_urls", {}).get("desktop", {}).get("page", "N/A")
                    output = (
                        f"📖 Wikipedia Search Results\n\n"
                        f"<blockquote>"
                        f"🏷️ <b>Title:</b> {title}\n"
                        f"📝 <b>Summary:</b> {extract[:200]}{'...' if len(extract) > 200 else ''}\n"
                        f"🔗 <b>URL:</b> <a href='{url}'>Read More</a>"
                        f"</blockquote>"
                    )
                    buttons = [
                        [
                            InlineKeyboardButton("🌐 Read More", url=url),
                            InlineKeyboardButton("🔒 Close", callback_data="close_wiki")
                        ]
                    ]
                    await message.reply_text(
                        output,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
                    await status_msg.delete()
                    await add_log_usage(message.from_user.id, "wiki")
                    return
            async with session.get(f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&format=json") as response:
                data = await response.json()
                search_results = [result["title"] for result in data.get("query", {}).get("search", [])]
                suggestions = [match[0] for match in process.extract(query, search_results, limit=5) if match[1] > 80] if search_results else []
                if suggestions:
                    output = (
                        f"📖 No Exact Match Found\n\n"
                        f"<blockquote>"
                        f"🔍 <b>Query:</b> {query}\n"
                        f"📝 <b>Suggestions:</b> Select a suggestion below"
                        f"</blockquote>"
                    )
                    buttons = [[InlineKeyboardButton(suggestion, callback_data=f"wiki_suggest:{suggestion}")] for suggestion in suggestions]
                    buttons.append([InlineKeyboardButton("🔍 Check Google", url=google_url)])
                    buttons.append([InlineKeyboardButton("🔒 Close", callback_data="close_wiki")])
                    await message.reply_text(
                        output,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
                else:
                    output = (
                        f"📖 No Results Found\n\n"
                        f"<blockquote>"
                        f"🔍 <b>Query:</b> {query}\n"
                        f"📝 <b>Try:</b> Check Google for more information"
                        f"</blockquote>"
                    )
                    buttons = [
                        [InlineKeyboardButton("🔍 Check Google", url=google_url)],
                        [InlineKeyboardButton("🔒 Close", callback_data="close_wiki")]
                    ]
                    await message.reply_text(
                        output,
                        reply_markup=InlineKeyboardMarkup(buttons),
                        parse_mode=enums.ParseMode.HTML,
                        quote=True
                    )
    except Exception as e:
        logging.error(f"Wiki search error for {query}: {e}", exc_info=True)
        await status_msg.edit_text("Failed to fetch Wikipedia results")
    finally:
        await status_msg.delete()
    await add_log_usage(message.from_user.id, "wiki")

@Client.on_callback_query(filters.regex(r"wiki_suggest:(.+)"))
async def wiki_suggest_callback(client: Client, callback_query: CallbackQuery):
    query = callback_query.data.split(":", 1)[1]
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{query.replace(' ', '_')}") as response:
                if response.status != 200:
                    await callback_query.message.edit_text("Failed to fetch Wikipedia page for suggestion")
                    return
                data = await response.json()
                title = data.get("title", "N/A")
                extract = data.get("extract", "No summary available")
                url = data.get("content_urls", {}).get("desktop", {}).get("page", "N/A")
                output = (
                    f"📖 Wikipedia Search Results\n\n"
                    f"<blockquote>"
                    f"🏷️ <b>Title:</b> {title}\n"
                    f"📝 <b>Summary:</b> {extract[:200]}{'...' if len(extract) > 200 else ''}\n"
                    f"🔗 <b>URL:</b> <a href='{url}'>Read More</a>"
                    f"</blockquote>"
                )
                buttons = [
                    [
                        InlineKeyboardButton("🌐 Read More", url=url),
                        InlineKeyboardButton("🔒 Close", callback_data="close_wiki")
                    ]
                ]
                await callback_query.message.edit_text(
                    output,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode=enums.ParseMode.HTML
                )
    except Exception as e:
        logging.error(f"Wiki suggestion error for {query}: {e}", exc_info=True)
        await callback_query.message.edit_text("Failed to fetch Wikipedia results")
    await callback_query.answer()

@Client.on_callback_query(filters.regex("close_wiki"))
async def close_wiki_callback(client: Client, callback_query: CallbackQuery):
    await callback_query.message.delete()
    await callback_query.answer()
