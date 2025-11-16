"""Browser automation setup using Selenium."""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
import time
from typing import Optional, Any
from loguru import logger

from utils.config import Config


class BrowserManager:
    """Manages Selenium WebDriver instance."""

    def __init__(self, config: Config):
        self.config = config
        self.driver: Optional[webdriver.Chrome] = None

    def setup_driver(self) -> bool:
        """Setup Chrome WebDriver with appropriate options."""
        try:
            chrome_options = Options()

            if self.config.headless:
                chrome_options.add_argument('--headless')

            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--disable-extensions')
            chrome_options.add_argument('--disable-plugins')
            chrome_options.add_argument('--disable-images')  # Speed up loading
            chrome_options.add_argument('--disable-javascript')  # We'll enable it selectively
            chrome_options.add_argument('--disable-web-security')
            chrome_options.add_argument('--allow-running-insecure-content')
            chrome_options.add_argument(f'--user-agent={self.config.user_agent}')

            # Additional options for stability
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)

            # Execute script to remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            logger.info("Chrome WebDriver initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to setup Chrome WebDriver: {e}")
            return False

    def quit_driver(self):
        """Quit the WebDriver instance."""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver quit successfully")
            except Exception as e:
                logger.warning(f"Error quitting WebDriver: {e}")
            finally:
                self.driver = None

    def get_page(self, url: str, timeout: int = 30) -> bool:
        """Navigate to a URL and wait for page to load."""
        if not self.driver:
            logger.error("WebDriver not initialized")
            return False

        try:
            logger.debug(f"Navigating to: {url}")
            self.driver.get(url)

            # Wait for page to be ready
            WebDriverWait(self.driver, timeout).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )

            # Additional wait for dynamic content
            time.sleep(2)

            return True

        except TimeoutException:
            logger.warning(f"Timeout loading page: {url}")
            return False
        except WebDriverException as e:
            logger.error(f"WebDriver error loading page {url}: {e}")
            return False

    def wait_for_element(self, selector: str, timeout: int = 10) -> Optional[Any]:
        """Wait for an element to be present and return it."""
        if not self.driver:
            return None

        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            return element
        except TimeoutException:
            logger.debug(f"Element not found: {selector}")
            return None

    def wait_for_elements(self, selector: str, timeout: int = 10) -> list:
        """Wait for elements to be present and return them."""
        if not self.driver:
            return []

        try:
            elements = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, selector))
            )
            return elements
        except TimeoutException:
            logger.debug(f"Elements not found: {selector}")
            return []

    def scroll_to_bottom(self):
        """Scroll to the bottom of the page to load more content."""
        if not self.driver:
            return

        try:
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait for content to load
        except Exception as e:
            logger.warning(f"Error scrolling to bottom: {e}")

    def get_page_source(self) -> str:
        """Get the current page source."""
        if not self.driver:
            return ""
        return self.driver.page_source

    def find_element(self, selector: str) -> Optional[Any]:
        """Find a single element by CSS selector."""
        if not self.driver:
            return None

        try:
            return self.driver.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            return None

    def find_elements(self, selector: str) -> list:
        """Find multiple elements by CSS selector."""
        if not self.driver:
            return []

        try:
            return self.driver.find_elements(By.CSS_SELECTOR, selector)
        except Exception:
            return []

    def get_element_text(self, selector: str) -> str:
        """Get text content of an element."""
        element = self.find_element(selector)
        if element:
            return element.text.strip()
        return ""

    def get_element_attribute(self, selector: str, attribute: str) -> str:
        """Get attribute value of an element."""
        element = self.find_element(selector)
        if element:
            return element.get_attribute(attribute) or ""
        return ""

    def is_element_present(self, selector: str) -> bool:
        """Check if an element is present on the page."""
        return self.find_element(selector) is not None
