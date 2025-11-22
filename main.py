#!/usr/bin/env python3
"""Main entry point for the & Other Stories scraper."""

import sys
import subprocess
from pathlib import Path

if __name__ == '__main__':
    # Ensure we're running from the project root
    project_root = Path(__file__).parent
    # Run as a module to ensure proper package structure for relative imports
    result = subprocess.run(
        [sys.executable, '-m', 'src.main'] + sys.argv[1:],
        cwd=str(project_root)
    )
    sys.exit(result.returncode)