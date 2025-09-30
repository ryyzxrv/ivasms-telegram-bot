"""
Main bot application with comprehensive error handling and security measures.
Coordinates all components and provides the main entry point.
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timedelta
from typing import Optional

from .config import get_config
from .storage import StorageManager
from .telegram_bot import IVASMSTelegramBot
from .monitor import OTPMonitor

logger = logging.getLogger(__name__)


class IVASMSBot:
    """Main bot application that coordinates all components."""

    def __init__(self):
        self.config = get_config()
        self.storage: Optional[StorageManager] = None
        self.telegram_bot: Optional[IVASMSTelegramBot] = None
        self.monitor: Optional[OTPMonitor] = None
        
        self.is_running = False
        self.start_time = datetime.now()
        self.shutdown_event = asyncio.Event()
        
        # Heartbeat task
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.cleanup_task: Optional[asyncio.Task] = None

    async def initialize(self):
        """Initialize all bot components."""
        try:
            logger.info("Initializing iVASMS Telegram Bot")
            
            # Create necessary directories
            self.config.create_directories()
            
            # Initialize storage
            logger.info("Initializing storage manager")
            self.storage = StorageManager(self.config.db_path)
            await self.storage.initialize()
            
            # Initialize Telegram bot
            logger.info("Initializing Telegram bot")
            self.telegram_bot = IVASMSTelegramBot(
                token=self.config.telegram_bot_token,
                admin_chat_ids=self.config.telegram_admin_chat_ids,
                storage_manager=self.storage,
                monitor_manager=None,  # Will be set after monitor initialization
            )
            await self.telegram_bot.initialize()
            
            # Initialize monitor
            logger.info("Initializing OTP monitor")
            self.monitor = OTPMonitor(
                email=self.config.ivasms_email,
                password=self.config.ivasms_password,
                storage_manager=self.storage,
                telegram_bot=self.telegram_bot,
                poll_interval=self.config.poll_interval_seconds,
                headless=self.config.headless,
                dry_run=self.config.dry_run,
                max_retries=self.config.max_retries,
                retry_delay=self.config.retry_delay_seconds,
            )
            
            # Set monitor reference in telegram bot
            self.telegram_bot.monitor = self.monitor
            
            logger.info("Bot initialization completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize bot: {e}")
            await self.cleanup()
            raise

    async def start(self):
        """Start the bot and all its components."""
        if self.is_running:
            logger.warning("Bot is already running")
            return

        try:
            logger.info("Starting iVASMS Telegram Bot")
            self.is_running = True
            
            # Start Telegram bot
            telegram_task = asyncio.create_task(self.telegram_bot.run())
            
            # Start monitor
            await self.monitor.start()
            self.telegram_bot.is_monitoring = True
            
            # Start heartbeat task
            if self.config.heartbeat_interval_hours > 0:
                self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            
            # Start cleanup task
            if self.config.cleanup_old_otps_days > 0:
                self.cleanup_task = asyncio.create_task(self._cleanup_loop())
            
            logger.info("Bot started successfully")
            
            # Wait for shutdown signal
            await self.shutdown_event.wait()
            
            # Cancel telegram task
            telegram_task.cancel()
            try:
                await telegram_task
            except asyncio.CancelledError:
                pass
                
        except Exception as e:
            logger.error(f"Error during bot execution: {e}")
            if self.telegram_bot:
                await self.telegram_bot.send_error_message(e, "Bot execution")
            raise
        finally:
            await self.stop()

    async def stop(self):
        """Stop the bot and all its components."""
        if not self.is_running:
            return

        logger.info("Stopping iVASMS Telegram Bot")
        self.is_running = False
        
        try:
            # Stop monitor
            if self.monitor:
                await self.monitor.stop()
                if self.telegram_bot:
                    self.telegram_bot.is_monitoring = False
            
            # Stop heartbeat task
            if self.heartbeat_task and not self.heartbeat_task.done():
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Stop cleanup task
            if self.cleanup_task and not self.cleanup_task.done():
                self.cleanup_task.cancel()
                try:
                    await self.cleanup_task
                except asyncio.CancelledError:
                    pass
            
            # Send shutdown message
            if self.telegram_bot:
                await self.telegram_bot.send_status_message("Bot stopped")
            
            logger.info("Bot stopped successfully")
            
        except Exception as e:
            logger.error(f"Error during bot shutdown: {e}")

    async def cleanup(self):
        """Clean up resources."""
        try:
            if self.storage:
                await self.storage.close()
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def _heartbeat_loop(self):
        """Send periodic heartbeat messages."""
        logger.info(f"Starting heartbeat loop (interval: {self.config.heartbeat_interval_hours}h)")
        
        while self.is_running:
            try:
                # Wait for heartbeat interval
                await asyncio.sleep(self.config.heartbeat_interval_hours * 3600)
                
                if not self.is_running:
                    break
                
                # Send heartbeat message
                uptime = datetime.now() - self.start_time
                uptime_str = self._format_timedelta(uptime)
                
                # Get statistics
                otp_count = await self.storage.get_otp_count()
                monitor_stats = self.monitor.get_statistics()
                
                heartbeat_msg = f"💓 Heartbeat - Bot is running\n"
                heartbeat_msg += f"Uptime: {uptime_str}\n"
                heartbeat_msg += f"Total OTPs: {otp_count}\n"
                heartbeat_msg += f"Successful fetches: {monitor_stats['successful_fetches']}\n"
                heartbeat_msg += f"Failed fetches: {monitor_stats['failed_fetches']}"
                
                await self.telegram_bot.send_status_message(heartbeat_msg)
                logger.info("Heartbeat sent")
                
            except asyncio.CancelledError:
                logger.info("Heartbeat loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}")
                # Continue the loop despite errors

    async def _cleanup_loop(self):
        """Periodic cleanup of old data."""
        logger.info(f"Starting cleanup loop (interval: {self.config.cleanup_old_otps_days} days)")
        
        while self.is_running:
            try:
                # Wait 24 hours between cleanup runs
                await asyncio.sleep(24 * 3600)
                
                if not self.is_running:
                    break
                
                # Clean up old OTPs
                deleted_count = await self.storage.delete_old_otps(self.config.cleanup_old_otps_days)
                
                if deleted_count > 0:
                    logger.info(f"Cleanup: deleted {deleted_count} old OTPs")
                    await self.telegram_bot.send_status_message(
                        f"🧹 Cleanup: deleted {deleted_count} old OTPs"
                    )
                
                # Vacuum database to reclaim space
                if deleted_count > 0:
                    await self.storage.vacuum_database()
                
            except asyncio.CancelledError:
                logger.info("Cleanup loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")
                # Continue the loop despite errors

    def _format_timedelta(self, td: timedelta) -> str:
        """Format timedelta as human-readable string."""
        days = td.days
        hours, remainder = divmod(td.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        
        return " ".join(parts) if parts else "0m"

    def setup_signal_handlers(self):
        """Set up signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown")
            self.shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def health_check(self) -> dict:
        """Perform comprehensive health check."""
        health = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "uptime": self._format_timedelta(datetime.now() - self.start_time),
            "components": {}
        }
        
        try:
            # Check storage
            db_info = await self.storage.get_database_info()
            health["components"]["storage"] = {
                "status": "healthy" if "error" not in db_info else "unhealthy",
                "otp_count": db_info.get("otp_count", 0),
                "db_size_mb": db_info.get("db_size_mb", 0),
            }
            
            # Check monitor
            monitor_health = await self.monitor.health_check()
            health["components"]["monitor"] = monitor_health
            
            # Check Telegram bot
            health["components"]["telegram"] = {
                "status": "healthy" if self.telegram_bot.application else "unhealthy",
                "admin_count": len(self.telegram_bot.admin_chat_ids),
            }
            
            # Overall status
            component_statuses = [comp.get("status", "unknown") for comp in health["components"].values()]
            if "unhealthy" in component_statuses:
                health["status"] = "unhealthy"
            elif "stale" in component_statuses:
                health["status"] = "degraded"
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            health["status"] = "unhealthy"
            health["error"] = str(e)
        
        return health

    async def get_status(self) -> dict:
        """Get comprehensive bot status."""
        status = {
            "bot": {
                "is_running": self.is_running,
                "start_time": self.start_time.isoformat(),
                "uptime": self._format_timedelta(datetime.now() - self.start_time),
            },
            "config": self.config.get_summary(),
            "health": await self.health_check(),
        }
        
        if self.monitor:
            status["monitor"] = self.monitor.get_statistics()
        
        if self.storage:
            status["storage"] = await self.storage.get_database_info()
        
        return status


async def main():
    """Main entry point for the bot."""
    bot = None
    
    try:
        # Initialize configuration and logging
        config = get_config()
        config.setup_logging()
        
        logger.info("Starting iVASMS Telegram Bot")
        logger.info(f"Configuration: {config}")
        
        # Create and initialize bot
        bot = IVASMSBot()
        await bot.initialize()
        
        # Set up signal handlers
        bot.setup_signal_handlers()
        
        # Start the bot
        await bot.start()
        
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
    finally:
        if bot:
            await bot.cleanup()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())
