"""
decision_contracts.py
======================
Typed Pydantic contracts for the Palantir-inspired Automotive World Model:
  • Investigation Request and Plan
  • Evidence Items and Packages
  • Analytical Models and Scenario Simulations
  • Decision Lifecycle Entities (Decision, Alternative, Approval, Action, Outcome)
  • Data Snapshots and Provenance
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enumerations ─────────────────────────────────────────────────────────────

class DecisionStatus(str, Enum):
    DRAFT = "DRAFT"
    INVESTIGATING = "INVESTIGATING"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class ExecutionStatus(str, Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    SIMULATED_SUCCESS = "SIMULATED_SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"


class OutcomeEvaluationStatus(str, Enum):
    MET_EXPECTATION = "MET_EXPECTATION"
    EXCEEDED_EXPECTATION = "EXCEEDED_EXPECTATION"
    MISSED_EXPECTATION = "MISSED_EXPECTATION"
    INCONCLUSIVE = "INCONCLUSIVE"
    REJECTED_INCOMPARABLE = "REJECTED_INCOMPARABLE"


class IncomparableObservationError(ValueError):
    """Raised when an outcome observation violates temporal, metric, vehicle, or scope comparability."""
    pass


class ActionExecutionError(Exception):
    """Raised when an action cannot be safely executed."""
    pass


class UnauthorizedAccessError(ActionExecutionError, PermissionError):
    """Raised when an operation is attempted without verified identity permissions."""
    pass


class StaleApprovalError(Exception):
    """Raised when an action execution references an expired or stale approval record."""
    pass


class MissingApprovalError(Exception):
    """Raised when action execution is attempted on an unapproved decision."""
    pass


class ConcurrencyConflictError(RuntimeError):
    """Raised when optimistic concurrency checks fail during state transitions."""
    pass


class QueryIntent(str, Enum):
    CUSTOMER_BEHAVIOR_ANALYSIS = "CUSTOMER_BEHAVIOR_ANALYSIS"
    COMPETITOR_COMPARISON = "COMPETITOR_COMPARISON"
    COMPETITOR_GAP_ANALYSIS = "COMPETITOR_GAP_ANALYSIS"
    MARKET_CHANGE_INVESTIGATION = "MARKET_CHANGE_INVESTIGATION"
    SALES_FORECAST = "SALES_FORECAST"
    PRICE_SCENARIO = "PRICE_SCENARIO"
    FEATURE_ANALYSIS = "FEATURE_ANALYSIS"
    MARKET_OVERVIEW = "MARKET_OVERVIEW"
    DATA_COVERAGE_AUDIT = "DATA_COVERAGE_AUDIT"
    DYNAMIC_GRAPH_QUERY = "DYNAMIC_GRAPH_QUERY"
    DECISION_RECOMMENDATION = "DECISION_RECOMMENDATION"
    DECISION_OUTCOME_REVIEW = "DECISION_OUTCOME_REVIEW"


# ── Investigation Contracts ──────────────────────────────────────────────────

class InvestigationRequest(BaseModel):
    request_id: str
    user_id: str = "analyst"
    query: str
    created_at: str = Field(default_factory=utc_now_iso)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class InvestigationPlan(BaseModel):
    request_id: str
    original_question: str
    intent: QueryIntent
    entities: List[str] = Field(default_factory=list)
    brands: List[str] = Field(default_factory=list)
    vehicle_models: List[str] = Field(default_factory=list)
    customer_segments: List[str] = Field(default_factory=list)
    buying_factors: List[str] = Field(default_factory=list)
    time_range: Optional[str] = None
    metrics: List[str] = Field(default_factory=list)
    required_tools: List[str] = Field(default_factory=list)
    dynamic_cypher: Optional[str] = None
    confidence: float = 0.90
    missing_information: List[str] = Field(default_factory=list)
    reasoning: str = ""
    planner_model: str = "SLM"


# ── Evidence Contracts ───────────────────────────────────────────────────────

class EvidenceItem(BaseModel):
    evidence_id: str
    claim_or_metric: str
    value: Any
    unit: Optional[str] = None
    entity_ids: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
    observation_period: Optional[str] = None
    geography: str = "National (India)"
    retrieval_method: str = "Neo4j Graph Traversal"
    quality_status: str = "VALIDATED"
    confidence: float = 0.90
    limitations: List[str] = Field(default_factory=list)


class EvidencePackage(BaseModel):
    package_id: str
    target_entity: str
    items: List[EvidenceItem] = Field(default_factory=list)
    coverage_report: Dict[str, Any] = Field(default_factory=dict)
    harvested_at: str = Field(default_factory=utc_now_iso)


# ── Logic & Simulation Contracts ─────────────────────────────────────────────

class ModelRun(BaseModel):
    model_run_id: str
    model_name: str
    model_version: str = "1.0.0"
    input_snapshot_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    started_at: str = Field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    status: str = "SUCCESS"


class ScenarioInput(BaseModel):
    scenario_id: str
    name: str
    scenario_type: str = "PRICE_REDUCTION"
    target_model: str
    baseline_price: float
    scenario_price: float
    baseline_quantity: float
    elasticity: float = -0.90
    cost_per_unit: Optional[float] = None
    horizon_months: int = 3


class ScenarioResult(BaseModel):
    result_id: str
    scenario_id: str
    alternative_id: Optional[str] = None
    target_model: str
    baseline_price: float
    scenario_price: float
    baseline_quantity: float
    predicted_quantity: float
    baseline_revenue: float
    predicted_revenue: float
    revenue_change: float
    pct_revenue_change: float
    baseline_contribution: Optional[float] = None
    predicted_contribution: Optional[float] = None
    assumed_elasticity: float
    elasticity_type: str = "ASSUMED_PRIOR"
    elasticity_provenance: str = "ASSUMED_INDUSTRY_PRIOR: -0.90 based on compact sedan historical econometrics"
    cost_or_margin_modeled: bool = False
    profit_optimization_claimed: bool = False
    uncertainty_range: Dict[str, float] = Field(default_factory=dict)
    constraints_violated: List[str] = Field(default_factory=list)
    model_run_id: Optional[str] = None

    @property
    def scenario_quantity(self) -> float:
        return self.predicted_quantity

    @property
    def scenario_revenue(self) -> float:
        return self.predicted_revenue

    @property
    def percentage_quantity_change(self) -> float:
        if self.baseline_quantity > 0:
            return ((self.predicted_quantity - self.baseline_quantity) / self.baseline_quantity) * 100.0
        return 0.0


# ── Decision Management Contracts ────────────────────────────────────────────

class DecisionAlternative(BaseModel):
    alternative_id: str
    decision_id: str
    name: str
    description: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    estimated_cost: float = 0.0
    estimated_benefit: float = 0.0
    risk_level: str = "LOW"  # 'LOW', 'MEDIUM', 'HIGH'
    feasibility_status: str = "FEASIBLE"
    scenario_result: Optional[ScenarioResult] = None
    created_at: str = Field(default_factory=utc_now_iso)


class DecisionRecord(BaseModel):
    decision_id: str
    title: str
    description: str
    decision_type: str = "PRICE_ADJUSTMENT"
    target_entity_ids: List[str] = Field(default_factory=list)
    objective: str
    constraints: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)
    created_by: str = "analyst"
    status: DecisionStatus = DecisionStatus.DRAFT
    priority: str = "HIGH"
    recommended_alternative_id: Optional[str] = None
    alternatives: List[DecisionAlternative] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    evaluation_window: Optional[str] = None
    algorithm_version: str = "PricingScenarioEngine_v1.2.0"
    assumptions: Dict[str, Any] = Field(default_factory=dict)
    source_references: List[str] = Field(default_factory=list)
    data_snapshot_hash: Optional[str] = None
    decision_parameters: Dict[str, Any] = Field(default_factory=dict)


class ApprovalRecord(BaseModel):
    approval_id: str
    decision_id: str
    alternative_id: str
    reviewer_id: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    reason: Optional[str] = None
    created_at: str = Field(default_factory=utc_now_iso)
    resolved_at: Optional[str] = None
    expires_at: Optional[str] = None
    policy_version: str = "v1.0"


# ── Governed Action Contracts ────────────────────────────────────────────────

class ActionProposal(BaseModel):
    action_id: str
    decision_id: str
    alternative_id: str
    action_type: str = "INTERNAL_DECISION_RECORD"
    target_system: str = "LOCAL_WORLD_MODEL"
    payload: Dict[str, Any] = Field(default_factory=dict)
    preconditions: List[str] = Field(default_factory=list)
    required_permissions: List[str] = Field(default_factory=lambda: ["execute_action"])
    status: ActionStatus = ActionStatus.PROPOSED
    idempotency_key: str
    created_at: str = Field(default_factory=utc_now_iso)


class ActionExecution(BaseModel):
    execution_id: str
    action_id: str
    execution_status: ExecutionStatus = ExecutionStatus.SUCCESS
    started_at: str = Field(default_factory=utc_now_iso)
    completed_at: Optional[str] = None
    result_summary: str = ""
    error_code: Optional[str] = None
    retry_count: int = 0
    confirmation_id: Optional[str] = None
    target_system_response: Dict[str, Any] = Field(default_factory=dict)


class CatalogPriceUpdate(BaseModel):
    """
    Governed internal pricing catalog update committed by an ActionExecution.
    Ontologically distinct from empirical market PriceObservation.
    """
    update_id: str
    action_id: str
    execution_id: str
    target_model: str
    previous_price_inr: float
    revised_price_inr: float
    price_change_percent: float
    effective_date: str
    source_system: str = "INTERNAL_PRICING_CATALOG"
    authorized_by: str
    confirmed_at: str = Field(default_factory=utc_now_iso)


# ── Outcome & Learning Contracts ─────────────────────────────────────────────

class ObservationComparability(BaseModel):
    is_comparable: bool = True
    incomparability_reason: Optional[str] = None
    temporal_alignment: str = "ALIGNED"
    metric_alignment: str = "ALIGNED"
    vehicle_scope_alignment: str = "ALIGNED"
    geography_alignment: str = "ALIGNED"
    aggregation_alignment: str = "ALIGNED"


class OutcomeObservation(BaseModel):
    outcome_id: str
    decision_id: str
    alternative_id: str
    metric: str
    baseline_value: float
    expected_value: float
    actual_value: float
    unit: str = "units"
    measurement_period: str
    source_reference: str
    observed_at: str = Field(default_factory=utc_now_iso)
    evaluation_status: OutcomeEvaluationStatus = OutcomeEvaluationStatus.MET_EXPECTATION
    error_percentage: float = 0.0
    notes: str = ""
    comparability: Optional[ObservationComparability] = None


class DataSnapshot(BaseModel):
    snapshot_id: str
    created_at: str = Field(default_factory=utc_now_iso)
    source_versions: Dict[str, str] = Field(default_factory=dict)
    entity_scope: List[str] = Field(default_factory=list)
    time_range: Optional[str] = None
    snapshot_hash: str = ""
