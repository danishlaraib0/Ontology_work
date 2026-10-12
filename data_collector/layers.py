"""
layers.py
==========
Each function in this module collects one data layer for a given vehicle.

Sequence (matches the ontology design):
  L01  vehicle_master
  L02  spec_master
  L03  feature_taxonomy
  L04  competitor_master
  L05  audience_segments
  L06  buying_factors
  L07  reviews
  L08  opinion_dataset
  L09  search_intent
  L10  sales_data
  L11  pricing_data
  L12  ontology_summary   (final synthesis card)

Each layer function:
  1. Builds targeted search queries
  2. Retrieves context via DDG + Tavily
  3. Calls Gemini with grounding + context
  4. Parses JSON response
  5. Saves to storage
  6. Returns the parsed data dict
"""
from __future__ import annotations

import logging
import time
from typing import Any

from . import prompts
from .search_tools import combined_search, gemini_grounded_search_with_tool, gemini_plain_call, gemini_synthesise
from .parser import safe_parse, merge_search_context
from .storage import save_layer, save_raw_text, load_layer

logger = logging.getLogger(__name__)

# Rate-limit buffer between layer calls (seconds)
_INTER_LAYER_DELAY = 2.0
_QUOTA_WAIT        = 10.0



def _vehicle_id(brand: str, model: str) -> str:
    return f"{brand.upper().replace(' ', '')}-{model.upper().replace(' ', '')}"


def _search_and_synthesise(
    queries: list[str],
    prompt_template: str,
    fmt_kwargs: dict,
    layer_name: str,
) -> tuple[str, list[dict]]:
    """
    Run multiple search queries, combine results, then call Gemini to synthesise.
    If Gemini returns empty (quota exhausted), wait 60s and retry once with
    just Tavily context to maximise the chance of getting a real response.
    Returns (raw_llm_response, search_results_list).
    """
    all_results: list[dict] = []
    seen_urls:  set[str]   = set()

    for q in queries:
        logger.info(f"  🔍 Searching: {q}")
        for r in combined_search(q):
            url = r.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                all_results.append(r)
        time.sleep(0.5)  # polite delay

    context = merge_search_context(all_results)
    prompt  = prompt_template.format(**fmt_kwargs)
    full_prompt = f"{prompt}\n\n## Additional Web Context\n{context}"

    # ── Attempt 1: grounded call ──────────────────────────────────────────
    logger.info(f"  🤖 Calling Gemini (grounded) for [{layer_name}]...")
    raw = gemini_grounded_search_with_tool(full_prompt, temperature=0.15, max_tokens=8192)

    # ── Attempt 2: if empty, wait for quota and retry plain ───────────────
    if not raw or not raw.strip():
        logger.warning(
            f"  ⚠️  [{layer_name}] Got empty response — waiting {_QUOTA_WAIT}s for quota "
            "recovery then retrying with plain call..."
        )
        time.sleep(_QUOTA_WAIT)
        raw = gemini_plain_call(full_prompt, temperature=0.15, max_tokens=8192)

    return raw, all_results


# ══════════════════════════════════════════════════════════════════════════
# L01 — Vehicle Master
# ══════════════════════════════════════════════════════════════════════════
def collect_vehicle_master(brand: str, model: str, force: bool = False) -> dict:
    layer = "01_vehicle_master"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    vehicle_id = _vehicle_id(brand, model)
    queries = [
        f"{brand} {model} variants price specifications India 2024",
        f"{brand} {model} launch date generation segment body type",
        f"{brand} {model} official specifications india",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.VEHICLE_MASTER,
        {"brand": brand, "model": model},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "brand": brand, "model": model, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L02 — Spec Master
# ══════════════════════════════════════════════════════════════════════════
def collect_spec_master(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "02_spec_master"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} engine specifications power torque mileage",
        f"{brand} {model} dimensions boot space ground clearance",
        f"{brand} {model} features list all variants comparison",
        f"{brand} {model} safety features airbags NCAP rating",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.SPEC_MASTER,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L03 — Feature Taxonomy
# ══════════════════════════════════════════════════════════════════════════
def collect_feature_taxonomy(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "03_feature_taxonomy"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} complete features list all variants 2024",
        f"{brand} {model} vs competitors features comparison",
        f"{brand} {model} safety technology comfort features",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.FEATURE_TAXONOMY,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L04 — Competitor Master
# ══════════════════════════════════════════════════════════════════════════
def collect_competitor_master(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "04_competitor_master"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} competitors India 2024 segment rivals",
        f"best {model.split()[0] if model else 'sedan'} under 10 lakh India 2024",
        f"{brand} {model} vs Honda Amaze vs Hyundai Aura sales comparison",
        f"{brand} {model} market share segment rank India",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.COMPETITOR_MASTER,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L05 — Audience Segments
# ══════════════════════════════════════════════════════════════════════════
def collect_audience_segments(brand: str, model: str, vehicle_id: str, force: bool = False) -> list:
    layer = "05_audience_segments"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"who buys {brand} {model} customer profile India",
        f"{brand} {model} target audience demographic age income",
        f"{brand} {model} buyer persona first time buyer family",
        f"compact sedan buyer profile India 2024 research",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.AUDIENCE_SEGMENTS,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or [{"vehicle_id": vehicle_id, "_parse_error": True}]
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L06 — Buying Factors
# ══════════════════════════════════════════════════════════════════════════
def collect_buying_factors(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "06_buying_factors"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"why do people buy {brand} {model} India reasons",
        f"{brand} {model} purchase reasons owners survey mileage safety comfort",
        f"what matters most when buying compact sedan India",
        f"{brand} {model} owner feedback important features",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.BUYING_FACTORS,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L07 — Reviews
# ══════════════════════════════════════════════════════════════════════════
def collect_reviews(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "07_reviews"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} owner reviews India pros cons 2024",
        f"{brand} {model} expert review Autocar Zigwheels CarDekho",
        f"{brand} {model} Team-BHP forum review long term",
        f"{brand} {model} common complaints problems issues",
        f"{brand} {model} what owners love about it",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.REVIEWS_COLLECT,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L08 — Opinion Dataset (Aspect-level Sentiment)
# ══════════════════════════════════════════════════════════════════════════
def collect_opinion_dataset(brand: str, model: str, vehicle_id: str, force: bool = False) -> list:
    layer = "08_opinion_dataset"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} mileage real world owner review",
        f"{brand} {model} boot space interior quality feedback",
        f"{brand} {model} ride comfort NVH noise vibration harshness",
        f"{brand} {model} infotainment system review",
        f"{brand} {model} after sales service experience India",
        f"{brand} {model} resale value depreciation",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.OPINION_DATASET,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or [{"vehicle_id": vehicle_id, "_parse_error": True}]
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L09 — Search / Intent Data
# ══════════════════════════════════════════════════════════════════════════
def collect_search_intent(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "09_search_intent"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    brand_model = f"{brand} {model}"
    queries = [
        f"{brand_model} most searched questions India",
        f"people also ask {brand_model} India",
        f"{brand_model} vs competitors search queries",
        f"common questions about {brand_model} buyers",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.SEARCH_INTENT,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L10 — Sales & Registration Data
# ══════════════════════════════════════════════════════════════════════════
def collect_sales_data(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "10_sales_data"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} monthly sales data 2024 India units",
        f"{brand} {model} sales figures SIAM FADA registration",
        f"{brand} {model} market share segment rank India 2024",
        f"best selling compact sedan India 2024 sales data",
        f"{brand} {model} geographic demand top cities states India",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.SALES_DATA,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L11 — Pricing Data
# ══════════════════════════════════════════════════════════════════════════
def collect_pricing_data(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "11_pricing_data"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    queries = [
        f"{brand} {model} ex showroom price all variants October 2024",
        f"{brand} {model} on road price Delhi Mumbai Bangalore 2024",
        f"{brand} {model} price hike history 2022 2023 2024",
        f"{brand} {model} discount offers this month 2024",
        f"{brand} {model} EMI calculator finance offers",
    ]
    raw, _ = _search_and_synthesise(
        queries,
        prompts.PRICING_DATA,
        {"brand": brand, "model": model, "vehicle_id": vehicle_id},
        layer,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    time.sleep(_INTER_LAYER_DELAY)
    return data


# ══════════════════════════════════════════════════════════════════════════
# L12 — Ontology Summary (Master Intelligence Card)
# ══════════════════════════════════════════════════════════════════════════
def collect_ontology_summary(brand: str, model: str, vehicle_id: str, force: bool = False) -> dict:
    layer = "12_ontology_summary"
    if not force:
        cached = load_layer(brand, model, layer)
        if cached:
            logger.info(f"[{layer}] Using cached data.")
            return cached

    # This layer synthesises across all prior layers — no additional search needed.
    # Just call Gemini with grounding to generate the master card.
    prompt = prompts.ONTOLOGY_SUMMARY.format(
        brand=brand, model=model, vehicle_id=vehicle_id
    )
    logger.info(f"  🤖 Generating Ontology Summary for {brand} {model}...")
    raw = gemini_grounded_search_with_tool(
        prompt=prompt,
        temperature=0.2,
        max_tokens=8192,
    )
    save_raw_text(brand, model, layer, raw)
    data = safe_parse(raw, layer) or {"vehicle_id": vehicle_id, "_parse_error": True}
    save_layer(brand, model, layer, data)
    return data
