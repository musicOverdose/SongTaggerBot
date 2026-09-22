"""Lyrics submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_lyrics_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Edit lyrics", callback_data=f"lyrics_edit:{job_uuid}"),
            InlineKeyboardButton(text="👁 Preview", callback_data=f"lyrics_preview:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Remove lyrics", callback_data=f"lyrics_remove:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back", callback_data=f"edit_menu:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
