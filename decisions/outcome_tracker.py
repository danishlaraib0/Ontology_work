"""
Outcome Tracker: Decision Lineage and Closed-Loop Learning.
Compares actual market observations with predicted/expected outcomes, computes error metrics,
updates decision records, and persists outcome observations in the knowledge graph.
"""

import uuid
import re
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from contracts.decision_contracts import (
    OutcomeObservation,
    OutcomeEvaluationStatus,
    ObservationComparability,
    IncomparableObservationError,
    DecisionStatus,
    utc_now_iso,
)
from decisions.decision_repository import DecisionRepository

logger = logging.getLogger("OutcomeTracker")


class OutcomeTracker:
    """
    Evaluates real-world market outcomes against scenario predictions to enable continuous decision learning.
    Enforces strict temporal alignment, metric compatibility, and scope comparability.
    """

    TOLERANCE_THRESHOLD_PCT = 10.0  # Within 10% error is deemed MET_EXPECTATION

    def __init__(self, repo: Optional[DecisionRepository] = None):
        self.repo = repo or DecisionRepository()

    def _extract_year_month(self, period_str: str) -> Optional[tuple[int, int, str]]:
        """Parses a period string like '2026-11', '2026-Q4', '2025-Q1', '2025' into (year, start_month, period_type)."""
        period_clean = (period_str or "").strip().upper()
        # YYYY-MM
        m_ym = re.match(r"^(\d{4})-(\d{2})$", period_clean)
        if m_ym:
            return int(m_ym.group(1)), int(m_ym.group(2)), "MONTH"
        # YYYY-Q#
        m_q = re.match(r"^(\d{4})-Q([1-4])$", period_clean)
        if m_q:
            year = int(m_q.group(1))
            q = int(m_q.group(2))
            start_month = (q - 1) * 3 + 1
            return year, start_month, "QUARTER"
        # YYYY
        m_y = re.match(r"^(\d{4})$", period_clean)
        if m_y:
            return int(m_y.group(1)), 1, "YEAR"
        return None

    def validate_comparability(
        self,
        decision_data: Dict[str, Any],
        metric: str,
        measurement_period: str,
        vehicle_model: Optional[str] = None,
        geography: str = "National (India)",
        unit: str = "units",
    ) -> ObservationComparability:
        """
        Validates temporal, metric, vehicle scope, and geographical comparability between
        the decision scenario and the reported observation.
        """
        comp = ObservationComparability(is_comparable=True)

        dec_record = decision_data.get("decision", {})
        created_at_str = dec_record.get("created_at") or utc_now_iso()
        eval_window = dec_record.get("evaluation_window")

        # 1. Temporal Alignment Validation
        obs_parsed = self._extract_year_month(measurement_period)
        dec_created_dt = None
        try:
            dec_created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except Exception:
            dec_created_dt = datetime(2026, 10, 11)

        if obs_parsed:
            obs_year, obs_month, obs_type = obs_parsed
            # Decision creation timeline
            dec_year = dec_created_dt.year
            dec_month = dec_created_dt.month

            # Observation period cannot precede decision creation year/month
            if (obs_year < dec_year) or (obs_year == dec_year and obs_month < dec_month):
                comp.is_comparable = False
                comp.temporal_alignment = "MISMATCH_PRECEDING_DECISION"
                comp.incomparability_reason = (
                    f"Temporal mismatch: Observation period '{measurement_period}' precedes decision "
                    f"creation date ({created_at_str[:10]}). Historical pre-decision observations cannot "
                    f"validate post-decision counterfactual outcomes."
                )
                return comp

            # If explicit evaluation window exists (e.g. 2026-Q4, 2025-09), check window containment
            if eval_window:
                win_parsed = self._extract_year_month(eval_window)
                if win_parsed:
                    win_year, win_month, win_type = win_parsed
                    in_window = True
                    if obs_year != win_year:
                        in_window = False
                    elif win_type == "MONTH" and obs_month != win_month:
                        in_window = False
                    elif win_type == "QUARTER":
                        # Check if obs_month falls in quarter [win_month, win_month+1, win_month+2]
                        if not (win_month <= obs_month <= win_month + 2):
                            in_window = False

                    if not in_window:
                        comp.is_comparable = False
                        comp.temporal_alignment = "MISMATCH_OUT_OF_WINDOW"
                        comp.incomparability_reason = (
                            f"Temporal mismatch: Observation period '{measurement_period}' is outside the "
                            f"decision evaluation window '{eval_window}'."
                        )
                        return comp

        # 2. Metric Definition Alignment
        scens = decision_data.get("scenario_results", [])
        valid_metrics = {"sales_volume", "quantity", "units", "revenue", "total_revenue"}
        if metric.lower() not in valid_metrics:
            comp.is_comparable = False
            comp.metric_alignment = "DEFINITION_MISMATCH"
            comp.incomparability_reason = f"Metric mismatch: '{metric}' is not modeled in scenario predictions (expected one of {valid_metrics})."
            return comp

        # Unit sanity check
        if metric.lower() in ("sales_volume", "quantity", "units") and unit.lower() in ("inr", "rupees", "crores"):
            comp.is_comparable = False
            comp.metric_alignment = "UNIT_INCOMPATIBLE"
            comp.incomparability_reason = f"Unit mismatch: Metric '{metric}' cannot have monetary unit '{unit}'."
            return comp

        # 3. Vehicle Scope Alignment
        target_entities = dec_record.get("target_entity_ids", [])
        if vehicle_model and target_entities:
            matched_veh = any(to_check.lower() == vehicle_model.lower() for to_check in target_entities)
            if not matched_veh:
                comp.is_comparable = False
                comp.vehicle_scope_alignment = "VEHICLE_SCOPE_MISMATCH"
                comp.incomparability_reason = (
                    f"Vehicle scope mismatch: Observation vehicle '{vehicle_model}' does not match "
                    f"decision target entities {target_entities}."
                )
                return comp

        return comp

    def record_and_evaluate_outcome(
        self,
        decision_id: str,
        alternative_id: str,
        metric: str,
        actual_value: float,
        measurement_period: str,
        source_reference: str = "SRC_SIAM_DISPATCHES",
        unit: str = "units",
        vehicle_model: Optional[str] = None,
        notes: str = "",
        strict: bool = True,
    ) -> OutcomeObservation:
        """
        Record an observed outcome for a decision alternative and evaluate accuracy against the expectation.
        Rejects incomparable observations (temporal, metric, vehicle, scope mismatches).

        Args:
            decision_id: ID of the DecisionRecord.
            alternative_id: ID of the executed DecisionAlternative.
            metric: Evaluated metric (e.g. 'sales_volume', 'revenue').
            actual_value: Measured actual value.
            measurement_period: Period of observation (e.g. '2026-Q4' or '2026-11').
            source_reference: Provenance source ID.
            unit: Metric unit ('units', 'INR', etc.).
            vehicle_model: Target vehicle name.
            notes: Context notes or external confounder observations.
            strict: If True, raises IncomparableObservationError upon incompatibility.

        Returns:
            OutcomeObservation: Evaluated outcome record with error percentage and status.
        """
        decision_data = self.repo.get_decision(decision_id)
        if not decision_data:
            raise ValueError(f"Decision '{decision_id}' not found.")

        # 1. Enforce Observation Comparability Validation
        comparability = self.validate_comparability(
            decision_data=decision_data,
            metric=metric,
            measurement_period=measurement_period,
            vehicle_model=vehicle_model,
            unit=unit,
        )

        if not comparability.is_comparable:
            logger.warning(f"Incomparable observation for decision {decision_id}: {comparability.incomparability_reason}")
            if strict:
                raise IncomparableObservationError(comparability.incomparability_reason)

            # Record as REJECTED_INCOMPARABLE when strict is False
            rejected_outcome = OutcomeObservation(
                outcome_id=f"OUTCOME_REJ_{uuid.uuid4().hex[:8]}",
                decision_id=decision_id,
                alternative_id=alternative_id,
                metric=metric,
                baseline_value=0.0,
                expected_value=0.0,
                actual_value=actual_value,
                unit=unit,
                measurement_period=measurement_period,
                source_reference=source_reference,
                observed_at=utc_now_iso(),
                evaluation_status=OutcomeEvaluationStatus.REJECTED_INCOMPARABLE,
                error_percentage=0.0,
                notes=f"REJECTED: {comparability.incomparability_reason}",
                comparability=comparability,
            )
            self.repo.save_outcome_observation(rejected_outcome)
            return rejected_outcome

        # Locate alternative
        alts = decision_data.get("alternatives", [])
        alt = next((a for a in alts if a.get("alternative_id") == alternative_id), None)
        if not alt and alts:
            alt = alts[0]

        # Determine expected value and baseline value
        expected_val = 0.0
        baseline_val = 0.0

        scens = decision_data.get("scenario_results", [])
        s_res = next((s for s in scens if s.get("alternative_id") == alternative_id), None)
        if not s_res and scens:
            s_res = scens[0]

        if s_res:
            if metric in ("sales_volume", "quantity", "units"):
                expected_val = float(s_res.get("predicted_quantity") or s_res.get("scenario_quantity") or 0.0)
                baseline_val = float(s_res.get("baseline_quantity") or 0.0)
            elif metric in ("revenue", "total_revenue"):
                expected_val = float(s_res.get("predicted_revenue", s_res.get("scenario_revenue", 0.0)))
                baseline_val = float(s_res.get("baseline_revenue", 0.0))
            else:
                expected_val = float(alt.get("estimated_benefit", 0.0) if alt else 0.0)
        elif alt:
            expected_val = float(alt.get("estimated_benefit", 0.0))

        # Calculate error percentage
        if expected_val > 0:
            error_pct = abs(actual_value - expected_val) / expected_val * 100.0
        else:
            error_pct = 0.0

        # Classify status
        if error_pct <= self.TOLERANCE_THRESHOLD_PCT:
            status = OutcomeEvaluationStatus.MET_EXPECTATION
            status_note = f"Actual value ({actual_value:,.0f}) is within {self.TOLERANCE_THRESHOLD_PCT}% of expected ({expected_val:,.0f})."
        elif actual_value > expected_val:
            status = OutcomeEvaluationStatus.EXCEEDED_EXPECTATION
            status_note = f"Actual value ({actual_value:,.0f}) exceeded expected ({expected_val:,.0f}) by {error_pct:.1f}%."
        else:
            status = OutcomeEvaluationStatus.MISSED_EXPECTATION
            status_note = f"Actual value ({actual_value:,.0f}) fell short of expected ({expected_val:,.0f}) by {error_pct:.1f}%."

        full_notes = f"{status_note} Confounders: {notes}" if notes else status_note

        outcome = OutcomeObservation(
            outcome_id=f"OUTCOME_{uuid.uuid4().hex[:10]}",
            decision_id=decision_id,
            alternative_id=alternative_id,
            metric=metric,
            baseline_value=baseline_val,
            expected_value=expected_val,
            actual_value=actual_value,
            unit=unit,
            measurement_period=measurement_period,
            source_reference=source_reference,
            observed_at=utc_now_iso(),
            evaluation_status=status,
            error_percentage=round(error_pct, 2),
            notes=full_notes,
            comparability=comparability,
        )

        # Save to graph
        self.repo.save_outcome_observation(outcome)
        logger.info(f"Recorded outcome {outcome.outcome_id} for decision {decision_id}: {status.value} (Error: {error_pct:.1f}%)")
        return outcome

    def get_decision_outcomes(self, decision_id: str) -> List[OutcomeObservation]:
        """Fetch all recorded outcomes for a decision from the graph repository."""
        return self.repo.get_outcomes_for_decision(decision_id)

