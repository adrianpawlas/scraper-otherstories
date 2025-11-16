"""Category page scraper for extracting product URLs."""

import re
import time
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from loguru import logger

from scraper.browser import BrowserManager
from utils.config import Config


class CategoryScraper:
    """Scraper for category pages to extract product information."""

    def __init__(self, config: Config, browser_manager: BrowserManager):
        self.config = config
        self.browser = browser_manager
        self.brand_config = config.get_brand_config()
        self.scraping_config = config.get_scraping_config()
        self.selectors = config.get_selectors()

    def extract_product_urls(self, category_url: str) -> List[str]:
        """Extract all product URLs from a category page."""
        product_urls = []
        page = 1
        max_pages = self.scraping_config.get('max_pages', 50)

        logger.info(f"Starting to extract product URLs from: {category_url}")

        while page <= max_pages:
            current_url = self._get_page_url(category_url, page)

            if not self.browser.get_page(current_url):
                logger.error(f"Failed to load page {page}: {current_url}")
                break

            # Wait for products to load
            if not self._wait_for_products():
                logger.warning(f"No products found on page {page}, stopping pagination")
                break

            # Extract product URLs from current page
            page_urls = self._extract_urls_from_page()
            product_urls.extend(page_urls)

            logger.info(f"Extracted {len(page_urls)} product URLs from page {page} (total: {len(product_urls)})")

            # Check if there's a next page
            if not self._has_next_page():
                logger.info("No more pages to scrape")
                break

            page += 1

            # Rate limiting
            time.sleep(self.scraping_config.get('rate_limit_delay', 1))

        logger.info(f"Total product URLs extracted: {len(product_urls)}")
        return list(set(product_urls))  # Remove duplicates

    def _get_page_url(self, base_url: str, page: int) -> str:
        """Generate URL for a specific page number."""
        if page == 1:
            return base_url

        # Check if URL already has query parameters
        if '?' in base_url:
            return f"{base_url}&page={page}"
        else:
            return f"{base_url}?page={page}"

    def _wait_for_products(self) -> bool:
        """Wait for product data to load."""
        # Wait a bit for JavaScript to execute
        import time
        time.sleep(5)  # Give more time for JavaScript to execute

        page_source = self.browser.get_page_source()
        has_products = '"href"' in page_source and 'product' in page_source
        logger.info(f"Page has product data: {has_products}")
        return has_products

    def _extract_urls_from_page(self) -> List[str]:
        """Extract product URLs from the current page."""
        product_urls = []

        # First try to extract from embedded JSON data
        json_urls = self._extract_urls_from_json()
        if json_urls:
            product_urls.extend(json_urls)

        # Fallback to HTML parsing if JSON extraction fails
        if not product_urls:
            html_urls = self._extract_urls_from_html()
            product_urls.extend(html_urls)

        return list(set(product_urls))  # Remove duplicates

    def _extract_urls_from_json(self) -> List[str]:
        """Extract product URLs from embedded JSON data."""
        try:
            page_source = self.browser.get_page_source()

            # Look for product data in JavaScript
            import re

            # Pattern to find href attributes that contain /product/
            href_pattern = r'"href"\s*:\s*"([^"]*/product/[^"]*)"'
            matches = re.findall(href_pattern, page_source)

            logger.info(f"Regex matches: {len(matches)}")
            if matches:
                logger.info(f"First few matches: {matches[:3]}")

            urls = []
            for relative_url in matches:
                if relative_url and '/product/' in relative_url:
                    # Ensure absolute URL
                    if relative_url.startswith('http'):
                        full_url = relative_url
                    else:
                        full_url = urljoin(self.brand_config['base_url'], relative_url)

                    logger.info(f"Checking URL: {full_url}")
                    if self._is_valid_product_url(full_url):
                        urls.append(full_url)
                        logger.info(f"Valid URL added: {full_url}")
                    else:
                        logger.info(f"Invalid URL rejected: {full_url}")

            logger.info(f"Extracted {len(urls)} URLs from JSON data")
            if urls:
                logger.info(f"Sample URLs: {urls[:3]}")
            else:
                logger.warning("No URLs found with regex pattern")
                # Debug: check if the pattern is finding anything at all
                all_href_matches = re.findall(r'"href"\s*:\s*"[^"]*"', page_source)
                logger.info(f"Found {len(all_href_matches)} href patterns in entire page")
                if all_href_matches:
                    # Filter for product URLs
                    product_hrefs = [m for m in all_href_matches if 'product' in m]
                    logger.info(f"Found {len(product_hrefs)} product href patterns")
                    if product_hrefs:
                        logger.info(f"Sample product href matches: {product_hrefs[:3]}")
            return urls

        except Exception as e:
            logger.debug(f"Error extracting URLs from JSON: {e}")
            return []

    def _extract_urls_from_html(self) -> List[str]:
        """Extract product URLs from HTML elements (fallback method)."""
        product_urls = []
        selector = self.selectors['category'].get('product_link', 'a[href*="/product/"]')

        try:
            product_links = self.browser.find_elements(selector)

            for link in product_links:
                try:
                    href = link.get_attribute('href')
                    if href:
                        # Ensure absolute URL
                        if href.startswith('http'):
                            full_url = href
                        else:
                            full_url = urljoin(self.brand_config['base_url'], href)

                        # Validate URL format
                        if self._is_valid_product_url(full_url):
                            product_urls.append(full_url)

                except Exception as e:
                    logger.debug(f"Error extracting URL from link: {e}")
                    continue

        except Exception as e:
            logger.warning(f"Error extracting product URLs from HTML: {e}")

        return product_urls

    def _is_valid_product_url(self, url: str) -> bool:
        """Validate if URL is a valid product URL."""
        try:
            parsed = urlparse(url)
            pattern = self.brand_config.get('product_url_pattern', '/product/')

            # Check if URL contains product pattern
            if isinstance(pattern, str):
                result = pattern in url
                logger.debug(f"URL validation: '{url}' contains '{pattern}': {result}")
                return result
            else:
                # If pattern is a regex
                return bool(re.search(pattern, url))

        except Exception as e:
            logger.debug(f"URL validation error for '{url}': {e}")
            return False

    def _has_next_page(self) -> bool:
        """Check if there's a next page available."""
        selector = self.selectors['category'].get('next_page', '[data-testid="pagination-next"]')

        try:
            next_button = self.browser.find_element(selector)
            if next_button:
                # Check if button is enabled/disabled
                disabled = next_button.get_attribute('disabled')
                aria_disabled = next_button.get_attribute('aria-disabled')

                if disabled or aria_disabled == 'true':
                    return False

                return True

            # Alternative: check for pagination links
            pagination_links = self.browser.find_elements('a[href*="page="]')
            current_page = self._get_current_page_number()

            for link in pagination_links:
                href = link.get_attribute('href')
                if href and 'page=' in href:
                    page_num = self._extract_page_number(href)
                    if page_num and page_num > current_page:
                        return True

            return False

        except Exception as e:
            logger.debug(f"Error checking for next page: {e}")
            return False

    def _get_current_page_number(self) -> int:
        """Get the current page number from URL."""
        try:
            current_url = self.browser.driver.current_url
            parsed = urlparse(current_url)

            # Check query parameters
            if 'page' in parsed.query:
                params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
                return int(params.get('page', 1))

            return 1

        except Exception:
            return 1

    def _extract_page_number(self, url: str) -> Optional[int]:
        """Extract page number from URL."""
        try:
            parsed = urlparse(url)
            if 'page' in parsed.query:
                params = dict(param.split('=') for param in parsed.query.split('&') if '=' in param)
                return int(params.get('page', 0))
            return None
        except Exception:
            return None

    def extract_product_summaries(self, category_url: str) -> List[Dict[str, Any]]:
        """Extract basic product information from category page."""
        summaries = []

        if not self.browser.get_page(category_url):
            logger.error(f"Failed to load category page: {category_url}")
            return summaries

        if not self._wait_for_products():
            logger.warning("No products found on category page")
            return summaries

        try:
            product_containers = self.browser.find_elements(
                self.selectors['category'].get('product_container', '[data-testid="product-item"]')
            )

            for container in product_containers:
                try:
                    summary = self._extract_product_summary(container)
                    if summary:
                        summaries.append(summary)

                except Exception as e:
                    logger.debug(f"Error extracting product summary: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error extracting product summaries: {e}")

        logger.info(f"Extracted {len(summaries)} product summaries")
        return summaries

    def _extract_product_summary(self, container) -> Optional[Dict[str, Any]]:
        """Extract basic product information from a container element."""
        try:
            # Extract title
            title_selector = self.selectors['category'].get('product_title', '[data-testid="product-title"]')
            title_elem = container.find_element(By.CSS_SELECTOR, title_selector) if hasattr(container, 'find_element') else None
            title = title_elem.text.strip() if title_elem else ""

            # Extract price
            price_selector = self.selectors['category'].get('product_price', '[data-testid="product-price"]')
            price_elem = container.find_element(By.CSS_SELECTOR, price_selector) if hasattr(container, 'find_element') else None
            price_text = price_elem.text.strip() if price_elem else ""

            # Extract image URL
            image_selector = self.selectors['category'].get('product_image', '[data-testid="product-image"] img')
            img_elem = container.find_element(By.CSS_SELECTOR, image_selector) if hasattr(container, 'find_element') else None
            image_url = img_elem.get_attribute('src') if img_elem else ""

            # Extract product URL
            link_selector = self.selectors['category'].get('product_link', 'a[href*="/product/"]')
            link_elem = container.find_element(By.CSS_SELECTOR, link_selector) if hasattr(container, 'find_element') else None
            product_url = link_elem.get_attribute('href') if link_elem else ""

            if not title or not product_url:
                return None

            return {
                'title': title,
                'price_text': price_text,
                'image_url': image_url,
                'product_url': urljoin(self.brand_config['base_url'], product_url) if product_url else "",
                'source': self.brand_config.get('source', 'other_stories'),
                'brand': self.brand_config.get('name', '& Other Stories')
            }

        except Exception as e:
            logger.debug(f"Error extracting product summary: {e}")
            return None
