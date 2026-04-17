"""
AgenticS Configuration Manager
"""

import os
import yaml
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG = {
    "models": {
        "default": "gemini",
        "providers": {
            "gemini": {
                "provider": "google",
                "model": "gemini-2.0-flash",
                "api_key": None,
            },
            "openai": {
                "provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": None,
            },
            "claude": {
                "provider": "anthropic",
                "model": "claude-sonnet-4-20250514",
                "api_key": None,
            },
            "ollama": {
                "provider": "ollama",
                "model": "llama3.1",
                "api_base": "http://localhost:11434",
            },
        },
    },
    "server": {
        "host": "0.0.0.0",
        "port": 7860,
        "debug": True,
    },
    "crews": {},
}


class Config:
    def __init__(self, config_path: Optional[str] = None):
        self.base_dir = Path(__file__).parent
        self.config_path = Path(config_path) if config_path else self.base_dir / "config.yaml"
        self._config = {}
        self.load()

    def load(self):
        """Load config from YAML file, fallback to defaults."""
        if self.config_path.exists():
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f) or {}
        # Merge with defaults
        self._config = self._deep_merge(DEFAULT_CONFIG, self._config)
        # Override with environment variables
        self._apply_env_overrides()

    def _deep_merge(self, base: dict, override: dict) -> dict:
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _apply_env_overrides(self):
        """Override config with environment variables."""
        env_map = {
            "GOOGLE_API_KEY": ("models", "providers", "gemini", "api_key"),
            "OPENAI_API_KEY": ("models", "providers", "openai", "api_key"),
            "ANTHROPIC_API_KEY": ("models", "providers", "claude", "api_key"),
        }
        for env_var, path in env_map.items():
            val = os.environ.get(env_var)
            if val:
                d = self._config
                for p in path[:-1]:
                    d = d.setdefault(p, {})
                d[path[-1]] = val

    def get(self, *keys, default=None):
        d = self._config
        for k in keys:
            if isinstance(d, dict):
                d = d.get(k)
            else:
                return default
        return d if d is not None else default

    @property
    def default_model(self) -> str:
        return self.get("models", "default", default="gemini")

    @property
    def model_providers(self) -> dict:
        return self.get("models", "providers", default={})

    @property
    def server_config(self) -> dict:
        return self.get("server", default={"host": "0.0.0.0", "port": 7860})

    def get_model_config(self, model_name: str) -> dict:
        """Get config for a specific model."""
        providers = self.model_providers
        if model_name in providers:
            return providers[model_name]
        return providers.get(self.default_model, {})


# Global config instance
_config_instance = None


def get_config(config_path: Optional[str] = None) -> Config:
    global _config_instance
    if _config_instance is None:
        _config_instance = Config(config_path)
    return _config_instance
