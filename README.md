# & Other Stories Fashion Product Scraper

A comprehensive web scraper for & Other Stories fashion products with AI-powered image embeddings and Supabase integration.

## Features

- 🕷️ **Intelligent Scraping**: Automated extraction of product data from & Other Stories
- 🖼️ **AI Embeddings**: SigLIP-powered image embeddings for visual similarity search
- 🗄️ **Database Integration**: Seamless Supabase integration with pgvector support
- ⚙️ **Modular Architecture**: Configurable and extensible scraping pipeline
- 📊 **Progress Tracking**: Real-time progress monitoring and comprehensive logging
- 🔄 **Error Handling**: Robust retry mechanisms and graceful failure handling

## Requirements

- Python 3.8+
- Supabase account with pgvector extension
- Chrome browser (for Selenium automation)

## Installation

1. **Clone and setup**:
```bash
git clone <repository-url>
cd scraper-otherstories
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Configure environment**:
```bash
cp env.example .env
# Edit .env with your Supabase credentials
```

## Configuration

### Environment Variables (.env)

```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_key
USER_AGENT=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36
HEADLESS=true
EMBEDDING_CACHE_DIR=./cache/embeddings
DEVICE=auto
LOG_LEVEL=INFO
```

### Brand Configuration (config/other_stories.yaml)

```yaml
brand:
  name: "& Other Stories"
  source: "other_stories"
  base_url: "https://www.stories.com"
  category_url: "https://www.stories.com/en-eu/clothing/"

scraping:
  max_retries: 3
  retry_delay: 2
  request_timeout: 30
  rate_limit_delay: 1
  max_pages: 50

selectors:
  category:
    product_container: "[data-testid='product-item']"
    product_link: "a[href*='/product/']"
    # ... more selectors

database:
  table_name: "products"
  batch_size: 50

embedding:
  model_name: "google/siglip-base-patch16-384"
  dimensions: 768
  device: "auto"
```

## Database Schema

Create the following table in your Supabase database:

```sql
CREATE TABLE products (
  id text not null PRIMARY KEY,
  source text null,
  product_url text null,
  affiliate_url text null,
  image_url text not null,
  brand text null,
  title text not null,
  description text null,
  category text null,
  gender text null,
  price double precision null,
  currency text null,
  search_tsv tsvector null,
  created_at timestamp with time zone null default now(),
  metadata text null,
  size text null,
  second_hand boolean null default false,
  embedding public.vector null
);
```

## Usage

### Full Pipeline

Run the complete scraping pipeline:

```bash
python main.py --mode full
```

### Category Scraping Only

Extract product URLs from category pages:

```bash
python main.py --mode category --output-file product_urls.json
```

### Product Scraping Only

Scrape individual products from URLs:

```bash
python main.py --mode products --urls "https://www.stories.com/en-eu/product/t-shirt-123/" --output-file products.json
```

Or from a file:

```bash
python main.py --mode products --input-file product_urls.json --output-file products.json
```

### Check Configuration

View scraping statistics and configuration:

```bash
python main.py --stats
```

## Command Line Options

```
usage: main.py [-h] [--config CONFIG] [--mode {full,category,products,embeddings}]
               [--urls [URLS ...]] [--category-url CATEGORY_URL]
               [--input-file INPUT_FILE] [--output-file OUTPUT_FILE] [--stats]

& Other Stories Product Scraper

optional arguments:
  -h, --help            show this help message and exit
  --config CONFIG, -c CONFIG
                        Path to configuration file (default: config/other_stories.yaml)
  --mode {full,category,products,embeddings}, -m {full,category,products,embeddings}
                        Scraping mode (default: full)
  --urls URLS [URLS ...], -u URLS [URLS ...]
                        Product URLs for product mode
  --category-url CATEGORY_URL
                        Custom category URL for category mode
  --input-file INPUT_FILE, -i INPUT_FILE
                        File with product URLs (one per line)
  --output-file OUTPUT_FILE, -o OUTPUT_FILE
                        Output file for results (JSON format)
  --stats               Show scraping statistics
```

## Architecture

```
src/
├── scraper/
│   ├── browser.py          # Selenium WebDriver management
│   ├── category_scraper.py # Category page scraping
│   ├── product_scraper.py  # Individual product scraping
│   └── orchestrator.py     # Main coordination logic
├── database/
│   └── connection.py       # Supabase integration
├── embeddings/
│   └── service.py          # SigLIP embedding generation
└── utils/
    ├── config.py           # Configuration management
    └── logger.py           # Logging setup
```

## Data Flow

1. **Category Scraping**: Extract all product URLs from paginated category pages
2. **Product Scraping**: Visit each product URL and extract detailed information
3. **Embedding Generation**: Generate AI embeddings for product images using SigLIP
4. **Database Storage**: Store processed products in Supabase with embeddings

## Error Handling

The scraper includes comprehensive error handling:

- **Network failures**: Automatic retry with exponential backoff
- **Parsing errors**: Graceful degradation with partial data extraction
- **Rate limiting**: Built-in delays and request throttling
- **Browser crashes**: Automatic browser restart and recovery

## Logging

Logs are stored in `logs/scraper.log` with the following levels:

- **DEBUG**: Detailed operation information
- **INFO**: General progress and milestones
- **WARNING**: Non-critical issues
- **ERROR**: Critical errors requiring attention

## Performance Considerations

- **Batch processing**: Products are processed in configurable batches
- **Rate limiting**: Built-in delays prevent overwhelming the target site
- **Caching**: Embedding cache prevents reprocessing of images
- **Parallelization**: Future-ready architecture for concurrent processing

## Troubleshooting

### Common Issues

1. **Browser not starting**: Ensure Chrome is installed and up to date
2. **Database connection failed**: Check Supabase credentials and network
3. **Embedding generation failed**: Verify PyTorch installation and GPU availability
4. **Rate limiting**: Increase delays in configuration if getting blocked

### Debug Mode

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
python main.py --mode full
```

### Manual Testing

Test individual components:

```bash
# Test browser setup
python -c "from src.scraper.browser import BrowserManager; from src.utils.config import Config; b = BrowserManager(Config()); print('Browser setup:', b.setup_driver())"

# Test database connection
python -c "from src.database.connection import DatabaseConnection; from src.utils.config import Config; db = DatabaseConnection(Config()); print('DB connected:', db.connect())"
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review the logs in `logs/scraper.log`
3. Open an issue with detailed information about your setup and the error
