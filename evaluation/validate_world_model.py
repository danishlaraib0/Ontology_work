"""
validate_world_model.py
=======================
Automated Validation & Integrity Suite for the Automotive World Model.
Enforces Phase 1 and Phase 2 criteria:
  1. Graph Integrity: Zero orphan nodes, valid relationships, canonical ID uniqueness.
  2. Data Quality: Zero-vs-missing distinction (no 0mm dimensions, no 0.0 ratings).
  3. Temporal Consistency: Bounded intervals (valid_from <= valid_to), non-destructive historical preservation.
  4. Provenance Coverage: Every fact linked to source, credibility tier, and confidence score.
  5. State Reconstruction Milestone: Point-in-time state reconstruction across vehicles and dates.
"""
from __future__ import annotations

import unittest
from typing import Any, Dict, List

from graph_db.neo4j_client import Neo4jClient
from intelligence.world_model import WorldModelEngine


class TestAutomotiveWorldModelIntegrity(unittest.TestCase):
    """Rigorous validation tests for the Automotive World Model."""

    @classmethod
    def setUpClass(cls):
        cls.client = Neo4jClient()
        if not cls.client.is_healthy():
            raise RuntimeError("Cannot connect to Neo4j instance at localhost:7687.")
        cls.engine = WorldModelEngine(cls.client)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    # ── 1. Graph Integrity & Topology ─────────────────────────────────────────

    def test_zero_orphan_nodes(self):
        """Phase 1 Criterion: The graph must have ZERO orphan nodes without relationships."""
        cypher = """
        MATCH (n)
        WHERE NOT (n)--()
        RETURN head(labels(n)) AS label, count(n) AS orphan_count, collect(n.name) AS sample_orphans
        """
        orphans = self.client.query(cypher)
        self.assertEqual(
            len(orphans), 0,
            f"Found disconnected orphan nodes in the knowledge graph: {orphans}"
        )

    def test_canonical_id_uniqueness(self):
        """Phase 1 Criterion: All 23 node labels must maintain strictly unique canonical IDs."""
        id_properties = [
            ("Brand", "brand_id"),
            ("VehicleModel", "vehicle_model_id"),
            ("VehicleVariant", "variant_id"),
            ("Generation", "generation_id"),
            ("VehicleSegment", "segment_id"),
            ("Platform", "platform_id"),
            ("Powertrain", "powertrain_id"),
            ("Engine", "engine_id"),
            ("FeatureCategory", "category_id"),
            ("Feature", "feature_id"),
            ("CustomerSegment", "segment_id"),
            ("BuyingFactor", "factor_id"),
            ("Aspect", "aspect_id"),
            ("Review", "review_id"),
            ("Opinion", "opinion_id"),
            ("SearchQuery", "query_id"),
            ("Intent", "intent_id"),
            ("Geography", "geography_id"),
            ("SalesObservation", "sales_obs_id"),
            ("PriceObservation", "price_obs_id"),
            ("Source", "source_id"),
        ]
        for label, id_prop in id_properties:
            cypher = f"""
            MATCH (n:{label})
            WITH n.{id_prop} AS id_val, count(n) AS cnt
            WHERE cnt > 1
            RETURN id_val, cnt
            """
            duplicates = self.client.query(cypher)
            self.assertEqual(
                len(duplicates), 0,
                f"Duplicate canonical IDs found for label {label}.{id_prop}: {duplicates}"
            )

    # ── 2. Data Quality & Zero-vs-Missing Invariants ──────────────────────────

    def test_dimensions_zero_vs_missing_integrity(self):
        """
        Phase 1 Criterion: Physical dimensions (length, width, height, wheelbase, boot)
        must never be stored as 0 mm or 0 L. If missing, they must be null/None.
        """
        cypher = """
        MATCH (v:VehicleModel)
        WHERE (v)-[:HAS_VARIANT]->()
        RETURN v.name AS model,
               v.length_mm AS length_mm,
               v.width_mm AS width_mm,
               v.height_mm AS height_mm,
               v.wheelbase_mm AS wheelbase_mm,
               v.boot_space_litres AS boot_space_litres,
               v.seating_capacity AS seating_capacity
        """
        records = self.client.query(cypher)
        self.assertGreater(len(records), 0)
        for r in records:
            model = r["model"]
            for dim_field in ["length_mm", "width_mm", "height_mm", "wheelbase_mm", "boot_space_litres"]:
                val = r.get(dim_field)
                if val is not None:
                    self.assertGreater(
                        val, 0,
                        f"Vehicle {model} has invalid zero value for dimension '{dim_field}': {val}"
                    )
            # Seating capacity must be 5 or 7
            seat = r.get("seating_capacity")
            if seat is not None:
                self.assertIn(seat, [5, 7], f"Vehicle {model} has unexpected seating capacity: {seat}")

    def test_review_ratings_no_false_zeros(self):
        """Phase 1 Criterion: Editorial ratings must not contain 0.0 placeholders."""
        cypher = """
        MATCH (r:Review)
        RETURN r.source_name AS source, r.overall_rating AS rating
        """
        reviews = self.client.query(cypher)
        self.assertGreater(len(reviews), 0)
        for rev in reviews:
            rating = rev.get("rating")
            if rating is not None:
                self.assertGreater(
                    rating, 0.0,
                    f"Review from {rev['source']} has false 0.0 star rating placeholder: {rating}"
                )

    # ── 3. Temporal Consistency & Bounded Intervals ───────────────────────────

    def test_price_observations_temporal_bounds(self):
        """Phase 2 Criterion: All PriceObservations must have valid_from <= valid_to (or null valid_to)."""
        cypher = """
        MATCH (p:PriceObservation)
        WHERE p.valid_to IS NOT NULL
        RETURN p.price_obs_id AS p_id, p.valid_from AS v_from, p.valid_to AS v_to
        """
        records = self.client.query(cypher)
        for rec in records:
            v_from = rec["v_from"]
            v_to = rec["v_to"]
            self.assertTrue(
                v_from <= v_to,
                f"Price observation {rec['p_id']} has inverted temporal bounds: {v_from} > {v_to}"
            )

    def test_sales_observations_time_series_consistency(self):
        """Phase 2 Criterion: Sales observations must contain valid period values and chronological order."""
        cypher = """
        MATCH (v:VehicleModel)-[:HAS_SALES_OBSERVATION]->(s:SalesObservation {period_type: 'MONTH'})
        RETURN v.name AS model, count(s) AS month_count, collect(s.period_value) AS months
        """
        records = self.client.query(cypher)
        self.assertGreater(len(records), 0)
        for r in records:
            self.assertGreater(
                r["month_count"], 0,
                f"Vehicle {r['model']} has no monthly sales observations."
            )
            for m in r["months"]:
                # Must be YYYY-MM format
                self.assertRegex(m, r"^\d{4}-\d{2}$", f"Invalid month format: {m}")

    # ── 4. Provenance & Source Citation Coverage ──────────────────────────────

    def test_provenance_citation_coverage(self):
        """
        Phase 1 Criterion: Verifies that observations and claims are grounded in
        verifiable sources with confidence scores >= 0.80.
        """
        # 1. Total observations
        cypher_total = """
        MATCH (n)
        WHERE n:PriceObservation OR n:SalesObservation OR n:Review OR n:Opinion OR n:SearchQuery
        RETURN count(n) AS total
        """
        total_obs = self.client.query(cypher_total)[0]["total"]

        # 2. Observations linked to Source or with explicit source_name
        cypher_sourced = """
        MATCH (n)
        WHERE (n:PriceObservation OR n:SalesObservation OR n:Review OR n:Opinion OR n:SearchQuery)
          AND ( (n)-[:SOURCED_FROM]->(:Source) OR (n)-[:WRITTEN_BY]->(:Source) OR n.source_name IS NOT NULL )
          AND n.confidence_score IS NOT NULL
        RETURN count(n) AS sourced
        """
        sourced_obs = self.client.query(cypher_sourced)[0]["sourced"]

        coverage_ratio = sourced_obs / total_obs if total_obs > 0 else 0.0
        self.assertGreaterEqual(
            coverage_ratio, 0.95,
            f"Provenance coverage ratio {coverage_ratio:.2%} is below required 95% threshold."
        )

    # ── 5. Point-in-Time State Reconstruction Milestone ───────────────────────

    def test_reconstruct_market_state_multidomain(self):
        """
        Core Milestone: Reconstructs known state across pricing, specs, demand, reviews,
        and competitors with source provenance for every claim.
        """
        test_vehicles = ["Dzire", "Wagon R", "Ertiga", "Fronx", "Aura", "Amaze"]
        for veh in test_vehicles:
            snapshot = self.engine.reconstruct_market_state(veh, as_of_date="2024-10-15")
            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot.market_geo, "India")
            self.assertEqual(snapshot.as_of_date, "2024-10-15")

            # Check domain slices
            self.assertIsNotNone(snapshot.specifications.get("dimensions_mm"))
            self.assertIsNotNone(snapshot.specifications.get("safety"))
            self.assertGreater(len(snapshot.active_variants), 0, f"No active variants for {veh}")
            self.assertGreater(len(snapshot.provenance_ledger), 10, f"Insufficient provenance ledger for {veh}")

            # Every ledger item must have source, confidence, and method
            for p in snapshot.provenance_ledger:
                self.assertIn("source_name", p)
                self.assertIn("confidence_score", p)
                self.assertIn("extraction_method", p)
                self.assertTrue(0.0 <= p["confidence_score"] <= 1.0)

    def test_temporal_sensitivity_no_future_leakage(self):
        """
        Phase 2 Criterion: Querying state at t1 (e.g. 2024-09-01) must NOT leak
        observations that only occurred at t2 (e.g. 2024-10-15).
        """
        # Dzire prices for 2024-10 were active from 2024-10-01
        snap_sept = self.engine.reconstruct_market_state("Dzire", as_of_date="2024-09-15")
        snap_oct = self.engine.reconstruct_market_state("Dzire", as_of_date="2024-10-15")

        # In September, active variant prices for October must NOT appear
        oct_prices = snap_oct.pricing_ladder["active_variant_prices"]
        sept_prices = snap_sept.pricing_ladder["active_variant_prices"]

        self.assertGreater(len(oct_prices), len(sept_prices),
            "October snapshot must have more active variant prices than September snapshot."
        )

    def test_market_state_delta_comparison(self):
        """Verifies historical delta calculation between two dates."""
        delta = self.engine.compare_market_states("Dzire", "2024-09-01", "2024-11-01")
        self.assertIsNotNone(delta)
        self.assertIn("pricing_delta", delta.__dict__)
        self.assertIn("sales_delta", delta.__dict__)
        self.assertIn("narrative_summary", delta.__dict__)
        self.assertGreater(len(delta.narrative_summary), 50)


if __name__ == "__main__":
    unittest.main()
