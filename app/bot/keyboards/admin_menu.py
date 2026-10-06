"""Interactive keyboards for the Telegram Admin Panel."""

from typing import List
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database.models import BannedUser, RequiredChannel, WhitelistedUser


def get_admin_dashboard_keyboard(maintenance_mode: bool = False) -> InlineKeyboardMarkup:
    """Main administrative dashboard keyboard with dynamic maintenance toggle."""
    maint_label = "🚧 Maint: ON" if maintenance_mode else "🚧 Maint: OFF"
    buttons = [
        [
            InlineKeyboardButton(text="📊 Live Stats", callback_data="adm_stats"),
            InlineKeyboardButton(text="📢 Channels", callback_data="adm_channels"),
        ],
        [
            InlineKeyboardButton(text="⭐ Whitelist", callback_data="adm_whitelist"),
            InlineKeyboardButton(text="🚫 Ban List", callback_data="adm_banlist"),
        ],
        [
            InlineKeyboardButton(text="📣 Broadcast", callback_data="adm_broadcast"),
            InlineKeyboardButton(text="📜 Audit Logs", callback_data="adm_audit:0"),
        ],
        [
            InlineKeyboardButton(text=maint_label, callback_data="adm_maint_toggle"),
            InlineKeyboardButton(text="🧹 GC Cleanup", callback_data="adm_cleanup"),
        ],
        [
            InlineKeyboardButton(text="💾 Backup DB", callback_data="adm_backup"),
            InlineKeyboardButton(text="🔄 Reload Config", callback_data="adm_reload"),
        ],
        [
            InlineKeyboardButton(text="❌ Close", callback_data="adm_close"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_channels_keyboard(channels: List[RequiredChannel]) -> InlineKeyboardMarkup:
    """Manage required broadcast channels."""
    buttons = []
    for c in channels:
        status_icon = "🟢" if c.is_enabled else "🔴"
        display = c.username or c.channel_id
        buttons.append([
            InlineKeyboardButton(
                text=f"{status_icon} {display}",
                callback_data=f"adm_ch_toggle:{c.channel_id}",
            ),
            InlineKeyboardButton(
                text="🗑 Delete",
                callback_data=f"adm_ch_del:{c.channel_id}",
            ),
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Add Channel", callback_data="adm_ch_add"),
    ])
    buttons.append([
        InlineKeyboardButton(text="↩ Back to Admin", callback_data="adm_home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_whitelist_keyboard(whitelist: List[WhitelistedUser]) -> InlineKeyboardMarkup:
    """Manage must-join whitelist users."""
    buttons = []
    for w in whitelist[:15]:  # Show latest 15
        label = f"⭐ {w.username or w.user_id}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"adm_wl_info:{w.user_id}"),
            InlineKeyboardButton(text="🗑 Remove", callback_data=f"adm_wl_del:{w.user_id}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Add to Whitelist", callback_data="adm_wl_add"),
    ])
    buttons.append([
        InlineKeyboardButton(text="↩ Back to Admin", callback_data="adm_home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_banlist_keyboard(banned: List[BannedUser]) -> InlineKeyboardMarkup:
    """Manage banned users."""
    buttons = []
    for b in banned[:15]:  # Show latest 15
        label = f"🚫 {b.username or b.user_id}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"adm_ban_info:{b.user_id}"),
            InlineKeyboardButton(text="🔓 Unban", callback_data=f"adm_ban_del:{b.user_id}"),
        ])
    buttons.append([
        InlineKeyboardButton(text="➕ Ban User", callback_data="adm_ban_add"),
    ])
    buttons.append([
        InlineKeyboardButton(text="↩ Back to Admin", callback_data="adm_home"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Confirmation keyboard before dispatching broadcast."""
    buttons = [
        [
            InlineKeyboardButton(text="🚀 Send to All Users", callback_data="adm_bcast_confirm"),
            InlineKeyboardButton(text="❌ Cancel", callback_data="adm_home"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_broadcast_running_keyboard(broadcast_id: int) -> InlineKeyboardMarkup:
    """Active broadcast status keyboard with cancellation button."""
    buttons = [
        [
            InlineKeyboardButton(text="🛑 Cancel Broadcast", callback_data=f"adm_bcast_cancel:{broadcast_id}"),
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_audit_logs_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Paginated navigation for audit logs."""
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"adm_audit:{page - 1}"))
    nav_buttons.append(InlineKeyboardButton(text=f"Page {page + 1}/{max(1, total_pages)}", callback_data="noop"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Next", callback_data=f"adm_audit:{page + 1}"))

    buttons = [
        nav_buttons,
        [InlineKeyboardButton(text="↩ Back to Admin", callback_data="adm_home")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Simple back button to return to admin home."""
    buttons = [
        [InlineKeyboardButton(text="↩ Back to Admin", callback_data="adm_home")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
