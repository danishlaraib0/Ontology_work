"""
query_planner.py
================
Dynamic AI Intent and Query Planner for the Automotive World Model:
  • Tier 1: SLM (Fast Intent Classifier & Tool Selector with schema context)
  • Tier 2: Stronger LLM Fallback (Multi-hop Investigations & Schema-Aware Cypher)
  • Dynamic Input Validation (Rejects noise/gibberish before model execution)
All prompts and keywords are externalized in prompts.yaml and constants.yaml.
"""
from __future__ import annotations

import re
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from intelligence.schema_registry import GraphSchemaRegistry
from data_collector.search_tools import gemini_plain_call
from data_collector.config import GEMINI_MODEL, GEMINI_MODEL_FALLBACK, GEMINI_MODEL_FINAL
from config_loader import get_constant, get_prompt

logger = logging.getLogger(__name__)

# Load constants from constants.yaml
_keywords_cfg = get_constant("keywords", default={})
_AUTOMOTIVE_KEYWORDS = set(_keywords_cfg.get("automotive_vocabulary", [
    "car", "cars", "auto", "automobile", "automotive", "vehicle", "vehicles",
    "sedan", "sedans", "suv", "suvs", "hatchback", "hatchbacks", "mpv", "cng",
    "ev", "petrol", "diesel", "hybrid", "engine", "airbag", "airbags", "ncap",
    "safety", "features", "powertrain", "transmission", "mileage", "fuel",
    "efficiency", "spec", "specs", "specification", "specifications", "variant",
    "variants", "trim", "trims", "boot", "space", "nvh", "clearance", "price",
    "prices", "pricing", "cost", "costs", "discount", "discounts", "sales", "gap",
    "gaps", "vulnerability", "vulnerable", "competitor", "competitors", "rival",
    "rivals", "decision", "strategy", "customer", "customers", "buyer", "buyers"
]))
_KEYBOARD_MASH_PATTERNS = _keywords_cfg.get("keyboard_mash_patterns", [
    "sdfgh", "dfghj", "fghjk", "ghjkl", "asdfg", "esfdgh",
    "qwert", "werty", "ertyu", "rtyui", "tyuio", "yuiop",
    "zxcvb", "xcvbn", "cvbnm"
])


@dataclass
class QueryPlan:
    """Structured plan specifying intent, tools, entities, and execution mode."""
    user_query: str
    intent: str
    selected_tool: str
    target_models: List[str] = field(default_factory=list)
    segments: List[str] = field(default_factory=list)
    aspects: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    dynamic_cypher: Optional[str] = None
    complexity: str = "SIMPLE"  # 'SIMPLE' or 'COMPLEX'
    planner_model: str = "SLM"  # 'SLM' or 'LLM_FALLBACK'
    reasoning: str = ""


class SLMQueryPlanner:
    """
    Translates natural-language automotive queries into structured query plans.
    Uses AI models with real-time schema and intent awareness, rather than
    brittle hardcoded regex pattern matching.
    """

    COMMON_AUTOMOTIVE_KEYWORDS = _AUTOMOTIVE_KEYWORDS
    KEYBOARD_MASH_PATTERNS = _KEYBOARD_MASH_PATTERNS

    def __init__(self, schema_registry: Optional[GraphSchemaRegistry] = None):
        self.schema = schema_registry or GraphSchemaRegistry()
        self.known_vehicles = [v.lower() for v in self.schema.get_known_vehicles()]

    def _is_gibberish_or_invalid(self, query: str) -> tuple[bool, str]:
        """Detects keyboard mashing, symbol noise, and queries lacking any automotive context."""
        q_clean = query.strip()
        if len(q_clean) < 2:
            return True, "Query is too short or empty."

        tokens = re.findall(r"[a-zA-Z0-9]+", q_clean)
        if not tokens:
            return True, "Query contains only punctuation or special symbols."

        alpha_tokens = [t.lower() for t in tokens if re.search(r"[a-zA-Z]", t)]
        if not alpha_tokens:
            return True, "Query contains no alphabetic words or recognizable terms."

        known_vehicles = set(self.known_vehicles)
        known_brands = {b.lower() for b in self.schema.get_known_brands()}
        known_segments = {s.lower() for s in self.schema.get_known_segments()}

        # 1. Check for keyboard mash patterns & unnatural consonant clusters
        for t in alpha_tokens:
            if t not in known_vehicles and t not in known_brands and t not in self.COMMON_AUTOMOTIVE_KEYWORDS:
                if any(p in t for p in self.KEYBOARD_MASH_PATTERNS):
                    return True, f"Detected keyboard mashing pattern in '{t}'."
                if re.search(r"[bcdfghjklmnpqrstvwxz]{5,}", t) and t.upper() not in ["SIAM", "GNCAP", "ARAI"]:
                    return True, f"Detected unnatural consonant cluster in '{t}'."

        # 2. Check for semantic word overlap
        recognized = 0
        for t in alpha_tokens:
            if (
                t in known_vehicles
                or t in known_brands
                or any(t in s for s in known_segments)
                or t in self.COMMON_AUTOMOTIVE_KEYWORDS
            ):
                recognized += 1

        if recognized == 0:
            return True, f"Unrecognized input: No automotive entities, segments, or inquiry terms detected in '{query}'."

        return False, "Valid"

    def plan_query(self, query: str, force_llm: bool = False) -> QueryPlan:
        """
        Dynamically plans the execution of an automotive intelligence inquiry using AI models.
        Does NOT rely on rigid hardcoded regex fast-paths.
        """
        clean_q = query.strip()

        # Step 0: Input Validation & Gibberish Rejection
        is_invalid, reason = self._is_gibberish_or_invalid(clean_q)
        if is_invalid:
            logger.info(f"🚫 Query Planner rejected invalid input: '{clean_q}' ({reason})")
            return QueryPlan(
                user_query=clean_q,
                intent="INVALID_QUERY",
                selected_tool="invalid_query",
                target_models=[],
                complexity="SIMPLE",
                planner_model="INPUT_VALIDATION",
                reasoning=f"Query rejected: {reason}",
            )

        # Step 1: SLM Intent & Query Planner (Dynamic Model Planning)
        if not force_llm:
            try:
                slm_plan = self._call_slm_planner(clean_q, model=GEMINI_MODEL)
                if slm_plan and slm_plan.selected_tool != "unknown":
                    if slm_plan.selected_tool == "dynamic_cypher" and not slm_plan.dynamic_cypher:
                        logger.info("Dynamic cypher selected without query text; synthesizing via LLM...")
                        fallback = self._call_llm_fallback_planner(clean_q)
                        slm_plan.dynamic_cypher = fallback.dynamic_cypher
                    logger.info(f"🤖 SLM Planner matched: intent='{slm_plan.intent}', tool='{slm_plan.selected_tool}'")
                    return slm_plan
            except Exception as exc:
                logger.warning(f"SLM planner encountered issue: {exc}. Escalating to LLM fallback.")

        # Step 2: Stronger LLM Fallback
        logger.info("🧠 Escalating to Stronger LLM Fallback Planner...")
        fallback_plan = self._call_llm_fallback_planner(clean_q)
        return fallback_plan

    # ── Tier 1: SLM Planner Call ──────────────────────────────────────────────
    def _call_slm_planner(self, query: str, model: str) -> Optional[QueryPlan]:
        """Plans query dynamically using the schema context and prompts.yaml definition."""
        schema_summary = self.schema.get_schema_prompt_summary()
        prompt_template = get_prompt("intelligence", "slm_planner")
        if not prompt_template:
            # Fallback if prompts.yaml missing
            prompt_template = """You are an SLM Automotive Intelligence Query Planner.
Analyze this user query and output a strict JSON plan without markdown code blocks.
Query: "{query}"
Schema:
{schema_summary}
Available Tools:
- decision_engine: Strategic decision evaluation, pricing repositioning scenarios.
- dynamic_cypher: Ad-hoc graph inquiries, segment profit/margin comparisons.
- category_gap_analysis: Identifies and ranks product gaps, safety deficits, and unmet needs.
- vehicle_spec_compare: Head-to-head spec/safety/price comparisons across 2+ models.
- audience_fit: Ranks models for specific customer segments.
- competitor_vulnerability: Simulates price drops / discounts and rival vulnerability.
- market_change_tracer: Investigates recorded market disruptions or safety leaps.
- evidence_correlator: Links search intent signals to sales dispatch time series.
- customer_behavior_analysis: Analyzes demographic impacts on vehicle buying preferences.
"""
        prompt = prompt_template.format(query=query, schema_summary=schema_summary)

        raw_text = gemini_plain_call(prompt, model=model, max_tokens=1000)
        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
            clean_text = re.sub(r"\n?```$", "", clean_text).strip()

        data = json.loads(clean_text)
        return QueryPlan(
            user_query=query,
            intent=data.get("intent", "DYNAMIC_GRAPH_QUERY"),
            selected_tool=data.get("selected_tool", "dynamic_cypher"),
            target_models=data.get("target_models", []),
            segments=data.get("segments", []),
            aspects=data.get("aspects", []),
            parameters=data.get("parameters", {}),
            dynamic_cypher=data.get("dynamic_cypher"),
            complexity=data.get("complexity", "SIMPLE"),
            planner_model="SLM",
            reasoning=data.get("reasoning", ""),
        )

    # ── Tier 2: Stronger LLM Fallback ─────────────────────────────────────────
    def _call_llm_fallback_planner(self, query: str) -> QueryPlan:
        """Invoked when SLM fails or encounters ambiguous ad-hoc questions."""
        schema_summary = self.schema.get_schema_prompt_summary()
        prompt_template = get_prompt("intelligence", "llm_fallback_planner")
        if not prompt_template:
            prompt_template = """You are a Principal Automotive Knowledge Graph Architect.
The user asked an ad-hoc or complex inquiry:
"{query}"
Schema:
{schema_summary}
Construct a schema-aware READ-ONLY Cypher query to retrieve evidence from Neo4j.
"""
        prompt = prompt_template.format(query=query, schema_summary=schema_summary)

        try:
            raw_text = gemini_plain_call(prompt, model=GEMINI_MODEL_FALLBACK, max_tokens=1000)
            clean_text = raw_text.strip()
            if clean_text.startswith("```"):
                clean_text = re.sub(r"^```(?:json)?\n?", "", clean_text)
                clean_text = re.sub(r"\n?```$", "", clean_text).strip()
            data = json.loads(clean_text)
            return QueryPlan(
                user_query=query,
                intent="DYNAMIC_GRAPH_QUERY",
                selected_tool="dynamic_cypher",
                target_models=data.get("target_models", []),
                dynamic_cypher=data.get("dynamic_cypher"),
                complexity="COMPLEX",
                planner_model="LLM_FALLBACK",
                reasoning=data.get("reasoning", "LLM-synthesized dynamic Cypher traversal"),
            )
        except Exception:
            # Safe default fallback Cypher
            safe_cypher = (
                "MATCH (v:VehicleModel)-[:COMPETES_WITH]-(rival:VehicleModel) "
                "RETURN v.name AS model, rival.name AS rival, rival.body_type AS body_type LIMIT 25"
            )
            return QueryPlan(
                user_query=query,
                intent="DYNAMIC_GRAPH_QUERY",
                selected_tool="dynamic_cypher",
                dynamic_cypher=safe_cypher,
                complexity="COMPLEX",
                planner_model="LLM_FALLBACK",
                reasoning="Safe default graph exploration fallback.",
            )
