"""
storage.py
===========
Handles saving collected data to:
  1. Local JSON files  (always)
  2. Cloudflare R2     (optional — if boto3 is available and keys are set)
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from .config import DATA_DIR

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Create a filesystem-safe slug from brand/model name."""
    return text.lower().replace(" ", "_").replace("/", "-")


def vehicle_dir(brand: str, model: str) -> Path:
    """Return (and create) the output directory for a vehicle."""
    d = DATA_DIR / _slugify(brand) / _slugify(model)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_layer(
    brand: str,
    model: str,
    layer_name: str,
    data: Any,
    *,
    pretty: bool = True,
) -> Path:
    """
    Save a data layer to a JSON file.

    Args:
        brand:      Vehicle brand (e.g. "Maruti Suzuki")
        model:      Vehicle model (e.g. "Dzire")
        layer_name: Layer identifier (e.g. "01_vehicle_master")
        data:       JSON-serialisable Python object (dict / list)
        pretty:     If True, indent JSON for human readability

    Returns:
        Path to the saved file.
    """
    out_dir = vehicle_dir(brand, model)
    filename = f"{layer_name}.json"
    filepath = out_dir / filename

    # Add collection metadata
    envelope = {
        "metadata": {
            "brand":      brand,
            "model":      model,
            "layer":      layer_name,
            "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
        "data": data,
    }

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(envelope, f, ensure_ascii=False, indent=2 if pretty else None)

    logger.info(f"✅ Saved layer '{layer_name}' → {filepath}")
    return filepath


def load_layer(brand: str, model: str, layer_name: str) -> Any | None:
    """Load a previously saved layer. Returns None if file doesn't exist."""
    filepath = vehicle_dir(brand, model) / f"{layer_name}.json"
    if not filepath.exists():
        return None
    with open(filepath, encoding="utf-8") as f:
        envelope = json.load(f)
    return envelope.get("data")


def save_raw_text(brand: str, model: str, layer_name: str, text: str) -> Path:
    """Save raw LLM response text for debugging / re-parsing."""
    out_dir = vehicle_dir(brand, model) / "raw"
    out_dir.mkdir(exist_ok=True)
    filepath = out_dir / f"{layer_name}.txt"
    filepath.write_text(text, encoding="utf-8")
    logger.debug(f"💾 Raw text saved → {filepath}")
    return filepath


def list_collected_vehicles() -> list[dict]:
    """List all vehicles that have been collected."""
    results = []
    if not DATA_DIR.exists():
        return results
    for brand_dir in DATA_DIR.iterdir():
        if brand_dir.is_dir():
            for model_dir in brand_dir.iterdir():
                if model_dir.is_dir():
                    layers = [f.stem for f in model_dir.glob("*.json")]
                    results.append({
                        "brand":  brand_dir.name,
                        "model":  model_dir.name,
                        "layers": sorted(layers),
                        "path":   str(model_dir),
                    })
    return results
