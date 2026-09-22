"""Cover art submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_cover_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="📤 Upload new cover", callback_data=f"cover_upload:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔍 View current cover", callback_data=f"cover_view:{job_uuid}"),
            InlineKeyboardButton(text="🗑 Remove cover", callback_data=f"cover_remove:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back", callback_data=f"edit_menu:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cover_confirm_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Use this cover", callback_data=f"cover_confirm:{job_uuid}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cover_menu:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
