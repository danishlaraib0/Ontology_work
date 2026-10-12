"""
canonical_ids.py
================
Generates deterministic, standardized canonical entity IDs across all domains
of the Automotive World Ontology.
"""
from __future__ import annotations

import re
import hashlib


def _clean_token(text: str) -> str:
    """Normalize text into UPPERCASE_SNAKE_CASE."""
    if not text:
        return "UNKNOWN"
    s = re.sub(r"[^a-zA-Z0-9]+", "_", str(text).strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s.upper() or "UNKNOWN"


def canonical_brand_id(brand: str) -> str:
    return f"BRAND_{_clean_token(brand)}"


def canonical_vehicle_model_id(brand: str, model: str) -> str:
    return f"VEH_{_clean_token(brand)}_{_clean_token(model)}"


def canonical_generation_id(brand: str, model: str, gen_name_or_num: str | int) -> str:
    return f"GEN_{_clean_token(brand)}_{_clean_token(model)}_{_clean_token(str(gen_name_or_num))}"


def canonical_variant_id(brand: str, model: str, variant_name: str) -> str:
    return f"VAR_{_clean_token(brand)}_{_clean_token(model)}_{_clean_token(variant_name)}"


def canonical_segment_id(segment_name: str) -> str:
    return f"SEG_{_clean_token(segment_name)}"


def canonical_platform_id(platform_name: str) -> str:
    return f"PLATFORM_{_clean_token(platform_name)}"


def canonical_powertrain_id(pt_type_or_name: str, fuel_type: str = "") -> str:
    combo = f"{pt_type_or_name}_{fuel_type}".strip("_")
    return f"PT_{_clean_token(combo)}"


def canonical_engine_id(engine_code: str, displacement_cc: int | str = "") -> str:
    combo = f"{engine_code}_{displacement_cc}".strip("_")
    return f"ENG_{_clean_token(combo)}"


def canonical_feature_category_id(category_name: str) -> str:
    return f"FCAT_{_clean_token(category_name)}"


def canonical_feature_id(feature_name: str) -> str:
    return f"FEAT_{_clean_token(feature_name)}"


def canonical_customer_segment_id(model: str, segment_name_or_id: str) -> str:
    return f"AUD_{_clean_token(model)}_{_clean_token(segment_name_or_id)}"


def canonical_need_id(need_name: str) -> str:
    return f"NEED_{_clean_token(need_name)}"


def canonical_buying_factor_id(factor_name: str) -> str:
    return f"BF_{_clean_token(factor_name)}"


def canonical_aspect_id(aspect_name: str) -> str:
    return f"ASPECT_{_clean_token(aspect_name)}"


def canonical_review_id(brand: str, model: str, source_or_id: str) -> str:
    return f"REV_{_clean_token(brand)}_{_clean_token(model)}_{_clean_token(source_or_id)}"


def canonical_opinion_id(brand: str, model: str, aspect: str, claim: str) -> str:
    short_hash = hashlib.md5(claim.encode("utf-8")).hexdigest()[:8].upper()
    return f"OP_{_clean_token(brand)}_{_clean_token(model)}_{_clean_token(aspect)}_{short_hash}"


def canonical_query_id(query_text: str) -> str:
    short_hash = hashlib.md5(query_text.encode("utf-8")).hexdigest()[:8].upper()
    clean_snippet = _clean_token(query_text)[:25]
    return f"QRY_{clean_snippet}_{short_hash}"


def canonical_intent_id(intent_type: str) -> str:
    return f"INTENT_{_clean_token(intent_type)}"


def canonical_geography_id(geo_name: str) -> str:
    return f"GEO_{_clean_token(geo_name)}"


def canonical_sales_obs_id(brand: str, model: str, period: str) -> str:
    return f"SOBS_{_clean_token(brand)}_{_clean_token(model)}_{_clean_token(period)}"


def canonical_price_obs_id(variant_id: str, market: str = "DELHI", period_or_date: str = "CURRENT") -> str:
    return f"POBS_{_clean_token(variant_id)}_{_clean_token(market)}_{_clean_token(period_or_date)}"


def canonical_source_id(source_name: str) -> str:
    return f"SRC_{_clean_token(source_name)}"


def canonical_evidence_id(claim_or_source: str) -> str:
    short_hash = hashlib.md5(claim_or_source.encode("utf-8")).hexdigest()[:8].upper()
    return f"EVID_{short_hash}"


def canonical_market_change_id(model: str, change_type: str, date: str) -> str:
    return f"CHG_{_clean_token(model)}_{_clean_token(change_type)}_{_clean_token(date)}"


def canonical_forecast_run_id(model: str, model_type: str, run_date: str) -> str:
    return f"FCRUN_{_clean_token(model)}_{_clean_token(model_type)}_{_clean_token(run_date)}"


def canonical_sales_prediction_id(run_id: str, target_period: str) -> str:
    return f"PRED_{_clean_token(run_id)}_{_clean_token(target_period)}"

