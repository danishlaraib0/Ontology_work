"""
config_loader.py
================
Unified loader for externalized configuration files (prompts.yaml, constants.yaml).
Provides cached access and clean fallbacks across all modules.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional
import yaml

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
PROMPTS_FILE = BASE_DIR / "prompts.yaml"
CONSTANTS_FILE = BASE_DIR / "constants.yaml"

_prompts_cache: Optional[Dict[str, Any]] = None
_constants_cache: Optional[Dict[str, Any]] = None


def load_prompts() -> Dict[str, Any]:
    """Loads prompts.yaml with caching."""
    global _prompts_cache
    if _prompts_cache is not None:
        return _prompts_cache

    if PROMPTS_FILE.exists():
        try:
            with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
                _prompts_cache = yaml.safe_load(f) or {}
                return _prompts_cache
        except Exception as e:
            logger.error(f"Error loading {PROMPTS_FILE}: {e}")

    _prompts_cache = {}
    return _prompts_cache


def load_constants() -> Dict[str, Any]:
    """Loads constants.yaml with caching."""
    global _constants_cache
    if _constants_cache is not None:
        return _constants_cache

    if CONSTANTS_FILE.exists():
        try:
            with open(CONSTANTS_FILE, "r", encoding="utf-8") as f:
                _constants_cache = yaml.safe_load(f) or {}
                return _constants_cache
        except Exception as e:
            logger.error(f"Error loading {CONSTANTS_FILE}: {e}")

    _constants_cache = {}
    return _constants_cache


def get_prompt(category: str, prompt_name: str, fallback: str = "") -> str:
    """Fetches a specific prompt string from prompts.yaml."""
    data = load_prompts()
    cat = data.get(category, {})
    return cat.get(prompt_name, fallback)


def get_constant(section: str, key: Optional[str] = None, default: Any = None) -> Any:
    """Fetches a constant value or section from constants.yaml."""
    data = load_constants()
    sec = data.get(section, {})
    if key is None:
        return sec if sec else default
    return sec.get(key, default)


# Module-level exported dicts
PROMPTS = load_prompts()
CONSTANTS = load_constants()
