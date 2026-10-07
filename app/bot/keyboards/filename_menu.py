"""Filename editing submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_filename_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Custom Filename", callback_data=f"fn_edit:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="✨ Auto-Generate", callback_data=f"fn_generate:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back to Tags", callback_data=f"edit_menu:{job_uuid}"),
            InlineKeyboardButton(text="🏠 Back to Main", callback_data=f"preview:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
