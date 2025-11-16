"""Configuration management utilities."""

import os
import yaml
from typing import Dict, Any
from pathlib import Path


class Config:
    """Configuration manager for the scraper."""

    def __init__(self, config_path: str = None):
        self.config_path = config_path or "config/other_stories.yaml"
        self._config = self._load_config()
        self._env_vars = self._load_env_vars()

    def _load_config(self) -> Dict[str, Any]:
        """Load YAML configuration file."""
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _load_env_vars(self) -> Dict[str, str]:
        """Load environment variables."""
        return {
            'SUPABASE_URL': os.getenv('SUPABASE_URL'),
            'SUPABASE_KEY': os.getenv('SUPABASE_KEY'),
            'USER_AGENT': os.getenv('USER_AGENT', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'),
            'HEADLESS': os.getenv('HEADLESS', 'true').lower() == 'true',
            'EMBEDDING_CACHE_DIR': os.getenv('EMBEDDING_CACHE_DIR', './cache/embeddings'),
            'DEVICE': os.getenv('DEVICE', 'auto'),
            'LOG_LEVEL': os.getenv('LOG_LEVEL', 'INFO')
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split('.')
        value = self._config

        try:
            for k in keys:
                value = value[k]
            return value
        except KeyError:
            # Check environment variables
            env_key = key.upper().replace('.', '_')
            if env_key in self._env_vars:
                return self._env_vars[env_key]
            return default

    def get_brand_config(self) -> Dict[str, Any]:
        """Get brand-specific configuration."""
        return self._config.get('brand', {})

    def get_scraping_config(self) -> Dict[str, Any]:
        """Get scraping configuration."""
        return self._config.get('scraping', {})

    def get_selectors(self) -> Dict[str, Any]:
        """Get CSS selectors configuration."""
        return self._config.get('selectors', {})

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration."""
        return self._config.get('database', {})

    def get_embedding_config(self) -> Dict[str, Any]:
        """Get embedding configuration."""
        return self._config.get('embedding', {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self._config.get('logging', {})

    @property
    def supabase_url(self) -> str:
        """Get Supabase URL."""
        return self._env_vars.get('SUPABASE_URL')

    @property
    def supabase_key(self) -> str:
        """Get Supabase key."""
        return self._env_vars.get('SUPABASE_KEY')

    @property
    def user_agent(self) -> str:
        """Get user agent."""
        return self._env_vars.get('USER_AGENT')

    @property
    def headless(self) -> bool:
        """Get headless mode setting."""
        return self._env_vars.get('HEADLESS')

    @property
    def device(self) -> str:
        """Get device for embeddings."""
        return self._env_vars.get('DEVICE')

    @property
    def embedding_cache_dir(self) -> str:
        """Get embedding cache directory."""
        return self._env_vars.get('EMBEDDING_CACHE_DIR')
