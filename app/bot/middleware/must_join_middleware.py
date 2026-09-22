"""Middleware to enforce mandatory channel memberships."""

from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.bot.keyboards.must_join_menu import get_must_join_keyboard
from app.services.must_join_service import MustJoinService


class MustJoinMiddleware(BaseMiddleware):
    """Enforces must-join requirements before allowing audio processing."""

    def __init__(self, must_join_service: MustJoinService):
        super().__init__()
        self.must_join_service = must_join_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Check user ID from Message or CallbackQuery
        user = data.get("event_from_user")
        if user is None or user.is_bot:
            return await handler(event, data)

        bot = data["bot"]
        settings = data.get("settings")

        # Bypass for configured administrators
        if settings and settings.is_admin(user.id):
            return await handler(event, data)

        # Allow /start, /help, /channels, and must_join_verify callback
        if isinstance(event, Message) and event.text:
            cmd = event.text.split()[0].lower()
            if cmd in ("/start", "/help"):
                return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "must_join_verify":
            return await handler(event, data)

        # Verify membership
        has_joined, missing = await self.must_join_service.check_user_membership(
            bot=bot, user_id=user.id
        )

        if not has_joined:
            kb = get_must_join_keyboard(missing)
            text = (
                "📢 <b>Channel Membership Required</b>\n\n"
                "To use MusicOverdose audio metadata editor, please join our channel(s) below, "
                "then press <b>I've joined</b>."
            )
            if isinstance(event, Message):
                await event.reply(text, reply_markup=kb, parse_mode="HTML")
            elif isinstance(event, CallbackQuery):
                await event.answer("Please join the required channels first.", show_alert=True)
                if event.message:
                    await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
            return None

        return await handler(event, data)
