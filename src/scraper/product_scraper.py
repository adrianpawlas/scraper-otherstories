"""Individual product page scraper."""

import re
import json
from typing import Dict, Any, Optional, List
from urllib.parse import urljoin
from loguru import logger

from scraper.browser import BrowserManager
from utils.config import Config


class ProductScraper:
    """Scraper for individual product pages."""

    def __init__(self, config: Config, browser_manager: BrowserManager):
        self.config = config
        self.browser = browser_manager
        self.brand_config = config.get_brand_config()
        self.selectors = config.get_selectors()

    def scrape_product(self, product_url: str) -> Optional[Dict[str, Any]]:
        """Scrape detailed product information from a product page."""
        logger.debug(f"Scraping product: {product_url}")

        if not self.browser.get_page(product_url):
            logger.warning(f"Failed to load product page: {product_url}")
            return None

        try:
            # Extract basic product information
            product_data = {
                'source': self.brand_config.get('source', 'other_stories'),
                'product_url': product_url,
                'brand': self.brand_config.get('name', '& Other Stories'),
                'second_hand': False  # This brand sells new items only
            }

            # Extract product ID from URL
            product_id = self._extract_product_id(product_url)
            if product_id:
                product_data['id'] = product_id

            # Extract title
            title = self._extract_title()
            if title:
                product_data['title'] = title

            # Extract description
            description = self._extract_description()
            if description:
                product_data['description'] = description

            # Extract price and currency
            price_info = self._extract_price()
            if price_info:
                product_data.update(price_info)

            # Extract image URL
            image_url = self._extract_image_url()
            if image_url:
                product_data['image_url'] = image_url

            # Extract sizes
            sizes = self._extract_sizes()
            if sizes:
                product_data['size'] = ', '.join(sizes)

            # Extract gender (inferred from categories or URL)
            gender = self._extract_gender()
            if gender:
                product_data['gender'] = gender

            # Extract category
            category = self._extract_category()
            if category:
                product_data['category'] = category

            # Extract additional metadata
            metadata = self._extract_metadata()
            if metadata:
                product_data['metadata'] = metadata

            # Validate required fields
            required_fields = ['id', 'product_url', 'image_url', 'title']
            if not all(field in product_data for field in required_fields):
                logger.warning(f"Missing required fields for product: {product_url}")
                return None

            logger.debug(f"Successfully scraped product: {product_data.get('title', 'Unknown')}")
            return product_data

        except Exception as e:
            logger.error(f"Error scraping product {product_url}: {e}")
            return None

    def _extract_product_id(self, url: str) -> Optional[str]:
        """Extract product ID from URL."""
        try:
            # Pattern: /product/product-name-product-id/
            match = re.search(r'/product/[^/]+-(\d+)/?$', url)
            if match:
                return match.group(1)

            # Alternative pattern: extract from URL path
            from urllib.parse import urlparse
            path = urlparse(url).path
            parts = path.strip('/').split('/')
            if len(parts) >= 2 and parts[-2] == 'product':
                return parts[-1].split('-')[-1]

            return None

        except Exception as e:
            logger.debug(f"Error extracting product ID from {url}: {e}")
            return None

    def _extract_title(self) -> Optional[str]:
        """Extract product title."""
        selectors = self.selectors['product'].get('title', ['h1', '[data-testid="product-title"]'])

        if isinstance(selectors, str):
            selectors = [selectors]

        for selector in selectors:
            title = self.browser.get_element_text(selector)
            if title:
                return title.strip()

        return None

    def _extract_description(self) -> Optional[str]:
        """Extract product description."""
        selectors = self.selectors['product'].get('description', [
            '[data-testid="product-description"]',
            '.product-description',
            '.description'
        ])

        if isinstance(selectors, str):
            selectors = [selectors]

        for selector in selectors:
            description = self.browser.get_element_text(selector)
            if description:
                return description.strip()

        return None

    def _extract_price(self) -> Optional[Dict[str, Any]]:
        """Extract price and currency information."""
        selectors = self.selectors['product'].get('price', [
            '[data-testid="product-price"]',
            '.product-price',
            '.price'
        ])

        if isinstance(selectors, str):
            selectors = [selectors]

        for selector in selectors:
            price_text = self.browser.get_element_text(selector)
            if price_text:
                return self._parse_price(price_text)

        return None

    def _parse_price(self, price_text: str) -> Dict[str, Any]:
        """Parse price text to extract numeric value and currency."""
        try:
            # Remove extra whitespace
            price_text = ' '.join(price_text.split())

            # Common patterns: "€49", "$49.99", "49 €", etc.
            # Extract currency symbol and amount
            match = re.search(r'([€$£¥₹₽₩₦₨₪₫₡₵₺₴₸₼₲₱₭₯₰₳₶₷₹₻₽₾₿⃀])?\s*(\d+(?:[.,]\d+)?)', price_text)

            if match:
                currency_symbol = match.group(1) or ''
                amount_str = match.group(2)

                # Convert to float, handling different decimal separators
                amount_str = amount_str.replace(',', '.')
                amount = float(amount_str)

                # Map currency symbols to codes
                currency_map = {
                    '€': 'EUR',
                    '$': 'USD',
                    '£': 'GBP',
                    '¥': 'JPY',
                    '₹': 'INR',
                    '₽': 'RUB',
                    '₩': 'KRW'
                }

                currency = currency_map.get(currency_symbol, 'EUR')  # Default to EUR

                return {
                    'price': amount,
                    'currency': currency
                }

            # Fallback: try to extract just the number
            numbers = re.findall(r'\d+(?:[.,]\d+)?', price_text)
            if numbers:
                amount = float(numbers[0].replace(',', '.'))
                return {
                    'price': amount,
                    'currency': 'EUR'  # Default for & Other Stories
                }

        except Exception as e:
            logger.debug(f"Error parsing price '{price_text}': {e}")

        return None

    def _extract_image_url(self) -> Optional[str]:
        """Extract main product image URL."""
        selectors = self.selectors['product'].get('image', [
            '[data-testid="product-image"] img',
            '.product-gallery img',
            '.product-image img'
        ])

        if isinstance(selectors, str):
            selectors = [selectors]

        for selector in selectors:
            img_url = self.browser.get_element_attribute(selector, 'src')
            if img_url:
                # Ensure absolute URL
                if img_url.startswith('http'):
                    return img_url
                else:
                    return urljoin(self.brand_config['base_url'], img_url)

        return None

    def _extract_sizes(self) -> List[str]:
        """Extract available sizes."""
        sizes = []
        selector = self.selectors['product'].get('sizes', '[data-testid="size-selector"] button')

        try:
            size_elements = self.browser.find_elements(selector)

            for element in size_elements:
                size_text = element.text.strip()
                if size_text and size_text not in ['Size', 'Select size']:
                    sizes.append(size_text)

        except Exception as e:
            logger.debug(f"Error extracting sizes: {e}")

        return sizes

    def _extract_gender(self) -> Optional[str]:
        """Extract gender information."""
        # For & Other Stories, most items are unisex/women's
        # Check URL or breadcrumbs for gender hints
        current_url = self.browser.driver.current_url.lower()

        if 'women' in current_url or 'womens' in current_url:
            return 'women'
        elif 'men' in current_url or 'mens' in current_url:
            return 'men'
        elif 'unisex' in current_url:
            return 'unisex'
        else:
            # Default to women for & Other Stories
            return 'women'

    def _extract_category(self) -> Optional[str]:
        """Extract product category."""
        # Try to extract from breadcrumbs or URL
        try:
            current_url = self.browser.driver.current_url

            # Check URL path for category information
            from urllib.parse import urlparse
            path = urlparse(current_url).path

            # Common category patterns
            if '/clothing/' in path:
                return 'clothing'
            elif '/shoes/' in path:
                return 'shoes'
            elif '/accessories/' in path:
                return 'accessories'
            elif '/beauty/' in path:
                return 'beauty'
            elif '/bags/' in path:
                return 'bags'

            # Try breadcrumbs
            breadcrumb_selectors = ['.breadcrumb', '.breadcrumbs', '[data-testid="breadcrumbs"]']
            for selector in breadcrumb_selectors:
                breadcrumbs = self.browser.get_element_text(selector)
                if breadcrumbs:
                    # Extract last meaningful breadcrumb
                    parts = [part.strip() for part in breadcrumbs.split('>') if part.strip()]
                    if len(parts) > 1:
                        return parts[-2].lower()  # Second to last is usually the category

        except Exception as e:
            logger.debug(f"Error extracting category: {e}")

        return 'clothing'  # Default category

    def _extract_metadata(self) -> Dict[str, Any]:
        """Extract additional metadata."""
        metadata = {}

        try:
            # Extract material information if available
            material_selectors = ['.material', '.materials', '[data-testid="product-materials"]']
            for selector in material_selectors:
                material = self.browser.get_element_text(selector)
                if material:
                    metadata['materials'] = material.strip()
                    break

            # Extract care instructions
            care_selectors = ['.care', '.care-instructions', '[data-testid="product-care"]']
            for selector in care_selectors:
                care = self.browser.get_element_text(selector)
                if care:
                    metadata['care_instructions'] = care.strip()
                    break

            # Extract product details
            details_selector = self.selectors['product'].get('metadata', '[data-testid="product-metadata"]')
            details = self.browser.get_element_text(details_selector)
            if details:
                metadata['details'] = details.strip()

            # Extract color information
            color_selectors = ['.color', '[data-testid="product-color"]']
            for selector in color_selectors:
                color = self.browser.get_element_text(selector)
                if color:
                    metadata['color'] = color.strip()
                    break

            # Add scraping timestamp
            import datetime
            metadata['scraped_at'] = datetime.datetime.utcnow().isoformat()

        except Exception as e:
            logger.debug(f"Error extracting metadata: {e}")

        return metadata
