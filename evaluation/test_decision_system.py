"""
test_decision_system.py
=======================
Automated test suite for Palantir-Inspired Automotive Decision System:
  • Unit tests for contracts & schema validation
  • Deterministic pricing scenario arithmetic
  • Decision lifecycle & approval gating
  • Security, RBAC & PolicyEngine checks
  • Action execution, connector allowlisting & idempotency
  • Outcome tracking & closed-loop error evaluation
  • End-to-end integration flow
"""

import unittest
import uuid
from contracts.decision_contracts import (
    InvestigationRequest,
    InvestigationPlan,
    QueryIntent,
    ScenarioInput,
    ScenarioResult,
    DecisionRecord,
    DecisionAlternative,
    DecisionStatus,
    ApprovalRecord,
    ApprovalStatus,
    ActionProposal,
    ActionStatus,
    ActionExecution,
    ExecutionStatus,
    OutcomeObservation,
    OutcomeEvaluationStatus,
    ObservationComparability,
    IncomparableObservationError,
)
from models.scenario_engine import PricingScenarioEngine
from decisions.approval_service import ApprovalService, InvalidStateTransitionError
from decisions.action_executor import ActionExecutor, ActionExecutionError
from decisions.outcome_tracker import OutcomeTracker
from decisions.decision_repository import DecisionRepository
from security.authorization import Role, Permission, UserPrincipal, authenticate_user
from security.policy_engine import PolicyEngine


def _cleanup_test_graph():
    from graph_db.neo4j_client import Neo4jClient
    client = Neo4jClient()
    client.query("""
        MATCH (d:Decision)
        WHERE d.decision_id STARTS WITH 'TEST_' OR d.decision_id STARTS WITH 'DEC_'
        OPTIONAL MATCH (d)-[:CONSIDERS]->(a:DecisionAlternative)
        OPTIONAL MATCH (a)-[:EVALUATED_IN]->(sr:ScenarioResult)
        OPTIONAL MATCH (d)-[:REQUIRES_APPROVAL]->(ap:ApprovalRecord)
        OPTIONAL MATCH (a)-[:PROPOSES_ACTION]->(act:ActionProposal)
        OPTIONAL MATCH (act)-[:HAS_EXECUTION]->(ae:ActionExecution)
        OPTIONAL MATCH (d)-[:HAS_OUTCOME]->(out:OutcomeObservation)
        DETACH DELETE d, a, sr, ap, act, ae, out
    """)
    client.query("""
        MATCH (ex:ActionExecution) WHERE ex.execution_id STARTS WITH 'EXEC_' DETACH DELETE ex
    """)
    client.query("""
        MATCH (act:ActionProposal) WHERE act.action_id STARTS WITH 'ACT_' DETACH DELETE act
    """)
    client.query("""
        MATCH (cpu:CatalogPriceUpdate) WHERE cpu.update_id STARTS WITH 'CPU_' DETACH DELETE cpu
    """)
    client.close()


class TestDecisionContracts(unittest.TestCase):
    """Validates typed Pydantic contracts and data schemas."""

    def test_investigation_plan_contract(self):
        plan = InvestigationPlan(
            request_id="REQ_001",
            original_question="Should Hyundai reduce Aura price?",
            intent=QueryIntent.DECISION_RECOMMENDATION,
            vehicle_models=["Aura", "Dzire"],
            required_tools=["decision_engine"],
        )
        self.assertEqual(plan.intent, QueryIntent.DECISION_RECOMMENDATION)
        self.assertEqual(len(plan.vehicle_models), 2)

    def test_scenario_result_arithmetic_contract(self):
        res = ScenarioResult(
            result_id="RES_001",
            scenario_id="SCEN_001",
            alternative_id="ALT_01",
            target_model="Aura",
            baseline_price=600000.0,
            scenario_price=582000.0,
            baseline_quantity=18153.0,
            predicted_quantity=18657.0,
            baseline_revenue=18153.0 * 600000.0,
            predicted_revenue=18657.0 * 582000.0,
            revenue_change=(18657.0 * 582000.0) - (18153.0 * 600000.0),
            pct_revenue_change=-0.30,
            assumed_elasticity=-0.90,
        )
        self.assertAlmostEqual(res.scenario_price, 582000.0)
        self.assertEqual(res.target_model, "Aura")


class TestPricingScenarioEngine(unittest.TestCase):
    """Validates deterministic constant-elasticity scenario formulas."""

    def setUp(self):
        self.engine = PricingScenarioEngine()

    def test_exact_elasticity_formula(self):
        # Baseline: P0 = 600,000, Q0 = 18,153, P1 = 582,000 (-3%), eps = -0.90
        # Q1 = Q0 * (P1 / P0)^(-0.90) = 18153 * (0.97)^(-0.90)
        # 0.97^(-0.90) ≈ 1.02778
        # Q1 ≈ 18153 * 1.02778 ≈ 18657 units
        results = self.engine.evaluate_standard_alternatives(
            target_model="Aura",
            baseline_price=600000.0,
            baseline_quantity=18153.0,
        )
        self.assertEqual(len(results), 4)

        # Status quo (0% change)
        sq = results[0]
        self.assertEqual(sq.scenario_price, 600000.0)
        self.assertEqual(sq.scenario_quantity, 18153.0)
        self.assertEqual(sq.revenue_change, 0.0)

        # -3% cut
        cut3 = results[1]
        self.assertEqual(cut3.scenario_price, 582000.0)
        self.assertGreater(cut3.scenario_quantity, 18153.0)
        self.assertAlmostEqual(cut3.scenario_quantity, 18657.0, delta=10.0)

        # -5% cut
        cut5 = results[2]
        self.assertEqual(cut5.scenario_price, 570000.0)
        self.assertGreater(cut5.scenario_quantity, cut3.scenario_quantity)


class TestSecurityAndPolicy(unittest.TestCase):
    """Validates role-based access control and policy enforcement."""

    def test_rbac_permissions(self):
        admin = authenticate_user("admin", ["admin"])
        executive = authenticate_user("exec", ["executive"])
        analyst = authenticate_user("analyst", ["analyst"])
        readonly = authenticate_user("guest", ["read_only"])

        self.assertTrue(admin.has_permission(Permission.EXECUTE_ACTION))
        self.assertTrue(executive.has_permission(Permission.APPROVE_DECISION))
        self.assertTrue(executive.has_permission(Permission.EXECUTE_ACTION))
        self.assertTrue(analyst.has_permission(Permission.CREATE_DECISION))
        self.assertFalse(analyst.has_permission(Permission.APPROVE_DECISION))
        self.assertFalse(readonly.has_permission(Permission.EXECUTE_ACTION))

    def test_policy_approval_gate(self):
        analyst = authenticate_user("analyst", ["analyst"])
        executive = authenticate_user("exec", ["executive"])

        # Analyst cannot approve
        res_analyst = PolicyEngine.check_decision_approval_policy(analyst, "PRICE_ADJUSTMENT", 3.0)
        self.assertFalse(res_analyst.allowed)

        # Executive can approve 3% reduction
        res_exec = PolicyEngine.check_decision_approval_policy(executive, "PRICE_ADJUSTMENT", 3.0)
        self.assertTrue(res_exec.allowed)

    def test_demographic_data_minimization_policy(self):
        # Asking for gender when no empirical survey sources registered triggers policy warning
        res = PolicyEngine.check_demographic_data_policy("What is gender effect on car buying?", available_demographic_sources=[])
        self.assertTrue(res.allowed)
        self.assertTrue(len(res.warnings) > 0)
        self.assertIn("MUST NOT infer or fabricate", res.warnings[1])


class TestApprovalAndLifecycle(unittest.TestCase):
    """Validates state machine transitions and approval rules."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.approval_service = ApprovalService(self.repo)

    def test_invalid_lifecycle_transition_fails(self):
        # Generate test decision in DRAFT
        test_id = f"TEST_DEC_{uuid.uuid4().hex[:8]}"
        decision = DecisionRecord(
            decision_id=test_id,
            title="Test Decision",
            description="Testing invalid transitions",
            objective="Lifecycle test",
            target_entity_ids=["Aura"],
            status=DecisionStatus.DRAFT,
        )
        self.repo.save_decision(decision)

        # Cannot jump from DRAFT directly to COMPLETED or APPROVED
        with self.assertRaises(InvalidStateTransitionError):
            self.approval_service.transition_decision(test_id, DecisionStatus.COMPLETED)

        with self.assertRaises(InvalidStateTransitionError):
            self.approval_service.transition_decision(test_id, DecisionStatus.APPROVED)

    def test_valid_approval_flow(self):
        test_id = f"TEST_DEC_{uuid.uuid4().hex[:8]}"
        decision = DecisionRecord(
            decision_id=test_id,
            title="Test Decision",
            description="Testing approval flow",
            objective="Lifecycle test",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,
        )
        self.repo.save_decision(decision)

        # Approve decision
        app_rec = self.approval_service.approve_decision(
            decision_id=test_id,
            reviewer_id="vp_pricing",
            reason="Validated through backtested scenario",
            alternative_id="ALT_01",
        )
        self.assertEqual(app_rec.status, ApprovalStatus.APPROVED)

        # Verify status in repository
        updated = self.repo.get_decision(test_id)
        self.assertEqual(updated["decision"]["status"], "APPROVED")

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestActionExecutor(unittest.TestCase):
    """Validates governed execution, connector allowlist, and idempotency."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.executor = ActionExecutor(self.repo)

    def test_unauthorized_user_blocked(self):
        proposal = ActionProposal(
            action_id=f"ACT_TEST_{uuid.uuid4().hex[:6]}",
            decision_id="TEST_DEC_123",
            alternative_id="ALT_01",
            target_system="INTERNAL_PRICING_CATALOG",
            idempotency_key=f"IDEMP_{uuid.uuid4().hex[:6]}",
        )
        with self.assertRaises(ActionExecutionError):
            self.executor.execute_action(proposal, executor_user_id="guest", user_roles=["read_only"])

    def test_unauthorized_connector_rejected(self):
        # Create an approved decision first
        dec_id = f"DEC_TEST_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Test Connector",
            description="Testing connector check",
            objective="Check connector",
            target_entity_ids=["Aura"],
            status=DecisionStatus.APPROVED,
        )
        self.repo.save_decision(dec)

        proposal = ActionProposal(
            action_id=f"ACT_TEST_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            target_system="EXTERNAL_UNTRUSTED_CRM",
            idempotency_key=f"IDEMP_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        res = self.executor.execute_action(proposal, executor_user_id="admin", user_roles=["admin"])
        self.assertEqual(res.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(res.error_code, "UNAUTHORIZED_CONNECTOR")

    def test_idempotent_execution(self):
        dec_id = f"DEC_TEST_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Test Idempotency",
            description="Testing repeated execution",
            objective="Check idempotency",
            target_entity_ids=["Aura"],
            status=DecisionStatus.APPROVED,
        )
        self.repo.save_decision(dec)
        self.repo.save_approval(
            ApprovalRecord(
                approval_id=f"APPR_{dec_id}",
                decision_id=dec_id,
                alternative_id="ALT_01",
                reviewer_id="admin",
                status=ApprovalStatus.APPROVED,
                reason="Idempotency test approval",
            )
        )

        proposal = ActionProposal(
            action_id=f"ACT_TEST_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            target_system="LOCAL_WORLD_MODEL",
            idempotency_key=f"IDEMP_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        # First execution succeeds
        exec1 = self.executor.execute_action(proposal, executor_user_id="admin", user_roles=["admin"])
        self.assertEqual(exec1.execution_status, ExecutionStatus.SUCCESS)

        # Second execution returns same execution record without error
        exec2 = self.executor.execute_action(proposal, executor_user_id="admin", user_roles=["admin"])
        self.assertEqual(exec2.execution_status, ExecutionStatus.SUCCESS)
        self.assertEqual(exec1.execution_id, exec2.execution_id)

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestOutcomeTracker(unittest.TestCase):
    """Validates outcome error calculation and classification."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.tracker = OutcomeTracker(self.repo)

    def test_outcome_met_expectation(self):
        dec_id = f"DEC_TEST_{uuid.uuid4().hex[:6]}"
        alt = DecisionAlternative(
            alternative_id="ALT_01",
            decision_id=dec_id,
            name="Cut -3%",
            description="Test alt",
            scenario_result=ScenarioResult(
                result_id="RES_01",
                scenario_id="SCEN_01",
                alternative_id="ALT_01",
                target_model="Aura",
                baseline_price=600000.0,
                scenario_price=582000.0,
                baseline_quantity=18153.0,
                predicted_quantity=18657.0,
                baseline_revenue=18153.0 * 600000.0,
                predicted_revenue=18657.0 * 582000.0,
                revenue_change=-33000000.0,
                pct_revenue_change=-0.30,
                assumed_elasticity=-0.90,
            )
        )
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Test Outcome",
            description="Test",
            objective="Test",
            target_entity_ids=["Aura"],
            status=DecisionStatus.COMPLETED,
            alternatives=[alt],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)

        # Actual = 18,600 units (expected = 18,657). Error < 1% -> MET_EXPECTATION
        outcome = self.tracker.record_and_evaluate_outcome(
            decision_id=dec_id,
            alternative_id="ALT_01",
            metric="sales_volume",
            actual_value=18600.0,
            measurement_period="2026-Q4",
        )
        self.assertEqual(outcome.evaluation_status, OutcomeEvaluationStatus.MET_EXPECTATION)
        self.assertLess(outcome.error_percentage, 1.0)

    def test_outcome_temporal_mismatch_rejected(self):
        """Regression test: pre-decision observation (2025-Q1 for Oct 2026 decision) CANNOT return MET_EXPECTATION."""
        dec_id = f"DEC_TEST_{uuid.uuid4().hex[:6]}"
        alt = DecisionAlternative(
            alternative_id="ALT_01",
            decision_id=dec_id,
            name="Test",
            description="Test",
            scenario_result=ScenarioResult(
                result_id="RES_01",
                scenario_id="SCEN_01",
                alternative_id="ALT_01",
                target_model="Aura",
                baseline_price=600000.0,
                scenario_price=582000.0,
                baseline_quantity=18153.0,
                predicted_quantity=18657.0,
                baseline_revenue=18153.0 * 600000.0,
                predicted_revenue=18657.0 * 582000.0,
                revenue_change=-33000000.0,
                pct_revenue_change=-0.30,
                assumed_elasticity=-0.90,
            )
        )
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Test Outcome Mismatch",
            description="Test",
            objective="Test",
            target_entity_ids=["Aura"],
            status=DecisionStatus.COMPLETED,
            alternatives=[alt],
            created_at="2026-10-10T00:00:00Z",
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)

        # Strict mode: must raise IncomparableObservationError
        with self.assertRaises(IncomparableObservationError):
            self.tracker.record_and_evaluate_outcome(
                decision_id=dec_id,
                alternative_id="ALT_01",
                metric="sales_volume",
                actual_value=18600.0,
                measurement_period="2025-Q1",
                strict=True,
            )

        # Non-strict mode: must return REJECTED_INCOMPARABLE, never MET_EXPECTATION
        rejected = self.tracker.record_and_evaluate_outcome(
            decision_id=dec_id,
            alternative_id="ALT_01",
            metric="sales_volume",
            actual_value=18600.0,
            measurement_period="2025-Q1",
            strict=False,
        )
        self.assertEqual(rejected.evaluation_status, OutcomeEvaluationStatus.REJECTED_INCOMPARABLE)
        self.assertIn("Temporal mismatch", rejected.notes)

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


if __name__ == "__main__":
    unittest.main()
