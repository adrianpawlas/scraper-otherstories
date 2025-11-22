# & Other Stories Scraper - Usage Guide

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Supabase (optional):**
   The scraper already has your Supabase credentials hardcoded. If you want to use environment variables instead, create a `.env` file:
   ```
   SUPABASE_URL=https://yqawmzggcgpeyaaynrjk.supabase.co
   SUPABASE_KEY=your_key_here
   ```

3. **Run the scraper:**
   ```bash
   python scraper.py
   ```

## What It Does

1. **Discovers Products**: Scrapes all 20 pages from `https://www.stories.com/en-eu/clothing/` to collect product URLs
2. **Extracts Product Data**: For each product, extracts:
   - Title, description, price, currency
   - Product images (uses first image for embedding)
   - Category, brand, sizes
   - All metadata from JSON-LD structured data

3. **Generates Embeddings**: Creates 768-dimensional image embeddings using `google/siglip-base-patch16-384` model

4. **Saves to Supabase**: Inserts/updates products in your `products` table

## Field Mappings

- `source`: Always set to "scraper"
- `brand`: Always set to "Other Stories"
- `gender`: Always set to "WOMAN" (all products are women's clothing)
- `second_hand`: Always set to `false`
- `id`: Generated from product URL (format: `otherstories_{product_id}`)
- `embedding`: 768-dimensional vector from product image
- `price`: Extracted from JSON-LD or meta tags
- `currency`: EUR (default) or extracted from page
- `metadata`: JSON object with SKU, color, ratings, sizes, etc.

## Performance

- **Rate Limiting**: 1.5 seconds delay between requests (configurable)
- **Retry Logic**: 3 retries for failed requests
- **Progress Tracking**: Uses tqdm for progress bars
- **Error Handling**: Comprehensive error handling with logging

## Notes

- The scraper uses JSON-LD structured data as the primary source (most reliable)
- Falls back to HTML parsing if JSON-LD is not available
- Handles pagination automatically (20 pages)
- Removes duplicate product URLs
- Normalizes embeddings for better similarity search

## Troubleshooting

- **No products found**: Check if the website structure has changed
- **Embedding errors**: Ensure you have enough disk space for the model (~500MB)
- **Database errors**: Verify your Supabase credentials and table schema
- **Memory issues**: The model loads into memory. For large batches, consider processing in chunks

