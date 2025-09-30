"""
Integration tests for the bot components.
"""

import asyncio
import os
import tempfile
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.storage import StorageManager
from src.monitor import OTPMonitor
from src.telegram_bot import IVASMSTelegramBot


@pytest.fixture
async def storage_manager():
    """Create a temporary storage manager for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    storage = StorageManager(db_path)
    await storage.initialize()
    
    yield storage
    
    await storage.close()
    
    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_telegram_bot():
    """Create a mock Telegram bot for testing."""
    bot = MagicMock()
    bot.send_otp_notification = AsyncMock()
    bot.send_status_message = AsyncMock()
    bot.send_error_message = AsyncMock()
    bot.update_login_time = MagicMock()
    bot.update_fetch_time = MagicMock()
    return bot


@pytest.fixture
def sample_otps():
    """Sample OTP data for testing."""
    return [
        {
            'id': 'otp_1_+1234567890',
            'timestamp': '2025-09-30 12:00:00',
            'from_number': '+1234567890',
            'text': 'Your verification code is 123456',
            'service': 'TestService1'
        },
        {
            'id': 'otp_2_+0987654321',
            'timestamp': '2025-09-30 12:01:00',
            'from_number': '+0987654321',
            'text': 'Your OTP is 654321',
            'service': 'TestService2'
        }
    ]


@pytest.mark.asyncio
async def test_monitor_otp_processing(storage_manager, mock_telegram_bot, sample_otps):
    """Test OTP processing in the monitor."""
    # Create monitor with mocked client
    monitor = OTPMonitor(
        email="test@example.com",
        password="test_password",
        storage_manager=storage_manager,
        telegram_bot=mock_telegram_bot,
        poll_interval=1,
        headless=True,
        dry_run=False
    )
    
    # Mock the client
    mock_client = AsyncMock()
    mock_client.fetch_otps.return_value = sample_otps
    monitor.client = mock_client
    monitor.is_logged_in = True
    
    # Process OTPs
    new_otps = await monitor._process_otps(sample_otps)
    
    # Should have processed both OTPs as new
    assert len(new_otps) == 2
    
    # Check that OTPs were stored
    stored_count = await storage_manager.get_otp_count()
    assert stored_count == 2
    
    # Check that notifications were sent
    assert mock_telegram_bot.send_otp_notification.call_count == 2
    
    # Process same OTPs again - should not create duplicates
    new_otps = await monitor._process_otps(sample_otps)
    assert len(new_otps) == 0  # No new OTPs
    
    # Count should still be 2
    stored_count = await storage_manager.get_otp_count()
    assert stored_count == 2


@pytest.mark.asyncio
async def test_monitor_dry_run_mode(storage_manager, mock_telegram_bot, sample_otps):
    """Test monitor in dry run mode."""
    # Create monitor in dry run mode
    monitor = OTPMonitor(
        email="test@example.com",
        password="test_password",
        storage_manager=storage_manager,
        telegram_bot=mock_telegram_bot,
        poll_interval=1,
        headless=True,
        dry_run=True  # Dry run mode
    )
    
    # Mock the client
    mock_client = AsyncMock()
    mock_client.fetch_otps.return_value = sample_otps
    monitor.client = mock_client
    monitor.is_logged_in = True
    
    # Process OTPs
    new_otps = await monitor._process_otps(sample_otps)
    
    # Should have processed both OTPs as new
    assert len(new_otps) == 2
    
    # Check that OTPs were stored (even in dry run)
    stored_count = await storage_manager.get_otp_count()
    assert stored_count == 2
    
    # Check that NO notifications were sent (dry run mode)
    assert mock_telegram_bot.send_otp_notification.call_count == 0


@pytest.mark.asyncio
async def test_monitor_statistics(storage_manager, mock_telegram_bot):
    """Test monitor statistics tracking."""
    monitor = OTPMonitor(
        email="test@example.com",
        password="test_password",
        storage_manager=storage_manager,
        telegram_bot=mock_telegram_bot,
        poll_interval=1,
        headless=True
    )
    
    # Initial statistics
    stats = monitor.get_statistics()
    assert stats['is_running'] is False
    assert stats['successful_fetches'] == 0
    assert stats['failed_fetches'] == 0
    assert stats['login_attempts'] == 0
    
    # Simulate some activity
    monitor.successful_fetches = 5
    monitor.failed_fetches = 2
    monitor.login_attempts = 3
    
    stats = monitor.get_statistics()
    assert stats['successful_fetches'] == 5
    assert stats['failed_fetches'] == 2
    assert stats['login_attempts'] == 3


@pytest.mark.asyncio
async def test_monitor_health_check(storage_manager, mock_telegram_bot):
    """Test monitor health check."""
    monitor = OTPMonitor(
        email="test@example.com",
        password="test_password",
        storage_manager=storage_manager,
        telegram_bot=mock_telegram_bot,
        poll_interval=1,
        headless=True
    )
    
    # Health check when not running
    health = await monitor.health_check()
    assert health['status'] == 'unhealthy'
    assert health['is_running'] is False
    assert health['is_logged_in'] is False
    
    # Simulate running state
    monitor.is_running = True
    monitor.is_logged_in = True
    
    health = await monitor.health_check()
    assert health['status'] == 'healthy'
    assert health['is_running'] is True
    assert health['is_logged_in'] is True


@pytest.mark.asyncio
async def test_storage_and_retrieval_integration(storage_manager, sample_otps):
    """Test integration between storage operations."""
    # Store OTPs
    for otp in sample_otps:
        await storage_manager.store_otp(otp)
    
    # Test last seen OTP ID functionality
    await storage_manager.set_last_seen_otp_id(sample_otps[0]['id'])
    last_seen = await storage_manager.get_last_seen_otp_id()
    assert last_seen == sample_otps[0]['id']
    
    # Test recent OTPs retrieval
    recent = await storage_manager.get_recent_otps(5)
    assert len(recent) == 2
    
    # Test last OTP
    last_otp = await storage_manager.get_last_otp()
    assert last_otp is not None
    assert last_otp['id'] in [otp['id'] for otp in sample_otps]
    
    # Test database info
    info = await storage_manager.get_database_info()
    assert info['otp_count'] == 2
    assert info['db_size_bytes'] > 0


@pytest.mark.asyncio
async def test_telegram_bot_admin_validation():
    """Test Telegram bot admin validation."""
    admin_chat_ids = [123456789, 987654321]
    
    bot = IVASMSTelegramBot(
        token="test_token",
        admin_chat_ids=admin_chat_ids,
        storage_manager=None,
        monitor_manager=None
    )
    
    # Test admin validation
    assert bot.is_admin(123456789) is True
    assert bot.is_admin(987654321) is True
    assert bot.is_admin(555666777) is False


@pytest.mark.asyncio
async def test_telegram_bot_markdown_escaping():
    """Test Telegram bot markdown escaping."""
    bot = IVASMSTelegramBot(
        token="test_token",
        admin_chat_ids=[123456789],
        storage_manager=None,
        monitor_manager=None
    )
    
    # Test special character escaping
    test_text = "Test_message*with[special]characters(and)more~stuff`here"
    escaped = bot.escape_markdown(test_text)
    
    # Should escape all special characters
    assert "_" not in escaped or "\\\_" in escaped
    assert "*" not in escaped or "\\*" in escaped
    assert "[" not in escaped or "\\[" in escaped


@pytest.mark.asyncio
async def test_end_to_end_otp_flow(storage_manager, mock_telegram_bot, sample_otps):
    """Test complete OTP processing flow."""
    # Create monitor
    monitor = OTPMonitor(
        email="test@example.com",
        password="test_password",
        storage_manager=storage_manager,
        telegram_bot=mock_telegram_bot,
        poll_interval=1,
        headless=True,
        dry_run=False
    )
    
    # Mock successful login and navigation
    mock_client = AsyncMock()
    mock_client.login.return_value = (True, "Login successful")
    mock_client.navigate_to_sms_received.return_value = (True, "Navigation successful")
    mock_client.is_logged_in.return_value = True
    mock_client.fetch_otps.return_value = sample_otps
    
    monitor.client = mock_client
    
    # Simulate login process
    login_success = await monitor._ensure_logged_in()
    assert login_success is True
    
    # Verify login notifications were sent
    assert mock_telegram_bot.send_status_message.call_count >= 2  # Login + Navigation
    
    # Simulate fetch cycle
    await monitor._fetch_cycle()
    
    # Verify OTPs were processed and notifications sent
    stored_count = await storage_manager.get_otp_count()
    assert stored_count == 2
    
    assert mock_telegram_bot.send_otp_notification.call_count == 2
    
    # Verify last seen OTP ID was updated
    last_seen = await storage_manager.get_last_seen_otp_id()
    assert last_seen is not None
    assert last_seen in [otp['id'] for otp in sample_otps]


if __name__ == "__main__":
    pytest.main([__file__])
