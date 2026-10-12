"""
query_engine.py
===============
High-level graph traversals and business intelligence queries against the
Automotive World Ontology stored in Neo4j.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
from .neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class AutomotiveGraphQueryEngine:
    """Traverses the Automotive Ontology in Neo4j to answer complex strategic questions."""

    def __init__(self, client: Neo4jClient | None = None):
        self.client = client or Neo4jClient()

    def why_popular_with_audience(self, model_name: str, audience_keyword: str) -> Dict[str, Any]:
        """
        Traverses the core magic relationship:
        CustomerSegment -> PRIORITIZES -> BuyingFactor -> Need
        CustomerSegment -> CONSIDERS -> VehicleModel -> HAS_VARIANT -> HAS_FEATURE
        VehicleModel -> HAS_REVIEW -> CONTAINS -> Opinion -> ABOUT_ASPECT
        """
        cypher = """
        MATCH (v:VehicleModel)
        WHERE v.name =~ ('(?i).*' + $model_name + '.*')
        
        OPTIONAL MATCH (s:CustomerSegment)-[:CONSIDERS]->(v)
        WHERE s.name =~ ('(?i).*' + $audience_keyword + '.*') OR s.description =~ ('(?i).*' + $audience_keyword + '.*')
        
        OPTIONAL MATCH (s)-[p:PRIORITIZES]->(bf:BuyingFactor)
        
        OPTIONAL MATCH (v)-[:HAS_VARIANT]->(var:VehicleVariant)-[:HAS_FEATURE]->(f:Feature)
        
        OPTIONAL MATCH (op:Opinion)-[:ABOUT]->(v)
        WHERE op.sentiment = 'POSITIVE'
        OPTIONAL MATCH (op)-[:ABOUT_ASPECT]->(asp:Aspect)
        
        RETURN 
            v.name AS vehicle,
            s.name AS customer_segment,
            s.description AS segment_description,
            collect(DISTINCT {factor: bf.name, importance: p.importance_weight}) AS prioritized_factors,
            collect(DISTINCT f.name)[..8] AS key_features,
            collect(DISTINCT {aspect: asp.name, claim: op.claim, score: op.sentiment_score})[..6] AS positive_opinions
        LIMIT 1
        """
        records = self.client.query(cypher, {"model_name": model_name, "audience_keyword": audience_keyword})
        return records[0] if records else {"error": "No matching segment/vehicle found."}

    def competitor_comparison(self, model_a: str, model_b: str) -> Dict[str, Any]:
        """
        Compares two vehicles via COMPETES_WITH relationship, variant price differences,
        and sentiment drivers.
        """
        cypher = """
        MATCH (v1:VehicleModel)-[comp:COMPETES_WITH]-(v2:VehicleModel)
        WHERE v1.name =~ ('(?i).*' + $model_a + '.*') AND v2.name =~ ('(?i).*' + $model_b + '.*')
        
        OPTIONAL MATCH (v1)-[:HAS_VARIANT]->(var1:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p1:PriceObservation)
        OPTIONAL MATCH (v2)-[:HAS_VARIANT]->(var2:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p2:PriceObservation)
        
        RETURN
            v1.name AS model_a,
            v2.name AS model_b,
            comp.competition_score AS competition_intensity,
            comp.competition_tier AS tier,
            comp.price_overlap AS price_overlap,
            comp.customer_overlap AS customer_overlap,
            comp.key_battleground AS battleground,
            avg(p1.ex_showroom_inr) AS avg_price_a,
            avg(p2.ex_showroom_inr) AS avg_price_b
        LIMIT 1
        """
        records = self.client.query(cypher, {"model_a": model_a, "model_b": model_b})
        return records[0] if records else {"error": "Competitor relationship not found."}

    def get_vehicle_summary_graph(self, model_name: str) -> Dict[str, Any]:
        """Fetch a complete 360-degree graph profile for a vehicle."""
        cypher = """
        MATCH (b:Brand)-[:PRODUCES]->(v:VehicleModel)
        WHERE v.name =~ ('(?i).*' + $model_name + '.*')
        OPTIONAL MATCH (v)-[:BELONGS_TO]->(seg:VehicleSegment)
        OPTIONAL MATCH (v)-[:HAS_GENERATION]->(gen:Generation)
        OPTIONAL MATCH (v)-[:HAS_VARIANT]->(var:VehicleVariant)
        OPTIONAL MATCH (v)-[:HAS_POWERTRAIN]->(pt:Powertrain)
        OPTIONAL MATCH (v)-[c:COMPETES_WITH]->(comp:VehicleModel)
        OPTIONAL MATCH (s:CustomerSegment)-[:CONSIDERS]->(v)
        OPTIONAL MATCH (v)-[:HAS_SALES_OBSERVATION]->(sales:SalesObservation)
        
        RETURN
            b.name AS brand,
            v.name AS model,
            v.body_type AS body_type,
            seg.name AS segment,
            gen.name AS generation,
            collect(DISTINCT var.name) AS variants,
            collect(DISTINCT {powertrain: pt.powertrain_type, mileage: pt.claimed_efficiency}) AS powertrains,
            collect(DISTINCT {competitor: comp.name, score: c.competition_score}) AS competitors,
            collect(DISTINCT s.name) AS target_audiences,
            sales.units_sold AS annual_sales
        LIMIT 1
        """
        records = self.client.query(cypher, {"model_name": model_name})
        return records[0] if records else {"error": f"Vehicle '{model_name}' not found."}

    def find_product_gaps(self, model_name: str) -> Dict[str, Any]:
        """
        Identifies multi-dimensional gaps for a vehicle:
          1. Purchase Barrier Gaps (Negative Opinions acting as conversion blockers)
          2. Customer Unmet Need Gaps (High importance buying factors with friction)
          3. Competitor Feature Gaps (Features rivals possess that we lack)
          4. Search Intent Demand Gaps (Unserved consumer search demand)
        """
        cypher = """
        MATCH (v:VehicleModel)
        WHERE v.name =~ ('(?i).*' + $model_name + '.*')
        
        // 1. Purchase Barrier Gaps
        OPTIONAL MATCH (op_barrier:Opinion)-[:ABOUT]->(v)
        WHERE op_barrier.is_purchase_barrier = true OR op_barrier.sentiment = 'NEGATIVE'
        OPTIONAL MATCH (op_barrier)-[:ABOUT_ASPECT]->(asp_b:Aspect)
        
        // 2. High-Priority Buying Factors
        OPTIONAL MATCH (v)-[:HAS_BUYING_FACTOR]->(bf:BuyingFactor)
        
        // 3. Competitor Feature Discrepancies
        OPTIONAL MATCH (v)-[comp:COMPETES_WITH]->(rival:VehicleModel)
        OPTIONAL MATCH (rival)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(rival_f:Feature)
        WHERE NOT (v)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(rival_f)
        
        // 4. High-Volume Search Queries (Potential unaddressed intents)
        OPTIONAL MATCH (q:SearchQuery)-[:TARGETS]->(v)
        WHERE q.intent_type IN ['COMPARISON', 'FEATURE_CHECK', 'REVIEW']
        
        RETURN
            v.name AS target_vehicle,
            collect(DISTINCT {
                aspect: asp_b.name,
                barrier_claim: op_barrier.claim,
                intensity: op_barrier.intensity,
                sentiment_score: op_barrier.sentiment_score
            })[..6] AS purchase_barriers,
            collect(DISTINCT bf.name)[..6] AS key_decision_factors,
            collect(DISTINCT {
                competitor: rival.name,
                competitor_feature: rival_f.name
            })[..6] AS competitor_feature_advantages,
            collect(DISTINCT {
                query: q.query_text,
                intent: q.intent_type,
                stage: q.purchase_stage
            })[..5] AS consumer_search_signals
        LIMIT 1
        """
        records = self.client.query(cypher, {"model_name": model_name})
        return records[0] if records else {"error": f"No data found for '{model_name}'"}

