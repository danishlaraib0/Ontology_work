"""
test_dynamic_query.py
=====================
Automated test suite validating the Dynamic Querying Engine and Operational Pipeline:
  1. Cypher Safety Validator (rejection of write operations, limit clamping)
  2. Graph Schema Registry (schema introspection, label/rel validation)
  3. SLM / Fastpath Query Planner (intent & tool routing accuracy)
  4. Dynamic Query Engine execution across Level 1, 2, and 3 capabilities
  5. Closed-Loop Operational Feedback Pipeline execution
"""
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from graph_db.neo4j_client import Neo4jClient
from intelligence.schema_registry import GraphSchemaRegistry
from intelligence.query_safety import CypherSafetyValidator
from intelligence.query_planner import SLMQueryPlanner
from intelligence.dynamic_query_engine import DynamicQueryEngine
from intelligence.dynamic_pipeline import AutomatedDynamicPipeline


class TestDynamicQueryArchitecture(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = Neo4jClient()
        cls.schema = GraphSchemaRegistry(cls.client)
        cls.validator = CypherSafetyValidator()
        cls.planner = SLMQueryPlanner(cls.schema)
        cls.query_engine = DynamicQueryEngine(cls.client)
        cls.pipeline = AutomatedDynamicPipeline(cls.client)

    # ── Test 1: Cypher Safety & Guardrails ───────────────────────────────────
    def test_01_safety_validator_rejects_mutations(self):
        # 1. Reject CREATE
        res_create = self.validator.validate_and_sanitize("CREATE (n:TestNode {name: 'Malicious'})")
        self.assertFalse(res_create.is_safe)
        self.assertIn("CREATE", res_create.rejection_reason)

        # 2. Reject MERGE
        res_merge = self.validator.validate_and_sanitize("MERGE (v:VehicleModel {name: 'Fake'}) SET v.price = 0")
        self.assertFalse(res_merge.is_safe)

        # 3. Reject DELETE
        res_del = self.validator.validate_and_sanitize("MATCH (n) DELETE n")
        self.assertFalse(res_del.is_safe)
        self.assertIn("DELETE", res_del.rejection_reason)

        # 4. Reject administrative procedures
        res_admin = self.validator.validate_and_sanitize("CALL dbms.security.listUsers()")
        self.assertFalse(res_admin.is_safe)

    def test_02_safety_validator_enforces_limits(self):
        # Without limit: appends LIMIT 50
        res_no_limit = self.validator.validate_and_sanitize("MATCH (v:VehicleModel) RETURN v.name")
        self.assertTrue(res_no_limit.is_safe)
        self.assertTrue(res_no_limit.sanitized_cypher.endswith("LIMIT 50"))

        # Excess limit clamped to 50
        res_excess = self.validator.validate_and_sanitize("MATCH (v:VehicleModel) RETURN v.name LIMIT 500")
        self.assertTrue(res_excess.is_safe)
        self.assertTrue(res_excess.sanitized_cypher.endswith("LIMIT 50"))

    # ── Test 2: Schema Registry ──────────────────────────────────────────────
    def test_03_schema_registry_validation(self):
        self.assertTrue(self.schema.is_valid_label("VehicleModel"))
        self.assertTrue(self.schema.is_valid_label("CustomerSegment"))
        self.assertFalse(self.schema.is_valid_label("NonExistentLabel"))

        self.assertTrue(self.schema.is_valid_relationship("COMPETES_WITH"))
        self.assertTrue(self.schema.is_valid_relationship("PRIORITIZES"))
        self.assertFalse(self.schema.is_valid_relationship("INVALID_REL"))

        prompt_summary = self.schema.get_schema_prompt_summary()
        self.assertIn("VehicleModel", prompt_summary)
        self.assertIn("COMPETES_WITH", prompt_summary)

    # ── Test 3: Query Planner Intent Routing ─────────────────────────────────
    def test_04_query_planner_intents(self):
        # 1. Spec Compare
        p1 = self.planner.plan_query("Compare Dzire and Amaze on safety and price.")
        self.assertEqual(p1.intent, "SPEC_FEATURE_COMPARE")
        self.assertEqual(p1.selected_tool, "vehicle_spec_compare")
        self.assertIn("Dzire", p1.target_models)
        self.assertIn("Amaze", p1.target_models)

        # 2. Audience Fit
        p2 = self.planner.plan_query("Which vehicles compete with Dzire for family buyers?")
        self.assertEqual(p2.intent, "AUDIENCE_FIT")
        self.assertEqual(p2.selected_tool, "audience_fit")

        # 3. Competitor Vulnerability
        p3 = self.planner.plan_query("Which competitors are most vulnerable if Dzire cuts its price by ₹30,000?")
        self.assertEqual(p3.intent, "COMPETITOR_VULNERABILITY")
        self.assertEqual(p3.selected_tool, "competitor_vulnerability")

        # 4. Market Change
        p4 = self.planner.plan_query("What changed in the market over the last six months?")
        self.assertEqual(p4.intent, "MARKET_CHANGE_INVESTIGATION")
        self.assertEqual(p4.selected_tool, "market_change_tracer")

        # 5. Intent vs Sales Correlation
        p5 = self.planner.plan_query("Show the evidence connecting customer search intent to sales for Dzire.")
        self.assertEqual(p5.intent, "CORRELATION_ANALYSIS")
        self.assertEqual(p5.selected_tool, "evidence_correlator")

    # ── Test 4: Dynamic Query Engine Execution ───────────────────────────────
    def test_05_dynamic_query_execution_competitor_vulnerability(self):
        q = "Which competitors are most vulnerable if Dzire cuts its price by ₹30,000?"
        res = self.query_engine.execute(q)

        self.assertTrue(res.tool_result.success)
        self.assertEqual(res.plan.selected_tool, "competitor_vulnerability")
        self.assertIn("vulnerable_rivals", res.tool_result.data)
        self.assertGreater(len(res.tool_result.data["vulnerable_rivals"]), 0)
        self.assertGreater(res.confidence_score, 0.80)
        self.assertIn("Amaze", [r["rival_name"] for r in res.tool_result.data["vulnerable_rivals"]])
        self.assertGreater(len(res.markdown_report), 100)

    def test_06_dynamic_query_execution_spec_compare(self):
        q = "Compare Dzire and Amaze on safety and price."
        res = self.query_engine.execute(q)

        self.assertTrue(res.tool_result.success)
        self.assertEqual(res.plan.selected_tool, "vehicle_spec_compare")
        self.assertIn("comparison_matrix", res.tool_result.data)
        matrix = res.tool_result.data["comparison_matrix"]
        self.assertIn("Dzire", matrix)
        self.assertIn("Amaze", matrix)
        self.assertEqual(matrix["Dzire"]["safety_rating"], "5-Star GNCAP")
        self.assertEqual(matrix["Amaze"]["safety_rating"], "2-Star GNCAP")

    def test_07_dynamic_query_execution_audience_fit(self):
        q = "Which vehicles compete with Dzire for family buyers?"
        res = self.query_engine.execute(q)

        self.assertTrue(res.tool_result.success)
        self.assertEqual(res.plan.selected_tool, "audience_fit")
        self.assertIn("rankings", res.tool_result.data)
        self.assertGreaterEqual(len(res.tool_result.data["rankings"]), 3)

    # ── Test 5: Operational Pipeline Execution ───────────────────────────────
    def test_08_dynamic_pipeline_run(self):
        report = self.pipeline.run_pipeline(reload_data=False)
        self.assertEqual(report.status, "SUCCESS")
        self.assertGreaterEqual(report.detected_changes_count, 5)
        self.assertGreaterEqual(report.impacted_rivals_count, 5)
        self.assertEqual(report.forecasts_recalibrated_count, 4)
        self.assertGreaterEqual(report.weight_drift_updates_count, 1)


if __name__ == "__main__":
    unittest.main()
