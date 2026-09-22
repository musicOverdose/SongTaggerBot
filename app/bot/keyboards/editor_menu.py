"""Interactive metadata editor inline keyboards."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def get_editor_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    """Core metadata editor keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📝 filename", callback_data=f"fn_menu:{job_uuid}"),
            InlineKeyboardButton(text="🏷 title", callback_data=f"field:title:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="👤 artist", callback_data=f"field:artist:{job_uuid}"),
            InlineKeyboardButton(text="📅 year", callback_data=f"field:date:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="💿 album", callback_data=f"field:album:{job_uuid}"),
            InlineKeyboardButton(text="🎸 genre", callback_data=f"field:genre:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="👥 album artist", callback_data=f"field:albumartist:{job_uuid}"),
            InlineKeyboardButton(text="🔢 track", callback_data=f"field:track_number:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="💽 disc", callback_data=f"field:disc_number:{job_uuid}"),
            InlineKeyboardButton(text="🎼 composer", callback_data=f"field:composer:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="💬 comment", callback_data=f"field:comment:{job_uuid}"),
            InlineKeyboardButton(text="© copyright", callback_data=f"field:copyright:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🖼 cover", callback_data=f"cover_menu:{job_uuid}"),
            InlineKeyboardButton(text="🎤 lyrics", callback_data=f"lyrics_menu:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="⚙️ More metadata", callback_data=f"adv_menu:{job_uuid}"),
            InlineKeyboardButton(text="👁 Preview", callback_data=f"preview:{job_uuid}"),
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


def get_advanced_editor_keyboard(job_uuid: str) -> InlineKeyboardMarkup:
    """Advanced metadata fields editor keyboard."""
    buttons = [
        [
            InlineKeyboardButton(text="📁 grouping", callback_data=f"field:grouping:{job_uuid}"),
            InlineKeyboardButton(text="⏱ BPM", callback_data=f"field:bpm:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🏢 publisher", callback_data=f"field:publisher:{job_uuid}"),
            InlineKeyboardButton(text="🎻 conductor", callback_data=f"field:conductor:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="📦 compilation", callback_data=f"field:compilation:{job_uuid}"),
            InlineKeyboardButton(text="🆔 ISRC", callback_data=f"field:isrc:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔤 sort title", callback_data=f"field:sort_title:{job_uuid}"),
            InlineKeyboardButton(text="🔤 sort artist", callback_data=f"field:sort_artist:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="🔤 sort album", callback_data=f"field:sort_album:{job_uuid}"),
            InlineKeyboardButton(text="🔤 sort album artist", callback_data=f"field:sort_album_artist:{job_uuid}"),
        ],
        [
            InlineKeyboardButton(text="↩ Back to Core", callback_data=f"edit_menu:{job_uuid}"),
            InlineKeyboardButton(text="👁 Preview", callback_data=f"preview:{job_uuid}"),
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
