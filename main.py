#!/usr/bin/env python3
"""Main entry point for the & Other Stories scraper."""

import sys
from pathlib import Path

# Import and run the main module from src
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from main import main

if __name__ == '__main__':
    main()