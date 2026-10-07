"""Lyrics submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_lyrics_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Edit Lyrics", callback_data=f"lyrics_edit:{job_uuid}"),
            InlineKeyboardButton(text="👁 View Lyrics", callback_data=f"lyrics_preview:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🗑 Remove Lyrics", callback_data=f"lyrics_remove:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Back to Main", callback_data=f"preview:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
