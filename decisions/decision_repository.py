"""
decision_repository.py
======================
Neo4j Persistence and Lineage Repository for Decision-Centric Entities:
  • Decision, DecisionAlternative, Scenario, ScenarioResult
  • ApprovalRecord, ActionProposal, ActionExecution, OutcomeObservation
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from graph_db.neo4j_client import Neo4jClient
from contracts.decision_contracts import (
    DecisionRecord,
    DecisionAlternative,
    DecisionStatus,
    ApprovalRecord,
    ApprovalStatus,
    ActionProposal,
    ActionStatus,
    ActionExecution,
    CatalogPriceUpdate,
    ExecutionStatus,
    OutcomeObservation,
    OutcomeEvaluationStatus,
    ScenarioResult,
)

logger = logging.getLogger(__name__)


import json


class DecisionRepository:
    """Manages CRUD and graph lineage persistence for decisions in Neo4j."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()
        self.ensure_schema_constraints()

    def ensure_schema_constraints(self):
        """Creates uniqueness constraints on decision, approval, action, and outcome identifiers in Neo4j."""
        if not self.client or not self.client.is_healthy():
            return

        constraints = [
            ("decision_id_unique", "Decision", "decision_id"),
            ("alt_id_unique", "DecisionAlternative", "alternative_id"),
            ("approval_id_unique", "ApprovalRecord", "approval_id"),
            ("action_id_unique", "ActionProposal", "action_id"),
            ("execution_id_unique", "ActionExecution", "execution_id"),
            ("catalog_update_id_unique", "CatalogPriceUpdate", "update_id"),
            ("outcome_id_unique", "OutcomeObservation", "outcome_id"),
            ("action_idempotency_key_unique", "ActionProposal", "idempotency_key"),
        ]
        for name, label, prop in constraints:
            cypher = f"CREATE CONSTRAINT {name} IF NOT EXISTS FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            try:
                self.client.query(cypher)
            except Exception as e:
                logger.warning(f"Failed to create constraint {name}: {e}")

    def save_decision(self, decision: DecisionRecord) -> str:
        """Persists or updates a Decision node and its alternatives in Neo4j with reproducibility lineage."""
        cypher = """
        MERGE (d:Decision {decision_id: $decision_id})
        SET d.title = $title,
            d.description = $description,
            d.decision_type = $decision_type,
            d.target_entity_ids = $target_entity_ids,
            d.objective = $objective,
            d.constraints = $constraints,
            d.created_at = $created_at,
            d.created_by = $created_by,
            d.status = $status,
            d.priority = $priority,
            d.recommended_alternative_id = $recommended_alt_id,
            d.algorithm_version = $algorithm_version,
            d.evaluation_window = $evaluation_window,
            d.assumptions_json = $assumptions_json,
            d.source_references = $source_references,
            d.data_snapshot_hash = $data_snapshot_hash,
            d.decision_parameters_json = $decision_parameters_json
        RETURN d.decision_id AS id
        """
        self.client.query(cypher, {
            "decision_id": decision.decision_id,
            "title": decision.title,
            "description": decision.description,
            "decision_type": decision.decision_type,
            "target_entity_ids": decision.target_entity_ids,
            "objective": decision.objective,
            "constraints": decision.constraints,
            "created_at": decision.created_at,
            "created_by": decision.created_by,
            "status": decision.status.value if isinstance(decision.status, DecisionStatus) else str(decision.status),
            "priority": decision.priority,
            "recommended_alt_id": decision.recommended_alternative_id or "",
            "algorithm_version": decision.algorithm_version,
            "evaluation_window": decision.evaluation_window or "",
            "assumptions_json": json.dumps(decision.assumptions),
            "source_references": decision.source_references,
            "data_snapshot_hash": decision.data_snapshot_hash or "",
            "decision_parameters_json": json.dumps(decision.decision_parameters),
        })

        # Connect target vehicles
        for target_id in decision.target_entity_ids:
            link_cypher = """
            MATCH (d:Decision {decision_id: $decision_id})
            MATCH (v:VehicleModel)
            WHERE toLower(v.name) = toLower($target) OR v.vehicle_model_id = $target
            MERGE (d)-[:TARGETS]->(v)
            """
            self.client.query(link_cypher, {"decision_id": decision.decision_id, "target": target_id})

        # Persist Alternatives & Scenario Results
        for alt in decision.alternatives:
            self.save_alternative(alt)

        return decision.decision_id

    def save_alternative(self, alt: DecisionAlternative):
        """Persists DecisionAlternative and connects to Decision."""
        cypher = """
        MERGE (a:DecisionAlternative {alternative_id: $alternative_id})
        SET a.decision_id = $decision_id,
            a.name = $name,
            a.description = $description,
            a.estimated_cost = $estimated_cost,
            a.estimated_benefit = $estimated_benefit,
            a.risk_level = $risk_level,
            a.feasibility_status = $feasibility_status,
            a.created_at = $created_at
        WITH a
        MATCH (d:Decision {decision_id: $decision_id})
        MERGE (d)-[:CONSIDERS]->(a)
        """
        self.client.query(cypher, {
            "alternative_id": alt.alternative_id,
            "decision_id": alt.decision_id,
            "name": alt.name,
            "description": alt.description,
            "estimated_cost": alt.estimated_cost,
            "estimated_benefit": alt.estimated_benefit,
            "risk_level": alt.risk_level,
            "feasibility_status": alt.feasibility_status,
            "created_at": alt.created_at,
        })

        # Persist Scenario Result if attached
        if alt.scenario_result:
            s_res = alt.scenario_result
            scen_cypher = """
            MERGE (sr:ScenarioResult {result_id: $result_id})
            SET sr.scenario_id = $scenario_id,
                sr.alternative_id = $alternative_id,
                sr.target_model = $target_model,
                sr.baseline_price = $baseline_price,
                sr.scenario_price = $scenario_price,
                sr.baseline_quantity = $baseline_quantity,
                sr.predicted_quantity = $predicted_quantity,
                sr.baseline_revenue = $baseline_revenue,
                sr.predicted_revenue = $predicted_revenue,
                sr.revenue_change = $revenue_change,
                sr.pct_revenue_change = $pct_revenue_change,
                sr.assumed_elasticity = $assumed_elasticity
            WITH sr
            MATCH (a:DecisionAlternative {alternative_id: $alternative_id})
            MERGE (a)-[:EVALUATED_IN]->(sr)
            """
            self.client.query(scen_cypher, {
                "result_id": s_res.result_id,
                "scenario_id": s_res.scenario_id,
                "alternative_id": alt.alternative_id,
                "target_model": s_res.target_model,
                "baseline_price": s_res.baseline_price,
                "scenario_price": s_res.scenario_price,
                "baseline_quantity": s_res.baseline_quantity,
                "predicted_quantity": s_res.predicted_quantity,
                "baseline_revenue": s_res.baseline_revenue,
                "predicted_revenue": s_res.predicted_revenue,
                "revenue_change": s_res.revenue_change,
                "pct_revenue_change": s_res.pct_revenue_change,
                "assumed_elasticity": s_res.assumed_elasticity,
            })

    def get_decision(self, decision_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves full decision lineage with alternatives, approvals, and outcomes."""
        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})
        OPTIONAL MATCH (d)-[:CONSIDERS]->(a:DecisionAlternative)
        OPTIONAL MATCH (a)-[:EVALUATED_IN]->(sr:ScenarioResult)
        OPTIONAL MATCH (d)-[:REQUIRES_APPROVAL]->(ap:ApprovalRecord)
        OPTIONAL MATCH (a)-[:PROPOSES_ACTION]->(act:ActionProposal)
        OPTIONAL MATCH (d)-[:HAS_OUTCOME]->(out:OutcomeObservation)
        RETURN d,
               collect(DISTINCT a) AS alternatives,
               collect(DISTINCT sr) AS scenario_results,
               collect(DISTINCT ap) AS approvals,
               collect(DISTINCT act) AS actions,
               collect(DISTINCT out) AS outcomes
        """
        rows = self.client.query(cypher, {"decision_id": decision_id})
        if not rows or not rows[0].get("d"):
            return None
        r = rows[0]
        return {
            "decision": dict(r["d"]),
            "alternatives": [dict(x) for x in r["alternatives"] if x],
            "scenario_results": [dict(x) for x in r["scenario_results"] if x],
            "approvals": [dict(x) for x in r["approvals"] if x],
            "actions": [dict(x) for x in r["actions"] if x],
            "outcomes": [dict(x) for x in r["outcomes"] if x],
        }

    def list_decisions(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists registered decisions."""
        filter_clause = "WHERE d.status = $status" if status else ""
        cypher = f"""
        MATCH (d:Decision)
        {filter_clause}
        RETURN d.decision_id AS id,
               d.title AS title,
               d.status AS status,
               d.priority AS priority,
               d.decision_type AS type,
               d.created_at AS created_at
        ORDER BY d.created_at DESC
        LIMIT 50
        """
        rows = self.client.query(cypher, {"status": status})
        return rows

    def save_approval(self, approval: ApprovalRecord):
        """Persists approval record and links to decision."""
        cypher = """
        MERGE (ap:ApprovalRecord {approval_id: $approval_id})
        SET ap.decision_id = $decision_id,
            ap.alternative_id = $alternative_id,
            ap.reviewer_id = $reviewer_id,
            ap.status = $status,
            ap.reason = $reason,
            ap.created_at = $created_at,
            ap.resolved_at = $resolved_at,
            ap.expires_at = $expires_at,
            ap.policy_version = $policy_version
        WITH ap
        MATCH (d:Decision {decision_id: $decision_id})
        MERGE (d)-[:REQUIRES_APPROVAL]->(ap)
        """
        self.client.query(cypher, {
            "approval_id": approval.approval_id,
            "decision_id": approval.decision_id,
            "alternative_id": approval.alternative_id,
            "reviewer_id": approval.reviewer_id,
            "status": approval.status.value if isinstance(approval.status, ApprovalStatus) else str(approval.status),
            "reason": approval.reason or "",
            "created_at": approval.created_at,
            "resolved_at": approval.resolved_at or "",
            "expires_at": approval.expires_at or "",
            "policy_version": approval.policy_version,
        })

    def save_action_proposal(self, action: ActionProposal):
        """Persists action proposal and links to alternative."""
        cypher = """
        MERGE (act:ActionProposal {action_id: $action_id})
        SET act.decision_id = $decision_id,
            act.alternative_id = $alternative_id,
            act.action_type = $action_type,
            act.target_system = $target_system,
            act.payload_json = $payload_json,
            act.status = $status,
            act.idempotency_key = $idempotency_key,
            act.created_at = $created_at
        WITH act
        MATCH (a:DecisionAlternative {alternative_id: $alternative_id})
        MERGE (a)-[:PROPOSES_ACTION]->(act)
        """
        self.client.query(cypher, {
            "action_id": action.action_id,
            "decision_id": action.decision_id,
            "alternative_id": action.alternative_id,
            "action_type": action.action_type,
            "target_system": action.target_system,
            "payload_json": json.dumps(action.payload),
            "status": action.status.value,
            "idempotency_key": action.idempotency_key,
            "created_at": action.created_at,
        })

    def save_outcome(self, outcome: OutcomeObservation):
        """Persists outcome observation and links to decision."""
        comparability_dict = outcome.comparability.dict() if outcome.comparability else {}
        cypher = """
        MERGE (out:OutcomeObservation {outcome_id: $outcome_id})
        SET out.decision_id = $decision_id,
            out.alternative_id = $alternative_id,
            out.metric = $metric,
            out.baseline_value = $baseline_value,
            out.expected_value = $expected_value,
            out.actual_value = $actual_value,
            out.unit = $unit,
            out.measurement_period = $measurement_period,
            out.source_reference = $source_reference,
            out.observed_at = $observed_at,
            out.evaluation_status = $evaluation_status,
            out.error_percentage = $error_percentage,
            out.notes = $notes,
            out.comparability_json = $comparability_json
        WITH out
        MATCH (d:Decision {decision_id: $decision_id})
        MERGE (d)-[:HAS_OUTCOME]->(out)
        """
        self.client.query(cypher, {
            "outcome_id": outcome.outcome_id,
            "decision_id": outcome.decision_id,
            "alternative_id": outcome.alternative_id,
            "metric": outcome.metric,
            "baseline_value": outcome.baseline_value,
            "expected_value": outcome.expected_value,
            "actual_value": outcome.actual_value,
            "unit": outcome.unit,
            "measurement_period": outcome.measurement_period,
            "source_reference": outcome.source_reference,
            "observed_at": outcome.observed_at,
            "evaluation_status": outcome.evaluation_status.value,
            "error_percentage": outcome.error_percentage,
            "notes": outcome.notes,
            "comparability_json": json.dumps(comparability_dict),
        })

    def save_outcome_observation(self, outcome: OutcomeObservation):
        """Alias for save_outcome."""
        self.save_outcome(outcome)

    def get_action_proposal(self, action_id: str) -> Optional[ActionProposal]:
        """Retrieves an ActionProposal by ID."""
        cypher = """
        MATCH (act:ActionProposal {action_id: $action_id})
        RETURN act
        """
        rows = self.client.query(cypher, {"action_id": action_id})
        if not rows or not rows[0].get("act"):
            return None
        props = dict(rows[0]["act"])
        payload = {}
        if props.get("payload_json"):
            try:
                payload = json.loads(props["payload_json"])
            except Exception:
                pass
        return ActionProposal(
            action_id=props.get("action_id", action_id),
            decision_id=props.get("decision_id", ""),
            alternative_id=props.get("alternative_id", ""),
            action_type=props.get("action_type", "INTERNAL_DECISION_RECORD"),
            target_system=props.get("target_system", "LOCAL_WORLD_MODEL"),
            payload=payload,
            status=ActionStatus(props.get("status", "PROPOSED")),
            idempotency_key=props.get("idempotency_key", f"IDEMP_{action_id}"),
            created_at=props.get("created_at", datetime.now(timezone.utc).isoformat()),
        )

    def save_action_execution(self, execution: ActionExecution):
        """Persists an ActionExecution node and links it to ActionProposal."""
        cypher = """
        MERGE (ex:ActionExecution {execution_id: $execution_id})
        SET ex.action_id = $action_id,
            ex.execution_status = $execution_status,
            ex.started_at = $started_at,
            ex.completed_at = $completed_at,
            ex.result_summary = $result_summary,
            ex.error_code = $error_code,
            ex.retry_count = $retry_count,
            ex.confirmation_id = $confirmation_id,
            ex.target_system_response_json = $target_system_response_json
        WITH ex
        MATCH (act:ActionProposal {action_id: $action_id})
        MERGE (act)-[:HAS_EXECUTION]->(ex)
        """
        self.client.query(cypher, {
            "execution_id": execution.execution_id,
            "action_id": execution.action_id,
            "execution_status": execution.execution_status.value,
            "started_at": execution.started_at,
            "completed_at": execution.completed_at or "",
            "result_summary": execution.result_summary,
            "error_code": execution.error_code or "",
            "retry_count": execution.retry_count,
            "confirmation_id": execution.confirmation_id or "",
            "target_system_response_json": json.dumps(execution.target_system_response),
        })

    def get_action_execution(self, action_id: str) -> Optional[ActionExecution]:
        """Retrieves the latest execution for an action proposal."""
        cypher = """
        MATCH (act:ActionProposal {action_id: $action_id})-[:HAS_EXECUTION]->(ex:ActionExecution)
        RETURN ex
        ORDER BY ex.started_at DESC
        LIMIT 1
        """
        rows = self.client.query(cypher, {"action_id": action_id})
        if not rows or not rows[0].get("ex"):
            return None
        props = dict(rows[0]["ex"])
        return ActionExecution(
            execution_id=props.get("execution_id", ""),
            action_id=action_id,
            execution_status=ExecutionStatus(props.get("execution_status", "SUCCESS")),
            started_at=props.get("started_at", ""),
            completed_at=props.get("completed_at"),
            result_summary=props.get("result_summary", ""),
            error_code=props.get("error_code"),
            retry_count=int(props.get("retry_count", 0)),
        )

    def save_catalog_price_update(self, update: CatalogPriceUpdate):
        """Persists a CatalogPriceUpdate node, linking it to ActionExecution and VehicleModel."""
        cypher = """
        MERGE (cpu:CatalogPriceUpdate {update_id: $update_id})
        SET cpu.action_id = $action_id,
            cpu.execution_id = $execution_id,
            cpu.target_model = $target_model,
            cpu.previous_price_inr = $previous_price_inr,
            cpu.revised_price_inr = $revised_price_inr,
            cpu.price_change_percent = $price_change_percent,
            cpu.effective_date = $effective_date,
            cpu.source_system = $source_system,
            cpu.authorized_by = $authorized_by,
            cpu.confirmed_at = $confirmed_at
        WITH cpu
        MATCH (ae:ActionExecution {execution_id: $execution_id})
        MERGE (ae)-[:COMMITTED_PRICE_UPDATE]->(cpu)
        WITH cpu
        MATCH (v:VehicleModel)
        WHERE toLower(v.name) = toLower($target_model) OR v.vehicle_model_id = $target_model
        MERGE (cpu)-[:UPDATED_VEHICLE_PRICE]->(v)
        """
        self.client.query(cypher, {
            "update_id": update.update_id,
            "action_id": update.action_id,
            "execution_id": update.execution_id,
            "target_model": update.target_model,
            "previous_price_inr": update.previous_price_inr,
            "revised_price_inr": update.revised_price_inr,
            "price_change_percent": update.price_change_percent,
            "effective_date": update.effective_date,
            "source_system": update.source_system,
            "authorized_by": update.authorized_by,
            "confirmed_at": update.confirmed_at,
        })

    def get_catalog_price_update(self, id_val: str) -> Optional[CatalogPriceUpdate]:
        """Retrieves catalog price update associated with an action execution or update_id."""
        cypher = """
        MATCH (cpu:CatalogPriceUpdate)
        WHERE cpu.execution_id = $id_val OR cpu.update_id = $id_val
        RETURN cpu
        LIMIT 1
        """
        rows = self.client.query(cypher, {"id_val": id_val})
        if not rows or not rows[0].get("cpu"):
            return None
        c = rows[0]["cpu"]
        return CatalogPriceUpdate(
            update_id=c.get("update_id"),
            action_id=c.get("action_id"),
            execution_id=c.get("execution_id"),
            target_model=c.get("target_model"),
            previous_price_inr=float(c.get("previous_price_inr", 0.0)),
            revised_price_inr=float(c.get("revised_price_inr", 0.0)),
            price_change_percent=float(c.get("price_change_percent", 0.0)),
            effective_date=c.get("effective_date", ""),
            source_system=c.get("source_system", "INTERNAL_PRICING_CATALOG"),
            authorized_by=c.get("authorized_by", ""),
            confirmed_at=c.get("confirmed_at", ""),
        )

    def update_decision_status(self, decision_id: str, new_status: DecisionStatus):
        """Updates the status of a decision."""
        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})
        SET d.status = $status,
            d.updated_at = $updated_at
        """
        self.client.query(cypher, {
            "decision_id": decision_id,
            "status": new_status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

    def get_outcomes_for_decision(self, decision_id: str) -> List[OutcomeObservation]:
        """Retrieves all recorded outcome observations for a decision."""
        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})-[:HAS_OUTCOME]->(out:OutcomeObservation)
        RETURN out
        ORDER BY out.observed_at DESC
        """
        rows = self.client.query(cypher, {"decision_id": decision_id})
        outcomes = []
        for r in rows:
            props = dict(r["out"])
            outcomes.append(OutcomeObservation(
                outcome_id=props.get("outcome_id", ""),
                decision_id=decision_id,
                alternative_id=props.get("alternative_id", ""),
                metric=props.get("metric", "sales_volume"),
                baseline_value=float(props.get("baseline_value", 0)),
                expected_value=float(props.get("expected_value", 0)),
                actual_value=float(props.get("actual_value", 0)),
                unit=props.get("unit", "units"),
                measurement_period=props.get("measurement_period", ""),
                source_reference=props.get("source_reference", ""),
                observed_at=props.get("observed_at", ""),
                evaluation_status=OutcomeEvaluationStatus(props.get("evaluation_status", "MET_EXPECTATION")),
                error_percentage=float(props.get("error_percentage", 0)),
                notes=props.get("notes", ""),
            ))
        return outcomes
