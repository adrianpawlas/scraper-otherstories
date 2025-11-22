"""Supabase database connection and operations."""

import json
from typing import Dict, List, Any, Optional
from supabase import create_client, Client
from loguru import logger

from ..utils.config import Config


class DatabaseConnection:
    """Supabase database connection manager."""

    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[Client] = None
        self.table_name = config.get_database_config().get('table_name', 'products')
        self.batch_size = config.get_database_config().get('batch_size', 50)

    def connect(self) -> bool:
        """Establish connection to Supabase."""
        try:
            url = self.config.supabase_url
            key = self.config.supabase_key

            if not url or not key:
                logger.error("Supabase URL and key must be provided")
                return False

            self.client = create_client(url, key)
            logger.info("Connected to Supabase successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Supabase: {e}")
            return False

    def disconnect(self):
        """Close database connection."""
        if self.client:
            # Supabase client doesn't have explicit disconnect method
            self.client = None
            logger.info("Disconnected from Supabase")

    def insert_products(self, products: List[Dict[str, Any]]) -> bool:
        """Insert products into database."""
        if not self.client:
            logger.error("Database not connected")
            return False

        try:
            # Process in batches
            for i in range(0, len(products), self.batch_size):
                batch = products[i:i + self.batch_size]

                # Convert metadata to JSON string
                for product in batch:
                    if 'metadata' in product and isinstance(product['metadata'], dict):
                        product['metadata'] = json.dumps(product['metadata'])

                response = self.client.table(self.table_name).insert(batch).execute()

                if hasattr(response, 'data') and response.data:
                    logger.info(f"Inserted batch of {len(batch)} products")
                else:
                    logger.warning(f"No data returned for batch insertion")

            logger.info(f"Successfully inserted {len(products)} products")
            return True

        except Exception as e:
            logger.error(f"Failed to insert products: {e}")
            return False

    def update_product(self, product_id: str, updates: Dict[str, Any]) -> bool:
        """Update a specific product."""
        if not self.client:
            logger.error("Database not connected")
            return False

        try:
            # Convert metadata to JSON string if present
            if 'metadata' in updates and isinstance(updates['metadata'], dict):
                updates['metadata'] = json.dumps(updates['metadata'])

            response = self.client.table(self.table_name).update(updates).eq('id', product_id).execute()

            if hasattr(response, 'data') and response.data:
                logger.info(f"Updated product {product_id}")
                return True
            else:
                logger.warning(f"No product found with ID {product_id}")
                return False

        except Exception as e:
            logger.error(f"Failed to update product {product_id}: {e}")
            return False

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a product by ID."""
        if not self.client:
            logger.error("Database not connected")
            return None

        try:
            response = self.client.table(self.table_name).select('*').eq('id', product_id).execute()

            if hasattr(response, 'data') and response.data:
                product = response.data[0]
                # Parse metadata JSON
                if product.get('metadata'):
                    try:
                        product['metadata'] = json.loads(product['metadata'])
                    except json.JSONDecodeError:
                        logger.warning(f"Failed to parse metadata for product {product_id}")
                return product
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to get product {product_id}: {e}")
            return None

    def get_products_by_brand(self, brand: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get products by brand."""
        if not self.client:
            logger.error("Database not connected")
            return []

        try:
            response = self.client.table(self.table_name).select('*').eq('brand', brand).limit(limit).execute()

            products = []
            if hasattr(response, 'data') and response.data:
                for product in response.data:
                    # Parse metadata JSON
                    if product.get('metadata'):
                        try:
                            product['metadata'] = json.loads(product['metadata'])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse metadata for product {product.get('id')}")
                    products.append(product)

            return products

        except Exception as e:
            logger.error(f"Failed to get products by brand {brand}: {e}")
            return []

    def check_product_exists(self, product_id: str) -> bool:
        """Check if a product exists."""
        return self.get_product_by_id(product_id) is not None
