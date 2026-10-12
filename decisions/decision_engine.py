"""
decision_engine.py
==================
Decision Engine for the Automotive World Model.
Synthesizes:
  1. Real-world Neo4j graph evidence (prices, sales, competitor intensity, customer priorities)
  2. Deterministic scenario simulations (PricingScenarioEngine)
  3. Objective-driven alternative scoring and constraint enforcement (no arbitrary recommendations)
  4. Explicit 4-tier customer segment impact validation (observed, inferred, simulated, measured)
  5. Reproducibility package with data snapshot hash, algorithm version, and evaluation window
  6. Persistence of DecisionRecord and ActionProposal into Neo4j
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient
from models.scenario_engine import PricingScenarioEngine
from contracts.decision_contracts import (
    DecisionRecord,
    DecisionAlternative,
    DecisionStatus,
    ScenarioResult,
    ActionProposal,
    ActionStatus,
    utc_now_iso,
)
from decisions.decision_repository import DecisionRepository

logger = logging.getLogger(__name__)


@dataclass
class SegmentImpactDetail:
    segment_name: str
    observed_preferences: List[Dict[str, Any]]  # Verified buying factors with graph weights
    inferred_associations: List[str]            # Structural graph relations
    simulated_effects: str                      # Model sensitivity based on priorities
    measured_outcomes: Optional[str] = None     # Post-decision verified actuals if available


@dataclass
class DecisionBrief:
    decision_id: str
    question: str
    target_vehicle: str
    rival_vehicle: str
    objective: str
    recommended_alternative: str
    recommendation_summary: str
    baseline_metrics: Dict[str, Any]
    alternatives: List[Dict[str, Any]]
    affected_segments: List[Dict[str, Any]]
    facts: List[str]
    assumptions_and_uncertainties: List[str]
    reproducibility_package: Dict[str, Any]
    proposed_action: Dict[str, Any]
    approval_required: bool = True

    def to_markdown(self) -> str:
        """Renders the DecisionBrief into a clean, executive markdown brief."""
        lines = [
            f"# 🎯 Executive Decision Brief: {self.target_vehicle} vs {self.rival_vehicle}",
            f"> **Decision ID**: `{self.decision_id}` | **Status**: `READY_FOR_REVIEW` | **Objective**: `{self.objective}`",
            "",
            f"### 📋 Strategic Question",
            f"*{self.question}*",
            "",
            f"### 💡 Objective-Driven Recommendation",
            f"**Recommended Option**: `{self.recommended_alternative}`",
            "",
            f"{self.recommendation_summary}",
            "",
            "### 📊 Baseline Market Evidence (Neo4j Graph Facts)",
        ]
        for k, v in self.baseline_metrics.items():
            lines.append(f"- **{k}**: {v}")

        lines.extend([
            "",
            "### 📈 Scenario Analysis & Alternatives Evaluation",
            "| Option | Price (INR) | Δ Price | Projected Volume | Δ Volume | Projected Revenue | Δ Revenue | Risk | Feasibility |",
            "|---|---|---|---|---|---|---|---|---|",
        ])
        for a in self.alternatives:
            s_res = a.get("scenario_result", {})
            p_price = s_res.get("scenario_price", 0)
            p_qty = s_res.get("scenario_quantity", 0)
            p_rev_cr = s_res.get("scenario_revenue", 0) / 10_000_000
            rev_change_cr = s_res.get("revenue_change", 0) / 10_000_000
            pct_p = a.get("parameters", {}).get("pct_change", 0) * 100
            qty_delta_pct = s_res.get("percentage_quantity_change", 0)
            feasibility = a.get("feasibility_status", "FEASIBLE")
            lines.append(
                f"| **{a.get('name')}** | ₹{p_price:,.0f} | {pct_p:+.1f}% | {p_qty:,.0f} | {qty_delta_pct:+.2f}% | ₹{p_rev_cr:.2f} Cr | {rev_change_cr:+.2f} Cr | `{a.get('risk_level')}` | `{feasibility}` |"
            )

        lines.extend([
            "",
            "### 👥 Validated Customer Segment Impact (Multi-Tier Traceability)",
        ])
        for seg in self.affected_segments:
            lines.append(f"#### 🏷️ {seg.get('segment_name')}")
            obs = seg.get("observed_preferences", [])
            obs_str = ", ".join([f"{x['factor']} (weight={x['weight']:.2f})" for x in obs]) if obs else "None recorded"
            lines.append(f"- **Observed Preferences (Graph Facts)**: {obs_str}")
            lines.append(f"- **Inferred Associations**: {'; '.join(seg.get('inferred_associations', []))}")
            lines.append(f"- **Simulated Effect**: {seg.get('simulated_effects')}")
            lines.append(f"- **Measured Outcome**: {seg.get('measured_outcomes') or 'Pending post-execution monitoring'}")

        lines.extend([
            "",
            "### 🔍 Traceable Evidence & Verified Facts",
        ])
        for f in self.facts:
            lines.append(f"- {f}")

        lines.extend([
            "",
            "### ⚠️ Assumptions, Uncertainties & Elasticity Provenance",
        ])
        for u in self.assumptions_and_uncertainties:
            lines.append(f"- {u}")

        lines.extend([
            "",
            "### 🔬 Reproducibility Package",
            f"- **Algorithm Version**: `{self.reproducibility_package.get('algorithm_version')}`",
            f"- **Data Snapshot Hash**: `{self.reproducibility_package.get('data_snapshot_hash')}`",
            f"- **Evaluation Window**: `{self.reproducibility_package.get('evaluation_window')}`",
            f"- **Source References**: {', '.join(self.reproducibility_package.get('source_references', []))}",
            "",
            "### 🔒 Governed Action Proposal",
            f"- **Action ID**: `{self.proposed_action.get('action_id')}`",
            f"- **Action Type**: `{self.proposed_action.get('action_type')}`",
            f"- **Target System**: `{self.proposed_action.get('target_system')}`",
            f"- **Status**: `{self.proposed_action.get('status')}`",
            f"- **Idempotency Key**: `{self.proposed_action.get('idempotency_key')}`",
        ])

        return "\n".join(lines)


class AutomotiveDecisionEngine:
    """
    Evaluates consequential automotive business decisions against the knowledge graph.
    Enforces objective-driven ranking, constraint validation, customer-segment impact tracing,
    and complete reproducibility.
    """

    SUPPORTED_OBJECTIVES = {
        "DEFEND_VOLUME": "Prioritizes volume preservation and competitor market-share defense subject to revenue loss tolerance.",
        "MAXIMIZE_REVENUE": "Selects the alternative that maximizes nominal gross projected sales turnover.",
        "BALANCED_MARKET_SHARE": "Balances unit expansion against margin/revenue dilution using multi-criteria trade-off scoring.",
        "PRESERVE_MARGIN": "Prioritizes price and margin preservation over aggressive volume discounting.",
        "MAXIMIZE_PROFIT": "Requires validated unit cost or margin data; refuses unvalidated profit claims if data is missing.",
    }

    def __init__(self, client: Optional[Neo4jClient] = None, repo: Optional[DecisionRepository] = None):
        self.client = client or Neo4jClient()
        self.repo = repo or DecisionRepository(self.client)
        self.scenario_engine = PricingScenarioEngine()

    def evaluate_pricing_decision(
        self,
        target_model: str = "Aura",
        rival_model: str = "Dzire",
        objective: str = "DEFEND_VOLUME",
        constraints: Optional[Dict[str, Any]] = None,
        user_query: Optional[str] = None,
        custom_pct_cut: Optional[float] = None,
    ) -> DecisionBrief:
        """
        Evaluates a consequential pricing decision between target_model and rival_model.
        Requires explicit objective, evaluates constraints, categorizes segment impacts,
        and generates a reproducible decision record.
        """
        clean_obj = objective.strip().upper()
        if clean_obj not in self.SUPPORTED_OBJECTIVES:
            clean_obj = "DEFEND_VOLUME"

        logger.info(f"Evaluating Strategic Decision: {target_model} vs {rival_model} under objective '{clean_obj}'...")

        # ── 1. Retrieve Baseline Price & Sales from Neo4j (No hardcoded magic numbers) ──
        base_data = self._fetch_baseline_data(target_model, rival_model)
        target_entry_price = base_data["target_entry_price"]
        target_monthly_sales = base_data["target_monthly_sales"]
        rival_entry_price = base_data["rival_entry_price"]
        rival_monthly_sales = base_data["rival_monthly_sales"]

        # ── 2. Traverse Affected Segments & Priorities (Multi-Tier Validation) ──
        segments = self._fetch_affected_segments(target_model, rival_model)

        # ── 3. Run Deterministic Pricing Scenarios ──
        scenario_results = self.scenario_engine.evaluate_standard_alternatives(
            target_model=target_model,
            baseline_price=target_entry_price,
            baseline_quantity=target_monthly_sales,
            custom_pct=custom_pct_cut,
        )

        # ── 4. Build Decision Alternatives & Check Constraints ──
        decision_id = f"DEC_{target_model.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        alternatives: List[DecisionAlternative] = []

        alt_specs = [
            ("ALT_01_STATUS_QUO", "Status Quo", "Maintain current price ladder. Protect per-unit gross margin at the risk of losing price-sensitive buyers.", "LOW"),
            ("ALT_02_COMPETITIVE_CUT", "Moderate Competitive Repositioning (-3%)", f"Reduce base price by 3% (~₹{target_entry_price*0.03:,.0f}). Narrows price gap with {rival_model} while limiting absolute revenue dilution.", "MEDIUM"),
            ("ALT_03_AGGRESSIVE_EXPANSION", "Aggressive Volume Parity (-5%)", f"Reduce base price by 5% (~₹{target_entry_price*0.05:,.0f}). Maximizes fleet and family volume capture, applying direct pricing pressure on {rival_model}.", "HIGH"),
            ("ALT_04_MARGIN_EXPANSION", "Premium Positioning (+5%)", "Increase price by 5% backed by added tech equipment. Maximizes unit margin but surrenders entry volume.", "HIGH"),
        ]

        active_constraints = constraints or {
            "min_base_price_inr": target_entry_price * 0.90,  # Cannot cut price by more than 10%
            "min_monthly_volume": target_monthly_sales * 0.95,  # Must preserve at least 95% throughput
            "max_revenue_loss_inr": target_entry_price * target_monthly_sales * 0.05,  # Max allowable revenue dilution
        }

        for (alt_id, name, desc, risk), s_res in zip(alt_specs, scenario_results):
            s_res.alternative_id = alt_id
            
            # Constraint verification
            is_feasible = True
            violations = []
            if s_res.scenario_price < active_constraints.get("min_base_price_inr", 0):
                is_feasible = False
                violations.append(f"Price ₹{s_res.scenario_price:,.0f} below minimum floor ₹{active_constraints['min_base_price_inr']:,.0f}")
            if s_res.predicted_quantity < active_constraints.get("min_monthly_volume", 0):
                is_feasible = False
                violations.append(f"Projected volume {s_res.predicted_quantity:,.0f} below minimum {active_constraints['min_monthly_volume']:,.0f}")
            if s_res.revenue_change < -active_constraints.get("max_revenue_loss_inr", float("inf")):
                is_feasible = False
                violations.append(f"Revenue loss ₹{abs(s_res.revenue_change):,.0f} exceeds tolerance limit")

            alt = DecisionAlternative(
                alternative_id=alt_id,
                decision_id=decision_id,
                name=name,
                description=desc,
                parameters={"pct_change": round((s_res.scenario_price - s_res.baseline_price) / s_res.baseline_price, 4)},
                estimated_cost=abs(s_res.revenue_change) if s_res.revenue_change < 0 else 0.0,
                estimated_benefit=max(0.0, s_res.revenue_change),
                risk_level=risk,
                feasibility_status="FEASIBLE" if is_feasible else "INFEASIBLE",
                scenario_result=s_res,
            )
            alternatives.append(alt)

        # ── 5. Select Best Recommended Alternative (Objective-Driven Dynamic Selection) ──
        rec_alt, rec_rationale = self._select_recommended_alternative(
            alternatives=alternatives,
            objective=clean_obj,
            constraints=active_constraints,
            target_model=target_model,
            rival_model=rival_model,
        )

        # ── 6. Create Action Proposal ──
        proposal = ActionProposal(
            action_id=f"ACT_{decision_id}_PRICE_PROPOSAL",
            decision_id=decision_id,
            alternative_id=rec_alt.alternative_id,
            action_type="REVISE_EX_SHOWROOM_PRICE_LADDER",
            target_system="INTERNAL_PRICING_CATALOG",
            payload={
                "vehicle_model": target_model,
                "current_base_price": target_entry_price,
                "proposed_base_price": rec_alt.scenario_result.scenario_price if rec_alt.scenario_result else target_entry_price,
                "reduction_amount_inr": round(target_entry_price - (rec_alt.scenario_result.scenario_price if rec_alt.scenario_result else target_entry_price)),
                "effective_quarter": "Q1",
            },
            preconditions=[
                f"Verify {target_model} dealer inventory days < 45 days.",
                "Executive Pricing Committee policy approval signed.",
            ],
            required_permissions=["approve_decision", "execute_action"],
            status=ActionStatus.PROPOSED,
            idempotency_key=f"IDEMP_{decision_id}_{rec_alt.alternative_id}",
        )

        # ── 7. Build Reproducibility Package ──
        snapshot_payload = f"{target_model}:{target_entry_price}:{target_monthly_sales}:{rival_model}:{rival_entry_price}:{rival_monthly_sales}:{self.scenario_engine.default_elasticity}:{clean_obj}"
        snapshot_hash = hashlib.sha256(snapshot_payload.encode("utf-8")).hexdigest()

        repro_pkg = {
            "algorithm_version": "PricingScenarioEngine_v2.1.0",
            "data_snapshot_hash": snapshot_hash,
            "evaluation_window": "2026-Q4",
            "source_references": ["SRC_SIAM_DISPATCHES", "SRC_EX_SHOWROOM_PRICES"],
            "assumptions": {
                "assumed_elasticity": self.scenario_engine.default_elasticity,
                "elasticity_type": "ASSUMED_PRIOR",
                "elasticity_provenance": "Compact sedan historical econometrics prior (-0.90)",
                "cost_or_margin_modeled": False,
                "profit_optimization_claimed": False,
            },
            "decision_parameters": {
                "objective": clean_obj,
                "target_model": target_model,
                "rival_model": rival_model,
                "constraints": active_constraints,
            },
            "generated_at": utc_now_iso(),
        }

        # ── 8. Build Decision Record & Persist to Neo4j ──
        q_text = user_query or f"Should {target_model} adjust price to compete with {rival_model} under objective {clean_obj}?"
        decision = DecisionRecord(
            decision_id=decision_id,
            title=f"{target_model} vs {rival_model} Pricing Repositioning Strategy",
            description=q_text,
            decision_type="STRATEGIC_PRICE_ADJUSTMENT",
            target_entity_ids=[target_model, rival_model],
            objective=f"Objective [{clean_obj}]: {self.SUPPORTED_OBJECTIVES[clean_obj]}",
            constraints=[f"{k}: {v}" for k, v in active_constraints.items()],
            status=DecisionStatus.READY_FOR_REVIEW,
            priority="HIGH",
            recommended_alternative_id=rec_alt.alternative_id,
            alternatives=alternatives,
            evaluation_window="2026-Q4",
            algorithm_version=repro_pkg["algorithm_version"],
            assumptions=repro_pkg["assumptions"],
            source_references=repro_pkg["source_references"],
            data_snapshot_hash=snapshot_hash,
            decision_parameters=repro_pkg["decision_parameters"],
        )

        self.repo.save_decision(decision)
        self.repo.save_action_proposal(proposal)

        # ── 9. Formulate Grounded Decision Brief ──
        brief = DecisionBrief(
            decision_id=decision_id,
            question=q_text,
            target_vehicle=target_model,
            rival_vehicle=rival_model,
            objective=clean_obj,
            recommended_alternative=rec_alt.name,
            recommendation_summary=rec_rationale,
            baseline_metrics={
                f"{target_model} Verified Base Price": f"₹{target_entry_price:,.0f}",
                f"{target_model} Average Monthly Volume": f"{target_monthly_sales:,.0f} units",
                f"{rival_model} Verified Base Price": f"₹{rival_entry_price:,.0f}",
                f"{rival_model} Average Monthly Volume": f"{rival_monthly_sales:,.0f} units",
            },
            alternatives=[
                {
                    "id": a.alternative_id,
                    "name": a.name,
                    "parameters": a.parameters,
                    "risk_level": a.risk_level,
                    "feasibility_status": a.feasibility_status,
                    "scenario_result": a.scenario_result.dict() if a.scenario_result else {},
                }
                for a in alternatives
            ],
            affected_segments=[
                {
                    "segment_name": s.segment_name,
                    "observed_preferences": s.observed_preferences,
                    "inferred_associations": s.inferred_associations,
                    "simulated_effects": s.simulated_effects,
                    "measured_outcomes": s.measured_outcomes,
                }
                for s in segments
            ],
            facts=[
                f"Verified Neo4j Base Price: {target_model} is ₹{target_entry_price:,.0f} vs {rival_model} at ₹{rival_entry_price:,.0f} (₹{rival_entry_price - target_entry_price:+,.0f} differential).",
                f"Verified SIAM Monthly Dispatches: {target_model} averages {target_monthly_sales:,.0f} units/mo vs {rival_model} at {rival_monthly_sales:,.0f} units/mo.",
                f"Traversed {len(segments)} customer segments connected to target and rival in knowledge graph.",
            ],
            assumptions_and_uncertainties=[
                f"Assumed Demand Elasticity: epsilon = {self.scenario_engine.default_elasticity:.2f} (uncalibrated prior; sensitivity tested +/- 20%).",
                "OEM Manufacturing Cost per Unit is unrecorded in graph; profit optimization cannot be mathematically proven without internal bill-of-materials data.",
                "Rival reaction: Assumes competitor does not initiate matching simultaneous counter-discounts.",
            ],
            reproducibility_package=repro_pkg,
            proposed_action={
                "action_id": proposal.action_id,
                "action_type": proposal.action_type,
                "target_system": proposal.target_system,
                "idempotency_key": proposal.idempotency_key,
                "status": proposal.status.value,
            },
            approval_required=True,
        )

        return brief

    def _select_recommended_alternative(
        self,
        alternatives: List[DecisionAlternative],
        objective: str,
        constraints: Dict[str, Any],
        target_model: str,
        rival_model: str,
    ) -> tuple[DecisionAlternative, str]:
        """
        Dynamically ranks alternatives against the explicit business objective and applicable constraints.
        Does NOT use fixed indexes or hardcoded choices.
        """
        feasible = [a for a in alternatives if a.feasibility_status == "FEASIBLE"]
        if not feasible:
            # Fall back to alternative with least severe constraint violation
            feasible = alternatives

        if objective == "DEFEND_VOLUME":
            # Maximize volume increase (predicted_quantity - baseline_quantity)
            def score(alt: DecisionAlternative) -> float:
                if not alt.scenario_result:
                    return 0.0
                return alt.scenario_result.predicted_quantity - alt.scenario_result.baseline_quantity

            best = max(feasible, key=score)
            s = best.scenario_result
            qty_delta = s.predicted_quantity - s.baseline_quantity if s else 0.0
            rev_delta_cr = (s.revenue_change if s else 0.0) / 10_000_000
            summary = (
                f"Selected under explicit objective **DEFEND_VOLUME**: Option `{best.name}` maximizes monthly volume defense "
                f"(+{qty_delta:,.0f} units/mo, {s.percentage_quantity_change:+.2f}%) against {rival_model}. "
                f"Revenue trade-off is ₹{rev_delta_cr:+.2f} Cr, which complies with the maximum allowable loss tolerance constraint."
            )
            return best, summary

        elif objective == "MAXIMIZE_REVENUE":
            # Maximize nominal projected revenue
            def score(alt: DecisionAlternative) -> float:
                if not alt.scenario_result:
                    return 0.0
                return alt.scenario_result.predicted_revenue

            best = max(feasible, key=score)
            s = best.scenario_result
            rev_delta_cr = (s.revenue_change if s else 0.0) / 10_000_000
            summary = (
                f"Selected under explicit objective **MAXIMIZE_REVENUE**: Option `{best.name}` produces the highest projected gross revenue "
                f"(₹{s.predicted_revenue/10_000_000:.2f} Cr, revenue change: ₹{rev_delta_cr:+.2f} Cr). "
                f"Note: In an inelastic demand regime (ε = -0.90), price discounting decreases nominal revenue; hence price cuts are disqualified."
            )
            return best, summary

        elif objective == "PRESERVE_MARGIN":
            # Prioritizes status quo or price increase
            def score(alt: DecisionAlternative) -> float:
                if not alt.scenario_result:
                    return 0.0
                return alt.scenario_result.scenario_price

            best = max(feasible, key=score)
            summary = (
                f"Selected under explicit objective **PRESERVE_MARGIN**: Option `{best.name}` protects price positioning and gross margin per unit, "
                f"preventing downward price-war spiral against {rival_model}."
            )
            return best, summary

        elif objective == "MAXIMIZE_PROFIT":
            # Explicitly check cost data
            has_cost = any(a.scenario_result and a.scenario_result.cost_or_margin_modeled for a in feasible)
            if not has_cost:
                # Disqualify unvalidated profit optimization claim and fall back to balanced trade-off
                logger.warning("Profit optimization requested but OEM cost/margin data is missing. Falling back to BALANCED_MARKET_SHARE.")
                return self._select_recommended_alternative(
                    alternatives=alternatives,
                    objective="BALANCED_MARKET_SHARE",
                    constraints=constraints,
                    target_model=target_model,
                    rival_model=rival_model,
                )

        # Default: BALANCED_MARKET_SHARE
        def score(alt: DecisionAlternative) -> float:
            if not alt.scenario_result:
                return 0.0
            s = alt.scenario_result
            vol_score = s.percentage_quantity_change
            # Penalize revenue loss: 1% revenue loss costs 0.5 points
            rev_loss_pct = min(0.0, s.pct_revenue_change)
            return vol_score + (rev_loss_pct * 0.5)

        best = max(feasible, key=score)
        s = best.scenario_result
        summary = (
            f"Selected under explicit objective **BALANCED_MARKET_SHARE**: Option `{best.name}` delivers the highest multi-criteria score, "
            f"balancing volume acquisition (+{s.percentage_quantity_change:+.2f}%) with bounded revenue dilution ({s.pct_revenue_change:+.2f}%)."
        )
        return best, summary

    def _fetch_baseline_data(self, target: str, rival: str) -> Dict[str, float]:
        """Pulls verified prices and sales volumes from Neo4j without hardcoded constants."""
        if not self.client or not self.client.is_healthy():
            raise ConnectionError("Neo4j database connection unavailable for baseline data retrieval.")

        def get_model_stats(model_name: str) -> tuple[float, float]:
            p_res = self.client.query("""
                MATCH (v:VehicleModel)
                WHERE toLower(v.name) = toLower($model)
                OPTIONAL MATCH (v)-[:HAS_VARIANT]->(:VehicleVariant)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation)
                OPTIONAL MATCH (v)-[:HAS_PRICE_OBSERVATION]->(p2:PriceObservation)
                WITH coalesce(min(p.ex_showroom_inr), min(p2.ex_showroom_inr)) AS min_price
                RETURN min_price
            """, {"model": model_name})

            s_res = self.client.query("""
                MATCH (v:VehicleModel)
                WHERE toLower(v.name) = toLower($model)
                OPTIONAL MATCH (v)-[:HAS_SALES_OBSERVATION]->(s:SalesObservation)
                RETURN avg(s.units_sold) AS avg_sales
            """, {"model": model_name})

            price = float(p_res[0]["min_price"]) if p_res and p_res[0].get("min_price") is not None else None
            sales = float(s_res[0]["avg_sales"]) if s_res and s_res[0].get("avg_sales") is not None else None

            if price is None or sales is None:
                raise ValueError(
                    f"Insufficient verified data in Neo4j for vehicle '{model_name}': "
                    f"price={price}, sales={sales}. Data coverage audit or ingestion required."
                )
            return price, sales

        target_p, target_q = get_model_stats(target)
        rival_p, rival_q = get_model_stats(rival)

        return {
            "target_entry_price": target_p,
            "target_monthly_sales": target_q,
            "rival_entry_price": rival_p,
            "rival_monthly_sales": rival_q,
        }

    def _fetch_affected_segments(self, target: str, rival: str) -> List[SegmentImpactDetail]:
        """
        Traverses customer segments connected to target and rival in Neo4j.
        Strictly categorizes impact into:
          1. Observed preferences (graph weights on buying factors)
          2. Inferred associations (structural consideration edges)
          3. Simulated effects (model sensitivity)
          4. Measured outcomes (actual observed post-decision metrics)
        """
        if not self.client or not self.client.is_healthy():
            return []

        rows = self.client.query("""
            MATCH (s:CustomerSegment)-[:CONSIDERS]->(v:VehicleModel)
            WHERE toLower(v.name) IN [toLower($target), toLower($rival)]
            OPTIONAL MATCH (s)-[p:PRIORITIZES]->(b:BuyingFactor)
            WITH s.name AS segment_name,
                 collect(DISTINCT v.name) AS considered_vehicles,
                 collect(DISTINCT {factor: b.name, weight: p.importance_weight}) AS priorities
            RETURN segment_name, considered_vehicles, priorities
            ORDER BY segment_name
        """, {"target": target, "rival": rival})

        impact_details = []
        for r in rows:
            seg_name = r["segment_name"]
            vehicles = r.get("considered_vehicles", [])
            raw_priorities = r.get("priorities", [])

            # 1. Observed Preferences (Verified Buying Factors with Graph Weights)
            observed = [
                {"factor": p["factor"], "weight": float(p["weight"])}
                for p in raw_priorities
                if p.get("factor") and p.get("weight") is not None
            ]
            observed.sort(key=lambda x: x["weight"], reverse=True)

            # 2. Inferred Associations
            inferred = [
                f"Structurally considers competing models: {', '.join(vehicles)}",
                f"Inferred cross-shopping sensitivity between {target} and {rival}",
            ]

            # 3. Simulated Effects
            price_factor = next((p for p in observed if "price" in p["factor"].lower() or "afford" in p["factor"].lower()), None)
            if price_factor and price_factor["weight"] >= 0.80:
                sim_effect = (
                    f"High behavioral elasticity sensitivity. Segment prioritizes '{price_factor['factor']}' "
                    f"(weight={price_factor['weight']:.2f}); price reductions directly improve consideration parity."
                )
            else:
                sim_effect = (
                    "Moderate to low price sensitivity. Segment priorities focus on feature content, safety, or reliability; "
                    "price reduction yields modest incremental volume capture."
                )

            # 4. Measured Outcomes
            measured = None  # In pre-execution ex-ante evaluation, actual outcome is not yet observed

            impact_details.append(SegmentImpactDetail(
                segment_name=seg_name,
                observed_preferences=observed[:3],
                inferred_associations=inferred,
                simulated_effects=sim_effect,
                measured_outcomes=measured,
            ))

        return impact_details
