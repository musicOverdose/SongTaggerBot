"""Interactive metadata editor inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_editor_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    """Core metadata editor keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="🏷 Title", callback_data=f"field:title:{job_uuid}"),
            InlineKeyboardButton(text="👤 Artist", callback_data=f"field:artist:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="💿 Album", callback_data=f"field:album:{job_uuid}"),
            InlineKeyboardButton(text="📅 Year", callback_data=f"field:date:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🎸 Genre", callback_data=f"field:genre:{job_uuid}"),
            InlineKeyboardButton(text="🔢 Track", callback_data=f"field:track_number:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="👥 Album Artist", callback_data=f"field:albumartist:{job_uuid}"),
            InlineKeyboardButton(text="💽 Disc", callback_data=f"field:disc_number:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="📝 Filename", callback_data=f"fn_menu:{job_uuid}"),
            InlineKeyboardButton(text="🎼 Composer", callback_data=f"field:composer:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="💬 Comment", callback_data=f"field:comment:{job_uuid}"),
            InlineKeyboardButton(text="© Copyright", callback_data=f"field:copyright:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ More Tags", callback_data=f"adv_menu:{job_uuid}"),
            InlineKeyboardButton(text="↩ Back to Main", callback_data=f"preview:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Undo", callback_data=f"undo:editor:{job_uuid}"),
            InlineKeyboardButton(text="✅ Finish", callback_data=f"finish:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_advanced_editor_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    """Advanced metadata fields editor keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📁 Grouping", callback_data=f"field:grouping:{job_uuid}"),
            InlineKeyboardButton(text="⏱ BPM", callback_data=f"field:bpm:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🏢 Publisher", callback_data=f"field:publisher:{job_uuid}"),
            InlineKeyboardButton(text="🎻 Conductor", callback_data=f"field:conductor:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="📦 Compilation", callback_data=f"field:compilation:{job_uuid}"),
            InlineKeyboardButton(text="🆔 ISRC", callback_data=f"field:isrc:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔤 Sort Title", callback_data=f"field:sort_title:{job_uuid}"),
            InlineKeyboardButton(text="🔤 Sort Artist", callback_data=f"field:sort_artist:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔤 Sort Album", callback_data=f"field:sort_album:{job_uuid}"),
            InlineKeyboardButton(text="🔤 Sort Album Artist", callback_data=f"field:sort_album_artist:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back to Tags", callback_data=f"edit_menu:{job_uuid}"),
            InlineKeyboardButton(text="🏠 Main Menu", callback_data=f"preview:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Undo", callback_data=f"undo:adv:{job_uuid}"),
            InlineKeyboardButton(text="✅ Finish", callback_data=f"finish:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="❌ Cancel", callback_data=f"cancel:{job_uuid}"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
