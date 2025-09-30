"""
Unit tests for the configuration manager.
"""

import os
import tempfile
import pytest
from unittest.mock import patch

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.config import Config


@pytest.fixture
def temp_env_file():
    """Create a temporary .env file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as tmp_file:
        tmp_file.write("""
TELEGRAM_BOT_TOKEN=test_bot_token
TELEGRAM_ADMIN_CHAT_ID=123456789
IVASMS_EMAIL=test@example.com
IVASMS_PASSWORD=test_password
POLL_INTERVAL_SECONDS=30
HEADLESS=false
DRY_RUN=true
LOG_LEVEL=DEBUG
""")
        tmp_file.flush()
        yield tmp_file.name
    
    # Clean up
    if os.path.exists(tmp_file.name):
        os.unlink(tmp_file.name)


def test_config_loading_from_env_file(temp_env_file):
    """Test loading configuration from .env file."""
    config = Config(temp_env_file)
    
    assert config.telegram_bot_token == "test_bot_token"
    assert config.telegram_admin_chat_ids == [123456789]
    assert config.ivasms_email == "test@example.com"
    assert config.ivasms_password == "test_password"
    assert config.poll_interval_seconds == 30
    assert config.headless is False
    assert config.dry_run is True
    assert config.log_level == "DEBUG"


def test_config_multiple_admin_chat_ids():
    """Test parsing multiple admin chat IDs."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789,987654321,555666777',
        'IVASMS_EMAIL': 'test@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        assert config.telegram_admin_chat_ids == [123456789, 987654321, 555666777]


def test_config_defaults():
    """Test default configuration values."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789',
        'IVASMS_EMAIL': 'test@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        
        assert config.poll_interval_seconds == 15  # default
        assert config.headless is True  # default
        assert config.dry_run is False  # default
        assert config.log_level == "INFO"  # default
        assert config.max_retries == 3  # default


def test_config_validation_missing_required():
    """Test configuration validation with missing required fields."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            Config()
        
        error_msg = str(exc_info.value)
        assert "TELEGRAM_BOT_TOKEN is required" in error_msg
        assert "TELEGRAM_ADMIN_CHAT_ID is required" in error_msg
        assert "IVASMS_EMAIL is required" in error_msg
        assert "IVASMS_PASSWORD is required" in error_msg


def test_config_validation_invalid_values():
    """Test configuration validation with invalid values."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789',
        'IVASMS_EMAIL': 'invalid_email',  # no @
        'IVASMS_PASSWORD': 'test_password',
        'POLL_INTERVAL_SECONDS': '0',  # invalid
        'LOG_LEVEL': 'INVALID'  # invalid
    }):
        with pytest.raises(ValueError) as exc_info:
            Config()
        
        error_msg = str(exc_info.value)
        assert "IVASMS_EMAIL must be a valid email address" in error_msg
        assert "POLL_INTERVAL_SECONDS must be at least 1" in error_msg
        assert "LOG_LEVEL must be one of" in error_msg


def test_config_boolean_parsing():
    """Test boolean configuration parsing."""
    test_cases = [
        ('true', True),
        ('True', True),
        ('TRUE', True),
        ('1', True),
        ('yes', True),
        ('on', True),
        ('false', False),
        ('False', False),
        ('FALSE', False),
        ('0', False),
        ('no', False),
        ('off', False),
        ('anything_else', False),
    ]
    
    for value, expected in test_cases:
        with patch.dict(os.environ, {
            'TELEGRAM_BOT_TOKEN': 'test_token',
            'TELEGRAM_ADMIN_CHAT_ID': '123456789',
            'IVASMS_EMAIL': 'test@example.com',
            'IVASMS_PASSWORD': 'test_password',
            'HEADLESS': value
        }):
            config = Config()
            assert config.headless is expected, f"Failed for value: {value}"


def test_get_masked_email():
    """Test email masking functionality."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789',
        'IVASMS_EMAIL': 'testuser@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        masked = config.get_masked_email()
        assert masked == "******er@example.com"


def test_get_masked_email_short():
    """Test email masking with short username."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789',
        'IVASMS_EMAIL': 'ab@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        masked = config.get_masked_email()
        assert masked == "**@example.com"


def test_config_summary():
    """Test configuration summary generation."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789,987654321',
        'IVASMS_EMAIL': 'test@example.com',
        'IVASMS_PASSWORD': 'test_password',
        'POLL_INTERVAL_SECONDS': '20'
    }):
        config = Config()
        summary = config.get_summary()
        
        assert summary['telegram']['bot_token_set'] is True
        assert summary['telegram']['admin_count'] == 2
        assert summary['ivasms']['password_set'] is True
        assert summary['behavior']['poll_interval_seconds'] == 20


def test_config_string_representation():
    """Test string representation of config."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789',
        'IVASMS_EMAIL': 'testuser@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        config_str = str(config)
        
        assert "Config(" in config_str
        assert "******er@example.com" in config_str
        assert "admins=1" in config_str
        assert "poll=15s" in config_str


def test_invalid_chat_id_handling():
    """Test handling of invalid chat IDs."""
    with patch.dict(os.environ, {
        'TELEGRAM_BOT_TOKEN': 'test_token',
        'TELEGRAM_ADMIN_CHAT_ID': '123456789,invalid_id,987654321',
        'IVASMS_EMAIL': 'test@example.com',
        'IVASMS_PASSWORD': 'test_password'
    }):
        config = Config()
        # Should only include valid chat IDs
        assert config.telegram_admin_chat_ids == [123456789, 987654321]


if __name__ == "__main__":
    pytest.main([__file__])
