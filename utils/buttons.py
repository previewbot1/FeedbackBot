import re
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging

logger = logging.getLogger(__name__)

def parse_buttons(response_text: str) -> tuple[str, InlineKeyboardMarkup | None]:
    lines = response_text.strip().split("\n")
    buttons = []
    current_row = []
    clean_text = []

    url_regex = re.compile(r"^(.*?)\s*-\s*(https?://\S+?)$")
    callback_regex = re.compile(r"^(.*?)\s*-\s*callback:(\S+)$")
    popup_regex = re.compile(r"^(.*?)\s*-\s*(popup|alert):(.+)$")

    for line in lines:
        button_parts = line.strip().split("&&")
        same_row_buttons = []

        for part in button_parts:
            part = part.strip()
            url_match = url_regex.match(part)
            callback_match = callback_regex.match(part)
            popup_match = popup_regex.match(part)

            if url_match:
                button_text, url = url_match.groups()
                same_row_buttons.append(
                    InlineKeyboardButton(text=button_text.strip(), url=url.strip())
                )
            elif callback_match:
                button_text, data = callback_match.groups()
                same_row_buttons.append(
                    InlineKeyboardButton(text=button_text.strip(), callback_data=data.strip())
                )
            elif popup_match:
                button_text, popup_type, popup_text = popup_match.groups()
                same_row_buttons.append(
                    InlineKeyboardButton(text=button_text.strip(), callback_data=f"{popup_type}:{popup_text.strip()}")
                )
            else:
                if len(button_parts) == 1:
                    clean_text.append(line)
                    break

        if same_row_buttons:
            buttons.append(same_row_buttons)

    reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
    final_text = "\n".join(clean_text).strip()
    if not final_text and reply_markup:
        final_text = "Select an option below:"
    return final_text, reply_markup
