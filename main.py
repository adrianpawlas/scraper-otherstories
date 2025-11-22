#!/usr/bin/env python3
"""Main entry point for the & Other Stories scraper."""

import argparse
import sys
from pathlib import Path

# Add src to path for proper module resolution
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from src.scraper.orchestrator import ScrapingOrchestrator
from src.utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='& Other Stories Product Scraper')
    parser.add_argument('--config', '-c', default='config/other_stories.yaml',
                       help='Path to configuration file')
    parser.add_argument('--mode', '-m', choices=['full', 'category', 'products', 'embeddings'],
                       default='full', help='Scraping mode')
    parser.add_argument('--urls', '-u', nargs='+', help='Product URLs for product mode')
    parser.add_argument('--category-url', help='Custom category URL for category mode')
    parser.add_argument('--input-file', '-i', help='File with product URLs (one per line)')
    parser.add_argument('--output-file', '-o', help='Output file for results (JSON format)')
    parser.add_argument('--stats', action='store_true', help='Show scraping statistics')

    args = parser.parse_args()

    try:
        # Initialize orchestrator
        orchestrator = ScrapingOrchestrator(args.config)

        if args.stats:
            stats = orchestrator.get_stats()
            print("Scraping Statistics:")
            print(f"Brand: {stats['config']['brand']}")
            print(f"Category URL: {stats['config']['category_url']}")
            print(f"Max Pages: {stats['config']['max_pages']}")
            print(f"Browser Initialized: {stats['components']['browser_initialized']}")
            print(f"Database Connected: {stats['components']['database_connected']}")
            print(f"Embedding Service: {stats['components']['embedding_service_initialized']}")
            return

        if args.mode == 'full':
            # Run full pipeline
            logger.info("Starting full scraping pipeline")
            success = orchestrator.run_full_pipeline()

            if success:
                logger.info("Full scraping pipeline completed successfully")
                print("✅ Scraping completed successfully!")
            else:
                logger.error("Full scraping pipeline failed")
                print("❌ Scraping failed!")
                sys.exit(1)

        elif args.mode == 'category':
            # Run category scraping only
            logger.info("Starting category scraping")
            category_url = args.category_url
            product_urls = orchestrator.run_category_only(category_url)

            print(f"Found {len(product_urls)} product URLs")

            if args.output_file:
                import json
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    json.dump(product_urls, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {args.output_file}")
            else:
                for url in product_urls[:10]:  # Show first 10
                    print(url)
                if len(product_urls) > 10:
                    print(f"... and {len(product_urls) - 10} more")

        elif args.mode == 'products':
            # Run product scraping only
            product_urls = []

            # Get URLs from arguments
            if args.urls:
                product_urls.extend(args.urls)

            # Get URLs from file
            if args.input_file:
                with open(args.input_file, 'r', encoding='utf-8') as f:
                    file_urls = [line.strip() for line in f if line.strip()]
                    product_urls.extend(file_urls)

            if not product_urls:
                print("❌ No product URLs provided. Use --urls or --input-file")
                sys.exit(1)

            logger.info(f"Starting product scraping for {len(product_urls)} URLs")
            products = orchestrator.run_product_scraping(product_urls)

            print(f"Successfully scraped {len(products)} products")

            if args.output_file:
                import json
                with open(args.output_file, 'w', encoding='utf-8') as f:
                    json.dump(products, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {args.output_file}")
            else:
                for product in products[:5]:  # Show first 5
                    print(f"- {product.get('title', 'Unknown')}: {product.get('price', 'N/A')} {product.get('currency', '')}")
                if len(products) > 5:
                    print(f"... and {len(products) - 5} more")

        elif args.mode == 'embeddings':
            # This mode would require products as input
            print("❌ Embedding mode requires product data as input")
            print("Use --input-file to provide products JSON file")
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        print("\n⚠️  Scraping interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
