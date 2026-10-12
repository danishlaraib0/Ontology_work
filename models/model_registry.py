"""
model_registry.py
=================
Lightweight analytical model registry for the Automotive World Model.
Registers models, algorithms, versioning, input/output schemas, and limitations.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class RegisteredModel:
    model_name: str
    version: str
    description: str
    input_schema: Dict[str, str]
    output_schema: Dict[str, str]
    supported_use_cases: List[str]
    assumptions_and_limitations: List[str]
    deployment_status: str = "PRODUCTION"


class ModelRegistry:
    """Manages metadata and interfaces for deterministic models and ML engines."""

    def __init__(self):
        self._registry: Dict[str, RegisteredModel] = {}
        self._seed_registered_models()

    def _seed_registered_models(self):
        models = [
            RegisteredModel(
                model_name="PricingScenarioEngine",
                version="1.2.0",
                description="Exact constant price elasticity simulation (Q1 = Q0 * (P1/P0)^eps).",
                input_schema={
                    "baseline_price": "float",
                    "baseline_quantity": "float",
                    "pct_price_change": "float",
                    "elasticity": "float (optional, default -0.90)",
                },
                output_schema={
                    "predicted_quantity": "float",
                    "predicted_revenue": "float",
                    "revenue_change": "float",
                    "uncertainty_range": "dict",
                },
                supported_use_cases=["PRICE_SCENARIO", "DECISION_RECOMMENDATION", "COMPETITOR_VULNERABILITY"],
                assumptions_and_limitations=[
                    "Assumes constant price elasticity across target volume range.",
                    "Does not account for sudden supplier inventory or production capacity caps.",
                    "Local approximation valid within +/- 15% price adjustment band.",
                ],
            ),
            RegisteredModel(
                model_name="SalesForecastingEngine",
                version="1.0.0",
                description="Time-series baseline suite (Naive, SMA-3, Holt Linear, Seasonal Naive).",
                input_schema={
                    "monthly_series": "list[dict(period, units_sold)]",
                    "horizon": "int",
                },
                output_schema={
                    "chosen_model": "str",
                    "backtest_mape": "float",
                    "forecast_points": "list[dict]",
                    "prediction_intervals": "list[dict]",
                },
                supported_use_cases=["SALES_FORECAST", "DECISION_RECOMMENDATION"],
                assumptions_and_limitations=[
                    "Requires at least 6 consecutive monthly observations for minimal validity.",
                    "Assumes seasonal stability when historical length >= 12 months.",
                ],
            ),
            RegisteredModel(
                model_name="FitScoringEngine",
                version="1.0.0",
                description="Multi-factor weighted alignment engine scoring vehicles against persona priorities.",
                input_schema={
                    "segment_name": "str",
                    "vehicle_model": "str (optional)",
                },
                output_schema={
                    "fit_percentage": "float",
                    "top_strengths": "list[str]",
                    "key_tradeoffs": "list[str]",
                },
                supported_use_cases=["AUDIENCE_FIT", "COMPETITOR_COMPARISON"],
                assumptions_and_limitations=[
                    "Normalized weights derived from CustomerSegment -> BuyingFactor relationships in Neo4j.",
                ],
            ),
        ]
        for m in models:
            self._registry[m.model_name] = m

    def get_model(self, model_name: str) -> Optional[RegisteredModel]:
        return self._registry.get(model_name)

    def list_models(self) -> List[RegisteredModel]:
        return list(self._registry.values())
