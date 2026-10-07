"""Service coordinating safe runtime switching between Cloud and Local Bot API modes."""

import asyncio
import logging
from typing import Optional, Tuple
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.client.telegram import PRODUCTION, TelegramAPIServer

from app.config import Settings
from app.database.repository import DatabaseRepository

logger = logging.getLogger(__name__)


class ApiModeManager:
    """Coordinates safe runtime switching between Cloud and Centralized Local Bot API modes."""

    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        repository: DatabaseRepository,
    ):
        self.bot = bot
        self.settings = settings
        self.repository = repository
        self._switch_lock = asyncio.Lock()

    def get_current_mode(self) -> str:
        return "local" if self.settings.is_local_mode else "cloud"

    def get_current_endpoint(self) -> str:
        return self.settings.effective_api_base_url

    @staticmethod
    def validate_local_url(url: str) -> bool:
        """Validates that a URL is a valid HTTP/HTTPS endpoint."""
        try:
            parsed = urlparse(url.strip())
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    async def switch_mode(
        self,
        new_mode: str,
        new_base_url: Optional[str] = None,
        admin_id: Optional[int] = None,
    ) -> Tuple[bool, str]:
        """
        Safely transitions the bot between Cloud and Local Bot API modes at runtime.

        Steps:
        1. Acquire switch lock to avoid race conditions.
        2. Resolve and validate target TelegramAPIServer (always is_local=False).
        3. Temporarily update bot.session.api.
        4. Verify connectivity using bot.get_me().
        5. If get_me() fails, rollback to previous API server immediately.
        6. If get_me() succeeds, persist to DB, update Settings, adjust limits, and log audit.
        """
        new_mode = new_mode.lower().strip()
        if new_mode not in ("cloud", "local"):
            return False, f"Invalid API mode: '{new_mode}'. Must be 'cloud' or 'local'."

        async with self._switch_lock:
            prev_mode = self.get_current_mode()
            prev_url = self.get_current_endpoint()
            prev_server = getattr(self.bot.session, "api", PRODUCTION)

            # Determine candidate API server
            if new_mode == "local":
                target_url = (new_base_url or self.settings.telegram_api_base_url).strip().rstrip("/")
                if not target_url or target_url == "https://api.telegram.org":
                    target_url = "http://telegram-bot-api:8081"

                if not self.validate_local_url(target_url):
                    return False, f"Invalid Local Bot API URL: '{target_url}'. Must start with http:// or https:// with a valid host."

                # Centralized server MUST use is_local=False
                candidate_server = TelegramAPIServer.from_base(target_url, is_local=False)
            else:
                target_url = "https://api.telegram.org"
                candidate_server = PRODUCTION

            logger.info(f"Initiating runtime API switch from {prev_mode} ({prev_url}) to {new_mode} ({target_url})...")

            # Apply candidate server temporarily
            self.bot.session.api = candidate_server

            # Verify connectivity via getMe
            try:
                me = await asyncio.wait_for(self.bot.get_me(), timeout=10.0)
            except Exception as exc:
                # Rollback immediately to prevent disruption
                self.bot.session.api = prev_server
                logger.error(f"Runtime switch verification failed for {new_mode} ({target_url}): {exc}. Reverted to {prev_mode}.")
                return False, f"Connection verification failed for {new_mode.upper()} mode: {exc}. Rolled back to {prev_mode} mode."

            # Verification succeeded - update in-memory settings
            self.settings.telegram_api_mode = new_mode
            if new_mode == "local":
                self.settings.telegram_api_base_url = target_url

            # Adjust application file size limits sensibly
            if new_mode == "cloud":
                if self.settings.max_input_mb > 20:
                    self.settings.max_input_mb = 20
                    await self.repository.set_system_setting("max_input_mb", "20")
                if self.settings.max_output_mb > 50:
                    self.settings.max_output_mb = 50
                    await self.repository.set_system_setting("max_output_mb", "50")
            elif new_mode == "local":
                # If limits were at default cloud limits, scale up to local defaults
                if self.settings.max_input_mb <= 20:
                    self.settings.max_input_mb = 2000
                    await self.repository.set_system_setting("max_input_mb", "2000")
                if self.settings.max_output_mb <= 50:
                    self.settings.max_output_mb = 2000
                    await self.repository.set_system_setting("max_output_mb", "2000")

            # Persist mode & base URL in database system_settings
            await self.repository.set_system_setting("telegram_api_mode", new_mode)
            if new_mode == "local":
                await self.repository.set_system_setting("telegram_api_base_url", target_url)

            # Record in admin audit log
            if admin_id:
                await self.repository.log_audit_action(
                    admin_id=admin_id,
                    action="switch_api_mode",
                    details=f"Switched to {new_mode} mode ({target_url}). Verified as @{me.username} (ID: {me.id})",
                )

            logger.info(f"Runtime API switch completed successfully. Bot active in {new_mode} mode ({target_url}).")
            return True, f"Switched to {new_mode.upper()} mode!\nEndpoint: <code>{target_url}</code>\nConnected as: @{me.username}"

    async def update_local_url(self, new_url: str, admin_id: Optional[int] = None) -> Tuple[bool, str]:
        """Updates the local API URL. If already in local mode, applies and verifies immediately."""
        new_url = new_url.strip().rstrip("/")
        if not self.validate_local_url(new_url):
            return False, f"Invalid URL: '{new_url}'. Must start with http:// or https:// with a valid host."

        if self.settings.is_local_mode:
            return await self.switch_mode("local", new_base_url=new_url, admin_id=admin_id)

        # In cloud mode, simply save the local URL setting for future use
        self.settings.telegram_api_base_url = new_url
        await self.repository.set_system_setting("telegram_api_base_url", new_url)
        if admin_id:
            await self.repository.log_audit_action(
                admin_id=admin_id,
                action="update_setting",
                details=f"Updated Local Bot API URL to {new_url}",
            )
        return True, f"Local Bot API URL set to <code>{new_url}</code> (will be used when Local Mode is active)."

    async def reset_to_env_defaults(self, admin_id: Optional[int] = None) -> Tuple[bool, str]:
        """
        Transactionally resets dynamic overrides back to .env values with verification and rollback.

        Steps:
        1. Acquire switch lock to avoid race conditions.
        2. Save the current API server/session state.
        3. Load the .env configuration into a candidate instance.
        4. Build candidate API server.
        5. Temporarily assign candidate to bot.session.api.
        6. Verify connectivity using get_me() with 10s timeout.
        7. If verification fails:
           - restore previous bot.session.api
           - do NOT clear any DB overrides
           - do NOT change in-memory settings
           - do NOT write an audit log
           - return clear failure message
        8. Only if verification succeeds:
           - clear the database overrides
           - update in-memory settings
           - commit the successful reset
           - write the audit log
           - return success
        """
        async with self._switch_lock:
            # 2. Save current API server/session state
            prev_server = getattr(self.bot.session, "api", PRODUCTION)
            prev_mode = self.get_current_mode()

            # 3. Load the .env configuration
            candidate_settings = Settings()

            # 4. Build candidate API server
            if candidate_settings.is_local_mode:
                target_server = TelegramAPIServer.from_base(
                    candidate_settings.effective_api_base_url,
                    is_local=False,
                )
            else:
                target_server = PRODUCTION

            # 5. Temporarily assign candidate
            self.bot.session.api = target_server

            # 6. Verify connectivity via getMe
            try:
                me = await asyncio.wait_for(self.bot.get_me(), timeout=10.0)
            except Exception as exc:
                # 7. Verification failed: restore previous bot.session.api, leave DB and memory untouched
                self.bot.session.api = prev_server
                logger.error(
                    f"Connection verification failed during reset to .env defaults: {exc}. "
                    f"Rolled back to {prev_mode} mode."
                )
                return False, f"Connection verification failed during reset ({exc}). Previous configuration retained."

            # 8. Verification succeeded: clear database overrides
            for key in (
                "telegram_api_mode",
                "telegram_api_base_url",
                "max_input_mb",
                "max_output_mb",
                "show_technical_info",
                "send_cover_separately",
            ):
                await self.repository.set_system_setting(key, "")

            # Update in-memory settings
            self.settings.telegram_api_mode = candidate_settings.telegram_api_mode
            self.settings.telegram_api_base_url = candidate_settings.telegram_api_base_url
            self.settings.max_input_mb = candidate_settings.max_input_mb
            self.settings.max_output_mb = candidate_settings.max_output_mb
            self.settings.show_technical_info = candidate_settings.show_technical_info
            self.settings.send_cover_separately = candidate_settings.send_cover_separately

            # Synchronize global settings singleton
            try:
                from app.config import reload_settings
                reload_settings()
            except Exception:
                pass

            if admin_id:
                await self.repository.log_audit_action(
                    admin_id=admin_id,
                    action="reset_settings",
                    details=f"Reset settings to .env defaults ({candidate_settings.telegram_api_mode}). Verified as @{me.username}",
                )

            return True, f"Settings reset to .env defaults!\nMode: {candidate_settings.telegram_api_mode.upper()}\nConnected as: @{me.username}"

