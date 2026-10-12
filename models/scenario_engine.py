"""
scenario_engine.py
==================
Deterministic Pricing Scenario Simulation Engine for the Automotive World Model.
Implements exact constant price elasticity dynamics:
    Q_1 = Q_0 * (P_1 / P_0) ^ epsilon

Calculates:
  • Baseline and scenario price (INR)
  • Baseline and scenario sales volume (units/month)
  • Revenue impact (INR and percentage change)
  • Gross contribution margin impact (when unit cost is available)
  • Bounded uncertainty sensitivity (elasticity range [epsilon * 0.8, epsilon * 1.2])
  • Distinguishes deterministic simulation from empirical observational forecasting.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional
from contracts.decision_contracts import ScenarioInput, ScenarioResult


class PricingScenarioEngine:
    """Simulates counterfactual price adjustments under exact constant-elasticity demand."""

    DEFAULT_ASSUMED_ELASTICITY: float = -0.90  # Typical automotive price elasticity assumption

    def __init__(self, default_elasticity: float = DEFAULT_ASSUMED_ELASTICITY):
        self.default_elasticity = default_elasticity

    def simulate(
        self,
        target_model: str,
        baseline_price: float,
        baseline_quantity: float,
        pct_price_change: float,
        elasticity: Optional[float] = None,
        cost_per_unit: Optional[float] = None,
        scenario_id: Optional[str] = None,
        alternative_id: Optional[str] = None,
    ) -> ScenarioResult:
        """
        Runs a deterministic pricing simulation for a given percentage price change.
        pct_price_change: e.g. -0.05 for -5% cut, +0.03 for +3% increase.
        """
        eps = elasticity if elasticity is not None else self.default_elasticity
        p0 = float(baseline_price)
        q0 = float(baseline_quantity)

        # 1. Scenario Price
        p1 = round(p0 * (1.0 + pct_price_change), 2)
        if p1 <= 0:
            raise ValueError(f"Scenario price must be positive, got {p1}")

        # 2. Exact Constant-Elasticity Demand Formula: Q_1 = Q_0 * (P_1 / P_0)^eps
        price_ratio = p1 / p0
        q1 = round(q0 * (price_ratio ** eps), 2)

        # 3. Revenue Arithmetic
        rev0 = round(p0 * q0, 2)
        rev1 = round(p1 * q1, 2)
        rev_change = round(rev1 - rev0, 2)
        pct_rev_change = round((rev_change / rev0) * 100.0, 2) if rev0 > 0 else 0.0

        # 4. Gross Contribution (if cost per unit available)
        base_contrib = None
        pred_contrib = None
        if cost_per_unit is not None:
            c = float(cost_per_unit)
            base_contrib = round((p0 - c) * q0, 2)
            pred_contrib = round((p1 - c) * q1, 2)

        # 5. Sensitivity Uncertainty Bounds (low elasticity = eps * 0.8, high = eps * 1.2)
        eps_conservative = eps * 0.80
        eps_aggressive = eps * 1.20
        q1_conservative = round(q0 * (price_ratio ** eps_conservative), 2)
        q1_aggressive = round(q0 * (price_ratio ** eps_aggressive), 2)

        scen_id = scenario_id or f"SCEN_{target_model.upper()}_{int(pct_price_change * 100):+d}PCT"
        res_id = f"RES_{scen_id}"

        return ScenarioResult(
            result_id=res_id,
            scenario_id=scen_id,
            alternative_id=alternative_id,
            target_model=target_model,
            baseline_price=p0,
            scenario_price=p1,
            baseline_quantity=q0,
            predicted_quantity=q1,
            baseline_revenue=rev0,
            predicted_revenue=rev1,
            revenue_change=rev_change,
            pct_revenue_change=pct_rev_change,
            baseline_contribution=base_contrib,
            predicted_contribution=pred_contrib,
            assumed_elasticity=eps,
            elasticity_type="ASSUMED_PRIOR",
            elasticity_provenance=(
                f"ASSUMED_INDUSTRY_PRIOR: {eps:.2f} based on compact sedan historical econometrics; "
                "empirical estimation requires longitudinal price-ladder natural experiment variation"
            ),
            cost_or_margin_modeled=(cost_per_unit is not None),
            profit_optimization_claimed=False,
            uncertainty_range={
                "quantity_conservative": q1_conservative,
                "quantity_aggressive": q1_aggressive,
                "revenue_conservative": round(p1 * q1_conservative, 2),
                "revenue_aggressive": round(p1 * q1_aggressive, 2),
            },
            constraints_violated=[],
            model_run_id=f"MRUN_PRICING_ENGINE_v1.2",
        )

    def evaluate_standard_alternatives(
        self,
        target_model: str,
        baseline_price: float,
        baseline_quantity: float,
        cost_per_unit: Optional[float] = None,
        custom_pct: Optional[float] = None,
    ) -> List[ScenarioResult]:
        """
        Evaluates standard decision alternatives:
          • Status Quo: 0% price change
          • Competitive Repositioning: -3% price reduction
          • Aggressive Volume Expansion: -5% price reduction
          • Premium Margin Expansion: +5% price increase
          • Custom alternative if provided
        """
        deltas = [
            ("Status Quo (0%)", 0.0),
            ("Competitive Repositioning (-3%)", -0.03),
            ("Aggressive Volume Expansion (-5%)", -0.05),
            ("Premium Margin Expansion (+5%)", +0.05),
        ]
        if custom_pct is not None and custom_pct not in [0.0, -0.03, -0.05, 0.05]:
            deltas.append((f"Custom Alternative ({custom_pct * 100:+.1f}%)", custom_pct))

        results = []
        for name, delta in deltas:
            scen_res = self.simulate(
                target_model=target_model,
                baseline_price=baseline_price,
                baseline_quantity=baseline_quantity,
                pct_price_change=delta,
                cost_per_unit=cost_per_unit,
                scenario_id=f"SCEN_{target_model.upper()}_{int(delta*100):+d}PCT",
            )
            results.append(scen_res)

        return results
