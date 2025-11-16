"""Main orchestrator for the scraping pipeline."""

import time
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from loguru import logger

from scraper.browser import BrowserManager
from scraper.category_scraper import CategoryScraper
from scraper.product_scraper import ProductScraper
from database.connection import DatabaseConnection
from embeddings.service import EmbeddingService
from utils.config import Config
from utils.logger import setup_logging


class ScrapingOrchestrator:
    """Main orchestrator for the complete scraping pipeline."""

    def __init__(self, config_path: str = "config/other_stories.yaml"):
        self.config = Config(config_path)
        setup_logging(self.config)

        self.browser_manager = BrowserManager(self.config)
        self.category_scraper = CategoryScraper(self.config, self.browser_manager)
        self.product_scraper = ProductScraper(self.config, self.browser_manager)
        self.database = DatabaseConnection(self.config)
        self.embedding_service = EmbeddingService(self.config)

        self.scraping_config = self.config.get_scraping_config()

    def run_full_pipeline(self) -> bool:
        """Run the complete scraping pipeline."""
        try:
            logger.info("Starting full scraping pipeline")

            # Initialize components
            if not self._initialize_components():
                return False

            # Get category URL
            category_url = self.config.get_brand_config().get('category_url')
            if not category_url:
                logger.error("No category URL configured")
                return False

            # Step 1: Extract product URLs
            logger.info("Step 1: Extracting product URLs")
            product_urls = self.category_scraper.extract_product_urls(category_url)

            if not product_urls:
                logger.warning("No product URLs found")
                return False

            logger.info(f"Found {len(product_urls)} product URLs")

            # Step 2: Scrape individual products
            logger.info("Step 2: Scraping individual products")
            products = self._scrape_products_batch(product_urls)

            if not products:
                logger.warning("No products scraped successfully")
                return False

            logger.info(f"Successfully scraped {len(products)} products")

            # Step 3: Generate embeddings
            logger.info("Step 3: Generating embeddings")
            products_with_embeddings = self._generate_embeddings(products)

            # Step 4: Store in database
            logger.info("Step 4: Storing products in database")
            success = self.database.insert_products(products_with_embeddings)

            if success:
                logger.info("Scraping pipeline completed successfully")
                return True
            else:
                logger.error("Failed to store products in database")
                return False

        except Exception as e:
            logger.error(f"Error in scraping pipeline: {e}")
            return False

        finally:
            self._cleanup()

    def run_category_only(self, category_url: Optional[str] = None) -> List[str]:
        """Run only the category scraping to get product URLs."""
        try:
            if not self._initialize_browser():
                return []

            if not category_url:
                category_url = self.config.get_brand_config().get('category_url')

            if not category_url:
                logger.error("No category URL configured")
                return []

            product_urls = self.category_scraper.extract_product_urls(category_url)
            logger.info(f"Extracted {len(product_urls)} product URLs")

            return product_urls

        except Exception as e:
            logger.error(f"Error in category scraping: {e}")
            return []

        finally:
            self._cleanup()

    def run_product_scraping(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Run only product scraping for given URLs."""
        try:
            if not self._initialize_browser():
                return []

            products = self._scrape_products_batch(product_urls)
            logger.info(f"Scraped {len(products)} products")

            return products

        except Exception as e:
            logger.error(f"Error in product scraping: {e}")
            return []

        finally:
            self._cleanup()

    def run_embedding_generation(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run only embedding generation for products."""
        try:
            if not self._initialize_embedding_service():
                return products

            products_with_embeddings = self._generate_embeddings(products)
            logger.info(f"Generated embeddings for {len(products_with_embeddings)} products")

            return products_with_embeddings

        except Exception as e:
            logger.error(f"Error in embedding generation: {e}")
            return products

    def _initialize_components(self) -> bool:
        """Initialize all required components."""
        logger.info("Initializing components")

        # Initialize browser
        if not self.browser_manager.setup_driver():
            logger.error("Failed to initialize browser")
            return False

        # Initialize database connection
        if not self.database.connect():
            logger.error("Failed to connect to database")
            return False

        # Initialize embedding service
        if not self.embedding_service.initialize():
            logger.warning("Failed to initialize embedding service - continuing without embeddings")

        logger.info("All components initialized successfully")
        return True

    def _initialize_browser(self) -> bool:
        """Initialize only the browser component."""
        return self.browser_manager.setup_driver()

    def _initialize_embedding_service(self) -> bool:
        """Initialize only the embedding service."""
        return self.embedding_service.initialize()

    def _scrape_products_batch(self, product_urls: List[str]) -> List[Dict[str, Any]]:
        """Scrape products in batches with progress tracking."""
        products = []
        batch_size = 10  # Process 10 products at a time
        max_retries = self.scraping_config.get('max_retries', 3)

        with tqdm(total=len(product_urls), desc="Scraping products") as pbar:
            for i in range(0, len(product_urls), batch_size):
                batch_urls = product_urls[i:i + batch_size]

                # Scrape batch
                batch_products = self._scrape_batch(batch_urls, max_retries)
                products.extend(batch_products)

                pbar.update(len(batch_urls))

                # Rate limiting between batches
                time.sleep(self.scraping_config.get('rate_limit_delay', 1))

        return products

    def _scrape_batch(self, urls: List[str], max_retries: int) -> List[Dict[str, Any]]:
        """Scrape a batch of product URLs."""
        products = []

        for url in urls:
            for attempt in range(max_retries):
                try:
                    product = self.product_scraper.scrape_product(url)
                    if product:
                        products.append(product)
                        break
                    else:
                        logger.debug(f"Failed to scrape product (attempt {attempt + 1}): {url}")

                except Exception as e:
                    logger.warning(f"Error scraping product {url} (attempt {attempt + 1}): {e}")

                    if attempt < max_retries - 1:
                        # Wait before retry
                        time.sleep(self.scraping_config.get('retry_delay', 2))
                    else:
                        logger.error(f"Failed to scrape product after {max_retries} attempts: {url}")

        return products

    def _generate_embeddings(self, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate embeddings for products."""
        if not self.embedding_service._initialized:
            logger.warning("Embedding service not initialized, skipping embeddings")
            return products

        products_with_embeddings = []

        with tqdm(total=len(products), desc="Generating embeddings") as pbar:
            for product in products:
                try:
                    image_url = product.get('image_url')
                    if image_url:
                        embedding = self.embedding_service.generate_embedding(image_url)
                        if embedding is not None:
                            product['embedding'] = embedding.tolist()  # Convert numpy array to list
                        else:
                            logger.debug(f"Failed to generate embedding for product: {product.get('title', 'Unknown')}")

                    products_with_embeddings.append(product)

                except Exception as e:
                    logger.warning(f"Error generating embedding for product {product.get('id', 'Unknown')}: {e}")
                    products_with_embeddings.append(product)  # Add without embedding

                pbar.update(1)

        return products_with_embeddings

    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up resources")

        if hasattr(self, 'browser_manager'):
            self.browser_manager.quit_driver()

        if hasattr(self, 'database'):
            self.database.disconnect()

    def get_stats(self) -> Dict[str, Any]:
        """Get scraping statistics."""
        return {
            'config': {
                'brand': self.config.get_brand_config().get('name'),
                'category_url': self.config.get_brand_config().get('category_url'),
                'max_pages': self.scraping_config.get('max_pages'),
                'batch_size': self.config.get_database_config().get('batch_size')
            },
            'components': {
                'browser_initialized': self.browser_manager.driver is not None,
                'database_connected': self.database.client is not None,
                'embedding_service_initialized': self.embedding_service._initialized
            }
        }
