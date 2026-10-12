"""
impact_tracer.py
================
Multi-Hop Graph Impact Tracer for the Automotive World Model.
Traces causal ripples across Neo4j from a detected MarketChange:
  • Traverses rival models via COMPETES_WITH & IMPACTS_COMPETITOR
  • Performs dynamic feature differential / gap analysis across variants
  • Identifies vulnerable / attracted CustomerSegments prioritizing affected BuyingFactors
  • Harvests customer & expert AspectOpinions (purchase drivers vs barriers)
  • Generates formal Cypher graph traversal path proofs
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient
from intelligence.change_detection import MarketChange

logger = logging.getLogger(__name__)


@dataclass
class ImpactedRival:
    """A competitor model impacted by the market change."""
    model_id: str
    model_name: str
    brand_name: str
    competition_score: float
    price_overlap: float
    target_wins: List[str]
    target_loses: List[str]
    target_exclusive_features: List[str]
    rival_exclusive_features: List[str]


@dataclass
class ImpactedCustomerSegment:
    """A customer segment whose buying priorities intersect with the change."""
    segment_id: str
    segment_name: str
    demographics: str
    budget_range: str
    buying_factor: str
    factor_weight: float
    impact_nature: str  # e.g., 'VALUE_RESONANCE', 'SAFETY_CONVERTED', 'VULNERABILITY'


@dataclass
class AspectOpinionItem:
    """An aspect opinion item linked to the affected vehicle and aspects."""
    model_name: str
    aspect_name: str
    sentiment: str
    claim: str
    is_driver: bool
    is_barrier: bool
    source_name: str


@dataclass
class GraphTraversalPath:
    """A human-readable multi-hop Cypher traversal path."""
    source_node: str
    relationship_chain: str
    target_node: str
    context: str


@dataclass
class TracedImpactSummary:
    """Complete multi-hop impact analysis output from Neo4j."""
    change: MarketChange
    target_model_name: str
    target_model_id: str
    impacted_rivals: List[ImpactedRival] = field(default_factory=list)
    impacted_segments: List[ImpactedCustomerSegment] = field(default_factory=list)
    activated_opinions: List[AspectOpinionItem] = field(default_factory=list)
    graph_paths: List[GraphTraversalPath] = field(default_factory=list)


class ImpactPathTracer:
    """
    Executes multi-hop traversal across the knowledge graph starting from a MarketChange.
    """

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def trace_impact(self, change: MarketChange) -> TracedImpactSummary:
        """
        Traces all multi-hop relationships impacted by the given MarketChange.
        """
        logger.info(f"🔍 Tracing multi-hop impact for change [{change.change_id}] ({change.vehicle_model})...")

        # 1. Trace rivals & feature differentials
        rivals = self._trace_rivals_with_feature_gaps(change.vehicle_model)

        # 2. Trace customer segments prioritizing affected factors
        segments = self._trace_impacted_customer_segments(change.vehicle_model, change.affected_aspects)

        # 3. Trace aspect opinions (drivers vs barriers)
        opinions = self._trace_aspect_opinions(change.vehicle_model, change.affected_aspects)

        # 4. Generate structured graph traversal paths
        paths = self._construct_traversal_paths(change, rivals, segments)

        summary = TracedImpactSummary(
            change=change,
            target_model_name=change.vehicle_model,
            target_model_id=change.vehicle_model_id,
            impacted_rivals=rivals,
            impacted_segments=segments,
            activated_opinions=opinions,
            graph_paths=paths,
        )
        logger.info(
            f"✅ Impact traced: {len(rivals)} rivals, {len(segments)} segments, "
            f"{len(opinions)} opinions, {len(paths)} graph paths."
        )
        return summary

    def _trace_rivals_with_feature_gaps(self, target_model: str) -> List[ImpactedRival]:
        """
        Finds direct competitors and calculates feature differentials in Neo4j.
        Handles bi-directional COMPETES_WITH relationships.
        """
        comp_cypher = """
        MATCH (v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (v)-[comp:COMPETES_WITH]-(rival:VehicleModel)
        OPTIONAL MATCH (b:Brand)-[:PRODUCES]->(rival)
        RETURN DISTINCT rival.vehicle_model_id AS rival_id,
                        rival.name AS rival_name,
                        coalesce(b.name, rival.brand_id) AS brand,
                        comp.competition_score AS score,
                        comp.price_overlap AS price_overlap,
                        comp.where_it_wins AS target_wins,
                        comp.where_it_loses AS target_loses
        ORDER BY score DESC
        """
        rows = self.client.query(comp_cypher, {"model": target_model})
        rivals: List[ImpactedRival] = []

        seen_rival_ids = set()
        for r in rows:
            rival_id = r.get("rival_id")
            if not rival_id or rival_id in seen_rival_ids:
                continue
            seen_rival_ids.add(rival_id)

            rival_name = r.get("rival_name", "")
            brand_name = r.get("brand", "Unknown")
            score = float(r.get("score") or 0.8)
            price_overlap = float(r.get("price_overlap") or 0.7)

            wins_raw = r.get("target_wins")
            target_wins = [w.strip() for w in wins_raw.split(",")] if isinstance(wins_raw, str) else []
            loses_raw = r.get("target_loses")
            target_loses = [l.strip() for l in loses_raw.split(",")] if isinstance(loses_raw, str) else []

            # Feature differential query
            gaps = self._compute_feature_gaps(target_model, rival_name)

            rivals.append(
                ImpactedRival(
                    model_id=rival_id,
                    model_name=rival_name,
                    brand_name=brand_name,
                    competition_score=score,
                    price_overlap=price_overlap,
                    target_wins=target_wins,
                    target_loses=target_loses,
                    target_exclusive_features=gaps.get("target_exclusive", []),
                    rival_exclusive_features=gaps.get("rival_exclusive", []),
                )
            )

        return rivals

    def _compute_feature_gaps(self, target_model: str, rival_model: str) -> Dict[str, List[str]]:
        """
        Computes distinct feature sets for target vs rival variants in Neo4j,
        filtering out common baseline automotive features and prioritizing key differentiators.
        """
        import re

        BASELINE_PATTERNS = [
            r"\bmanual\b", r"5-speed", r"6-speed", r"\bmt\b", r"power steering",
            r"power windows?", r"fabric seats?", r"tilt steering", r"seat belt",
            r"speed alert", r"child lock", r"immobilis?er", r"parking sensors?",
            r"mud guard", r"protector", r"garnish", r"visor", r"cover", r"halogen",
            r"heater", r"orvms?", r"central lock", r"front power", r"all power",
            r"steel wheels?", r"spare wheel"
        ]

        PRIORITY_PATTERNS = [
            r"\bcvt\b", r"\bdsg\b", r"\bdct\b", r"\bamt\b", r"\bags\b", r"sunroof",
            r"360", r"blind spot", r"adas", r"wireless charg", r"rear ac", r"ventilated",
            r"cruise control", r"paddle shift", r"6 airbags", r"\bcng\b", r"hybrid",
            r"turbo", r"android auto", r"apple carplay", r"touchscreen", r"\besc\b",
            r"\besp\b", r"led projector", r"rear armrest"
        ]

        def _is_baseline(name: str) -> bool:
            n = name.lower()
            return any(re.search(p, n) for p in BASELINE_PATTERNS)

        def _score_feature(name: str) -> int:
            n = name.lower()
            if any(re.search(p, n) for p in PRIORITY_PATTERNS):
                return 10
            return 1

        gap_cypher = """
        MATCH (v1:VehicleModel) WHERE toLower(v1.name) = toLower($target)
        MATCH (v2:VehicleModel) WHERE toLower(v2.name) = toLower($rival)
        OPTIONAL MATCH (v1)-[cw:COMPETES_WITH]->(v2)
        WITH v1, v2, cw,
             [(v1)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(f1:Feature) | f1.name] AS t_raw,
             [(v2)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(f2:Feature) | f2.name] AS r_raw
        RETURN apoc.coll.toSet(t_raw) AS target_features,
               apoc.coll.toSet(r_raw) AS rival_features,
               cw.key_differentiators AS key_diffs,
               cw.where_it_wins AS where_wins,
               cw.where_it_loses AS where_loses
        """
        try:
            res = self.client.query(gap_cypher, {"target": target_model, "rival": rival_model})
        except Exception:
            # Fallback without APOC
            fallback_cypher = """
            MATCH (v1:VehicleModel) WHERE toLower(v1.name) = toLower($target)
            MATCH (v2:VehicleModel) WHERE toLower(v2.name) = toLower($rival)
            OPTIONAL MATCH (v1)-[cw:COMPETES_WITH]->(v2)
            WITH v1, v2, cw,
                 [(v1)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(f1:Feature) | f1.name] AS t_raw,
                 [(v2)-[:HAS_VARIANT]->()-[:HAS_FEATURE]->(f2:Feature) | f2.name] AS r_raw
            RETURN t_raw AS target_features,
                   r_raw AS rival_features,
                   cw.key_differentiators AS key_diffs,
                   cw.where_it_wins AS where_wins,
                   cw.where_it_loses AS where_loses
            """
            res = self.client.query(fallback_cypher, {"target": target_model, "rival": rival_model})

        if res and len(res) > 0:
            row = res[0]
            t_set = set(row.get("target_features") or [])
            r_set = set(row.get("rival_features") or [])

            # Compute set differences
            t_excl = [f for f in (t_set - r_set) if not _is_baseline(f)]
            r_excl = [f for f in (r_set - t_set) if not _is_baseline(f)]

            # Sort by priority score (high-value differentiators first)
            t_excl.sort(key=_score_feature, reverse=True)
            r_excl.sort(key=_score_feature, reverse=True)

            # If rival had 0 variant features (e.g. Tigor unseeded), populate from graph relationship metadata
            if not r_set or not r_excl:
                where_wins = row.get("where_wins") or ""
                where_loses = row.get("where_loses") or ""
                key_diffs = row.get("key_diffs") or ""
                if where_loses:
                    r_excl = [x.strip() for x in where_loses.split(",") if x.strip()]
                elif key_diffs:
                    r_excl = [x.strip() for x in key_diffs.split(",") if x.strip()][:3]
                if not t_excl and where_wins:
                    t_excl = [x.strip() for x in where_wins.split(",") if x.strip()]

            return {
                "target_exclusive": t_excl[:6] if t_excl else ["Specification Parity"],
                "rival_exclusive": r_excl[:6] if r_excl else ["Specification Parity"],
            }

        return {"target_exclusive": ["Specification Parity"], "rival_exclusive": ["Specification Parity"]}

    def _trace_impacted_customer_segments(
        self, target_model: str, affected_aspects: List[str]
    ) -> List[ImpactedCustomerSegment]:
        """
        Finds customer segments considering the vehicle whose prioritized buying factors
        intersect with the aspects affected by the market change.
        """
        aspect_keywords = [a.lower() for a in affected_aspects] if affected_aspects else ["safety", "price", "mileage"]

        seg_cypher = """
        MATCH (s:CustomerSegment)-[:CONSIDERS]->(v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (s)-[p:PRIORITIZES]->(bf:BuyingFactor)
        RETURN DISTINCT s.segment_id AS seg_id,
                        s.name AS seg_name,
                        s.description AS description,
                        s.budget_band_inr AS budget_band,
                        s.primary_use AS primary_use,
                        s.income_band_inr_annual AS income_band,
                        bf.name AS factor_name,
                        p.importance_weight AS weight
        ORDER BY weight DESC
        """
        rows = self.client.query(seg_cypher, {"model": target_model})
        segments: List[ImpactedCustomerSegment] = []

        seen_keys = set()
        for r in rows:
            factor_name = r.get("factor_name", "")
            f_lower = factor_name.lower()

            # Check if factor matches affected aspects or high priority
            is_affected = any(kw in f_lower or f_lower in kw for kw in aspect_keywords)
            weight = float(r.get("weight") or 0.5)

            if is_affected or weight >= 0.75:
                seg_name = r.get("seg_name", "Target Segment")
                key = (seg_name, factor_name)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                budget_str = r.get("budget_band", "") or "₹6.0–10.0L"
                demographics = f"{r.get('primary_use', 'commute')}, income {r.get('income_band', 'standard')}"

                impact_nature = "HIGH_PRIORITY_RESONANCE" if is_affected else "CORE_BUYING_FACTOR"
                if "safety" in f_lower:
                    impact_nature = "CRITICAL_SAFETY_FILTER"
                elif "price" in f_lower or "afford" in f_lower:
                    impact_nature = "PRICE_SENSITIVITY_FILTER"
                elif "mileage" in f_lower or "fuel" in f_lower:
                    impact_nature = "RUNNING_COST_FILTER"

                segments.append(
                    ImpactedCustomerSegment(
                        segment_id=r.get("seg_id", ""),
                        segment_name=seg_name,
                        demographics=demographics,
                        budget_range=budget_str,
                        buying_factor=factor_name,
                        factor_weight=weight,
                        impact_nature=impact_nature,
                    )
                )

        return segments

    def _trace_aspect_opinions(
        self, target_model: str, affected_aspects: List[str]
    ) -> List[AspectOpinionItem]:
        """
        Harvests opinions and reviews related to the vehicle and the affected aspects.
        """
        op_cypher = """
        MATCH (rev:Review)-[:ABOUT]->(v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (rev)-[:CONTAINS]->(o:Opinion)-[:ABOUT_ASPECT]->(a:Aspect)
        RETURN v.name AS model_name,
               a.name AS aspect_name,
               o.sentiment AS sentiment,
               o.claim AS claim,
               o.is_purchase_driver AS is_driver,
               o.is_purchase_barrier AS is_barrier,
               rev.source_name AS source_name
        LIMIT 20
        """
        rows = self.client.query(op_cypher, {"model": target_model})
        opinions: List[AspectOpinionItem] = []

        for r in rows:
            claim = r.get("claim") or ""
            if not claim:
                continue
            opinions.append(
                AspectOpinionItem(
                    model_name=r.get("model_name", target_model),
                    aspect_name=r.get("aspect_name", "General"),
                    sentiment=r.get("sentiment", "NEUTRAL"),
                    claim=claim,
                    is_driver=bool(r.get("is_driver")),
                    is_barrier=bool(r.get("is_barrier")),
                    source_name=r.get("source_name", "Verified Review"),
                )
            )
        return opinions

    def _construct_traversal_paths(
        self,
        change: MarketChange,
        rivals: List[ImpactedRival],
        segments: List[ImpactedCustomerSegment],
    ) -> List[GraphTraversalPath]:
        """
        Constructs explicit graph traversal path representations for business and audit transparency.
        """
        paths: List[GraphTraversalPath] = []

        # Path 1: Market Change to Target Model
        paths.append(
            GraphTraversalPath(
                source_node=f"MarketChange({change.change_id})",
                relationship_chain="<-[:UNDERWENT_CHANGE]-",
                target_node=f"VehicleModel({change.vehicle_model})",
                context=f"Root event: {change.title} on {change.date}",
            )
        )

        # Path 2: Rivals impacted
        for riv in rivals[:3]:
            paths.append(
                GraphTraversalPath(
                    source_node=f"VehicleModel({change.vehicle_model})",
                    relationship_chain=f"-[:COMPETES_WITH {{score: {riv.competition_score:.2f}, overlap: {riv.price_overlap:.2f}}}]->",
                    target_node=f"VehicleModel({riv.model_name})",
                    context=(
                        f"Competitive ripple: {change.vehicle_model} pressures {riv.model_name}. "
                        f"Key advantage: {', '.join(riv.target_wins[:2]) if riv.target_wins else 'Segment Parity'}"
                    ),
                )
            )

        # Path 3: Customer Segments
        for seg in segments[:3]:
            paths.append(
                GraphTraversalPath(
                    source_node=f"CustomerSegment({seg.segment_name})",
                    relationship_chain=f"-[:PRIORITIZES {{weight: {seg.factor_weight:.2f}}}]->",
                    target_node=f"BuyingFactor({seg.buying_factor})",
                    context=f"Audience sensitivity: {seg.segment_name} filters purchases by {seg.buying_factor} ({seg.impact_nature})",
                )
            )

        return paths
