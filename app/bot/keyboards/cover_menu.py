"""Cover art submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_cover_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📤 Upload New Cover", callback_data=f"cover_upload:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔍 View Current Cover", callback_data=f"cover_view:{job_uuid}"),
            InlineKeyboardButton(text="🗑 Remove Cover", callback_data=f"cover_remove:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🏠 Back to Main", callback_data=f"preview:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cover_confirm_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Use This Cover", callback_data=f"cover_confirm:{job_uuid}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cover_menu:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
