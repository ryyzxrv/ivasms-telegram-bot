"""
Monitor module for continuous OTP fetching and processing.
Handles the main polling loop and coordinates between web scraping and Telegram bot.
"""

import asyncio
import logging
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_exponential

from .playwright_client import IVASMSClient

logger = logging.getLogger(__name__)


class OTPMonitor:
    """Monitors iVASMS for new OTPs and processes them."""

    def __init__(
        self,
        email: str,
        password: str,
        storage_manager,
        telegram_bot,
        poll_interval: int = 15,
        headless: bool = True,
        dry_run: bool = False,
        max_retries: int = 3,
        retry_delay: int = 5,
    ):
        self.email = email
        self.password = password
        self.storage = storage_manager
        self.telegram_bot = telegram_bot
        self.poll_interval = poll_interval
        self.headless = headless
        self.dry_run = dry_run
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        self.client: Optional[IVASMSClient] = None
        self.is_running = False
        self.is_logged_in = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        # Statistics
        self.login_attempts = 0
        self.successful_fetches = 0
        self.failed_fetches = 0
        self.last_error: Optional[str] = None
        self.last_login_attempt: Optional[datetime] = None
        self.last_successful_fetch: Optional[datetime] = None

    async def start(self):
        """Start the monitoring process."""
        if self.is_running:
            logger.warning("Monitor is already running")
            return

        logger.info("Starting OTP monitor")
        self.is_running = True
        
        # Start the monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        logger.info("OTP monitor started successfully")

    async def stop(self):
        """Stop the monitoring process."""
        if not self.is_running:
            logger.warning("Monitor is not running")
            return

        logger.info("Stopping OTP monitor")
        self.is_running = False
        
        # Cancel the monitoring task
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass

        # Close the client
        if self.client:
            await self.client.close()
            self.client = None
            
        self.is_logged_in = False
        logger.info("OTP monitor stopped")

    async def force_fetch(self) -> List[Dict[str, str]]:
        """Force a manual OTP fetch (for /new_otp command)."""
        logger.info("Forcing manual OTP fetch")
        
        try:
            # Ensure we have a client and are logged in
            if not await self._ensure_logged_in():
                raise Exception("Failed to login for manual fetch")
            
            # Fetch OTPs
            otps = await self.client.fetch_otps()
            
            # Process new OTPs
            new_otps = await self._process_otps(otps)
            
            self.last_successful_fetch = datetime.now()
            self.successful_fetches += 1
            
            logger.info(f"Manual fetch completed: {len(new_otps)} new OTPs")
            return new_otps
            
        except Exception as e:
            logger.error(f"Manual fetch failed: {e}")
            self.failed_fetches += 1
            self.last_error = str(e)
            raise

    async def _monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Starting monitor loop")
        
        while self.is_running:
            try:
                # Add jitter to avoid fixed intervals
                jitter = random.uniform(0.9, 1.1)
                sleep_time = self.poll_interval * jitter
                
                logger.debug(f"Starting fetch cycle (next in {sleep_time:.1f}s)")
                
                # Perform the fetch cycle
                await self._fetch_cycle()
                
                # Sleep until next cycle
                await asyncio.sleep(sleep_time)
                
            except asyncio.CancelledError:
                logger.info("Monitor loop cancelled")
                break
            except Exception as e:
                logger.error(f"Unexpected error in monitor loop: {e}")
                self.last_error = str(e)
                
                # Send error notification
                await self.telegram_bot.send_error_message(e, "Monitor loop")
                
                # Wait before retrying
                await asyncio.sleep(self.retry_delay)

    async def _fetch_cycle(self):
        """Perform one fetch cycle."""
        try:
            # Ensure we're logged in
            if not await self._ensure_logged_in():
                logger.error("Failed to ensure login, skipping fetch cycle")
                return

            # Fetch OTPs
            otps = await self.client.fetch_otps()
            
            # Process new OTPs
            new_otps = await self._process_otps(otps)
            
            # Update statistics
            self.last_successful_fetch = datetime.now()
            self.successful_fetches += 1
            self.telegram_bot.update_fetch_time()
            
            if new_otps:
                logger.info(f"Fetch cycle completed: {len(new_otps)} new OTPs")
            else:
                logger.debug("Fetch cycle completed: no new OTPs")
                
        except Exception as e:
            logger.error(f"Fetch cycle failed: {e}")
            self.failed_fetches += 1
            self.last_error = str(e)
            
            # Send error notification for persistent failures
            if self.failed_fetches % 5 == 0:  # Every 5th failure
                await self.telegram_bot.send_error_message(e, "Fetch cycle")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def _ensure_logged_in(self) -> bool:
        """Ensure we have a valid login session."""
        try:
            # Create client if needed
            if not self.client:
                self.client = IVASMSClient(
                    email=self.email,
                    password=self.password,
                    headless=self.headless,
                )
                await self.client.start()

            # Check if already logged in
            if self.is_logged_in:
                try:
                    # Verify login is still valid
                    if await self.client.is_logged_in():
                        logger.debug("Already logged in and session is valid")
                        return True
                    else:
                        logger.info("Session expired, need to re-login")
                        self.is_logged_in = False
                except Exception as e:
                    logger.warning(f"Login check failed: {e}")
                    self.is_logged_in = False

            # Attempt login
            logger.info("Attempting login to iVASMS")
            self.login_attempts += 1
            self.last_login_attempt = datetime.now()
            
            success, message = await self.client.login()
            
            if success:
                self.is_logged_in = True
                self.telegram_bot.update_login_time()
                
                # Send success notification
                await self.telegram_bot.send_status_message(f"Login successful: {message}")
                
                # Navigate to SMS received page
                nav_success, nav_message = await self.client.navigate_to_sms_received()
                if nav_success:
                    await self.telegram_bot.send_status_message(f"Navigation successful: {nav_message}")
                    logger.info(f"Login and navigation successful: {message}, {nav_message}")
                    return True
                else:
                    logger.error(f"Navigation failed: {nav_message}")
                    await self.telegram_bot.send_status_message(f"Navigation failed: {nav_message}", is_error=True)
                    return False
            else:
                logger.error(f"Login failed: {message}")
                await self.telegram_bot.send_status_message(f"Login failed: {message}", is_error=True)
                return False
                
        except Exception as e:
            logger.error(f"Login process failed: {e}")
            self.is_logged_in = False
            
            # Close and recreate client on persistent failures
            if self.client:
                await self.client.close()
                self.client = None
                
            raise

    async def _process_otps(self, otps: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Process fetched OTPs and identify new ones."""
        if not otps:
            return []

        logger.debug(f"Processing {len(otps)} OTPs")
        
        # Get the last seen OTP ID
        last_seen_id = await self.storage.get_last_seen_otp_id()
        
        new_otps = []
        latest_id = last_seen_id
        
        for otp in otps:
            otp_id = otp['id']
            
            # Check if this is a new OTP
            if not last_seen_id or otp_id != last_seen_id:
                # Check if we've already processed this OTP
                if not await self.storage.otp_exists(otp_id):
                    new_otps.append(otp)
                    
                    # Store the OTP
                    await self.storage.store_otp(otp)
                    
                    # Update latest ID
                    latest_id = otp_id
                    
                    logger.info(f"New OTP detected: {otp_id}")
                    
                    # Send notification (unless in dry run mode)
                    if not self.dry_run:
                        await self.telegram_bot.send_otp_notification(otp)
                    else:
                        logger.info(f"DRY RUN: Would send OTP notification for {otp_id}")

        # Update last seen OTP ID
        if latest_id != last_seen_id:
            await self.storage.set_last_seen_otp_id(latest_id)
            logger.debug(f"Updated last seen OTP ID: {latest_id}")

        return new_otps

    def get_statistics(self) -> Dict[str, any]:
        """Get monitoring statistics."""
        return {
            "is_running": self.is_running,
            "is_logged_in": self.is_logged_in,
            "login_attempts": self.login_attempts,
            "successful_fetches": self.successful_fetches,
            "failed_fetches": self.failed_fetches,
            "last_error": self.last_error,
            "last_login_attempt": self.last_login_attempt,
            "last_successful_fetch": self.last_successful_fetch,
            "poll_interval": self.poll_interval,
            "dry_run": self.dry_run,
        }

    async def health_check(self) -> Dict[str, any]:
        """Perform health check."""
        health = {
            "status": "healthy" if self.is_running and self.is_logged_in else "unhealthy",
            "is_running": self.is_running,
            "is_logged_in": self.is_logged_in,
            "last_successful_fetch": self.last_successful_fetch,
            "last_error": self.last_error,
        }
        
        # Check if we haven't had a successful fetch in too long
        if self.last_successful_fetch:
            time_since_fetch = datetime.now() - self.last_successful_fetch
            if time_since_fetch > timedelta(minutes=self.poll_interval * 5):  # 5x poll interval
                health["status"] = "stale"
                health["warning"] = f"No successful fetch in {time_since_fetch}"
        
        return health

    async def restart_client(self):
        """Restart the Playwright client."""
        logger.info("Restarting Playwright client")
        
        if self.client:
            await self.client.close()
            self.client = None
            
        self.is_logged_in = False
        
        # The client will be recreated on next login attempt
        logger.info("Playwright client restarted")
