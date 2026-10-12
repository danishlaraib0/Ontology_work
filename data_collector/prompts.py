"""
prompts.py
===========
Centralized Gemini prompt templates for data collection layers.
Prompts are loaded from prompts.yaml with fallback to local defaults.
"""
from __future__ import annotations

from config_loader import get_prompt, load_prompts

# Load from prompts.yaml
_dc = load_prompts().get("data_collector", {})

VEHICLE_MASTER = _dc.get("vehicle_master", "")
SPEC_MASTER = _dc.get("spec_master", "")
FEATURE_TAXONOMY = _dc.get("feature_taxonomy", "")
COMPETITOR_MASTER = _dc.get("competitor_master", "")
AUDIENCE_SEGMENTS = _dc.get("audience_segments", "")
BUYING_FACTORS = _dc.get("buying_factors", "")
REVIEWS_COLLECT = _dc.get("reviews", "")
REVIEWS = REVIEWS_COLLECT
OPINION_DATASET = _dc.get("opinion_dataset", "")
SEARCH_INTENT = _dc.get("search_intent", "")
SALES_DATA = _dc.get("sales_data", "")
PRICING_DATA = _dc.get("pricing_data", "")
ONTOLOGY_SUMMARY = _dc.get("ontology_summary", "")


def _wrap(title: str, body: str) -> str:
    return f"# {title}\n\n{body}"
