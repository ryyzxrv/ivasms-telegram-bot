"""
Playwright client for interacting with ivasms.com website.
Handles login, navigation, and OTP fetching operations.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class IVASMSClient:
    """Playwright client for ivasms.com website interactions."""

    def __init__(
        self,
        email: str,
        password: str,
        headless: bool = True,
        browser_state_path: str = "./browser_state",
    ):
        self.email = email
        self.password = password
        self.headless = headless
        self.browser_state_path = browser_state_path
        
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # URLs
        self.base_url = "https://www.ivasms.com"
        self.login_url = f"{self.base_url}/login"
        self.dashboard_url = f"{self.base_url}/portal"
        self.sms_received_url = f"{self.base_url}/portal/sms/received"
        
        # Selectors (may need adjustment based on actual site structure)
        self.selectors = {
            "email_input": 'input[name="email"], input[type="email"], #email',
            "password_input": 'input[name="password"], input[type="password"], #password',
            "login_button": 'button[type="submit"], input[type="submit"], button:has-text("Log in")',
            "dashboard_indicator": '.dashboard, .sidebar, .main-content, [data-testid="dashboard"]',
            "client_menu": 'a:has-text("Client"), .nav-item:has-text("Client")',
            "sms_statistics_menu": 'a:has-text("My SMS Statistics"), a[href*="sms/received"]',
            "sms_table": 'table, .message-list, .sms-list, #received-sms-table',
            "sms_rows": 'tbody tr, .message, .sms-item, .sms-entry',
            "sms_timestamp": '.sms-time, .timestamp, .date, .time, td:nth-child(1)',
            "sms_from": '.sms-from, .sender, .from, .number, td:nth-child(2)',
            "sms_text": '.sms-text, .message-text, .content, .text, td:nth-child(3)',
            "sms_service": '.sms-service, .service, .source, td:nth-child(4)',
        }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def start(self):
        """Initialize Playwright and browser."""
        try:
            self.playwright = await async_playwright().start()
            
            # Launch browser
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ]
            )
            
            # Create or restore browser context
            if os.path.exists(f"{self.browser_state_path}/state.json"):
                logger.info("Restoring browser state from previous session")
                self.context = await self.browser.new_context(
                    storage_state=f"{self.browser_state_path}/state.json"
                )
            else:
                logger.info("Creating new browser context")
                self.context = await self.browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
            
            # Create page
            self.page = await self.context.new_page()
            
            # Set reasonable timeouts
            self.page.set_default_timeout(30000)  # 30 seconds
            
            logger.info("Playwright client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Playwright client: {e}")
            await self.close()
            raise

    async def close(self):
        """Clean up resources."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def save_browser_state(self):
        """Save browser state for session persistence."""
        try:
            os.makedirs(self.browser_state_path, exist_ok=True)
            await self.context.storage_state(path=f"{self.browser_state_path}/state.json")
            logger.debug("Browser state saved successfully")
        except Exception as e:
            logger.error(f"Failed to save browser state: {e}")

    async def take_screenshot(self, filename: str = None) -> str:
        """Take a screenshot for debugging purposes."""
        try:
            if not filename:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            screenshot_dir = "./screenshots"
            os.makedirs(screenshot_dir, exist_ok=True)
            screenshot_path = os.path.join(screenshot_dir, filename)
            
            await self.page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot saved: {screenshot_path}")
            return screenshot_path
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            return ""

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def login(self) -> Tuple[bool, str]:
        """
        Attempt to login to ivasms.com.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            logger.info("Attempting to login to ivasms.com")
            
            # Navigate to login page
            await self.page.goto(self.login_url, wait_until="networkidle")
            await asyncio.sleep(2)  # Allow page to fully load
            
            # Check if already logged in by trying to access dashboard
            try:
                await self.page.goto(self.dashboard_url, wait_until="networkidle")
                if await self.page.locator(self.selectors["dashboard_indicator"]).first.is_visible():
                    logger.info("Already logged in, skipping login process")
                    await self.save_browser_state()
                    return True, "Already logged in"
            except:
                # Not logged in, proceed with login
                pass
            
            # Go back to login page if needed
            await self.page.goto(self.login_url, wait_until="networkidle")
            
            # Fill email
            email_input = self.page.locator(self.selectors["email_input"]).first
            await email_input.wait_for(state="visible", timeout=10000)
            await email_input.fill(self.email)
            logger.debug("Email filled")
            
            # Fill password
            password_input = self.page.locator(self.selectors["password_input"]).first
            await password_input.wait_for(state="visible", timeout=10000)
            await password_input.fill(self.password)
            logger.debug("Password filled")
            
            # Click login button
            login_button = self.page.locator(self.selectors["login_button"]).first
            await login_button.wait_for(state="visible", timeout=10000)
            
            # Wait for navigation after login
            async with self.page.expect_navigation(wait_until="networkidle", timeout=30000):
                await login_button.click()
            
            # Verify login success by checking for dashboard elements
            try:
                await self.page.wait_for_selector(
                    self.selectors["dashboard_indicator"], 
                    timeout=15000
                )
                logger.info("Login successful - dashboard detected")
                await self.save_browser_state()
                return True, "Login successful"
                
            except Exception as e:
                # Check for error messages
                error_message = "Login failed - unknown error"
                try:
                    # Common error selectors
                    error_selectors = [
                        '.error, .alert-danger, .login-error',
                        '[class*="error"]',
                        '[class*="invalid"]'
                    ]
                    
                    for selector in error_selectors:
                        error_element = self.page.locator(selector).first
                        if await error_element.is_visible():
                            error_text = await error_element.text_content()
                            if error_text:
                                error_message = f"Login failed: {error_text.strip()}"
                                break
                except:
                    pass
                
                logger.error(f"Login verification failed: {error_message}")
                await self.take_screenshot("login_failed.png")
                return False, error_message
                
        except Exception as e:
            logger.error(f"Login attempt failed: {e}")
            await self.take_screenshot("login_error.png")
            return False, f"Login error: {str(e)}"

    async def navigate_to_sms_received(self) -> Tuple[bool, str]:
        """
        Navigate to the SMS received page.
        
        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            logger.info("Navigating to SMS received page")
            
            # Try direct navigation first
            try:
                await self.page.goto(self.sms_received_url, wait_until="networkidle")
                
                # Check if we're on the right page
                await self.page.wait_for_selector(
                    self.selectors["sms_table"], 
                    timeout=10000
                )
                logger.info("Successfully navigated directly to SMS received page")
                return True, "Navigation successful (direct)"
                
            except:
                logger.debug("Direct navigation failed, trying menu navigation")
                pass
            
            # If direct navigation fails, try menu navigation
            await self.page.goto(self.dashboard_url, wait_until="networkidle")
            
            # Click Client menu
            try:
                client_menu = self.page.locator(self.selectors["client_menu"]).first
                await client_menu.wait_for(state="visible", timeout=10000)
                await client_menu.click()
                await asyncio.sleep(1)  # Wait for submenu to appear
                logger.debug("Clicked Client menu")
            except Exception as e:
                logger.warning(f"Could not find Client menu: {e}")
            
            # Click My SMS Statistics
            sms_stats_menu = self.page.locator(self.selectors["sms_statistics_menu"]).first
            await sms_stats_menu.wait_for(state="visible", timeout=10000)
            await sms_stats_menu.click()
            
            # Wait for SMS table to load
            await self.page.wait_for_selector(
                self.selectors["sms_table"], 
                timeout=15000
            )
            
            logger.info("Successfully navigated to SMS received page via menu")
            return True, "Navigation successful (via menu)"
            
        except Exception as e:
            logger.error(f"Navigation to SMS received page failed: {e}")
            await self.take_screenshot("navigation_failed.png")
            return False, f"Navigation failed: {str(e)}"

    async def fetch_otps(self) -> List[Dict[str, str]]:
        """
        Fetch OTP messages from the SMS received page.
        
        Returns:
            List[Dict[str, str]]: List of OTP entries with keys:
                - id: unique identifier (timestamp + from number)
                - timestamp: when the SMS was received
                - from_number: sender phone number
                - text: SMS content
                - service: associated service (if available)
        """
        try:
            logger.info("Fetching OTPs from SMS received page")
            
            # Ensure we're on the right page
            current_url = self.page.url
            if "sms/received" not in current_url:
                success, message = await self.navigate_to_sms_received()
                if not success:
                    logger.error(f"Could not navigate to SMS page: {message}")
                    return []
            
            # Wait for table to load
            await self.page.wait_for_selector(self.selectors["sms_table"], timeout=10000)
            
            # Get all SMS rows
            rows = self.page.locator(self.selectors["sms_rows"])
            row_count = await rows.count()
            
            if row_count == 0:
                logger.info("No SMS messages found")
                return []
            
            logger.info(f"Found {row_count} SMS entries")
            
            otps = []
            
            for i in range(row_count):
                try:
                    row = rows.nth(i)
                    
                    # Extract timestamp
                    timestamp_element = row.locator(self.selectors["sms_timestamp"]).first
                    timestamp = await timestamp_element.text_content() or ""
                    timestamp = timestamp.strip()
                    
                    # Extract from number
                    from_element = row.locator(self.selectors["sms_from"]).first
                    from_number = await from_element.text_content() or ""
                    from_number = from_number.strip()
                    
                    # Extract SMS text
                    text_element = row.locator(self.selectors["sms_text"]).first
                    text = await text_element.text_content() or ""
                    text = text.strip()
                    
                    # Extract service (optional)
                    service = ""
                    try:
                        service_element = row.locator(self.selectors["sms_service"]).first
                        if await service_element.is_visible():
                            service = await service_element.text_content() or ""
                            service = service.strip()
                    except:
                        pass
                    
                    # Create unique ID
                    otp_id = f"{timestamp}_{from_number}".replace(" ", "_")
                    
                    # Only include if we have essential data
                    if timestamp and from_number and text:
                        otp_entry = {
                            "id": otp_id,
                            "timestamp": timestamp,
                            "from_number": from_number,
                            "text": text,
                            "service": service,
                        }
                        otps.append(otp_entry)
                        logger.debug(f"Extracted OTP: {otp_id}")
                    
                except Exception as e:
                    logger.warning(f"Failed to extract data from row {i}: {e}")
                    continue
            
            logger.info(f"Successfully extracted {len(otps)} OTP entries")
            return otps
            
        except Exception as e:
            logger.error(f"Failed to fetch OTPs: {e}")
            await self.take_screenshot("fetch_otps_failed.png")
            return []

    async def is_logged_in(self) -> bool:
        """Check if currently logged in."""
        try:
            await self.page.goto(self.dashboard_url, wait_until="networkidle")
            await self.page.wait_for_selector(
                self.selectors["dashboard_indicator"], 
                timeout=5000
            )
            return True
        except:
            return False

    async def get_page_title(self) -> str:
        """Get current page title for debugging."""
        try:
            return await self.page.title()
        except:
            return "Unknown"

    async def get_current_url(self) -> str:
        """Get current page URL for debugging."""
        try:
            return self.page.url
        except:
            return "Unknown"
