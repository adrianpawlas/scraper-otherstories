# & Other Stories Scraper

A comprehensive scraper for & Other Stories that extracts all product information, generates image embeddings, and imports data to Supabase.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your Supabase credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

3. Run the scraper:
```bash
python scraper.py
```

## Features

- Scrapes all products from & Other Stories
- Extracts complete product information
- Generates 768-dimensional image embeddings using google/siglip-base-patch16-384
- Imports data to Supabase products table
- Handles rate limiting and error recovery

