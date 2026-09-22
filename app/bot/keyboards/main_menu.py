"""Main metadata preview keyboard."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_preview_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    """Returns the main inspection screen keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="✏️ Edit metadata", callback_data=f"edit_menu:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🖼 Cover", callback_data=f"cover_menu:{job_uuid}"),
            InlineKeyboardButton(text="🎤 Lyrics", callback_data=f"lyrics_menu:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="📄 File info", callback_data=f"file_info:{job_uuid}"),
            InlineKeyboardButton(text="✂️ Cut", callback_data=f"cut_menu:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Undo", callback_data=f"undo:{job_uuid}"),
            InlineKeyboardButton(text="✅ Finish", callback_data=f"finish:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
