"""
evidence_aggregation.py
=======================
Fetches connected automotive intelligence from Neo4j:
  - Customer segments, prioritized buying factors, and importance weights
  - Vehicle specifications, powertrains, and feature suites
  - Aspect-level sentiment claims, purchase drivers, and barriers
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional
from graph_db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


class EvidenceAggregator:
    """Retrieves grounded automotive evidence and audience profiles from Neo4j."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def get_available_segments(self) -> List[Dict[str, Any]]:
        """List all customer segments that have prioritized buying factors."""
        cypher = """
        MATCH (cs:CustomerSegment)-[p:PRIORITIZES]->(bf:BuyingFactor)
        WITH cs, collect({factor: bf.name, weight: p.importance_weight}) AS factors
        RETURN cs.name AS segment_name,
               cs.segment_id AS segment_id,
               cs.description AS description,
               cs.budget_band_inr AS budget_band,
               cs.avg_daily_km AS daily_km,
               factors
        ORDER BY cs.name
        """
        return self.client.query(cypher)

    def get_segment_priorities(self, segment_query: str) -> Dict[str, Any]:
        """
        Retrieves buying factors and weights for a given customer segment dynamically.
        Uses schema-driven token overlap and fuzzy matching across all available segments in Neo4j.
        """
        try:
            # 1. Exact or partial match in graph
            cypher = """
            MATCH (cs:CustomerSegment)-[p:PRIORITIZES]->(bf:BuyingFactor)
            WHERE toLower(cs.name) CONTAINS toLower($query)
               OR toLower(cs.description) CONTAINS toLower($query)
            WITH cs, collect({factor: bf.name, weight: p.importance_weight}) AS factors
            RETURN cs.name AS segment_name,
                   cs.description AS description,
                   cs.budget_band_inr AS budget_band,
                   cs.avg_daily_km AS daily_km,
                   factors
            LIMIT 1
            """
            records = self.client.query(cypher, {"query": segment_query})
            if records:
                return records[0]

            # 2. Dynamic token overlap matching across all registered segments
            available = self.get_available_segments()
            if not available:
                return {"error": f"No customer segments found in database for query '{segment_query}'."}

            q_tokens = set(re.findall(r"\w+", segment_query.lower()))
            best_segment = None
            best_overlap = -1

            for s in available:
                s_name = s.get("segment_name", "")
                s_desc = s.get("description", "")
                combined = f"{s_name} {s_desc}".lower()
                c_tokens = set(re.findall(r"\w+", combined))
                overlap_score = len(q_tokens.intersection(c_tokens))
                if overlap_score > best_overlap:
                    best_overlap = overlap_score
                    best_segment = s

            if best_segment and best_overlap > 0:
                return best_segment

            # Fallback to first available segment if query has zero overlap
            return available[0] if available else {"error": f"No buying factors found for segment '{segment_query}'"}
        except Exception as exc:
            logger.error(f"Error querying segment priorities for '{segment_query}': {exc}", exc_info=True)
            return {"error": f"Database query failed: {str(exc)}"}

    def get_vehicle_evidence(self, model_name: str) -> Dict[str, Any]:
        """
        Retrieves full specifications, feature taxonomy, pricing boundaries,
        and sentiment claims for a single vehicle model dynamically.
        """
        try:
            cypher = """
            MATCH (v:VehicleModel)
            WHERE toLower(v.name) = toLower($model_name)
               OR v.name =~ ('(?i).*' + $model_name + '.*')
            OPTIONAL MATCH (v)<-[:PRODUCES]-(b:Brand)
            OPTIONAL MATCH (v)-[:HAS_POWERTRAIN]->(pt:Powertrain)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->(var:VehicleVariant)-[:USES_ENGINE]->(eng:Engine)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->(top_var:VehicleVariant)-[:HAS_FEATURE]->(f:Feature)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation)
            OPTIONAL MATCH (mc:MarketChange)
            WHERE mc.vehicle_model = v.name AND toLower(mc.change_type) CONTAINS 'safety'
            OPTIONAL MATCH (op:Opinion)-[:ABOUT]->(v)
            OPTIONAL MATCH (op)-[:ABOUT_ASPECT]->(asp:Aspect)
            RETURN v.name AS model,
                   v.vehicle_model_id AS vehicle_id,
                   coalesce(v.body_type, 'Sedan') AS body_type,
                   coalesce(v.segment_position, 'General') AS segment,
                   coalesce(mc.metric_after, v.ncap_rating, 'Not Rated') AS ncap_rating,
                   coalesce(v.airbags, 2) AS airbags,
                   coalesce(v.boot_space_litres, 350) AS boot_space_litres,
                   coalesce(v.ground_clearance_mm, 165) AS ground_clearance_mm,
                   coalesce(v.seating_capacity, 5) AS seating_capacity,
                   min(p.ex_showroom_inr) AS min_price,
                   max(p.ex_showroom_inr) AS max_price,
                   coalesce(b.name, v.brand_id, 'OEM') AS brand,
                   collect(DISTINCT pt.claimed_efficiency) AS mileages,
                   collect(DISTINCT pt.powertrain_type) AS powertrains,
                   collect(DISTINCT eng.displacement_cc) AS displacements,
                   collect(DISTINCT eng.max_power_hp) AS horsepower_list,
                   collect(DISTINCT f.name) AS features,
                   collect(DISTINCT {
                       claim: op.claim,
                       aspect: asp.name,
                       sentiment: op.sentiment,
                       score: op.sentiment_score,
                       barrier: op.is_purchase_barrier,
                       driver: op.is_purchase_driver,
                       intensity: op.intensity
                   }) AS opinions
            LIMIT 1
            """
            records = self.client.query(cypher, {"model_name": model_name})
            return records[0] if records else {"error": f"Vehicle '{model_name}' not found."}
        except Exception as exc:
            logger.error(f"Error querying vehicle evidence for '{model_name}': {exc}", exc_info=True)
            return {"error": f"Database query failed for '{model_name}': {str(exc)}"}

    def get_all_active_vehicles(self) -> List[Dict[str, Any]]:
        """
        Retrieves all vehicle models that have verified production data dynamically from Neo4j.
        """
        try:
            cypher = """
            MATCH (v:VehicleModel)<-[:PRODUCES]-(b:Brand)
            WHERE (v)-[:HAS_VARIANT]->()
            OPTIONAL MATCH (v)-[:HAS_POWERTRAIN]->(pt:Powertrain)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->(var:VehicleVariant)-[:USES_ENGINE]->(eng:Engine)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(f:Feature)
            OPTIONAL MATCH (v)-[:HAS_VARIANT]->(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation)
            OPTIONAL MATCH (mc:MarketChange)
            WHERE mc.vehicle_model = v.name AND toLower(mc.change_type) CONTAINS 'safety'
            OPTIONAL MATCH (op:Opinion)-[:ABOUT]->(v)
            OPTIONAL MATCH (op)-[:ABOUT_ASPECT]->(asp:Aspect)
            WITH v, b, pt, eng, f, p, mc, op, asp
            RETURN v.name AS model,
                   v.vehicle_model_id AS vehicle_id,
                   coalesce(v.body_type, 'Sedan') AS body_type,
                   coalesce(v.segment_position, 'General') AS segment,
                   coalesce(mc.metric_after, v.ncap_rating, 'Not Rated') AS ncap_rating,
                   coalesce(v.airbags, 2) AS airbags,
                   coalesce(v.boot_space_litres, 350) AS boot_space_litres,
                   coalesce(v.ground_clearance_mm, 165) AS ground_clearance_mm,
                   coalesce(v.seating_capacity, 5) AS seating_capacity,
                   min(p.ex_showroom_inr) AS min_price,
                   max(p.ex_showroom_inr) AS max_price,
                   coalesce(b.name, v.brand_id, 'OEM') AS brand,
                   collect(DISTINCT pt.claimed_efficiency) AS mileages,
                   collect(DISTINCT pt.powertrain_type) AS powertrains,
                   collect(DISTINCT eng.displacement_cc) AS displacements,
                   collect(DISTINCT eng.max_power_hp) AS horsepower_list,
                   collect(DISTINCT f.name) AS features,
                   collect(DISTINCT {
                       claim: op.claim,
                       aspect: asp.name,
                       sentiment: op.sentiment,
                       score: op.sentiment_score,
                       barrier: op.is_purchase_barrier,
                       driver: op.is_purchase_driver,
                       intensity: op.intensity
                   }) AS opinions
            ORDER BY v.name
            """
            return self.client.query(cypher)
        except Exception as exc:
            logger.error(f"Error querying active vehicles: {exc}", exc_info=True)
            return []
