#!/usr/bin/env python3
"""Main entry point for the & Other Stories scraper."""

import sys
import subprocess

if __name__ == '__main__':
    # Run as a module to ensure proper package structure
    sys.exit(subprocess.run([sys.executable, '-m', 'src.main'] + sys.argv[1:]).returncode)