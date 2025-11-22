"""
& Other Stories Scraper
Scrapes all products, generates image embeddings, and imports to Supabase
"""

import os
import time
import json
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional
from urllib.parse import urljoin, urlparse, parse_qs
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from tqdm import tqdm
# Removed supabase client import - using REST API directly
from PIL import Image
import io
import numpy as np

# Load environment variables
load_dotenv()

# Check if we're in test mode before importing heavy dependencies
import sys
TEST_MODE = '--test' in sys.argv or os.getenv('TEST_MODE', '').lower() == 'true'

# Import transformers only when not in test mode (lazy import)
TRANSFORMERS_AVAILABLE = False
AutoProcessor = None
AutoModel = None
torch = None

def _import_transformers():
    """Lazy import of transformers - only when needed"""
    global TRANSFORMERS_AVAILABLE, AutoProcessor, AutoModel, torch
    if TRANSFORMERS_AVAILABLE:
        return True
    try:
        # Try importing torch first to check compatibility
        import torch as t
        torch = t
        
        # Use SiglipProcessor and SiglipModel directly (more reliable)
        from transformers import SiglipProcessor, SiglipModel
        AutoProcessor = SiglipProcessor
        AutoModel = SiglipModel
        TRANSFORMERS_AVAILABLE = True
        return True
    except RuntimeError as e:
        error_msg = str(e)
        if "torchvision" in error_msg or "nms" in error_msg:
            logger.error("=" * 60)
            logger.error("TORCH/TORCHVISION COMPATIBILITY ERROR")
            logger.error("This is a known issue with Python 3.13 and certain torch versions.")
            logger.error("Try: pip install --upgrade torch torchvision")
            logger.error("Or use Python 3.11 instead.")
            logger.error("=" * 60)
        logger.error(f"Runtime error importing transformers: {e}")
        return False
    except ImportError as e:
        logger.error(f"Failed to import transformers: {e}")
        logger.error("Install with: pip install transformers torch torchvision")
        return False
    except Exception as e:
        logger.error(f"Error importing transformers: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OtherStoriesScraper:
    """Scraper for & Other Stories website"""
    
    BASE_URL = "https://www.stories.com"
    CATEGORY_URL = "https://www.stories.com/en-eu/clothing/"
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Linux"',
        'Cache-Control': 'max-age=0',
        'DNT': '1',
    }
    
    def __init__(self, supabase_url: str, supabase_key: str, delay: float = 1.5, test_mode: bool = False):
        """
        Initialize the scraper
        
        Args:
            supabase_url: Supabase project URL
            supabase_key: Supabase API key
            delay: Delay between requests in seconds
            test_mode: If True, skip embeddings and database insertion
        """
        self.delay = delay
        self.test_mode = test_mode
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        # Enable cookie handling
        self.session.cookies.clear()
        # Set some default cookies that might help
        self.session.cookies.set('user_geolocation_country', 'EU', domain='.stories.com')
        
        # Initialize Supabase REST client (direct REST API, not Python client)
        if not test_mode:
            self.supabase_url = supabase_url.rstrip("/")
            self.supabase_key = supabase_key
            self.supabase_session = requests.Session()
            self.supabase_session.headers.update({
                "apikey": supabase_key,
                "Authorization": f"Bearer {supabase_key}",
                "Content-Type": "application/json",
            })
        else:
            self.supabase_url = None
            self.supabase_key = None
            self.supabase_session = None
            logger.info("TEST MODE: Skipping database operations")
        
        # Initialize embedding model only if not in test mode
        if not test_mode:
            if not _import_transformers():
                raise ImportError("transformers library is required but not available. Install with: pip install transformers torch")
            logger.info("Loading embedding model...")
            try:
                model_name = "google/siglip-base-patch16-384"
                self.processor = AutoProcessor.from_pretrained(model_name)
                self.embedding_model = AutoModel.from_pretrained(model_name)
                self.embedding_model.eval()
                # Move to GPU if available
                if torch.cuda.is_available():
                    self.embedding_model = self.embedding_model.cuda()
                    logger.info("Using GPU for embeddings")
                logger.info(f"Embedding model {model_name} loaded successfully")
            except Exception as e:
                logger.error(f"Error loading embedding model: {e}")
                raise
        else:
            self.processor = None
            self.embedding_model = None
            logger.info("TEST MODE: Skipping embedding model loading")
        
    def get_page(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with retry logic"""
        for attempt in range(retries):
            try:
                time.sleep(self.delay)
                # Build headers with Referer
                headers = self.HEADERS.copy()
                if attempt > 0 or hasattr(self, '_last_url'):
                    headers['Referer'] = getattr(self, '_last_url', self.BASE_URL)
                else:
                    # First request - visit homepage first to get cookies
                    if not hasattr(self, '_homepage_visited'):
                        try:
                            logger.debug("Visiting homepage first to establish session...")
                            home_headers = headers.copy()
                            home_headers['Referer'] = ''
                            self.session.get(self.BASE_URL, headers=home_headers, timeout=30)
                            self._homepage_visited = True
                            time.sleep(1)  # Small delay after homepage
                        except:
                            pass
                    headers['Referer'] = self.BASE_URL
                
                headers['Origin'] = self.BASE_URL
                
                response = self.session.get(url, headers=headers, timeout=30, allow_redirects=True)
                
                # Check for 403 - try different strategies
                if response.status_code == 403:
                    logger.warning(f"403 Forbidden for {url}. Trying with enhanced headers...")
                    # Strategy 1: More complete browser headers with Sec-Fetch headers
                    enhanced_headers = headers.copy()
                    enhanced_headers.update({
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                        'Accept-Language': 'en-US,en;q=0.9',
                        'Cache-Control': 'max-age=0',
                        'Sec-Ch-Ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
                        'Sec-Ch-Ua-Mobile': '?0',
                        'Sec-Ch-Ua-Platform': '"Linux"',
                        'Sec-Fetch-Dest': 'document',
                        'Sec-Fetch-Mode': 'navigate',
                        'Sec-Fetch-Site': 'same-origin' if 'stories.com' in url else 'none',
                        'Sec-Fetch-User': '?1',
                    })
                    response = self.session.get(url, headers=enhanced_headers, timeout=30, allow_redirects=True)
                    
                    # Strategy 2: If still 403, try re-establishing session
                    if response.status_code == 403:
                        logger.warning("403 persists, re-establishing session...")
                        try:
                            self.visit_homepage_to_get_cookies()
                            time.sleep(2)
                            response = self.session.get(url, headers=enhanced_headers, timeout=30, allow_redirects=True)
                        except Exception:
                            pass
                    
                    # Strategy 3: If still 403, try minimal headers
                    if response.status_code == 403:
                        minimal_headers = {
                            'User-Agent': self.HEADERS['User-Agent'],
                            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                            'Accept-Language': 'en-US,en;q=0.5',
                            'Accept-Encoding': 'gzip, deflate, br',
                            'Connection': 'keep-alive',
                            'Upgrade-Insecure-Requests': '1',
                        }
                        response = self.session.get(url, headers=minimal_headers, timeout=30, allow_redirects=True)
                
                response.raise_for_status()
                self._last_url = url
                return BeautifulSoup(response.content, 'lxml')
            except requests.exceptions.RequestException as e:
                if attempt < retries - 1:
                    wait_time = (attempt + 1) * 3  # Longer wait between retries
                    logger.warning(f"Retry {attempt + 1}/{retries} for {url} after {wait_time}s")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error fetching {url} after {retries} attempts: {e}")
                    if hasattr(e, 'response') and e.response is not None:
                        logger.error(f"Response status: {e.response.status_code}")
                        # Don't log full headers in production to avoid clutter
                        if logger.level <= logging.DEBUG:
                            logger.error(f"Response headers: {dict(e.response.headers)}")
                    return None
        return None
    
    def visit_homepage_to_get_cookies(self):
        """
        Visit the homepage to establish a session and get cookies.
        This helps avoid 403 errors by making the scraper look more like a real browser.
        """
        try:
            headers = self.HEADERS.copy()
            headers['Referer'] = ''
            headers['Sec-Fetch-Site'] = 'none'
            headers['Sec-Fetch-Mode'] = 'navigate'
            headers['Sec-Fetch-Dest'] = 'document'
            headers['Sec-Fetch-User'] = '?1'
            
            response = self.session.get(self.BASE_URL, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            self._homepage_visited = True
            logger.debug("Successfully visited homepage and established session")
            return True
        except Exception as e:
            logger.warning(f"Failed to visit homepage: {e}")
            return False
    
    def get_products_from_category_page(self, category_url: str, page: int = 1) -> List[str]:
        """
        Extract all product URLs from a category page
        
        Args:
            category_url: Base category URL
            page: Page number (1-indexed)
            
        Returns:
            List of product URLs
        """
        # Build URL with page parameter
        if page > 1:
            url = f"{category_url}?page={page}"
        else:
            url = category_url
        
        soup = self.get_page(url)
        if not soup:
            return []
        
        product_urls = []
        
        # Look for product links - they typically have /product/ in the href
        # Try multiple selectors to be robust
        selectors = [
            'a[href*="/product/"]',
            'a[href*="/en-eu/product/"]',
            '.product-link',
            '[data-product-url]',
        ]
        
        for selector in selectors:
            links = soup.select(selector)
            if links:
                for link in links:
                    href = link.get('href', '')
                    if '/product/' in href:
                        # Make absolute URL if relative
                        if href.startswith('/'):
                            full_url = urljoin(self.BASE_URL, href)
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            full_url = urljoin(url, href)
                        
                        # Clean URL (remove fragments, query params if needed)
                        full_url = full_url.split('#')[0].split('?')[0]
                        
                        if full_url not in product_urls:
                            product_urls.append(full_url)
                break
        
        # Also try to find JSON-LD structured data
        json_scripts = soup.find_all('script', type='application/ld+json')
        for script in json_scripts:
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and 'url' in data:
                    url_val = data['url']
                    if '/product/' in url_val:
                        product_urls.append(url_val)
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and 'url' in item:
                            url_val = item['url']
                            if '/product/' in url_val:
                                product_urls.append(url_val)
            except:
                pass
        
        logger.info(f"Found {len(product_urls)} products on page {page}")
        return product_urls
    
    def get_all_product_urls(self, limit: Optional[int] = None) -> List[str]:
        """
        Get all product URLs from all pages of the category
        
        Args:
            limit: Maximum number of products to return (None for all)
        
        Returns:
            List of all unique product URLs
        """
        all_urls = []
        max_pages = 20  # User mentioned 20 pages
        
        for page in tqdm(range(1, max_pages + 1), desc="Discovering products"):
            page_urls = self.get_products_from_category_page(self.CATEGORY_URL, page)
            if not page_urls:
                logger.info(f"No products found on page {page}, stopping pagination")
                break
            all_urls.extend(page_urls)
            
            # Check if we've reached the limit (before deduplication)
            if limit and len(all_urls) >= limit:
                break
            
            time.sleep(self.delay)
        
        # Remove duplicates while preserving order (after collecting all URLs)
        seen = set()
        unique_urls = []
        for url in all_urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        # Apply limit after deduplication
        if limit and len(unique_urls) > limit:
            unique_urls = unique_urls[:limit]
            logger.info(f"Reached limit of {limit} products")
        
        logger.info(f"Found {len(unique_urls)} unique products")
        return unique_urls
    
    def scrape_product(self, product_url: str) -> Optional[Dict]:
        """
        Scrape a single product page and extract all information
        
        Args:
            product_url: URL of the product page
            
        Returns:
            Dictionary with product data or None if failed
        """
        soup = self.get_page(product_url)
        if not soup:
            return None
        
        try:
            product_data = {
                'source': 'scraper',
                'brand': 'Other Stories',
                'product_url': product_url,
                'second_hand': False,
                'gender': 'WOMAN',  # All products are for women according to user
            }
            
            # Extract product ID from URL
            # Format: /product/product-name-id/
            match = re.search(r'/product/[^/]+-(\d+)/', product_url)
            if match:
                product_data['id'] = f"otherstories_{match.group(1)}"
            else:
                # Fallback: use URL hash or generate ID
                product_data['id'] = f"otherstories_{hash(product_url) % 10**10}"
            
            # PRIORITY: Extract from JSON-LD structured data (most reliable)
            json_ld_data = None
            json_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'Product':
                        json_ld_data = data
                        break
                except:
                    continue
            
            # Extract data from JSON-LD if available
            if json_ld_data:
                # Title
                product_data['title'] = json_ld_data.get('name', 'Unknown Product')
                
                # Price and currency from offers
                offers = json_ld_data.get('offers', [])
                if isinstance(offers, list) and offers:
                    offer = offers[0]  # Take first offer
                    product_data['price'] = float(offer.get('price', 0))
                    product_data['currency'] = offer.get('priceCurrency', 'EUR')
                elif isinstance(offers, dict):
                    product_data['price'] = float(offers.get('price', 0))
                    product_data['currency'] = offers.get('priceCurrency', 'EUR')
                
                # Image - take first image from JSON-LD
                images = json_ld_data.get('image', [])
                if isinstance(images, list) and images:
                    product_data['image_url'] = images[0]
                elif isinstance(images, str):
                    product_data['image_url'] = images
                
                # Description - clean HTML tags
                description = json_ld_data.get('description', '')
                if description:
                    # Remove HTML tags
                    desc_soup = BeautifulSoup(description, 'html.parser')
                    product_data['description'] = desc_soup.get_text(separator=' ', strip=True)
                
                # Category
                category_obj = json_ld_data.get('category', {})
                if isinstance(category_obj, dict):
                    category_name = category_obj.get('name', '')
                    if category_name:
                        # Extract main category (e.g., "Clothing > Knitwear > Sweaters" -> "Clothing")
                        product_data['category'] = category_name.split('>')[0].strip()
                    else:
                        product_data['category'] = 'Clothing'
                else:
                    product_data['category'] = 'Clothing'
                
                # Brand
                brand_obj = json_ld_data.get('brand', {})
                if isinstance(brand_obj, dict):
                    brand_name = brand_obj.get('name', '')
                    if brand_name:
                        product_data['brand'] = brand_name.replace('&', 'Other Stories').strip()
                
                # SKU for metadata
                sku = json_ld_data.get('sku', '')
            
            # If no image found in JSON-LD, try comprehensive fallback methods
            if not product_data.get('image_url'):
                # Try meta tags (multiple sources)
                image_selectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    'meta[itemprop="image"]',
                    'link[rel="image_src"]',
                ]
                for selector in image_selectors:
                    image_elem = soup.select_one(selector)
                    if image_elem:
                        img_url = image_elem.get('content') or image_elem.get('href')
                        if img_url and ('media.stories.com' in img_url or img_url.startswith('http')):
                            product_data['image_url'] = img_url
                            break
                
                # Try finding images in HTML (multiple selectors)
                if not product_data.get('image_url'):
                    img_selectors = [
                        'img[src*="media.stories.com"]',
                        'img[data-src*="media.stories.com"]',
                        'img[data-lazy-src*="media.stories.com"]',
                        '.product-image img',
                        '.product-gallery img',
                        '[data-product-image] img',
                        '[class*="product"] img[src*="media"]',
                        'picture img',
                        'source[srcset*="media.stories.com"]',
                    ]
                    for selector in img_selectors:
                        img_elem = soup.select_one(selector)
                        if img_elem:
                            img_url = (img_elem.get('src') or 
                                      img_elem.get('data-src') or 
                                      img_elem.get('data-lazy-src') or
                                      img_elem.get('srcset', '').split(',')[0].strip().split(' ')[0] if img_elem.get('srcset') else None)
                            if img_url and 'media.stories.com' in img_url:
                                product_data['image_url'] = img_url
                                break
                
                # Last resort: try to find any image with media.stories.com
                if not product_data.get('image_url'):
                    all_imgs = soup.find_all('img')
                    for img in all_imgs:
                        for attr in ['src', 'data-src', 'data-lazy-src']:
                            img_url = img.get(attr, '')
                            if img_url and 'media.stories.com' in img_url:
                                product_data['image_url'] = img_url
                                break
                        if product_data.get('image_url'):
                            break
            
            else:
                # FALLBACK: Extract from HTML/meta tags if JSON-LD not available
                # Title
                title = None
                title_elem = soup.select_one('meta[property="og:title"]') or soup.find('title')
                if title_elem:
                    title = title_elem.get('content') if title_elem.name == 'meta' else title_elem.get_text(strip=True)
                product_data['title'] = title or 'Unknown Product'
                
                # Price from meta tags
                price_elem = soup.select_one('meta[property="product:price:amount"]')
                currency_elem = soup.select_one('meta[property="product:price:currency"]')
                if price_elem:
                    try:
                        product_data['price'] = float(price_elem.get('content', 0))
                        product_data['currency'] = currency_elem.get('content', 'EUR') if currency_elem else 'EUR'
                    except:
                        product_data['price'] = None
                        product_data['currency'] = 'EUR'
                else:
                    product_data['price'] = None
                    product_data['currency'] = 'EUR'
                
                # Image from meta tags
                image_elem = soup.select_one('meta[property="og:image"]')
                if image_elem:
                    product_data['image_url'] = image_elem.get('content', '')
                else:
                    # Try to find image in HTML
                    img_elem = soup.select_one('img[src*="media.stories.com"]')
                    if img_elem:
                        product_data['image_url'] = img_elem.get('src', '') or img_elem.get('data-src', '')
                
                # Description
                desc_elem = soup.select_one('meta[property="og:description"]')
                if desc_elem:
                    product_data['description'] = desc_elem.get('content', '')
                else:
                    product_data['description'] = None
                
                product_data['category'] = 'Clothing'
                sku = None
            
            # Validate required fields
            # Note: image_url is required for embeddings, but we can still save products without images
            if not product_data.get('image_url'):
                logger.warning(f"No image found for {product_url} - product will be saved without embedding")
                # Don't return None - allow product to be saved without image/embedding
            
            # Make image URL absolute if needed
            image_url = product_data['image_url']
            if image_url.startswith('//'):
                image_url = 'https:' + image_url
            elif image_url.startswith('/'):
                image_url = urljoin(self.BASE_URL, image_url)
            elif not image_url.startswith('http'):
                image_url = urljoin(product_url, image_url)
            product_data['image_url'] = image_url
            
            # Extract sizes from offers (SKUs often indicate sizes)
            sizes = []
            if json_ld_data and 'offers' in json_ld_data:
                offers = json_ld_data['offers']
                if isinstance(offers, list):
                    for offer in offers:
                        sku_val = offer.get('sku', '')
                        # SKU format often ends with size code (e.g., 1217076002002, 1217076002003)
                        # Extract size if available in the offer
                        if 'size' in offer:
                            sizes.append(str(offer['size']))
            
            # Also try HTML selectors as fallback
            if not sizes:
                size_selectors = [
                    '[data-size]',
                    '.size-selector button',
                    '.product-size option',
                    'button[aria-label*="size"]',
                ]
                for selector in size_selectors:
                    elems = soup.select(selector)
                    for elem in elems:
                        size_text = elem.get_text(strip=True) or elem.get('data-size', '') or elem.get('aria-label', '')
                        if size_text and size_text.lower() not in ['select size', 'size'] and size_text not in sizes:
                            sizes.append(size_text)
                    if sizes:
                        break
            
            product_data['size'] = ', '.join(sizes) if sizes else None
            
            # Build metadata object
            metadata = {
                'scraped_at': datetime.now().isoformat(),
                'url': product_url,
                'sizes_available': sizes,
            }
            
            # Add additional info from JSON-LD
            if json_ld_data:
                if sku:
                    metadata['sku'] = sku
                if 'color' in json_ld_data:
                    metadata['color'] = json_ld_data['color']
                if 'aggregateRating' in json_ld_data:
                    rating = json_ld_data['aggregateRating']
                    if isinstance(rating, dict):
                        metadata['rating'] = rating.get('ratingValue')
                        metadata['review_count'] = rating.get('reviewCount')
                if 'itemCondition' in json_ld_data:
                    metadata['condition'] = json_ld_data['itemCondition']
            
            product_data['metadata'] = metadata
            
            return product_data
            
        except Exception as e:
            logger.error(f"Error scraping product {product_url}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def generate_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate 768-dimensional embedding for an image using google/siglip-base-patch16-384
        
        Args:
            image_url: URL of the image
            
        Returns:
            768-dimensional embedding vector or None if failed
        """
        try:
            # Clean up URL
            raw_url = str(image_url).strip()
            if raw_url.startswith("//"):
                raw_url = "https:" + raw_url
            
            # Download image with proper headers (like working scraper)
            # Request JPEG/PNG instead of AVIF to avoid PIL compatibility issues
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/jpeg,image/png,image/*,*/*;q=0.8',  # Prefer JPEG/PNG over AVIF
                'Referer': self.BASE_URL,
            }
            
            # Use fresh requests call for images
            resp = requests.get(raw_url, headers=headers, timeout=15)
            resp.raise_for_status()
            
            # Try to open as image directly from response content
            try:
                img = Image.open(io.BytesIO(resp.content)).convert('RGB')
                image = img
            except Exception as e:
                # If still AVIF, try requesting JPEG version explicitly
                content_type = resp.headers.get('Content-Type', '').lower()
                if 'avif' in content_type:
                    # Try to get JPEG version by modifying Accept header
                    headers_jpg = headers.copy()
                    headers_jpg['Accept'] = 'image/jpeg,image/png,*/*;q=0.8'
                    try:
                        resp2 = requests.get(raw_url, headers=headers_jpg, timeout=15)
                        if resp2.status_code == 200 and 'image/jpeg' in resp2.headers.get('Content-Type', '').lower():
                            img = Image.open(io.BytesIO(resp2.content)).convert('RGB')
                            image = img
                        else:
                            logger.warning(f"AVIF image not supported by PIL, and JPEG fallback unavailable: {raw_url}")
                            return None
                    except Exception as e2:
                        logger.warning(f"Failed to get JPEG version of image: {raw_url}, error: {e2}")
                        return None
                else:
                    logger.warning(f"Failed to open image from {raw_url}: {e}")
                    return None
            
            # Process image with SigLIP processor (requires both image and text inputs)
            # SigLIP is a vision-language model, so it needs text input even if empty
            inputs = self.processor(images=image, text=[""], return_tensors="pt")
            
            # Move inputs to GPU if available
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            
            # Generate embedding
            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
                
                # SigLIP returns image_embeds directly
                embedding = outputs.image_embeds.squeeze()
                
                # Get the embedding tensor and convert to list
                if isinstance(embedding, torch.Tensor):
                    embedding = embedding.cpu().tolist()
                elif isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
                
                # Verify dimensions (should be exactly 768)
                if len(embedding) != 768:
                    logger.warning(f"Embedding dimension mismatch: got {len(embedding)}, expected 768 for {image_url}")
                    return None
                
                return embedding
        except Exception as e:
            logger.error(f"Error generating embedding for {image_url}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    def insert_product(self, product_data: Dict) -> bool:
        """
        Insert product into Supabase using direct REST API (like working scraper)
        
        Args:
            product_data: Dictionary containing product information
            
        Returns:
            True if successful, False otherwise
        """
        if self.test_mode:
            logger.info(f"TEST MODE: Would insert product: {product_data.get('title', 'Unknown')} - {product_data.get('price', 'N/A')} {product_data.get('currency', '')}")
            return True
        
        try:
            # Prepare data for Supabase - match exact schema
            supabase_data = {
                'id': product_data.get('id'),
                'source': product_data.get('source', 'scraper'),
                'product_url': product_data.get('product_url'),
                'affiliate_url': product_data.get('affiliate_url'),  # Optional
                'image_url': product_data.get('image_url'),
                'brand': product_data.get('brand', 'Other Stories'),
                'title': product_data.get('title'),
                'description': product_data.get('description'),  # Optional
                'category': product_data.get('category'),  # Optional
                'gender': product_data.get('gender', 'WOMAN'),
                'price': product_data.get('price'),
                'currency': product_data.get('currency'),
                'size': product_data.get('size'),  # Optional
                'second_hand': product_data.get('second_hand', False),
                'metadata': json.dumps(product_data.get('metadata', {})) if product_data.get('metadata') else None,
                'created_at': datetime.now().isoformat(),
            }
            
            # Add embedding if available (Supabase vector type expects array format)
            embedding = product_data.get('embedding')
            if embedding:
                # Format as PostgreSQL array string: [0.1,0.2,...]
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                supabase_data['embedding'] = embedding_str
            
            # Remove None values for optional fields (let database use defaults)
            supabase_data = {k: v for k, v in supabase_data.items() if v is not None}
            
            # Use REST API directly (same pattern as working scraper)
            endpoint = f"{self.supabase_url}/rest/v1/products"
            headers = {
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
            
            resp = self.supabase_session.post(
                endpoint,
                headers=headers,
                data=json.dumps(supabase_data),
                timeout=60
            )
            
            if resp.status_code not in (200, 201, 204):
                error_msg = f"Supabase upsert failed: {resp.status_code} {resp.text}"
                logger.error(f"Error inserting product {product_data.get('id')}: {error_msg}")
                return False
            
            return True
        except Exception as e:
            logger.error(f"Error inserting product {product_data.get('id')}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    def delete_missing_products(self, current_product_ids: List[str]):
        """
        Delete products from database that are no longer in the current scrape
        
        Args:
            current_product_ids: List of product IDs that were successfully scraped
        """
        if self.test_mode:
            logger.info(f"TEST MODE: Would delete products not in current scrape (keeping {len(current_product_ids)} products)")
            return
        
        try:
            # Fetch all existing product IDs for this source
            endpoint = f"{self.supabase_url}/rest/v1/products"
            params = {
                'source': 'eq.scraper',
                'select': 'id'
            }
            
            resp = self.supabase_session.get(endpoint, params=params, timeout=60)
            resp.raise_for_status()
            
            existing_ids = [item.get('id') for item in resp.json() if item.get('id')]
            current_ids_set = set(current_product_ids)
            
            # Find IDs to delete (exist in DB but not in current scrape)
            to_delete = [eid for eid in existing_ids if eid not in current_ids_set]
            
            if not to_delete:
                logger.info("No products to delete - all existing products are still present")
                return
            
            logger.info(f"Found {len(to_delete)} products to delete (not in current scrape)")
            
            # Delete in chunks using Supabase's 'in' operator for bulk deletes
            chunk_size = 100
            deleted_count = 0
            
            for i in range(0, len(to_delete), chunk_size):
                chunk = to_delete[i:i + chunk_size]
                try:
                    del_endpoint = f"{self.supabase_url}/rest/v1/products"
                    # Use 'in' operator for bulk delete: id=in.(id1,id2,id3)
                    ids_str = ','.join(chunk)
                    del_params = {
                        'source': 'eq.scraper',
                        'id': f'in.({ids_str})'
                    }
                    del_resp = self.supabase_session.delete(del_endpoint, params=del_params, timeout=60)
                    if del_resp.status_code in (200, 204):
                        deleted_count += len(chunk)
                        logger.debug(f"Deleted {len(chunk)} products (chunk {i//chunk_size + 1})")
                    else:
                        logger.warning(f"Failed to delete chunk: {del_resp.status_code} {del_resp.text}")
                except Exception as e:
                    logger.warning(f"Failed to delete chunk {i//chunk_size + 1}: {e}")
                    # Fallback: delete one by one if bulk delete fails
                    for product_id in chunk:
                        try:
                            del_endpoint = f"{self.supabase_url}/rest/v1/products"
                            del_params = {
                                'source': 'eq.scraper',
                                'id': f'eq.{product_id}'
                            }
                            del_resp = self.supabase_session.delete(del_endpoint, params=del_params, timeout=60)
                            if del_resp.status_code in (200, 204):
                                deleted_count += 1
                        except Exception as e2:
                            logger.warning(f"Failed to delete product {product_id}: {e2}")
            
            logger.info(f"Deleted {deleted_count} old products from database")
            
        except Exception as e:
            logger.error(f"Error during sync cleanup: {e}")
            import traceback
            logger.debug(traceback.format_exc())
    
    def run(self, product_limit: Optional[int] = None):
        """
        Main scraping loop with sync functionality
        
        Args:
            product_limit: Maximum number of products to scrape (None for all)
        """
        logger.info("Starting & Other Stories scraper...")
        logger.info(f"Category URL: {self.CATEGORY_URL}")
        if product_limit:
            logger.info(f"Product limit: {product_limit}")
        
        # Visit homepage first to establish session and get cookies (helps with 403)
        logger.info("Visiting homepage to establish session...")
        try:
            self.visit_homepage_to_get_cookies()
            time.sleep(2)  # Small delay after establishing session
        except Exception as e:
            logger.warning(f"Failed to visit homepage (continuing anyway): {e}")
        
        # Get all product URLs from all pages
        all_product_urls = self.get_all_product_urls(limit=product_limit)
        
        if not all_product_urls:
            logger.error("No products found! Check the website structure.")
            return
        
        logger.info(f"Found {len(all_product_urls)} unique products to scrape")
        
        # Scrape each product and track successful IDs
        successful = 0
        failed = 0
        successful_product_ids = []  # Track IDs for sync
        
        for product_url in tqdm(all_product_urls, desc="Scraping products"):
            try:
                product_data = self.scrape_product(product_url)
                if product_data:
                    product_id = product_data.get('id')
                    
                    # Generate embedding (skip in test mode)
                    if not self.test_mode and product_data.get('image_url'):
                        logger.debug(f"Generating embedding for {product_data.get('title', 'product')}")
                        embedding = self.generate_embedding(product_data['image_url'])
                        if embedding:
                            product_data['embedding'] = embedding
                        else:
                            logger.warning(f"Failed to generate embedding for {product_url}")
                    
                    # Insert/update into database (skip in test mode)
                    if self.test_mode:
                        logger.info(f"TEST MODE: Would insert product: {product_data.get('title', 'Unknown')} - {product_data.get('price', 'N/A')} {product_data.get('currency', '')}")
                        if product_id:
                            successful_product_ids.append(product_id)
                        successful += 1
                    elif self.insert_product(product_data):
                        if product_id:
                            successful_product_ids.append(product_id)
                        successful += 1
                    else:
                        failed += 1
                else:
                    failed += 1
                    logger.warning(f"Failed to scrape product: {product_url}")
            except Exception as e:
                failed += 1
                logger.error(f"Unexpected error processing {product_url}: {e}")
        
        logger.info(f"Scraping completed! Success: {successful}, Failed: {failed}")
        
        # Sync: Delete products that are no longer in the current scrape
        if not self.test_mode and successful_product_ids:
            logger.info("Starting database sync - removing old products...")
            self.delete_missing_products(successful_product_ids)
            logger.info("Database sync completed!")


if __name__ == "__main__":
    import sys
    
    # Check for test mode flag (already checked at module level)
    test_mode = TEST_MODE
    
    # Check for product limit
    product_limit = None
    if '--limit' in sys.argv:
        try:
            limit_idx = sys.argv.index('--limit')
            product_limit = int(sys.argv[limit_idx + 1])
        except (IndexError, ValueError):
            logger.warning("Invalid --limit value, ignoring")
    
    if test_mode:
        logger.info("=" * 60)
        logger.info("RUNNING IN TEST MODE")
        logger.info("- Skipping embedding generation")
        logger.info("- Skipping database insertion")
        logger.info("=" * 60)
    
    # Get Supabase credentials from environment variables
    # For local development, use .env file
    # For GitHub Actions, use secrets: SUPABASE_URL and SUPABASE_KEY
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    # Fallback to defaults for local development (remove in production)
    if not supabase_url:
        supabase_url = 'https://yqawmzggcgpeyaaynrjk.supabase.co'
    if not supabase_key:
        supabase_key = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4'
    
    if not test_mode and (not supabase_url or not supabase_key):
        logger.error("Please set SUPABASE_URL and SUPABASE_KEY as environment variables or in .env file")
        exit(1)
    
    # Initialize scraper with 1.5 second delay between requests
    scraper = OtherStoriesScraper(supabase_url, supabase_key, delay=1.5, test_mode=test_mode)
    scraper.run(product_limit=product_limit)

