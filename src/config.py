"""
Configuration manager for environment variables and settings.
Handles loading and validation of all bot configuration.
"""

import os
import logging
from typing import List, Optional
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for the iVASMS Telegram bot."""

    def __init__(self, env_file: str = ".env"):
        """Initialize configuration by loading environment variables."""
        # Load environment variables from .env file if it exists
        if os.path.exists(env_file):
            load_dotenv(env_file)
            logger.info(f"Loaded environment variables from {env_file}")
        else:
            logger.info("No .env file found, using system environment variables")

        # Load and validate configuration
        self._load_config()
        self._validate_config()

    def _load_config(self):
        """Load configuration from environment variables."""
        
        # Telegram configuration
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_admin_chat_id = os.getenv("TELEGRAM_ADMIN_CHAT_ID")
        
        # Parse admin chat IDs (support multiple admins)
        self.telegram_admin_chat_ids = []
        if self.telegram_admin_chat_id:
            chat_ids_str = self.telegram_admin_chat_id.replace(" ", "")
            for chat_id in chat_ids_str.split(","):
                try:
                    self.telegram_admin_chat_ids.append(int(chat_id))
                except ValueError:
                    logger.warning(f"Invalid chat ID format: {chat_id}")

        # iVASMS credentials
        self.ivasms_email = os.getenv("IVASMS_EMAIL")
        self.ivasms_password = os.getenv("IVASMS_PASSWORD")

        # Bot behavior configuration
        self.poll_interval_seconds = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))
        self.headless = os.getenv("HEADLESS", "true").lower() in ("true", "1", "yes", "on")
        self.dry_run = os.getenv("DRY_RUN", "false").lower() in ("true", "1", "yes", "on")
        
        # Retry and error handling
        self.max_retries = int(os.getenv("MAX_RETRIES", "3"))
        self.retry_delay_seconds = int(os.getenv("RETRY_DELAY_SECONDS", "5"))
        
        # Storage configuration
        self.db_path = os.getenv("DB_PATH", "./data/state.db")
        
        # Logging configuration
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_file = os.getenv("LOG_FILE", "./logs/bot.log")
        
        # Optional features
        self.heartbeat_interval_hours = int(os.getenv("HEARTBEAT_INTERVAL_HOURS", "24"))
        self.cleanup_old_otps_days = int(os.getenv("CLEANUP_OLD_OTPS_DAYS", "30"))
        
        # Browser configuration
        self.browser_state_path = os.getenv("BROWSER_STATE_PATH", "./browser_state")
        self.screenshot_path = os.getenv("SCREENSHOT_PATH", "./screenshots")
        
        # Development and debugging
        self.debug_mode = os.getenv("DEBUG_MODE", "false").lower() in ("true", "1", "yes", "on")
        self.save_screenshots = os.getenv("SAVE_SCREENSHOTS", "true").lower() in ("true", "1", "yes", "on")

    def _validate_config(self):
        """Validate required configuration values."""
        errors = []

        # Required Telegram configuration
        if not self.telegram_bot_token:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        
        if not self.telegram_admin_chat_ids:
            errors.append("TELEGRAM_ADMIN_CHAT_ID is required and must be a valid integer or comma-separated integers")

        # Required iVASMS credentials
        if not self.ivasms_email:
            errors.append("IVASMS_EMAIL is required")
        
        if not self.ivasms_password:
            errors.append("IVASMS_PASSWORD is required")

        # Validate numeric values
        if self.poll_interval_seconds < 1:
            errors.append("POLL_INTERVAL_SECONDS must be at least 1")
        
        if self.max_retries < 1:
            errors.append("MAX_RETRIES must be at least 1")
        
        if self.retry_delay_seconds < 1:
            errors.append("RETRY_DELAY_SECONDS must be at least 1")
        
        if self.heartbeat_interval_hours < 1:
            errors.append("HEARTBEAT_INTERVAL_HOURS must be at least 1")
        
        if self.cleanup_old_otps_days < 1:
            errors.append("CLEANUP_OLD_OTPS_DAYS must be at least 1")

        # Validate log level
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.log_level not in valid_log_levels:
            errors.append(f"LOG_LEVEL must be one of: {', '.join(valid_log_levels)}")

        # Validate email format (basic check)
        if self.ivasms_email and "@" not in self.ivasms_email:
            errors.append("IVASMS_EMAIL must be a valid email address")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Configuration validation passed")

    def get_masked_email(self) -> str:
        """Get email with masked username for display purposes."""
        if not self.ivasms_email or "@" not in self.ivasms_email:
            return "Invalid email"
        
        parts = self.ivasms_email.split("@")
        username = parts[0]
        domain = parts[1]
        
        if len(username) <= 2:
            masked_username = "*" * len(username)
        else:
            masked_username = "*" * (len(username) - 2) + username[-2:]
        
        return f"{masked_username}@{domain}"

    def get_summary(self) -> dict:
        """Get a summary of current configuration for display."""
        return {
            "telegram": {
                "bot_token_set": bool(self.telegram_bot_token),
                "admin_chat_ids": self.telegram_admin_chat_ids,
                "admin_count": len(self.telegram_admin_chat_ids),
            },
            "ivasms": {
                "email": self.get_masked_email(),
                "password_set": bool(self.ivasms_password),
            },
            "behavior": {
                "poll_interval_seconds": self.poll_interval_seconds,
                "headless": self.headless,
                "dry_run": self.dry_run,
                "max_retries": self.max_retries,
                "retry_delay_seconds": self.retry_delay_seconds,
            },
            "storage": {
                "db_path": self.db_path,
            },
            "logging": {
                "log_level": self.log_level,
                "log_file": self.log_file,
            },
            "optional": {
                "heartbeat_interval_hours": self.heartbeat_interval_hours,
                "cleanup_old_otps_days": self.cleanup_old_otps_days,
                "debug_mode": self.debug_mode,
                "save_screenshots": self.save_screenshots,
            }
        }

    def create_directories(self):
        """Create necessary directories based on configuration."""
        directories = [
            os.path.dirname(self.db_path),
            os.path.dirname(self.log_file),
            self.browser_state_path,
            self.screenshot_path,
        ]
        
        for directory in directories:
            if directory and not os.path.exists(directory):
                try:
                    os.makedirs(directory, exist_ok=True)
                    logger.debug(f"Created directory: {directory}")
                except Exception as e:
                    logger.warning(f"Failed to create directory {directory}: {e}")

    def setup_logging(self):
        """Set up logging based on configuration."""
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        # Configure logging
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        
        # Set up file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(getattr(logging, self.log_level))
        file_handler.setFormatter(logging.Formatter(log_format))

        # Set up console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(getattr(logging, self.log_level))
        console_handler.setFormatter(logging.Formatter(log_format))

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.log_level))
        
        # Clear existing handlers
        root_logger.handlers.clear()
        
        # Add handlers
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Reduce noise from external libraries
        logging.getLogger("telegram").setLevel(logging.WARNING)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("playwright").setLevel(logging.WARNING)

        logger.info(f"Logging configured: level={self.log_level}, file={self.log_file}")

    def __str__(self) -> str:
        """String representation of configuration."""
        summary = self.get_summary()
        return f"Config(email={summary['ivasms']['email']}, admins={summary['telegram']['admin_count']}, poll={summary['behavior']['poll_interval_seconds']}s)"

    def __repr__(self) -> str:
        """Detailed representation of configuration."""
        return f"Config({self.get_summary()})"


# Global configuration instance
config: Optional[Config] = None


def get_config(env_file: str = ".env") -> Config:
    """Get the global configuration instance."""
    global config
    if config is None:
        config = Config(env_file)
    return config


def reload_config(env_file: str = ".env") -> Config:
    """Reload the global configuration instance."""
    global config
    config = Config(env_file)
    return config
