"""Tests for Centralized Telegram Local Bot API Decoupling, Dual Mode, and Admin Settings."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from aiogram.client.telegram import PRODUCTION, TelegramAPIServer
from aiogram.types import CallbackQuery, Message, User
# no yaml import

from app.bot.handlers.admin_handlers import (
    callback_adm_set_mode,
    callback_adm_set_reset,
    callback_adm_set_toggle,
    callback_adm_settings,
    render_admin_dashboard,
    render_admin_settings,
)
from app.config import Settings
from app.database.repository import DatabaseRepository
from app.services.api_mode_manager import ApiModeManager


# ==============================================================================
# 1. Endpoint Resolution & Dual-Mode Settings Tests
# ==============================================================================

def test_cloud_mode_default_resolution():
    """Default configuration must resolve to official Telegram servers (Cloud mode)."""
    s = Settings(bot_token="test_token")
    assert s.telegram_api_mode == "cloud"
    assert s.is_local_mode is False
    assert s.effective_api_base_url == "https://api.telegram.org"
    assert s.max_input_mb == 20
    assert s.max_output_mb == 50


def test_local_mode_endpoint_resolution():
    """When TELEGRAM_API_MODE=local, resolves to local endpoint (defaulting to http://telegram-bot-api:8081)."""
    # Without custom URL
    s1 = Settings(bot_token="test_token", telegram_api_mode="local")
    assert s1.is_local_mode is True
    assert s1.effective_api_base_url == "http://telegram-bot-api:8081"

    # With custom URL
    s2 = Settings(
        bot_token="test_token",
        telegram_api_mode="local",
        telegram_api_base_url="http://custom-bot-api:8081/",
    )
    assert s2.is_local_mode is True
    assert s2.effective_api_base_url == "http://custom-bot-api:8081"


def test_explicit_cloud_mode_overrides_local_url():
    """Explicit TELEGRAM_API_MODE=cloud is authoritative and overrides local URL."""
    s = Settings(
        bot_token="test_token",
        telegram_api_mode="cloud",
        telegram_api_base_url="http://telegram-bot-api:8081",
    )
    assert s.is_local_mode is False
    assert s.effective_api_base_url == "https://api.telegram.org"


def test_no_api_id_or_hash_required():
    """Verify Settings requires neither api_id nor api_hash."""
    s = Settings(bot_token="test_token")
    assert not hasattr(s, "telegram_api_id")
    assert not hasattr(s, "telegram_api_hash")
    assert not hasattr(s, "api_id")
    assert not hasattr(s, "api_hash")


# ==============================================================================
# 2. Local Bot API Client Architecture Tests: is_local MUST BE False
# ==============================================================================

def test_centralized_server_uses_is_local_false():
    """
    Centralized Local Bot API runs in a separate container without shared filesystem.
    Client MUST communicate via HTTP with is_local=False.
    """
    server = TelegramAPIServer.from_base("http://telegram-bot-api:8081", is_local=False)
    assert server.is_local is False
    assert server.base == "http://telegram-bot-api:8081/bot{token}/{method}"
    assert server.file == "http://telegram-bot-api:8081/file/bot{token}/{path}"


# ==============================================================================
# 3. ApiModeManager Controlled Configuration & Migration Requirement Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_configure_mode_persists_without_mutating_bot_session_api(test_repo: DatabaseRepository):
    """
    Changing mode must persist target configuration to database and in-memory settings,
    but MUST NEVER dynamically mutate bot.session.api on the live running instance.
    """
    settings = Settings(bot_token="test_token", telegram_api_mode="cloud")
    mock_bot = MagicMock()
    mock_bot.session.api = PRODUCTION

    manager = ApiModeManager(
        bot=mock_bot,
        settings=settings,
        repository=test_repo,
        running_mode="cloud",
        running_endpoint="https://api.telegram.org",
    )

    # Configure local mode
    ok, msg = await manager.configure_mode("local", "http://telegram-bot-api:8081", admin_id=1001)
    assert ok is True
    assert "Telegram Bot API migration required" in msg
    assert "logOut" in msg

    # Settings and database MUST be updated
    assert settings.telegram_api_mode == "local"
    assert settings.is_local_mode is True
    assert settings.effective_api_base_url == "http://telegram-bot-api:8081"
    saved_mode = await test_repo.get_system_setting("telegram_api_mode")
    assert saved_mode == "local"
    saved_url = await test_repo.get_system_setting("telegram_api_base_url")
    assert saved_url == "http://telegram-bot-api:8081"

    # CRITICAL: bot.session.api must NOT be mutated on the running bot!
    assert mock_bot.session.api == PRODUCTION

    # Audit log recorded with migration notice
    logs, _ = await test_repo.get_audit_logs(limit=1)
    assert len(logs) == 1
    assert logs[0].action == "configure_api_mode"
    assert "Migration required" in logs[0].details


def test_restart_required_vs_migration_required_state_logic(test_repo: DatabaseRepository):
    """
    Verify distinct evaluation of is_restart_required() and is_migration_required().
    """
    settings = Settings(bot_token="test_token", telegram_api_mode="cloud")
    manager = ApiModeManager(
        bot=None,
        settings=settings,
        repository=test_repo,
        running_mode="cloud",
        running_endpoint="https://api.telegram.org",
    )

    # 1. Initially matching: neither restart nor migration required
    assert manager.is_restart_required() is False
    assert manager.is_migration_required() is False

    # 2. Configured changed to local: both restart and migration required
    settings.telegram_api_mode = "local"
    settings.telegram_api_base_url = "http://telegram-bot-api:8081"
    assert manager.is_restart_required() is True
    assert manager.is_migration_required() is True
    assert "logOut" in manager.get_migration_instructions()
    assert "logOut" in manager.get_migration_instructions_text()

    # 3. Simulated boot with local mode: running matches configured
    local_mgr = ApiModeManager(
        bot=None,
        settings=settings,
        repository=test_repo,
        running_mode="local",
        running_endpoint="http://telegram-bot-api:8081",
    )
    assert local_mgr.is_restart_required() is False
    assert local_mgr.is_migration_required() is False

    # 4. Local bot configured with a different local endpoint: migration required
    settings.telegram_api_base_url = "http://other-local-api:8081"
    assert local_mgr.is_restart_required() is True
    assert local_mgr.is_migration_required() is True


def test_invalid_local_url_handling():
    """Invalid URLs must be rejected."""
    assert ApiModeManager.validate_local_url("http://telegram-bot-api:8081") is True
    assert ApiModeManager.validate_local_url("https://api.local.net:8443") is True
    assert ApiModeManager.validate_local_url("ftp://invalid:8081") is False
    assert ApiModeManager.validate_local_url("not-a-url") is False
    assert ApiModeManager.validate_local_url("") is False


# ==============================================================================
# 4. Settings Persistence Across Restart Simulation
# ==============================================================================

@pytest.mark.asyncio
async def test_settings_persistence_across_startup(test_repo: DatabaseRepository):
    """Verify that settings persisted in DB override .env defaults when loaded on startup."""
    # Simulate user changing settings in DB
    await test_repo.set_system_setting("telegram_api_mode", "local")
    await test_repo.set_system_setting("telegram_api_base_url", "http://my-vps-api:8081")
    await test_repo.set_system_setting("max_input_mb", "1500")
    await test_repo.set_system_setting("max_output_mb", "1500")

    # Simulate new application startup loading DB overrides
    new_settings = Settings(bot_token="test_token", telegram_api_mode="cloud")
    db_mode = await test_repo.get_system_setting("telegram_api_mode", "")
    if db_mode:
        new_settings.telegram_api_mode = db_mode
    db_url = await test_repo.get_system_setting("telegram_api_base_url", "")
    if db_url:
        new_settings.telegram_api_base_url = db_url
    db_in = await test_repo.get_system_setting("max_input_mb", "")
    if db_in:
        new_settings.max_input_mb = int(db_in)

    assert new_settings.is_local_mode is True
    assert new_settings.effective_api_base_url == "http://my-vps-api:8081"
    assert new_settings.max_input_mb == 1500


# ==============================================================================
# 5. Telegram Admin Panel Handlers Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_admin_settings_rendering_and_mode_switch(test_repo: DatabaseRepository):
    settings = Settings(bot_token="test_token", admin_ids=[1001])
    api_mgr = ApiModeManager(
        bot=None,
        settings=settings,
        repository=test_repo,
        running_mode="cloud",
        running_endpoint="https://api.telegram.org",
    )

    # 1. Matching running and configured: no migration notice
    text, kb = render_admin_settings(settings, api_mode_manager=api_mgr)
    assert "Bot Configuration & API Settings" in text
    assert "Active API Mode:" in text
    assert "Telegram Bot API Migration Required" not in text

    # 2. Configured changed to local: displays migration notice
    settings.telegram_api_mode = "local"
    settings.telegram_api_base_url = "http://telegram-bot-api:8081"
    text_mig, _ = render_admin_settings(settings, api_mode_manager=api_mgr)
    assert "Telegram Bot API Migration Required" in text_mig
    assert "Call Telegram <code>logOut</code>" in text_mig

    # Test dashboard rendering includes API mode
    dash_text, dash_kb = await render_admin_dashboard(settings, test_repo)
    assert "API Mode:" in dash_text

    # Test callback_adm_settings
    cb = MagicMock()
    cb.from_user.id = 1001
    cb.message = MagicMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()

    await callback_adm_settings(cb, settings, api_mode_manager=api_mgr)
    cb.message.edit_text.assert_called_once()
    assert "Bot Configuration & API Settings" in cb.message.edit_text.call_args[0][0]

    # Test mode configuration via callback_adm_set_mode
    cb.data = "adm_set_mode:local"
    cb.bot = MagicMock()
    cb.bot.session.api = PRODUCTION

    await callback_adm_set_mode(cb, settings, test_repo, api_mode_manager=api_mgr)
    assert settings.is_local_mode is True
    assert cb.bot.session.api == PRODUCTION  # Must NOT mutate live session

    # Test feature toggle (Technical specs)
    cb.data = "adm_set_toggle:tech"
    initial_tech = settings.show_technical_info
    await callback_adm_set_toggle(cb, settings, test_repo, api_mode_manager=api_mgr)
    assert settings.show_technical_info is not initial_tech


# ==============================================================================
# 6. Docker External Network Configuration Test
# ==============================================================================

def test_compose_yaml_external_network():
    """Verify compose.yaml connects to external telegram-bots network."""
    compose_path = Path("/home/farzad/metadataeditor/compose.yaml")
    assert compose_path.exists()
    content = compose_path.read_text()

    # Bot service must join telegram-bots and declare external: true
    assert "telegram-bots" in content
    assert "external: true" in content
    assert "- telegram-bots" in content


def test_portainer_environment_configuration_in_compose():
    """Verify compose files are identical, pass variables through environment block and do not use env_file."""
    compose_path = Path("/home/farzad/metadataeditor/compose.yaml")
    docker_compose_path = Path("/home/farzad/metadataeditor/docker-compose.yml")

    assert compose_path.exists(), "compose.yaml must exist"
    assert docker_compose_path.exists(), "docker-compose.yml must exist"

    compose_text = compose_path.read_text()
    docker_compose_text = docker_compose_path.read_text()

    # Must be 100% identical
    assert compose_text == docker_compose_text, "compose.yaml and docker-compose.yml must be identical"

    for filename, content in (("compose.yaml", compose_text), ("docker-compose.yml", docker_compose_text)):
        # Must NOT depend on env_file: .env (Portainer compatibility)
        assert "env_file:" not in content, f"{filename} should not have env_file"
        assert ".env" not in content, f"{filename} should not reference .env"

        # Must have environment block with Portainer interpolation
        assert "environment:" in content, f"{filename} must have environment block"
        assert "BOT_TOKEN: ${BOT_TOKEN}" in content
        assert "ADMIN_IDS: ${ADMIN_IDS" in content
        assert "TELEGRAM_API_MODE: ${TELEGRAM_API_MODE" in content
        assert "TELEGRAM_API_BASE_URL: ${TELEGRAM_API_BASE_URL" in content
        assert "MAX_INPUT_MB: ${MAX_INPUT_MB" in content
        assert "MAX_OUTPUT_MB: ${MAX_OUTPUT_MB" in content

        # Must include external telegram-bots network
        assert "telegram-bots:" in content
        assert "external: true" in content


@pytest.mark.asyncio
async def test_reset_to_env_defaults_clears_db_and_updates_restart_state(test_repo: DatabaseRepository):
    """
    Resetting to defaults clears database overrides and detects if a restart/migration
    is needed without touching live bot session.
    """
    settings = Settings(
        bot_token="test_token",
        telegram_api_mode="local",
        telegram_api_base_url="http://local-stack:8081",
        max_input_mb=500,
        max_output_mb=1000,
    )
    mock_bot = MagicMock()
    mock_bot.session.api = TelegramAPIServer.from_base("http://local-stack:8081", is_local=False)

    # Set overrides in database
    await test_repo.set_system_setting("telegram_api_mode", "local")
    await test_repo.set_system_setting("telegram_api_base_url", "http://local-stack:8081")
    await test_repo.set_system_setting("max_input_mb", "500")
    await test_repo.set_system_setting("max_output_mb", "1000")

    manager = ApiModeManager(
        bot=mock_bot,
        settings=settings,
        repository=test_repo,
        running_mode="local",
        running_endpoint="http://local-stack:8081",
    )

    ok, msg = await manager.reset_to_env_defaults(admin_id=1001)
    assert ok is True
    assert "Settings reset to .env defaults" in msg

    # Database overrides must be cleared
    assert await test_repo.get_system_setting("telegram_api_mode") == ""
    assert await test_repo.get_system_setting("telegram_api_base_url") == ""
    assert await test_repo.get_system_setting("max_input_mb") == ""
    assert await test_repo.get_system_setting("max_output_mb") == ""

    # Live session must NOT be mutated
    assert mock_bot.session.api.is_local is False
    assert "http://local-stack:8081" in mock_bot.session.api.base

    # Configured is now cloud (from .env default), but running is local -> migration required!
    assert manager.is_migration_required() is True
    assert manager.is_restart_required() is True

    # Audit log recorded
    logs, _ = await test_repo.get_audit_logs(limit=1)
    assert len(logs) == 1
    assert logs[0].action == "reset_settings"


def test_docker_entrypoint_and_dockerfile_permissions():
    """Verify docker-entrypoint.sh exists, is executable, and Dockerfile uses it."""
    entrypoint_path = Path("/home/farzad/metadataeditor/docker-entrypoint.sh")
    assert entrypoint_path.exists(), "docker-entrypoint.sh must exist"
    content = entrypoint_path.read_text()
    assert "chown -R botuser:botgroup /data /tmp/audio-bot" in content
    assert "gosu botuser" in content

    dockerfile_path = Path("/home/farzad/metadataeditor/Dockerfile")
    assert dockerfile_path.exists()
    dockerfile_content = dockerfile_path.read_text()
    assert "gosu" in dockerfile_content
    assert 'ENTRYPOINT ["docker-entrypoint.sh"]' in dockerfile_content
    assert "docker-entrypoint.sh" in dockerfile_content

