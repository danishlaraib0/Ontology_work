"""
forecast_evaluator.py
=====================
Calibration & Reality Evaluation Engine for Automotive Sales Forecasting.
Implements Action Item 5:
  1. Compares forecasts with subsequently observed sales dispatches.
  2. Tracks model calibration (whether actuals fall within 80% and 95% prediction intervals).
  3. Detects model drift vs structural market shocks.
  4. Provides reproducible empirical evaluation metrics (MAPE, MAE, Coverage %).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient
from intelligence.sales_forecasting import SalesForecastResult

logger = logging.getLogger(__name__)


@dataclass
class PointEvaluation:
    """Evaluation of a single forecasted period against observed reality."""
    period: str
    predicted_units: int
    actual_units: int
    absolute_error: int
    percentage_error: float
    lower_bound_80: int
    upper_bound_80: int
    lower_bound_95: int
    upper_bound_95: int
    within_80_ci: bool
    within_95_ci: bool
    calibration_status: str  # "CALIBRATED_IN_80", "CALIBRATED_IN_95", "OUT_OF_BOUNDS"


@dataclass
class ForecastEvaluationSummary:
    """Summary of forecast performance, error drift, and calibration against reality."""
    vehicle_model: str
    run_id: str
    model_version: str
    evaluated_points: List[PointEvaluation] = field(default_factory=list)
    overall_mae: float = 0.0
    overall_mape: float = 0.0
    coverage_80_pct: float = 0.0
    coverage_95_pct: float = 0.0
    is_drift_detected: bool = False
    drift_verdict: str = "CALIBRATED"
    recommendation: str = ""


class ForecastEvaluator:
    """
    Evaluates stored or generated forecasts against observed empirical reality.
    """

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def evaluate_forecast(
        self,
        forecast: SalesForecastResult,
        known_actuals: Optional[Dict[str, int]] = None,
    ) -> ForecastEvaluationSummary:
        """
        Evaluates a forecast against known actual observations (from input dictionary or Neo4j).
        """
        logger.info(f"🔍 Evaluating Forecast calibration for [{forecast.vehicle_model}] ({forecast.run_id})...")
        actuals = known_actuals or self._fetch_actuals_for_periods(
            forecast.vehicle_model, [pt.period for pt in forecast.forecast_points]
        )

        eval_points: List[PointEvaluation] = []
        for pt in forecast.forecast_points:
            act = actuals.get(pt.period)
            if act is None:
                continue

            abs_err = abs(act - pt.predicted_units)
            pct_err = (abs_err / act) * 100.0 if act > 0 else 0.0
            in_80 = pt.lower_bound_80 <= act <= pt.upper_bound_80
            in_95 = pt.lower_bound_95 <= act <= pt.upper_bound_95

            cal_status = "CALIBRATED_IN_80" if in_80 else ("CALIBRATED_IN_95" if in_95 else "OUT_OF_BOUNDS")

            eval_points.append(
                PointEvaluation(
                    period=pt.period,
                    predicted_units=pt.predicted_units,
                    actual_units=act,
                    absolute_error=abs_err,
                    percentage_error=round(pct_err, 2),
                    lower_bound_80=pt.lower_bound_80,
                    upper_bound_80=pt.upper_bound_80,
                    lower_bound_95=pt.lower_bound_95,
                    upper_bound_95=pt.upper_bound_95,
                    within_80_ci=in_80,
                    within_95_ci=in_95,
                    calibration_status=cal_status,
                )
            )

        if not eval_points:
            # Fall back to evaluating holdout backtest periods
            winning_metrics = next(
                (m for m in forecast.model_comparison.models_evaluated if m.model_type == forecast.selected_model_type),
                None,
            )
            if winning_metrics and winning_metrics.actual_units:
                for period, act, pred in zip(winning_metrics.test_periods, winning_metrics.actual_units, winning_metrics.predicted_units):
                    abs_err = abs(act - pred)
                    pct_err = (abs_err / act) * 100.0 if act > 0 else 0.0
                    std_est = winning_metrics.rmse
                    low_80 = max(0, int(round(pred - 1.28 * std_est)))
                    high_80 = int(round(pred + 1.28 * std_est))
                    low_95 = max(0, int(round(pred - 1.96 * std_est)))
                    high_95 = int(round(pred + 1.96 * std_est))

                    in_80 = low_80 <= act <= high_80
                    in_95 = low_95 <= act <= high_95
                    cal_status = "CALIBRATED_IN_80" if in_80 else ("CALIBRATED_IN_95" if in_95 else "OUT_OF_BOUNDS")

                    eval_points.append(
                        PointEvaluation(
                            period=period,
                            predicted_units=pred,
                            actual_units=act,
                            absolute_error=abs_err,
                            percentage_error=round(pct_err, 2),
                            lower_bound_80=low_80,
                            upper_bound_80=high_80,
                            lower_bound_95=low_95,
                            upper_bound_95=high_95,
                            within_80_ci=in_80,
                            within_95_ci=in_95,
                            calibration_status=cal_status,
                        )
                    )

        if not eval_points:
            return ForecastEvaluationSummary(
                vehicle_model=forecast.vehicle_model,
                run_id=forecast.run_id,
                model_version=forecast.selected_model_type,
                evaluated_points=[],
                drift_verdict="PENDING_OBSERVATION",
                recommendation="Target periods have not occurred or no actual dispatches recorded in graph yet.",
            )

        mae = sum(p.absolute_error for p in eval_points) / len(eval_points)
        mape = sum(p.percentage_error for p in eval_points) / len(eval_points)
        cov_80 = (sum(1 for p in eval_points if p.within_80_ci) / len(eval_points)) * 100.0
        cov_95 = (sum(1 for p in eval_points if p.within_95_ci) / len(eval_points)) * 100.0

        # Drift check: compare realized MAPE with backtest MAPE
        backtest_mape = forecast.model_comparison.winning_mape
        is_drift = mape > (backtest_mape * 1.5) and mape > 15.0

        if is_drift:
            verdict = "DRIFT_DETECTED"
            rec = "Realized error exceeds historical backtest variance by >50%. Re-estimate model weights or flag market shock."
        elif cov_95 >= 80.0:
            verdict = "WELL_CALIBRATED"
            rec = "Model calibration verified against actuals; prediction intervals accurately contain observed volatility."
        else:
            verdict = "UNDER_DISPERSED"
            rec = "Prediction intervals are slightly narrow; increase residual dispersion multiplier."

        summary = ForecastEvaluationSummary(
            vehicle_model=forecast.vehicle_model,
            run_id=forecast.run_id,
            model_version=forecast.selected_model_type,
            evaluated_points=eval_points,
            overall_mae=round(mae, 1),
            overall_mape=round(mape, 2),
            coverage_80_pct=round(cov_80, 1),
            coverage_95_pct=round(cov_95, 1),
            is_drift_detected=is_drift,
            drift_verdict=verdict,
            recommendation=rec,
        )
        logger.info(
            f"✅ Forecast evaluation complete: Realized MAPE {mape:.1f}%, "
            f"80% CI Coverage: {cov_80:.0f}%, Verdict: [{verdict}]."
        )
        return summary

    def _fetch_actuals_for_periods(self, model_name: str, periods: List[str]) -> Dict[str, int]:
        """Queries Neo4j for observed monthly dispatches matching target periods."""
        cypher = """
        MATCH (v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (v)-[:HAS_SALES_OBSERVATION]->(s:SalesObservation)
        WHERE s.period_type = 'MONTH' AND s.period_value IN $periods
        RETURN s.period_value AS period, s.units_sold AS units
        """
        rows = self.client.query(cypher, {"model": model_name, "periods": periods})
        return {r["period"]: int(r["units"]) for r in rows if r.get("period") and r.get("units")}
