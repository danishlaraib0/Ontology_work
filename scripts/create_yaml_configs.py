"""
create_yaml_configs.py
======================
Generates prompts.yaml and constants.yaml from existing Python definitions,
centralizing all prompts and constants.
"""
import yaml
from pathlib import Path
import data_collector.prompts as dp
from intelligence.query_planner import SLMQueryPlanner
from intelligence.query_safety import FORBIDDEN_CYPHER_KEYWORDS, READ_ONLY_START_KEYWORDS, DEFAULT_MAX_LIMIT

prompts_data = {
    'data_collector': {
        'vehicle_master': dp.VEHICLE_MASTER.strip(),
        'spec_master': dp.SPEC_MASTER.strip(),
        'feature_taxonomy': dp.FEATURE_TAXONOMY.strip(),
        'competitor_master': dp.COMPETITOR_MASTER.strip(),
        'audience_segments': dp.AUDIENCE_SEGMENTS.strip(),
        'buying_factors': dp.BUYING_FACTORS.strip(),
        'reviews': dp.REVIEWS_COLLECT.strip(),
        'opinion_dataset': dp.OPINION_DATASET.strip(),
        'search_intent': dp.SEARCH_INTENT.strip(),
        'sales_data': dp.SALES_DATA.strip(),
        'pricing_data': dp.PRICING_DATA.strip(),
        'ontology_summary': dp.ONTOLOGY_SUMMARY.strip(),
    },
    'intelligence': {
        'slm_planner': """You are an SLM Automotive Intelligence Query Planner.
Analyze this user query and output a strict JSON plan without markdown code blocks.

Query: "{query}"

Schema:
{schema_summary}

Available Tools:
- decision_engine: Strategic decision evaluation, pricing repositioning scenarios, customer segment impact evaluation, and governed action proposals (e.g. 'Should [model] reduce price to compete with [rival]').
- dynamic_cypher: Ad-hoc graph inquiries, segment profit/margin comparisons, price ladder distributions, sales volume aggregations, market entry/launch opportunities, or any analytical question not covered by dedicated tools. If choosing dynamic_cypher, you MUST provide a valid, read-only Cypher query in the "dynamic_cypher" field that queries the schema to answer the user query.
- category_gap_analysis: Identifies and ranks product gaps, safety deficits, and unmet needs across vehicle categories/segments.
- vehicle_spec_compare: Head-to-head spec/safety/price comparisons across 2+ models.
- audience_fit: Ranks or evaluates models for specific customer segments ("Small Urban Families", "Budget First-Time Buyers", "High-Mileage Gig Workers").
- competitor_vulnerability: Simulates price drops / discounts and evaluates rival vulnerability.
- market_change_tracer: Investigates recorded market disruptions or safety leaps.
- evidence_correlator: Links search intent signals to sales dispatch time series.
- customer_behavior_analysis: Analyzes demographic (gender, age) impacts on vehicle buying factors and preferences.

Cypher Schema Rules (CRITICAL):
- Vehicle segments: (s:VehicleSegment)<-[:BELONGS_TO]-(v:VehicleModel)
- Customer segments: (cs:CustomerSegment)-[:CONSIDERS]->(v:VehicleModel)
- Pricing: (v:VehicleModel)-[:HAS_VARIANT]->(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation) OR (v)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation). Property: `p.ex_showroom_inr`
- Sales volume: (v:VehicleModel)-[:HAS_SALES_OBSERVATION]->(so:SalesObservation). Property: `so.units_sold` (NEVER use `units`!)
- Use undirected relationships `-[:CONSIDERS]-` or `-[:BELONGS_TO]-` if unsure of direction.

JSON Schema:
{{
  "intent": "DECISION_RECOMMENDATION" | "DYNAMIC_GRAPH_QUERY" | "CATEGORY_GAP_ANALYSIS" | "SPEC_FEATURE_COMPARE" | "AUDIENCE_FIT" | "COMPETITOR_VULNERABILITY" | "MARKET_CHANGE_INVESTIGATION" | "CORRELATION_ANALYSIS" | "CUSTOMER_BEHAVIOR_ANALYSIS",
  "selected_tool": "decision_engine" | "dynamic_cypher" | "category_gap_analysis" | "vehicle_spec_compare" | "audience_fit" | "competitor_vulnerability" | "market_change_tracer" | "evidence_correlator" | "customer_behavior_analysis",
  "target_models": ["Model1"],
  "segments": ["SegmentName"],
  "aspects": ["safety", "price"],
  "parameters": {{}},
  "dynamic_cypher": "MATCH ... RETURN ... LIMIT 25" or null,
  "complexity": "SIMPLE" | "COMPLEX",
  "reasoning": "brief explanation"
}}""".strip(),

        'llm_fallback_planner': """You are a Principal Automotive Knowledge Graph Architect.
The user asked an ad-hoc or complex inquiry:
"{query}"

Schema:
{schema_summary}

Construct a schema-aware READ-ONLY Cypher query to retrieve evidence from Neo4j.
Rules:
- Must only use MATCH, OPTIONAL MATCH, WITH, WHERE, RETURN, ORDER BY.
- NEVER use CREATE, MERGE, SET, DELETE, DROP.
- Include a LIMIT 25 clause.
- Return clean node and property aliases (e.g. segment, min_price, max_price, units_sold).
- Schema properties: SalesObservation has `units_sold` (NOT units), PriceObservation has `ex_showroom_inr`, VehicleModel has `name`, VehicleSegment has `name`.

Output JSON:
{{
  "intent": "DYNAMIC_GRAPH_QUERY",
  "selected_tool": "dynamic_cypher",
  "dynamic_cypher": "MATCH ... RETURN ... LIMIT 25",
  "target_models": [],
  "complexity": "COMPLEX",
  "reasoning": "multi-hop Cypher traversal"
}}""".strip(),

        'strategic_synthesis': """You are a Senior Automotive Strategy Director.
User Question: "{query}"

Retrieved Knowledge Graph Evidence:
Tool: {selected_tool}
Summary: {summary}
Data:
{data_json}

Instructions:
1. Deliver a crisp, highly professional, executive-ready strategic analysis answering the question directly.
2. Focus strictly on market dynamics, quantitative evidence, pricing bands, and commercial impact.
3. Keep it clear, concise, and structured. Avoid buzzwords, filler, repetitive meta-commentary, or robotic academic jargon (never use words like 'grounded finding', 'provenance ledger', etc.).
4. Use bullet points for key takeaways where appropriate.
5. Reference concrete numbers, variant prices, and volume statistics from the retrieved data.""".strip(),

        'executive_brief': """You are an Executive Automotive Product & Strategy Advisor.
Analyze the following strategic findings for an executive audience:

Inquiry: {query}
Key Findings:
{synthesis}

Provide a concise, 2-paragraph strategic recommendation focused on actionable commercial decisions, product positioning, and risk mitigation.
Maintain an authoritative, quantitative executive tone. Do not use academic jargon.""".strip(),
    }
}

constants_data = {
    'keywords': {
        'automotive_vocabulary': sorted(list(SLMQueryPlanner.COMMON_AUTOMOTIVE_KEYWORDS)),
        'keyboard_mash_patterns': SLMQueryPlanner.KEYBOARD_MASH_PATTERNS,
    },
    'cypher_safety': {
        'forbidden_keywords': sorted(list(FORBIDDEN_CYPHER_KEYWORDS)),
        'read_only_start_keywords': sorted(list(READ_ONLY_START_KEYWORDS)),
        'default_max_limit': DEFAULT_MAX_LIMIT,
    },
    'decision_defaults': {
        'default_assumed_elasticity': -0.90,
        'approval_validity_days': 30,
        'scenario_pct_brackets': [-0.05, -0.03, 0.0, 0.03],
    },
    'models': {
        'primary': 'gemini-2.5-flash',
        'fallback': 'gemini-2.5-flash',
        'final': 'gemini-2.5-flash',
    },
    'server': {
        'host': '0.0.0.0',
        'port': 8000,
        'default_rate_pace_seconds': 2.5,
        'max_poll_iterations': 120,
        'poll_interval_ms': 1500,
    },
    'data_collection_layers': [
        {'id': 'L01', 'name': 'Vehicle Master', 'needs_vehicle_id': False},
        {'id': 'L02', 'name': 'Spec & Features Master', 'needs_vehicle_id': True},
        {'id': 'L03', 'name': 'Feature Taxonomy', 'needs_vehicle_id': True},
        {'id': 'L04', 'name': 'Competitor Master', 'needs_vehicle_id': True},
        {'id': 'L05', 'name': 'Audience Segments', 'needs_vehicle_id': True},
        {'id': 'L06', 'name': 'Buying Factors', 'needs_vehicle_id': True},
        {'id': 'L07', 'name': 'Reviews', 'needs_vehicle_id': True},
        {'id': 'L08', 'name': 'Opinion Dataset', 'needs_vehicle_id': True},
        {'id': 'L09', 'name': 'Search & Intent Data', 'needs_vehicle_id': True},
        {'id': 'L10', 'name': 'Sales & Registration', 'needs_vehicle_id': True},
        {'id': 'L11', 'name': 'Pricing & Offers', 'needs_vehicle_id': True},
        {'id': 'L12', 'name': 'Ontology Summary', 'needs_vehicle_id': True},
    ]
}

with open('prompts.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(prompts_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

with open('constants.yaml', 'w', encoding='utf-8') as f:
    yaml.dump(constants_data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

print('✅ prompts.yaml and constants.yaml created successfully!')
