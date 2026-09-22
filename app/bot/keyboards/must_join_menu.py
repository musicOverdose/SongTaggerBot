"""Must-join required channels keyboard."""

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from app.database.models import RequiredChannel


def get_must_join_keyboard(missing_channels: List[RequiredChannel]) -> InlineKeyboardMarkup:
    buttons = []
    for idx, channel in enumerate(missing_channels, start=1):
        name = channel.title or channel.username or f"Channel {idx}"
        url = channel.invite_link
        if not url:
            if channel.username:
                url = f"https://t.me/{channel.username.lstrip('@')}"
            else:
                url = f"https://t.me/{channel.channel_id.lstrip('@')}"
        buttons.append([InlineKeyboardButton(text=f"📢 {name}", url=url)])

    buttons.append([InlineKeyboardButton(text="🔄 I've joined", callback_data="must_join_verify")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
