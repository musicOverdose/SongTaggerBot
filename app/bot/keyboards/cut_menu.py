"""Audio cut submenu keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_cut_menu_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✂️ Enter cut range", callback_data=f"cut_enter:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back", callback_data=f"preview:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_cut_confirm_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(text="✅ Apply cut", callback_data=f"cut_apply:{job_uuid}"),
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"preview:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back", callback_data=f"preview:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
