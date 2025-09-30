"""
Telegram bot for iVASMS OTP notifications.
Handles all bot commands and message sending functionality.
"""

import asyncio
import logging
import os
import subprocess
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)


class IVASMSTelegramBot:
    """Telegram bot for OTP notifications and management."""

    def __init__(
        self,
        token: str,
        admin_chat_ids: List[int],
        storage_manager,
        monitor_manager,
    ):
        self.token = token
        self.admin_chat_ids = admin_chat_ids
        self.storage = storage_manager
        self.monitor = monitor_manager
        
        self.application: Optional[Application] = None
        self.start_time = datetime.now()
        
        # Bot status
        self.is_monitoring = False
        self.last_login_time: Optional[datetime] = None
        self.last_fetch_time: Optional[datetime] = None

    async def initialize(self):
        """Initialize the Telegram bot application."""
        try:
            # Create application
            self.application = Application.builder().token(self.token).build()
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("config", self.config_command))
            self.application.add_handler(CommandHandler("info", self.info_command))
            self.application.add_handler(CommandHandler("recent_otps", self.recent_otps_command))
            self.application.add_handler(CommandHandler("last_otp", self.last_otp_command))
            self.application.add_handler(CommandHandler("new_otp", self.new_otp_command))
            self.application.add_handler(CommandHandler("restart", self.restart_command))
            self.application.add_handler(CommandHandler("stop", self.stop_command))
            self.application.add_handler(CommandHandler("start_monitor", self.start_monitor_command))
            self.application.add_handler(CommandHandler("logs", self.logs_command))
            
            # Add message handler for non-commands
            self.application.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
            )
            
            logger.info("Telegram bot initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Telegram bot: {e}")
            raise

    def is_admin(self, chat_id: int) -> bool:
        """Check if the chat ID is an authorized admin."""
        return chat_id in self.admin_chat_ids

    async def send_admin_message(
        self, 
        message: str, 
        parse_mode: ParseMode = ParseMode.MARKDOWN_V2,
        disable_notification: bool = False
    ):
        """Send message to all admin chats."""
        if not self.application:
            logger.error("Bot application not initialized")
            return
            
        for chat_id in self.admin_chat_ids:
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_notification=disable_notification,
                )
            except Exception as e:
                logger.error(f"Failed to send message to admin {chat_id}: {e}")

    def escape_markdown(self, text: str) -> str:
        """Escape special characters for MarkdownV2."""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        status_text = "🤖 *iVASMS Telegram Bot*\n\n"
        status_text += f"Status: {'🟢 Running' if self.is_monitoring else '🔴 Stopped'}\n"
        status_text += f"Uptime: {self._get_uptime()}\n"
        status_text += f"Admin Chat ID: `{update.effective_chat.id}`\n\n"
        status_text += "Available commands:\n"
        status_text += "• `/status` \\- Bot status\n"
        status_text += "• `/config` \\- Configuration\n"
        status_text += "• `/recent_otps` \\- Recent OTPs\n"
        status_text += "• `/last_otp` \\- Last OTP\n"
        status_text += "• `/new_otp` \\- Force fetch\n"
        status_text += "• `/logs` \\- View logs\n"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        status_text = "📊 *Bot Status*\n\n"
        status_text += f"Monitoring: {'🟢 Active' if self.is_monitoring else '🔴 Inactive'}\n"
        status_text += f"Uptime: {self._get_uptime()}\n"
        
        if self.last_login_time:
            login_time = self.last_login_time.strftime("%Y\\-%m\\-%d %H:%M:%S")
            status_text += f"Last Login: {login_time}\n"
        else:
            status_text += "Last Login: Never\n"
            
        if self.last_fetch_time:
            fetch_time = self.last_fetch_time.strftime("%Y\\-%m\\-%d %H:%M:%S")
            status_text += f"Last Fetch: {fetch_time}\n"
        else:
            status_text += "Last Fetch: Never\n"
            
        # Get OTP count
        otp_count = await self.storage.get_otp_count()
        status_text += f"Total OTPs: {otp_count}\n"
        
        await update.message.reply_text(status_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def config_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /config command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        # Mask sensitive information
        email = os.getenv("IVASMS_EMAIL", "Not set")
        if email != "Not set" and "@" in email:
            parts = email.split("@")
            masked_email = f"{'*' * (len(parts[0]) - 2)}{parts[0][-2:]}@{parts[1]}"
        else:
            masked_email = email

        config_text = "⚙️ *Configuration*\n\n"
        config_text += f"Email: `{self.escape_markdown(masked_email)}`\n"
        config_text += f"Poll Interval: {os.getenv('POLL_INTERVAL_SECONDS', '15')} seconds\n"
        config_text += f"Headless Mode: {os.getenv('HEADLESS', 'true')}\n"
        config_text += f"Log Level: {os.getenv('LOG_LEVEL', 'INFO')}\n"
        config_text += f"DB Path: `{self.escape_markdown(os.getenv('DB_PATH', './data/state.db'))}`\n"
        config_text += f"Dry Run: {os.getenv('DRY_RUN', 'false')}\n"

        await update.message.reply_text(config_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def info_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /info command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        # Get git info
        try:
            commit_sha = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"], 
                cwd=os.path.dirname(os.path.dirname(__file__)),
                text=True
            ).strip()
        except:
            commit_sha = "Unknown"

        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=os.path.dirname(os.path.dirname(__file__)),
                text=True
            ).strip()
        except:
            branch = "Unknown"

        info_text = "ℹ️ *Deployment Info*\n\n"
        info_text += f"Commit SHA: `{commit_sha}`\n"
        info_text += f"Branch: `{branch}`\n"
        info_text += f"Uptime: {self._get_uptime()}\n"
        info_text += f"Python Version: {os.sys.version.split()[0]}\n"
        info_text += f"Working Directory: `{self.escape_markdown(os.getcwd())}`\n"

        await update.message.reply_text(info_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def recent_otps_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /recent_otps command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        # Parse limit from command args
        limit = 10
        if context.args:
            try:
                limit = int(context.args[0])
                limit = max(1, min(limit, 50))  # Limit between 1 and 50
            except ValueError:
                await update.message.reply_text("❌ Invalid number format")
                return

        otps = await self.storage.get_recent_otps(limit)
        
        if not otps:
            await update.message.reply_text("📭 No OTPs found")
            return

        response_text = f"📱 *Recent {len(otps)} OTPs*\n\n"
        
        for i, otp in enumerate(otps, 1):
            response_text += f"*{i}\\.*\n"
            response_text += f"Time: `{self.escape_markdown(otp['timestamp'])}`\n"
            response_text += f"From: `{self.escape_markdown(otp['from_number'])}`\n"
            response_text += f"Text: `{self.escape_markdown(otp['text'])}`\n"
            if otp.get('service'):
                response_text += f"Service: `{self.escape_markdown(otp['service'])}`\n"
            response_text += "\n"

        # Split long messages
        if len(response_text) > 4000:
            chunks = self._split_message(response_text, 4000)
            for chunk in chunks:
                await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)
        else:
            await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def last_otp_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /last_otp command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        otp = await self.storage.get_last_otp()
        
        if not otp:
            await update.message.reply_text("📭 No OTPs found")
            return

        response_text = "📱 *Last OTP*\n\n"
        response_text += f"Time: `{self.escape_markdown(otp['timestamp'])}`\n"
        response_text += f"From: `{self.escape_markdown(otp['from_number'])}`\n"
        response_text += f"Text: `{self.escape_markdown(otp['text'])}`\n"
        if otp.get('service'):
            response_text += f"Service: `{self.escape_markdown(otp['service'])}`\n"

        await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN_V2)

    async def new_otp_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /new_otp command - force manual fetch."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        await update.message.reply_text("🔄 Forcing OTP fetch...")
        
        try:
            new_otps = await self.monitor.force_fetch()
            
            if new_otps:
                await update.message.reply_text(f"✅ Found {len(new_otps)} new OTP(s)")
            else:
                await update.message.reply_text("📭 No new OTPs found")
                
        except Exception as e:
            logger.error(f"Manual fetch failed: {e}")
            await update.message.reply_text(f"❌ Fetch failed: {str(e)}")

    async def restart_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /restart command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        await update.message.reply_text("🔄 Restarting bot...")
        
        try:
            # Stop monitoring
            await self.monitor.stop()
            
            # Restart monitoring
            await self.monitor.start()
            self.is_monitoring = True
            
            await update.message.reply_text("✅ Bot restarted successfully")
            
        except Exception as e:
            logger.error(f"Restart failed: {e}")
            await update.message.reply_text(f"❌ Restart failed: {str(e)}")

    async def stop_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stop command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        await self.monitor.stop()
        self.is_monitoring = False
        await update.message.reply_text("🛑 Monitoring stopped")

    async def start_monitor_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start_monitor command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        if self.is_monitoring:
            await update.message.reply_text("ℹ️ Monitoring is already active")
            return

        try:
            await self.monitor.start()
            self.is_monitoring = True
            await update.message.reply_text("▶️ Monitoring started")
        except Exception as e:
            logger.error(f"Failed to start monitoring: {e}")
            await update.message.reply_text(f"❌ Failed to start monitoring: {str(e)}")

    async def logs_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /logs command."""
        if not self.is_admin(update.effective_chat.id):
            await update.message.reply_text("❌ Unauthorized access")
            return

        # Parse lines from command args
        lines = 20
        if context.args:
            try:
                lines = int(context.args[0])
                lines = max(1, min(lines, 100))  # Limit between 1 and 100
            except ValueError:
                await update.message.reply_text("❌ Invalid number format")
                return

        try:
            log_file = os.getenv("LOG_FILE", "./logs/bot.log")
            
            if not os.path.exists(log_file):
                await update.message.reply_text("📄 Log file not found")
                return

            # Read last N lines
            with open(log_file, 'r') as f:
                log_lines = f.readlines()
                
            recent_lines = log_lines[-lines:] if len(log_lines) > lines else log_lines
            log_text = ''.join(recent_lines)
            
            if not log_text.strip():
                await update.message.reply_text("📄 Log file is empty")
                return

            response_text = f"📄 *Last {len(recent_lines)} log lines*\n\n"
            response_text += f"```\n{log_text}\n```"

            # Split long messages
            if len(response_text) > 4000:
                chunks = self._split_message(response_text, 4000)
                for chunk in chunks:
                    await update.message.reply_text(chunk, parse_mode=ParseMode.MARKDOWN_V2)
            else:
                await update.message.reply_text(response_text, parse_mode=ParseMode.MARKDOWN_V2)

        except Exception as e:
            logger.error(f"Failed to read logs: {e}")
            await update.message.reply_text(f"❌ Failed to read logs: {str(e)}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle non-command messages."""
        if not self.is_admin(update.effective_chat.id):
            return

        await update.message.reply_text(
            "ℹ️ Use /start to see available commands",
            parse_mode=ParseMode.MARKDOWN_V2
        )

    def _get_uptime(self) -> str:
        """Get bot uptime as formatted string."""
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def _split_message(self, text: str, max_length: int) -> List[str]:
        """Split long message into chunks."""
        chunks = []
        current_chunk = ""
        
        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 > max_length:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = line
                else:
                    # Line is too long, split it
                    chunks.append(line[:max_length])
                    current_chunk = line[max_length:]
            else:
                if current_chunk:
                    current_chunk += '\n' + line
                else:
                    current_chunk = line
        
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks

    async def send_otp_notification(self, otp: Dict[str, str]):
        """Send OTP notification to admin chats."""
        try:
            message = "🔔 *New OTP received*\n\n"
            message += f"Time: `{self.escape_markdown(otp['timestamp'])}`\n"
            message += f"From: `{self.escape_markdown(otp['from_number'])}`\n"
            message += f"Message: `{self.escape_markdown(otp['text'])}`\n"
            
            if otp.get('service'):
                message += f"Source: `{self.escape_markdown(otp['service'])}`\n"

            await self.send_admin_message(message)
            
        except Exception as e:
            logger.error(f"Failed to send OTP notification: {e}")

    async def send_status_message(self, message: str, is_error: bool = False):
        """Send status message to admin chats."""
        try:
            emoji = "❌" if is_error else "ℹ️"
            formatted_message = f"{emoji} {self.escape_markdown(message)}"
            await self.send_admin_message(formatted_message)
        except Exception as e:
            logger.error(f"Failed to send status message: {e}")

    async def send_error_message(self, error: Exception, context: str = ""):
        """Send error message to admin chats."""
        try:
            error_msg = f"❌ *Error*"
            if context:
                error_msg += f" \\({self.escape_markdown(context)}\\)"
            error_msg += f"\n\n`{self.escape_markdown(str(error))}`"
            
            # Add stack trace for debugging (truncated)
            stack_trace = traceback.format_exc()
            if len(stack_trace) > 500:
                stack_trace = stack_trace[:500] + "..."
            
            error_msg += f"\n\n```\n{stack_trace}\n```"
            
            await self.send_admin_message(error_msg)
            
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    async def run(self):
        """Run the Telegram bot."""
        try:
            logger.info("Starting Telegram bot...")
            
            # Send startup message
            await self.send_status_message("Bot started")
            
            # Start the bot
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info("Telegram bot is running")
            
            # Keep running
            while True:
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")
            await self.send_error_message(e, "Bot runtime")
            raise
        finally:
            if self.application:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()

    def update_login_time(self):
        """Update last login time."""
        self.last_login_time = datetime.now()

    def update_fetch_time(self):
        """Update last fetch time."""
        self.last_fetch_time = datetime.now()
