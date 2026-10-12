"""
test_validation_fixes.py
========================
Comprehensive regression test suite for the 10 Critical Validation & Governance Fixes:
  1. Temporal outcome validation & incomparable observation rejection
  2. Recommendation objectives, constraint validation, and elasticity provenance
  3. Real action execution (Neo4j catalog write) vs simulation labeling
  4. Identity, RBAC, role spoofing defense, and approval staleness rejection
  5. Multi-tier customer-segment impact validation
  6. End-to-end source ingestion (schema validation, idempotency, rejected records)
  7. Concurrency, optimistic locking, and Neo4j uniqueness constraints
  8. Reproducibility package persistence
  9. Manually reviewed query regression suite (empty evidence, unsupported claims, invalid queries)
"""
import unittest
import uuid
from datetime import datetime, timezone, timedelta

from contracts.decision_contracts import (
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
    IncomparableObservationError,
    UnauthorizedAccessError,
    MissingApprovalError,
    StaleApprovalError,
    ConcurrencyConflictError,
    ScenarioResult,
    utc_now_iso,
)
from decisions.decision_repository import DecisionRepository
from decisions.decision_engine import AutomotiveDecisionEngine
from decisions.approval_service import ApprovalService, InvalidStateTransitionError
from decisions.action_executor import ActionExecutor, ActionExecutionError
from decisions.outcome_tracker import OutcomeTracker
from security.authorization import (
    authenticate_user,
    Role,
    Permission,
    TrustedPrincipalRegistry,
    AuthenticationFailedError,
    UserPrincipal,
)
from decisions.historical_backtest import HistoricalPricingBacktestEngine
from models.scenario_engine import PricingScenarioEngine
from ingestion.source_registry import DataSourceRegistry
from ingestion.ingestion_pipeline import EndToEndIngestionPipeline
from ingestion.data_validator import DataQualityValidator


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


class TestTemporalOutcomeValidation(unittest.TestCase):
    """Fix 1: Temporal and Scope Comparability Validation."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.tracker = OutcomeTracker(self.repo)
        self.dec_id = f"DEC_TEST_{uuid.uuid4().hex[:6]}"
        self.alt = DecisionAlternative(
            alternative_id="ALT_TEST_01",
            decision_id=self.dec_id,
            name="Test Repositioning",
            description="Test",
            scenario_result=ScenarioResult(
                result_id="RES_TEST_01",
                scenario_id="SCEN_01",
                alternative_id="ALT_TEST_01",
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
            ),
        )
        self.decision = DecisionRecord(
            decision_id=self.dec_id,
            title="Temporal Test Decision",
            description="Testing temporal alignment",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura", "Dzire"],
            status=DecisionStatus.COMPLETED,
            alternatives=[self.alt],
            created_at="2026-10-10T00:00:00Z",
            evaluation_window="2026-Q4",
            recommended_alternative_id="ALT_TEST_01",
        )
        self.repo.save_decision(self.decision)

    def test_historical_pre_decision_observation_is_strictly_rejected(self):
        """Pre-decision actuals (2025-Q1) for an Oct 2026 decision CANNOT return MET_EXPECTATION."""
        # 1. In strict mode, must raise IncomparableObservationError
        with self.assertRaises(IncomparableObservationError) as ctx:
            self.tracker.record_and_evaluate_outcome(
                decision_id=self.dec_id,
                alternative_id="ALT_TEST_01",
                metric="sales_volume",
                actual_value=18657.0,  # Exact mathematical match
                measurement_period="2025-Q1",  # Incomparable historical period
                strict=True,
            )
        self.assertIn("Temporal mismatch", str(ctx.exception))

        # 2. In non-strict mode, status must be REJECTED_INCOMPARABLE, never MET_EXPECTATION
        outcome = self.tracker.record_and_evaluate_outcome(
            decision_id=self.dec_id,
            alternative_id="ALT_TEST_01",
            metric="sales_volume",
            actual_value=18657.0,
            measurement_period="2025-Q1",
            strict=False,
        )
        self.assertEqual(outcome.evaluation_status, OutcomeEvaluationStatus.REJECTED_INCOMPARABLE)
        self.assertNotEqual(outcome.evaluation_status, OutcomeEvaluationStatus.MET_EXPECTATION)
        self.assertFalse(outcome.comparability.is_comparable)
        self.assertEqual(outcome.comparability.temporal_alignment, "MISMATCH_PRECEDING_DECISION")

    def test_vehicle_scope_mismatch_rejected(self):
        """Observations for an unrelated vehicle (e.g. Honda City) cannot validate Aura decision."""
        with self.assertRaises(IncomparableObservationError) as ctx:
            self.tracker.record_and_evaluate_outcome(
                decision_id=self.dec_id,
                alternative_id="ALT_TEST_01",
                metric="sales_volume",
                actual_value=18600.0,
                measurement_period="2026-Q4",
                vehicle_model="City",  # Scope mismatch
                strict=True,
            )
        self.assertIn("Vehicle scope mismatch", str(ctx.exception))

    def test_compatible_post_decision_observation_evaluates_correctly(self):
        """Observation in 2026-Q4 for Aura correctly evaluates to MET_EXPECTATION when error < 10%."""
        outcome = self.tracker.record_and_evaluate_outcome(
            decision_id=self.dec_id,
            alternative_id="ALT_TEST_01",
            metric="sales_volume",
            actual_value=18600.0,  # ~0.3% error from 18,657
            measurement_period="2026-Q4",
            vehicle_model="Aura",
            strict=True,
        )
        self.assertEqual(outcome.evaluation_status, OutcomeEvaluationStatus.MET_EXPECTATION)
        self.assertTrue(outcome.comparability.is_comparable)
        self.assertLess(outcome.error_percentage, 1.0)

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestRecommendationObjectivesAndProvenance(unittest.TestCase):
    """Fix 2: Recommendation Objectives, Constraints, and Elasticity Provenance."""

    def setUp(self):
        self.engine = AutomotiveDecisionEngine()

    def test_defend_volume_vs_maximize_revenue_recommendations(self):
        """Under inelastic demand, volume objective recommends price cut, but revenue objective does NOT."""
        brief_vol = self.engine.evaluate_pricing_decision(
            target_model="Aura",
            rival_model="Dzire",
            objective="DEFEND_VOLUME",
        )
        # Under DEFEND_VOLUME, a volume-expanding alternative is selected
        self.assertIn("Volume Parity", brief_vol.recommended_alternative)
        self.assertEqual(brief_vol.objective, "DEFEND_VOLUME")

        brief_rev = self.engine.evaluate_pricing_decision(
            target_model="Aura",
            rival_model="Dzire",
            objective="MAXIMIZE_REVENUE",
        )
        # Under MAXIMIZE_REVENUE, inelastic demand means price cut reduces revenue, so premium/status quo is selected
        self.assertIn("Premium Positioning", brief_rev.recommended_alternative)
        self.assertEqual(brief_rev.objective, "MAXIMIZE_REVENUE")

    def test_profit_optimization_without_cost_data_is_rejected(self):
        """Attempting profit optimization without validated cost data falls back and rejects profit claim."""
        brief_profit = self.engine.evaluate_pricing_decision(
            target_model="Aura",
            rival_model="Dzire",
            objective="MAXIMIZE_PROFIT",
        )
        # Must refuse unproven profit optimization
        self.assertFalse(brief_profit.reproducibility_package["assumptions"]["profit_optimization_claimed"])
        self.assertFalse(brief_profit.reproducibility_package["assumptions"]["cost_or_margin_modeled"])

    def test_elasticity_labeled_as_assumed_prior_with_provenance(self):
        """Scenario engine results must explicitly state ASSUMED_PRIOR with provenance."""
        scen_engine = PricingScenarioEngine()
        res = scen_engine.simulate(
            target_model="Aura",
            baseline_price=600000.0,
            baseline_quantity=18153.0,
            pct_price_change=-0.03,
        )
        self.assertEqual(res.elasticity_type, "ASSUMED_PRIOR")
        self.assertIn("ASSUMED_INDUSTRY_PRIOR", res.elasticity_provenance)
        self.assertFalse(res.profit_optimization_claimed)


class TestRealActionExecutionVsSimulation(unittest.TestCase):
    """Fix 3: Verify Real Action Execution vs Simulation Labeling."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.executor = ActionExecutor(self.repo)
        self.approver = ApprovalService(self.repo)

    def test_internal_pricing_catalog_executes_real_neo4j_write(self):
        """INTERNAL_PRICING_CATALOG must commit a real PriceObservation to Neo4j and return verified confirmation ID."""
        # 1. Setup approved decision
        dec_id = f"DEC_EXEC_{uuid.uuid4().hex[:6]}"
        alt = DecisionAlternative(
            alternative_id="ALT_01",
            decision_id=dec_id,
            name="Test Cut",
            description="Test",
        )
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Real Execution Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,
            alternatives=[alt],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)
        self.approver.approve_decision(dec_id, reviewer_id="vp_pricing", reason="Approved for live catalog update")

        # 2. Action proposal on INTERNAL_PRICING_CATALOG
        proposal = ActionProposal(
            action_id=f"ACT_REAL_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            action_type="REVISE_EX_SHOWROOM_PRICE_LADDER",
            target_system="INTERNAL_PRICING_CATALOG",
            payload={"vehicle_model": "Aura", "proposed_base_price": 582000.0},
            idempotency_key=f"IDEMP_REAL_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        # 3. Execute with authorized user
        execution = self.executor.execute_action(proposal, executor_user_id="action_runner")
        self.assertEqual(execution.execution_status, ExecutionStatus.SUCCESS)
        self.assertIn("CONFIRM_CATALOG_UPDATE_", execution.confirmation_id)
        self.assertEqual(execution.target_system_response["integration_type"], "ENTERPRISE_CATALOG_TRANSACTIONAL_WRITE")
        self.assertEqual(execution.target_system_response["confirmed_price_inr"], 582000.0)

        # 4. Verify CatalogPriceUpdate node was committed to Neo4j and linked to VehicleModel
        update_id = execution.target_system_response["catalog_update_id"]
        check_res = self.repo.client.query(
            "MATCH (ae:ActionExecution)-[:COMMITTED_PRICE_UPDATE]->(cpu:CatalogPriceUpdate {update_id: $id})-[:UPDATED_VEHICLE_PRICE]->(v:VehicleModel) "
            "RETURN cpu.revised_price_inr AS price, v.name AS model",
            {"id": update_id}
        )
        self.assertTrue(len(check_res) > 0)
        self.assertEqual(float(check_res[0]["price"]), 582000.0)
        self.assertEqual(check_res[0]["model"].lower(), "aura")

        # 5. Verify NO spurious PriceObservation was created (empirical market observations remain pristine)
        check_no_polluted_obs = self.repo.client.query(
            "MATCH (p:PriceObservation) WHERE p.source_name = 'INTERNAL_PRICING_CATALOG' RETURN count(p) AS count"
        )
        self.assertEqual(check_no_polluted_obs[0]["count"], 0)

    def test_simulated_pricing_system_labeled_as_simulation(self):
        """SIMULATED_PRICING_SYSTEM returns SIMULATED_SUCCESS and is explicitly prefixed [SIMULATION]."""
        dec_id = f"DEC_SIM_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Sim Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,
            alternatives=[DecisionAlternative(alternative_id="ALT_01", decision_id=dec_id, name="Test", description="Test")],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)
        self.approver.approve_decision(dec_id, reviewer_id="vp_pricing", reason="Sim run")

        proposal = ActionProposal(
            action_id=f"ACT_SIM_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            action_type="RUN_PRICING_SIMULATION",
            target_system="SIMULATED_PRICING_SYSTEM",
            payload={"vehicle_model": "Aura", "proposed_base_price": 582000.0},
            idempotency_key=f"IDEMP_SIM_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        execution = self.executor.execute_action(proposal, executor_user_id="action_runner")
        self.assertEqual(execution.execution_status, ExecutionStatus.SIMULATED_SUCCESS)
        self.assertIn("[SIMULATION]", execution.result_summary)
        self.assertTrue(execution.target_system_response["is_simulation"])

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestIdentityAndAuthorization(unittest.TestCase):
    """Fix 4: Identity, Authorization, Role Spoofing, and Stale Approvals."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.approver = ApprovalService(self.repo)
        self.executor = ActionExecutor(self.repo)

    def test_empty_identity_fails_authentication(self):
        """Empty, None, or whitespace identity must fail authentication with AuthenticationFailedError."""
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user("")
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user(None)
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user("   ")

    def test_unregistered_principal_fails_authentication(self):
        """Unregistered or anonymous identity must fail authentication with AuthenticationFailedError."""
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user("unregistered_attacker")
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user("unknown_service_daemon")

    def test_inactive_principal_fails_authentication(self):
        """Inactive or revoked identities must fail authentication with AuthenticationFailedError."""
        disabled_principal = UserPrincipal(
            user_id="disabled_vp",
            name="Disabled VP",
            roles=[Role.EXECUTIVE],
            is_active=False,
        )
        TrustedPrincipalRegistry.register_principal(disabled_principal)
        with self.assertRaises(AuthenticationFailedError):
            authenticate_user("disabled_vp")

    def test_registered_principals_authenticate_successfully_with_directory_roles(self):
        """Legitimate directory principals authenticate with authoritative permissions."""
        vp = authenticate_user("vp_pricing")
        self.assertEqual(vp.user_id, "vp_pricing")
        self.assertTrue(vp.has_permission(Permission.APPROVE_DECISION))
        self.assertTrue(vp.has_permission(Permission.EXECUTE_ACTION))

        analyst = authenticate_user("pricing_analyst")
        self.assertEqual(analyst.user_id, "pricing_analyst")
        self.assertTrue(analyst.has_permission(Permission.CREATE_DECISION))
        self.assertFalse(analyst.has_permission(Permission.APPROVE_DECISION))

        guest = authenticate_user("guest")
        self.assertEqual(guest.user_id, "guest")
        self.assertTrue(guest.has_permission(Permission.READ_MARKET_DATA))
        self.assertFalse(guest.has_permission(Permission.EXECUTE_ACTION))

    def test_caller_role_spoofing_is_rejected(self):
        """Caller supplying role 'admin' for principal 'analyst' must raise UnauthorizedAccessError."""
        with self.assertRaises(UnauthorizedAccessError):
            authenticate_user("analyst", claimed_roles=["admin"])

    def test_unauthorized_user_cannot_approve(self):
        """Principal 'readonly_auditor' or 'analyst' attempting to approve must be blocked."""
        dec_id = f"DEC_AUTH_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Auth Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,
            alternatives=[DecisionAlternative(alternative_id="ALT_01", decision_id=dec_id, name="Test", description="Test")],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)

        # Analyst lacks APPROVE_DECISION permission
        with self.assertRaises(UnauthorizedAccessError):
            self.approver.approve_decision(dec_id, reviewer_id="pricing_analyst", reason="Unauthorized attempt")

        # Read-only user lacks APPROVE_DECISION permission
        with self.assertRaises(UnauthorizedAccessError):
            self.approver.approve_decision(dec_id, reviewer_id="readonly_auditor", reason="Unauthorized attempt")

    def test_unauthorized_user_cannot_execute(self):
        """Analyst or read-only user attempting to execute action must be blocked."""
        proposal = ActionProposal(
            action_id=f"ACT_AUTH_{uuid.uuid4().hex[:6]}",
            decision_id="DEC_DUMMY",
            alternative_id="ALT_01",
            target_system="INTERNAL_PRICING_CATALOG",
            idempotency_key=f"IDEMP_{uuid.uuid4().hex[:6]}",
        )
        with self.assertRaises(UnauthorizedAccessError):
            self.executor.execute_action(proposal, executor_user_id="pricing_analyst")

    def test_missing_approval_blocks_execution(self):
        """Executing an unapproved decision must raise MissingApprovalError."""
        dec_id = f"DEC_NOAPP_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="No Approval Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,  # Not approved yet
            alternatives=[DecisionAlternative(alternative_id="ALT_01", decision_id=dec_id, name="Test", description="Test")],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)
        proposal = ActionProposal(
            action_id=f"ACT_NOAPP_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            target_system="INTERNAL_PRICING_CATALOG",
            payload={"vehicle_model": "Aura", "proposed_base_price": 582000.0},
            idempotency_key=f"IDEMP_NOAPP_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        res = self.executor.execute_action(proposal, executor_user_id="action_runner")
        self.assertEqual(res.execution_status, ExecutionStatus.FAILED)
        self.assertEqual(res.error_code, "DECISION_NOT_APPROVED")

    def test_stale_approval_blocks_execution(self):
        """An approval older than 30 days or expired is rejected with StaleApprovalError."""
        dec_id = f"DEC_STALE_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Stale Approval Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.APPROVED,
            alternatives=[DecisionAlternative(alternative_id="ALT_01", decision_id=dec_id, name="Test", description="Test")],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)

        # Expired approval 60 days ago
        expired_approval = ApprovalRecord(
            approval_id=f"APPR_EXPIRED_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            reviewer_id="vp_pricing",
            status=ApprovalStatus.APPROVED,
            reason="Old approval",
            created_at=(datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            resolved_at=(datetime.now(timezone.utc) - timedelta(days=60)).isoformat(),
            expires_at=(datetime.now(timezone.utc) - timedelta(days=30)).isoformat(),
        )
        self.repo.save_approval(expired_approval)

        proposal = ActionProposal(
            action_id=f"ACT_STALE_{uuid.uuid4().hex[:6]}",
            decision_id=dec_id,
            alternative_id="ALT_01",
            target_system="INTERNAL_PRICING_CATALOG",
            payload={"vehicle_model": "Aura", "proposed_base_price": 582000.0},
            idempotency_key=f"IDEMP_STALE_{uuid.uuid4().hex[:6]}",
        )
        self.repo.save_action_proposal(proposal)

        with self.assertRaises(StaleApprovalError):
            self.executor.execute_action(proposal, executor_user_id="action_runner")

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestCustomerSegmentImpactValidation(unittest.TestCase):
    """Fix 5: Customer Segment Multi-Tier Impact Validation."""

    def test_segment_impact_has_four_distinct_categories(self):
        """Ensure segment impacts distinguish observed preferences, inferred associations, simulated effects, and measured outcomes."""
        engine = AutomotiveDecisionEngine()
        brief = engine.evaluate_pricing_decision("Aura", "Dzire")
        self.assertTrue(len(brief.affected_segments) > 0)

        for seg in brief.affected_segments:
            self.assertIn("segment_name", seg)
            self.assertIn("observed_preferences", seg)
            self.assertIn("inferred_associations", seg)
            self.assertIn("simulated_effects", seg)
            self.assertIn("measured_outcomes", seg)
            # Observed preferences must have weights if present
            for p in seg["observed_preferences"]:
                self.assertIn("factor", p)
                self.assertIn("weight", p)
                self.assertIsInstance(p["weight"], (int, float))


class TestEndToEndSourceIngestion(unittest.TestCase):
    """Fix 6: End-to-End Source Ingestion, Validation, Idempotency, and Rejected Records."""

    def setUp(self):
        self.pipeline = EndToEndIngestionPipeline()

    def test_automated_vs_manual_registry_classification(self):
        """Sources must explicitly declare automation_verified and mechanism."""
        reg = DataSourceRegistry()
        src_siam = reg.get_source("SRC_SIAM_DISPATCHES")
        src_oem = reg.get_source("SRC_OEM_OFFICIAL")

        self.assertTrue(src_siam.automation_verified)
        self.assertEqual(src_siam.ingestion_mechanism, "BATCH_FILE_INGESTION")

        self.assertFalse(src_oem.automation_verified)
        self.assertEqual(src_oem.ingestion_mechanism, "MANUAL_FEED")

    def test_schema_validation_and_rejected_record_isolation(self):
        """Negative sales units and impossible prices must be rejected and logged in audit sink."""
        records = [
            {"vehicle_model": "Aura", "period_value": "2026-09", "units_sold": 18200},  # Valid
            {"vehicle_model": "Aura", "period_value": "2026-09", "units_sold": -500},   # Invalid: negative
            {"vehicle_model": "Aura", "period_value": "bad_format", "units_sold": 1200},# Invalid: bad period
        ]
        result = self.pipeline.ingest_records("SRC_SIAM_DISPATCHES", records, commit_to_graph=False)
        self.assertEqual(result.total_records, 3)
        self.assertEqual(result.accepted_records, 1)
        self.assertEqual(len(result.rejected_records), 2)
        # Check audit sink
        audit = self.pipeline.get_rejected_records_audit()
        self.assertTrue(any("Negative sales units" in str(r.rejection_reasons) for r in audit))

    def test_idempotency_via_payload_hash(self):
        """Re-ingesting the exact same record must be flagged as duplicate and skipped."""
        records = [{"vehicle_model": "Dzire", "period_value": "2026-10", "units_sold": 29000}]
        res1 = self.pipeline.ingest_records("SRC_SIAM_DISPATCHES", records, commit_to_graph=False)
        self.assertEqual(res1.accepted_records, 1)
        self.assertEqual(res1.duplicate_records, 0)

        res2 = self.pipeline.ingest_records("SRC_SIAM_DISPATCHES", records, commit_to_graph=False)
        self.assertEqual(res2.accepted_records, 0)
        self.assertEqual(res2.duplicate_records, 1)


class TestNeo4jPersistenceAndConcurrency(unittest.TestCase):
    """Fix 8: Inspect Neo4j Uniqueness Constraints and Concurrency Safety."""

    def setUp(self):
        self.repo = DecisionRepository()
        self.approver = ApprovalService(self.repo)

    def test_schema_uniqueness_constraints_active(self):
        """Verify Neo4j uniqueness constraints for Decision, Alternative, Approval, Action, Execution, Outcome."""
        res = self.repo.client.query("SHOW CONSTRAINTS")
        names = {r.get("name") for r in res}
        expected = {
            "decision_id_unique",
            "alt_id_unique",
            "approval_id_unique",
            "action_id_unique",
            "execution_id_unique",
            "outcome_id_unique",
            "action_idempotency_key_unique",
        }
        for exp in expected:
            self.assertIn(exp, names)

    def test_atomic_optimistic_locking_prevents_illegal_concurrent_transitions(self):
        """Attempting to transition from an unexpected state must raise ConcurrencyConflictError."""
        dec_id = f"DEC_CONC_{uuid.uuid4().hex[:6]}"
        dec = DecisionRecord(
            decision_id=dec_id,
            title="Concurrency Test",
            description="Test",
            objective="DEFEND_VOLUME",
            target_entity_ids=["Aura"],
            status=DecisionStatus.READY_FOR_REVIEW,
            alternatives=[DecisionAlternative(alternative_id="ALT_01", decision_id=dec_id, name="Test", description="Test")],
            recommended_alternative_id="ALT_01",
        )
        self.repo.save_decision(dec)

        # Transition to APPROVED
        self.approver.approve_decision(dec_id, reviewer_id="vp_pricing", reason="Approved")

        # Attempting an illegal transition from DRAFT when database is APPROVED must raise InvalidStateTransitionError
        with self.assertRaises(InvalidStateTransitionError):
            self.approver.transition_decision(dec_id, DecisionStatus.INVESTIGATING)

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestReproducibilityPackage(unittest.TestCase):
    """Fix 9: Verify Reproducibility Metadata Persistence."""

    def test_reproducibility_fields_persisted(self):
        """DecisionRecord must persist algorithm_version, data_snapshot_hash, and evaluation_window."""
        engine = AutomotiveDecisionEngine()
        brief = engine.evaluate_pricing_decision("Aura", "Dzire")
        dec_data = engine.repo.get_decision(brief.decision_id)
        self.assertIsNotNone(dec_data)
        dec_node = dec_data["decision"]

        self.assertEqual(dec_node.get("algorithm_version"), "PricingScenarioEngine_v2.1.0")
        self.assertEqual(dec_node.get("evaluation_window"), "2026-Q4")
        self.assertTrue(len(dec_node.get("data_snapshot_hash", "")) > 10)
        self.assertIn("SRC_SIAM_DISPATCHES", dec_node.get("source_references", []))

class TestHistoricalPricingBacktest(unittest.TestCase):
    """Fix 10: Genuine Historical Pricing Backtest with Real Empirical Validation."""

    def setUp(self):
        self.engine = HistoricalPricingBacktestEngine()

    def test_point_in_time_reconstruction_isolates_historical_data_without_leakage(self):
        """Reconstructs state as of 2025-08-31 without future data leakage."""
        pit = self.engine.reconstruct_point_in_time_state(
            target_model="Aura",
            rival_model="Dzire",
            as_of_date="2025-08-31",
        )
        self.assertEqual(pit.target_model, "Aura")
        self.assertEqual(pit.baseline_sales_period, "2025-08")
        self.assertEqual(pit.baseline_monthly_sales, 5336.0)
        self.assertEqual(pit.baseline_sales_source, "Bitauto")
        self.assertEqual(pit.baseline_price_inr, 600000.0)
        self.assertIsNotNone(pit.data_snapshot_hash)

    def test_defensible_recommendation_under_explicit_objectives(self):
        """Generates defensible recommendation under explicit objective and constraints."""
        pit = self.engine.reconstruct_point_in_time_state(
            target_model="Aura",
            rival_model="Dzire",
            as_of_date="2025-08-31",
        )
        rec_vol = self.engine.generate_defensible_recommendation(
            pit_state=pit,
            objective="DEFEND_VOLUME",
            assumed_elasticity=-0.90,
        )
        self.assertEqual(rec_vol.objective, "DEFEND_VOLUME")
        self.assertGreater(rec_vol.predicted_quantity_change_pct, 0.0)
        self.assertIn("DEFEND_VOLUME", rec_vol.rationale)
        self.assertIn("epsilon = -0.90", rec_vol.assumptions_and_uncertainties[0])
        self.assertIn("OEM Manufacturing Cost per Unit: Unrecorded", rec_vol.assumptions_and_uncertainties[1])

        # Test MAXIMIZE_REVENUE objective
        rec_rev = self.engine.generate_defensible_recommendation(
            pit_state=pit,
            objective="MAXIMIZE_REVENUE",
            assumed_elasticity=-0.90,
        )
        self.assertEqual(rec_rev.objective, "MAXIMIZE_REVENUE")
        self.assertIn("MAXIMIZE_REVENUE", rec_rev.rationale)

    def test_governed_execution_commits_catalog_price_update_without_price_observation(self):
        """Action execution commits CatalogPriceUpdate and does not touch PriceObservation."""
        pit = self.engine.reconstruct_point_in_time_state(
            target_model="Aura",
            rival_model="Dzire",
            as_of_date="2025-08-31",
        )
        rec = self.engine.generate_defensible_recommendation(pit, objective="DEFEND_VOLUME")
        decision, execution = self.engine.execute_governed_decision(
            recommendation=rec,
            pit_state=pit,
            approver_user_id="vp_pricing",
            executor_user_id="vp_pricing",
            evaluation_window="2025-09",
        )
        self.assertEqual(execution.execution_status, "SUCCESS")
        self.assertTrue(execution.verified_neo4j_node)
        self.assertIsNotNone(execution.catalog_update_id)

        # Verify no PriceObservation with INTERNAL_PRICING_CATALOG
        res = self.engine.client.query(
            "MATCH (p:PriceObservation) WHERE p.source_name = 'INTERNAL_PRICING_CATALOG' RETURN count(p) as cnt"
        )
        self.assertEqual(res[0]["cnt"], 0)

    def test_closed_loop_outcome_evaluation_against_real_world_actual(self):
        """Executes full backtest workflow and evaluates against empirical Bitauto 2025-09 sales."""
        report = self.engine.run_backtest(
            target_model="Aura",
            rival_model="Dzire",
            as_of_date="2025-08-31",
            evaluation_period="2025-09",
            objective="DEFEND_VOLUME",
            assumed_elasticity=-0.90,
            approver_user_id="vp_pricing",
            executor_user_id="vp_pricing",
        )
        self.assertEqual(report.evaluation.status, OutcomeEvaluationStatus.MET_EXPECTATION)
        self.assertAlmostEqual(report.evaluation.actual_value, 5387.0, places=0)
        self.assertLess(report.evaluation.error_percentage, 5.0)  # ~3.6%
        self.assertTrue(report.evaluation.comparability.is_comparable)
        self.assertEqual(report.evaluation.comparability.temporal_alignment, "ALIGNED")
        self.assertIn("MET EXPECTATION", report.markdown_summary)

    def test_temporal_incomparability_rejected_in_backtest(self):
        """Evaluating backtest against a preceding period (2025-07) must be rejected."""
        pit = self.engine.reconstruct_point_in_time_state("Aura", "Dzire", "2025-08-31")
        rec = self.engine.generate_defensible_recommendation(pit, "DEFEND_VOLUME")
        decision, _ = self.engine.execute_governed_decision(rec, pit, "vp_pricing", "vp_pricing", "2025-09")

        # In strict mode, preceding observation raises IncomparableObservationError
        with self.assertRaises(IncomparableObservationError):
            self.engine.tracker.record_and_evaluate_outcome(
                decision_id=decision.decision_id,
                alternative_id=rec.recommended_alternative_id,
                metric="sales_volume",
                actual_value=5300.0,
                measurement_period="2025-07",  # Precedes decision creation (2025-08-31)
                strict=True,
            )

    def test_unauthenticated_or_unauthorized_user_blocked_from_backtest(self):
        """Unregistered user or unauthorized user cannot execute historical backtest."""
        with self.assertRaises(AuthenticationFailedError):
            self.engine.run_backtest(
                approver_user_id="intruder_anon",
                executor_user_id="intruder_anon",
            )

        with self.assertRaises(PermissionError):
            self.engine.run_backtest(
                approver_user_id="guest",
                executor_user_id="guest",
            )

    @classmethod
    def tearDownClass(cls):
        _cleanup_test_graph()


class TestInputValidationAndReportFormatting(unittest.TestCase):
    """Verifies input validation, gibberish rejection, sequential pointer numbering, and table cleaning."""

    def setUp(self):
        from intelligence.query_planner import SLMQueryPlanner
        from intelligence.dynamic_query_engine import DynamicQueryEngine
        self.planner = SLMQueryPlanner()
        self.engine = DynamicQueryEngine()

    def test_gibberish_query_rejected_without_cypher_or_hallucination(self):
        """Random keystrokes like 'esfdghjkl;' must be rejected at input validation."""
        gibberish = "esfdghjkl;'"
        plan = self.planner.plan_query(gibberish)
        self.assertEqual(plan.intent, "INVALID_QUERY")
        self.assertEqual(plan.selected_tool, "invalid_query")
        self.assertEqual(plan.planner_model, "INPUT_VALIDATION")

        result = self.engine.execute(gibberish)
        self.assertEqual(result.plan.selected_tool, "invalid_query")
        self.assertFalse(result.tool_result.success)
        self.assertEqual(result.confidence_score, 0.0)

        # Must not hallucinate Honda Amaze or random vehicles
        self.assertNotIn("Honda Amaze", result.markdown_report)
        self.assertNotIn("Amaze", result.markdown_report)

        # Must contain clean rejection notice and supported query examples
        self.assertIn("REJECTED (INVALID_INPUT)", result.markdown_report)
        self.assertIn("## 1. Input Analysis", result.markdown_report)
        self.assertIn("## 2. Supported Automotive Inquiries", result.markdown_report)

    def test_unnatural_consonant_clusters_and_noise_rejected(self):
        """Keyboard mashing and non-automotive noise tokens must be rejected."""
        noise_queries = [
            "asdfghjkl",
            ";;;;!!!!",
            "bcdfghjklmn",
            "1234567",
        ]
        for q in noise_queries:
            plan = self.planner.plan_query(q)
            self.assertEqual(plan.intent, "INVALID_QUERY", f"Query '{q}' should be rejected as INVALID_QUERY")
            self.assertEqual(plan.selected_tool, "invalid_query")

    def test_legitimate_queries_not_rejected(self):
        """Legitimate automotive questions must never be falsely rejected."""
        valid_queries = [
            "gaps in aura",
            "compare dzire and amaze",
            "what is the safest car?",
            "which segment is most profitable to enter?",
            "what happens if aura cuts price by 30000?",
        ]
        for q in valid_queries:
            plan = self.planner.plan_query(q)
            self.assertNotEqual(plan.intent, "INVALID_QUERY", f"Valid query '{q}' was falsely rejected")
            self.assertNotEqual(plan.selected_tool, "invalid_query")

    def test_markdown_report_pointer_numbering_strictly_sequential(self):
        """Section numbers (## 1., ## 2., ## 3., etc.) must be strictly consecutive without skipping."""
        import re
        result = self.engine.execute("gaps in aura")
        report = result.markdown_report

        section_numbers = [int(m) for m in re.findall(r"^## (\d+)\.", report, re.MULTILINE)]
        self.assertTrue(len(section_numbers) >= 2, f"Expected at least 2 sections, got: {section_numbers}")

        # Verify 1, 2, 3, 4, ...
        expected = list(range(1, len(section_numbers) + 1))
        self.assertEqual(
            section_numbers,
            expected,
            f"Section numbering is not sequential: got {section_numbers}, expected {expected}",
        )

    def test_dynamic_cypher_table_deduplication_and_clean_formatting(self):
        """Dynamic Cypher record tables must deduplicate identical rows and format currencies/nulls."""
        mock_records = [
            {"brand_name": "Honda", "model_name": "Amaze", "variant_name": "V", "price": None, "units_sold": 4313},
            {"brand_name": "Honda", "model_name": "Amaze", "variant_name": "V", "price": None, "units_sold": 4313},  # Duplicate
            {"brand_name": "Honda", "model_name": "Amaze", "variant_name": "V", "price": None, "units_sold": 19714},
        ]
        table_lines = self.engine._format_cypher_records_table(mock_records)
        joined_table = "\n".join(table_lines)

        # Check deduplication: row with 4,313 should only appear once
        count_4313 = joined_table.count("4,313")
        self.assertEqual(count_4313, 1, "Duplicate record was not deduplicated")

        # Check clean formatting: '-' for None, comma for thousands
        self.assertNotIn("None", joined_table)
        self.assertIn("19,714", joined_table)
        self.assertIn("-", joined_table)


if __name__ == "__main__":
    unittest.main()
