# & Other Stories Scraper

A comprehensive scraper for & Other Stories that extracts all product information, generates image embeddings, and imports data to Supabase.

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Create a `.env` file with your Supabase credentials:
```
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
```

3. Run the scraper:
```bash
python scraper.py
```

### GitHub Actions (Automated Daily Runs)

The scraper runs automatically every day at midnight UTC via GitHub Actions. You can also trigger it manually from the Actions tab.

**To set up GitHub Actions:**

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Add the following secrets:
   - `SUPABASE_URL`: Your Supabase project URL
   - `SUPABASE_KEY`: Your Supabase service role key

The workflow will run automatically at midnight UTC daily, or you can trigger it manually from the **Actions** tab.

## Features

- Scrapes all products from & Other Stories (20 pages)
- Extracts complete product information using JSON-LD structured data
- Generates 768-dimensional image embeddings using google/siglip-base-patch16-384
- Imports data to Supabase products table
- Handles rate limiting and error recovery
- Automated daily runs via GitHub Actions

