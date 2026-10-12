"""
test_intelligence_engine.py
===========================
Automated test suite validating Milestone 1 of Phase 3 using unittest:
  1. Detects a meaningful market change
  2. Traces related entities and relationships in Neo4j
  3. Retrieves supporting historical evidence across 6 domains
  4. Produces causal explanations with sources, confidence, and limitations
"""
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from graph_db.neo4j_client import Neo4jClient
from intelligence.change_detection import AutomatedChangeDetector, MarketChange
from intelligence.impact_tracer import ImpactPathTracer, TracedImpactSummary
from intelligence.evidence_harvester import EvidenceHarvester, CrossDomainEvidencePackage
from intelligence.intelligence_query import CrossDomainIntelligenceEngine, IntelligenceReport


class TestCrossDomainIntelligenceEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = Neo4jClient()
        cls.engine = CrossDomainIntelligenceEngine(cls.client)

    # ── Test 1: Change Detection ─────────────────────────────────────────────
    def test_01_market_change_detection(self):
        detector = AutomatedChangeDetector(self.client)
        changes = detector.detect_all_changes()
        self.assertGreaterEqual(len(changes), 5, f"Expected at least 5 market changes, got {len(changes)}")

        # Check Dzire safety change structure
        dzire_change = detector.find_change_by_query("Dzire safety crash rating")
        self.assertIsNotNone(dzire_change)
        self.assertEqual(dzire_change.vehicle_model, "Dzire")
        self.assertTrue("5-Star" in dzire_change.title or "Safety" in dzire_change.title)
        self.assertGreaterEqual(dzire_change.magnitude_score, 0.8)
        self.assertGreaterEqual(dzire_change.confidence_score, 0.85)
        self.assertGreater(len(dzire_change.affected_aspects), 0)

    def test_02_market_change_persistence_to_graph(self):
        detector = AutomatedChangeDetector(self.client)
        res = detector.persist_changes_to_graph()
        self.assertGreaterEqual(res["nodes_merged"], 5)
        self.assertGreaterEqual(res["relationships_merged"], 10)

        # Verify Neo4j holds the nodes and relationships
        cypher = """
        MATCH (c:MarketChange)<-[r:UNDERWENT_CHANGE]-(v:VehicleModel)
        RETURN c.change_id AS cid, v.name AS vname
        """
        records = self.client.query(cypher)
        self.assertGreaterEqual(len(records), 5, "Graph should contain MarketChange linked via UNDERWENT_CHANGE")

    # ── Test 2: Multi-Hop Graph Traversal ─────────────────────────────────────
    def test_03_impact_path_tracer_rivals_and_features(self):
        detector = AutomatedChangeDetector(self.client)
        tracer = ImpactPathTracer(self.client)

        dzire_change = detector.find_change_by_query("Dzire safety")
        impact = tracer.trace_impact(dzire_change)

        self.assertIsInstance(impact, TracedImpactSummary)
        self.assertEqual(impact.target_model_name, "Dzire")
        self.assertGreaterEqual(len(impact.impacted_rivals), 2, "Dzire must have at least 2 rivals traced")

        rival_names = [r.model_name for r in impact.impacted_rivals]
        self.assertTrue("Amaze" in rival_names or "Aura" in rival_names)

        # Check that feature gap analysis succeeded
        primary_rival = impact.impacted_rivals[0]
        self.assertGreater(primary_rival.competition_score, 0)
        self.assertGreater(primary_rival.price_overlap, 0)
        # At least some features exclusive to target or rival
        self.assertTrue(len(primary_rival.target_exclusive_features) > 0 or len(primary_rival.rival_exclusive_features) > 0)

    def test_04_impact_path_tracer_segments_and_paths(self):
        detector = AutomatedChangeDetector(self.client)
        tracer = ImpactPathTracer(self.client)

        dzire_change = detector.find_change_by_query("Dzire safety")
        impact = tracer.trace_impact(dzire_change)

        self.assertGreater(len(impact.impacted_segments), 0, "Should trace customer segments prioritizing safety/affordability")
        self.assertTrue(any("Safety" in s.buying_factor for s in impact.impacted_segments), "Should find segments prioritizing Safety")

        self.assertGreaterEqual(len(impact.graph_paths), 4, "Must generate structured multi-hop graph path records")
        self.assertTrue(any("UNDERWENT_CHANGE" in p.relationship_chain for p in impact.graph_paths))
        self.assertTrue(any("COMPETES_WITH" in p.relationship_chain for p in impact.graph_paths))
        self.assertTrue(any("PRIORITIZES" in p.relationship_chain for p in impact.graph_paths))

    # ── Test 3: Historical Evidence Retrieval ────────────────────────────────
    def test_05_evidence_harvester_all_domains(self):
        harvester = EvidenceHarvester(self.client)
        evidence = harvester.harvest_evidence("Dzire", ["Aura", "Amaze"])

        self.assertIsInstance(evidence, CrossDomainEvidencePackage)
        self.assertEqual(evidence.target_model, "Dzire")

        # 1. Price evidence
        self.assertGreater(len(evidence.target_price.price_points), 0)
        self.assertIsNotNone(evidence.target_price.min_ex_showroom)
        self.assertIsNotNone(evidence.target_price.max_ex_showroom)
        self.assertLess(evidence.target_price.min_ex_showroom, evidence.target_price.max_ex_showroom)

        # 2. Sales evidence
        self.assertGreaterEqual(len(evidence.target_sales.monthly_series), 2)
        self.assertIn(evidence.target_sales.trajectory_trend, ["STABLE", "INFLECTION_DROP", "ACCELERATING", "MODERATE_GROWTH", "SOFTENING"])

        # 3. Reviews evidence
        self.assertGreater(evidence.target_reviews.overall_rating, 0)
        self.assertTrue(len(evidence.target_reviews.pros) > 0 or len(evidence.target_reviews.purchase_drivers) > 0)

        # 4. Search demand evidence
        self.assertGreater(len(evidence.target_search.top_queries), 0)
        self.assertNotEqual(evidence.target_search.dominant_intent, "")

        # 5. Technical specs
        self.assertIsNotNone(evidence.target_specs.displacement_cc)
        self.assertGreater(evidence.target_specs.variant_count, 0)

        # 6. Source citations
        self.assertGreaterEqual(len(evidence.citations), 3)

    # ── Test 4: End-to-End Intelligence Query ─────────────────────────────────
    def test_06_end_to_end_intelligence_query_dzire_safety(self):
        report = self.engine.execute_intelligence_query("Dzire Safety Leap", use_ai_grounding=False)

        self.assertIsInstance(report, IntelligenceReport)
        self.assertEqual(report.query, "Dzire Safety Leap")
        self.assertEqual(report.change.vehicle_model, "Dzire")
        self.assertGreaterEqual(report.confidence_score, 0.8)

        # Causal explanation exists and differentiates from correlation
        self.assertIn("Direct Causal Driver", report.causal_explanation)
        self.assertGreaterEqual(len(report.correlational_disclaimers), 2)

        # Strategic recommendations exist for target and rivals
        self.assertIn("Dzire", report.strategic_recommendations)
        self.assertGreaterEqual(len(report.strategic_recommendations["Dzire"]), 2)

        # Limitations documented
        self.assertGreaterEqual(len(report.limitations), 3)

        # Rich markdown report generated
        self.assertGreater(len(report.markdown_report), 1000)
        self.assertIn("## 1. Executive Change Summary", report.markdown_report)
        self.assertIn("## 2. Multi-Hop Graph Impact Traversal (Neo4j)", report.markdown_report)
        self.assertIn("## 3. Cross-Domain Historical Evidence Matrix", report.markdown_report)
        self.assertIn("## 4. Causal Explanation & Correlation Disclaimers", report.markdown_report)
        self.assertIn("## 5. Strategic OEM Recommendations", report.markdown_report)
        self.assertIn("## 7. Sources, Citations & Limitations", report.markdown_report)

    def test_07_end_to_end_intelligence_query_aura_repricing(self):
        report = self.engine.execute_intelligence_query("Aura GST price reduction", use_ai_grounding=False)

        self.assertEqual(report.change.vehicle_model, "Aura")
        self.assertIn("PRICING", report.change.change_type)
        self.assertGreaterEqual(report.confidence_score, 0.8)
        self.assertTrue("₹78,465" in report.change.title or "Price" in report.change.title)
        self.assertTrue("Price / EMI Affordability" in report.causal_explanation or "price" in report.causal_explanation.lower())
        self.assertGreater(len(report.markdown_report), 1000)

    def test_08_end_to_end_intelligence_query_wagon_r_vulnerability(self):
        report = self.engine.execute_intelligence_query("Wagon R safety rating", use_ai_grounding=False)

        self.assertEqual(report.change.vehicle_model, "Wagon R")
        self.assertIn("SAFETY", report.change.change_type)
        self.assertTrue("1-Star" in report.change.title or "Vulnerability" in report.change.title)
        self.assertGreaterEqual(report.confidence_score, 0.8)
        self.assertGreater(len(report.impact.impacted_rivals), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
