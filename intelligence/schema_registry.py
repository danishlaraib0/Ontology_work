"""
schema_registry.py
==================
Schema Metadata Registry for the Neo4j Automotive World Model.
Provides schema definitions, label/relationship introspection,
and schema prompt generation for safe dynamic Cypher planning.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from graph_db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


# Standard Node Labels in Automotive World Model
KNOWN_NODE_LABELS: Set[str] = {
    "Brand",
    "VehicleModel",
    "Generation",
    "VehicleVariant",
    "VehicleSegment",
    "Platform",
    "Powertrain",
    "Engine",
    "FeatureCategory",
    "Feature",
    "CustomerSegment",
    "Need",
    "BuyingFactor",
    "Review",
    "Opinion",
    "Aspect",
    "SearchQuery",
    "Intent",
    "Geography",
    "SalesObservation",
    "PriceObservation",
    "Source",
    "Evidence",
    "MarketChange",
    "ForecastRun",
    "SalesPrediction",
}

# Standard Relationship Types in Automotive World Model
KNOWN_RELATIONSHIP_TYPES: Set[str] = {
    "PRODUCES",
    "BELONGS_TO",
    "HAS_GENERATION",
    "HAS_VARIANT",
    "HAS_POWERTRAIN",
    "USES_ENGINE",
    "USES_POWERTRAIN",
    "CONTAINS_FEATURE",
    "COMPETES_WITH",
    "CONSIDERS",
    "HAS_BUYING_FACTOR",
    "PRIORITIZES",
    "ABOUT_ASPECT",
    "ABOUT",
    "TARGETS",
    "HAS_INTENT",
    "HAS_SALES_OBSERVATION",
    "IN_GEOGRAPHY",
    "USES_PLATFORM",
    "HAS_FEATURE",
    "SOURCED_FROM",
    "WRITTEN_BY",
    "CONTAINS",
    "HAS_PRICE_OBSERVATION",
    "OFFERS_ENGINE",
    "OFFERS_POWERTRAIN",
    "UNDERWENT_CHANGE",
    "IMPACTS_COMPETITOR",
    "HAS_FORECAST_RUN",
    "PREDICTS",
    "BASED_ON_OBSERVATION",
}

# High-frequency node properties
NODE_PROPERTIES: Dict[str, List[str]] = {
    "VehicleModel": ["vehicle_model_id", "name", "body_type", "segment_position", "launch_year", "status"],
    "Brand": ["brand_id", "name", "country_of_origin"],
    "VehicleVariant": ["variant_id", "name", "transmission", "fuel_type", "ex_showroom_inr"],
    "Engine": ["engine_id", "code", "displacement_cc", "max_power_hp", "max_torque_nm", "cylinders"],
    "Powertrain": ["powertrain_id", "powertrain_type", "claimed_efficiency", "transmission"],
    "Feature": ["feature_id", "name", "category_id"],
    "CustomerSegment": ["segment_id", "name", "demographics", "budget_range", "usage_pattern"],
    "BuyingFactor": ["factor_id", "name", "category", "importance_weight"],
    "Need": ["need_id", "name", "priority"],
    "SalesObservation": ["sales_obs_id", "period_value", "units_sold", "yoy_change_percent", "source_name"],
    "PriceObservation": ["price_obs_id", "effective_date", "variant_name", "ex_showroom_inr"],
    "MarketChange": ["change_id", "change_type", "title", "date", "vehicle_model", "metric_before", "metric_after", "magnitude_score"],
    "SearchQuery": ["query_id", "query_text", "search_volume_index", "intent_stage", "temporal_period"],
    "Review": ["review_id", "overall_rating", "editorial_verdict", "publication_date"],
    "Opinion": ["opinion_id", "sentiment", "claim_text", "is_purchase_driver", "is_purchase_barrier"],
    "Aspect": ["aspect_id", "name"],
    "Source": ["source_id", "name", "credibility_tier", "source_type"],
}


class GraphSchemaRegistry:
    """Provides schema validation and formatted prompts for planners."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client
        self._cached_vehicles: Optional[List[str]] = None
        self._cached_segments: Optional[List[str]] = None
        self._cached_brands: Optional[List[str]] = None

    def get_known_labels(self) -> Set[str]:
        return KNOWN_NODE_LABELS

    def get_known_relationships(self) -> Set[str]:
        return KNOWN_RELATIONSHIP_TYPES

    def is_valid_label(self, label: str) -> bool:
        return label in KNOWN_NODE_LABELS

    def is_valid_relationship(self, rel: str) -> bool:
        return rel in KNOWN_RELATIONSHIP_TYPES

    def get_known_brands(self) -> List[str]:
        """Returns list of automotive brand names in the graph."""
        if self._cached_brands is not None:
            return self._cached_brands
        if self.client and self.client.is_healthy():
            try:
                res = self.client.query("MATCH (b:Brand) RETURN b.name AS name ORDER BY name")
                self._cached_brands = [r["name"] for r in res if r.get("name")]
                return self._cached_brands
            except Exception as e:
                logger.debug(f"Error querying brands: {e}")
        self._cached_brands = [
            "Maruti Suzuki", "Hyundai", "Honda", "Tata", "Toyota",
            "Kia", "Renault", "Mahindra", "Nissan", "Skoda", "Volkswagen", "MG"
        ]
        return self._cached_brands

    def get_known_vehicles(self) -> List[str]:
        """Returns list of canonical vehicle model names in the graph."""
        if self._cached_vehicles is not None:
            return self._cached_vehicles
        if self.client and self.client.is_healthy():
            try:
                res = self.client.query("MATCH (v:VehicleModel) RETURN v.name AS name ORDER BY name")
                self._cached_vehicles = [r["name"] for r in res if r.get("name")]
                return self._cached_vehicles
            except Exception as e:
                logger.debug(f"Error querying vehicle models: {e}")
        # Default fallback list
        self._cached_vehicles = [
            "Dzire", "Amaze", "Aura", "Tigor", "Wagon R", "Baleno", "Tiago",
            "Grand i10 Nios", "Celerio", "Punch", "Fronx", "Brezza", "Venue",
            "Sonet", "Nexon", "Ertiga", "Carens", "Triber", "Rumion", "Innova Hycross"
        ]
        return self._cached_vehicles

    def get_known_segments(self) -> List[str]:
        """Returns customer segments defined in the graph."""
        if self._cached_segments is not None:
            return self._cached_segments
        if self.client and self.client.is_healthy():
            try:
                res = self.client.query("MATCH (s:CustomerSegment) RETURN s.name AS name ORDER BY name")
                self._cached_segments = [r["name"] for r in res if r.get("name")]
                return self._cached_segments
            except Exception as e:
                logger.debug(f"Error querying customer segments: {e}")
        self._cached_segments = [
            "Small Urban Families",
            "Budget First-Time Buyers",
            "High-Mileage Gig Workers",
        ]
        return self._cached_segments

    def get_schema_prompt_summary(self) -> str:
        """Compact schema summary to inject into LLM/SLM prompt context."""
        lines = [
            "### Neo4j Knowledge Graph Schema",
            "**Node Labels**:",
            "- VehicleModel (name, body_type, segment_position)",
            "- Brand (name)",
            "- VehicleVariant (name, transmission, fuel_type, ex_showroom_inr)",
            "- Engine (code, displacement_cc, max_power_hp, max_torque_nm)",
            "- Powertrain (powertrain_type, claimed_efficiency)",
            "- Feature (name)",
            "- CustomerSegment (name, demographics, budget_range)",
            "- BuyingFactor (name, category, importance_weight)",
            "- SalesObservation (period, units, market_share_pct)",
            "- PriceObservation (effective_date, variant_name, ex_showroom_inr)",
            "- SearchQuery (query_text, search_volume_index, intent_stage, temporal_period)",
            "- Review (overall_rating, editorial_verdict)",
            "- Opinion (sentiment, claim_text, is_purchase_driver, is_purchase_barrier)",
            "- Aspect (name)",
            "- MarketChange (change_id, change_type, title, date, vehicle_model, metric_before, metric_after)",
            "",
            "**Key Relationships**:",
            "- (Brand)-[:PRODUCES]->(VehicleModel)",
            "- (VehicleModel)-[:COMPETES_WITH {competition_score, price_overlap}]->(VehicleModel)",
            "- (VehicleModel)-[:HAS_VARIANT]->(VehicleVariant)",
            "- (VehicleModel)-[:OFFERS_ENGINE]->(Engine)",
            "- (VehicleModel)-[:OFFERS_POWERTRAIN]->(Powertrain)",
            "- (VehicleVariant)-[:HAS_FEATURE]->(Feature)",
            "- (CustomerSegment)-[:PRIORITIZES {weight}]->(BuyingFactor)",
            "- (CustomerSegment)-[:CONSIDERS]->(VehicleModel)",
            "- (VehicleModel)-[:HAS_SALES_OBSERVATION]->(SalesObservation)",
            "- (VehicleModel)-[:HAS_PRICE_OBSERVATION]->(PriceObservation)",
            "- (VehicleModel)-[:UNDERWENT_CHANGE]->(MarketChange)",
            "- (MarketChange)-[:IMPACTS_COMPETITOR]->(VehicleModel)",
        ]
        return "\n".join(lines)
