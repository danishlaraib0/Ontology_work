"""
sales_forecasting.py
====================
Validated Sales Forecasting & Predictive Baseline Engine for the Automotive World Model.
Implements Action Items 2, 3, and 4:
  1. Statistical & Time-Series Baselines:
     • Naïve Baseline (yt)
     • 3-Month Simple Moving Average (SMA-3)
     • Holt's Linear Trend Exponential Smoothing (SES / Holt Level + Trend)
     • Linear Autoregressive Drift Trend
  2. Time-Based Backtesting & Validation:
     • Calculates MAE, MAPE, RMSE across historical holdout sets
     • Automatically selects the empirical winning model
  3. Prediction Intervals & Horizon Projections:
     • Multi-month forecasts (1, 2, 3+ months ahead)
     • Calibrated 80% and 95% uncertainty intervals based on residual volatility
  4. Scenario Engine (Counterfactual Simulations):
     • Defensible scenario simulation (Price cuts with segment elasticity, rival feature shocks)
     • Compares baseline vs scenario with explicit assumptions and uncertainty bands
  5. Neo4j Graph Traceability:
     • Persists ForecastRun and SalesPrediction nodes in Neo4j
     • Links predictions to input observations and rival entities while keeping
       predictions strictly segregated from observed facts
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from graph_db.neo4j_client import Neo4jClient
from graph_db.canonical_ids import (
    canonical_forecast_run_id,
    canonical_sales_prediction_id,
    canonical_vehicle_model_id,
    canonical_sales_obs_id,
)

logger = logging.getLogger(__name__)


@dataclass
class ForecastHorizonPoint:
    """A single monthly predicted dispatch point with uncertainty intervals."""
    period: str  # YYYY-MM
    predicted_units: int
    lower_bound_80: int
    upper_bound_80: int
    lower_bound_95: int
    upper_bound_95: int
    is_scenario: bool = False
    scenario_delta_units: int = 0
    scenario_assumptions: str = ""


@dataclass
class BacktestMetrics:
    """Empirical accuracy metrics on historical holdout periods."""
    model_type: str
    test_periods: List[str]
    actual_units: List[int]
    predicted_units: List[int]
    mae: float
    mape: float  # Percentage, e.g. 5.8%
    rmse: float


@dataclass
class BaselineModelComparison:
    """Comparison of candidate baseline models on holdout test set."""
    models_evaluated: List[BacktestMetrics]
    winning_model: str
    winning_mape: float
    comparison_summary: str


@dataclass
class SalesForecastResult:
    """Complete predictive sales forecasting output with validation and intervals."""
    vehicle_model: str
    vehicle_model_id: str
    run_id: str
    run_date: str
    selected_model_type: str
    historical_count: int
    history_start: str
    history_end: str
    model_comparison: BaselineModelComparison
    forecast_points: List[ForecastHorizonPoint]
    prediction_intervals_explained: str
    data_limitations: List[str]
    is_scenario: bool = False
    scenario_event: str = ""
    scenario_assumptions: str = ""
    affected_entities: List[str] = field(default_factory=list)


class SalesForecastingEngine:
    """
    Executes validated statistical forecasting, backtesting, scenario simulation,
    and graph persistence over vehicle monthly dispatches.
    """

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def fetch_historical_series(self, model_name: str) -> List[Dict[str, Any]]:
        """
        Retrieves chronological monthly sales dispatches for a vehicle model from Neo4j.
        """
        cypher = """
        MATCH (v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (v)-[:HAS_SALES_OBSERVATION]->(s:SalesObservation)
        WHERE s.period_type = 'MONTH'
        RETURN s.period_value AS period,
               s.units_sold AS units,
               s.yoy_change_percent AS yoy,
               s.source_name AS source
        ORDER BY s.period_value ASC
        """
        rows = self.client.query(cypher, {"model": model_name})
        return rows

    def generate_forecast(
        self,
        model_name: str,
        horizon_months: int = 3,
        scenario: Optional[Dict[str, Any]] = None,
        run_date: Optional[str] = None,
    ) -> SalesForecastResult:
        """
        Generates a validated sales forecast:
          1. Audits and fetches historical series.
          2. Runs time-based backtest across candidate baselines.
          3. Selects best baseline and projects forward with 80% & 95% intervals.
          4. Applies scenario shocks if specified.
        """
        logger.info(f"📈 Generating Sales Forecast for [{model_name}] (Horizon: {horizon_months}m)...")
        series = self.fetch_historical_series(model_name)
        if len(series) < 3:
            raise ValueError(
                f"Insufficient historical observations for {model_name}. "
                f"Requires at least 3 monthly observations for forecasting (found {len(series)})."
            )

        run_dt = run_date or datetime.now().strftime("%Y-%m-%d")

        # ── 1. Time-Based Backtest Model Selection ────────────────────────────
        comparison = self._run_backtests(series)
        selected_model = comparison.winning_model

        # ── 2. Fit Selected Model on Full History & Project ───────────────────
        full_actuals = [int(p["units"]) for p in series]
        forecast_points, residual_std = self._project_horizon(
            series=series,
            model_type=selected_model,
            horizon=horizon_months,
            scenario=scenario,
        )

        # ── 3. Handle Scenario Context ────────────────────────────────────────
        is_scen = scenario is not None
        scen_event = scenario.get("event", "Hypothetical Scenario") if is_scen else ""
        scen_assump = scenario.get("assumptions", "") if is_scen else ""
        affected_entities = scenario.get("affected_entities", []) if is_scen else []

        # Canonical IDs resolved dynamically from Neo4j
        brand_name = "Automaker"
        veh_id = None
        if self.client and self.client.is_healthy():
            try:
                b_res = self.client.query("""
                    MATCH (v:VehicleModel)
                    WHERE toLower(v.name) = toLower($model)
                    OPTIONAL MATCH (b:Brand)-[:PRODUCES]->(v)
                    RETURN coalesce(v.vehicle_model_id, '') AS veh_id, coalesce(b.name, v.brand_id, 'Automaker') AS brand
                    LIMIT 1
                """, {"model": model_name})
                if b_res and b_res[0].get("veh_id"):
                    veh_id = b_res[0]["veh_id"]
                    brand_name = b_res[0].get("brand") or "Automaker"
            except Exception as e:
                logger.debug(f"Dynamic brand resolution for {model_name}: {e}")

        if not veh_id:
            veh_id = canonical_vehicle_model_id(brand_name, model_name)
        run_id = canonical_forecast_run_id(model_name, selected_model, run_dt)

        interval_explanation = (
            f"Prediction intervals calculated from historical residual standard deviation (σ = {residual_std:,.0f} units). "
            f"80% bounds use ±1.28σ√h; 95% bounds use ±1.96σ√h where h is horizon step."
        )

        limitations = [
            f"Historical training window is bounded between {series[0]['period']} and {series[-1]['period']} ({len(series)} months).",
            "Wholesale dispatches capture factory-to-dealer deliveries, which precede consumer retail registration peaks by 2-4 weeks.",
            "Prediction intervals assume Gaussian residual variance; black swan shocks or factory retooling shifts fall outside linear bounds.",
        ]

        result = SalesForecastResult(
            vehicle_model=model_name,
            vehicle_model_id=veh_id,
            run_id=run_id,
            run_date=run_dt,
            selected_model_type=selected_model,
            historical_count=len(series),
            history_start=series[0]["period"],
            history_end=series[-1]["period"],
            model_comparison=comparison,
            forecast_points=forecast_points,
            prediction_intervals_explained=interval_explanation,
            data_limitations=limitations,
            is_scenario=is_scen,
            scenario_event=scen_event,
            scenario_assumptions=scen_assump,
            affected_entities=affected_entities,
        )
        logger.info(
            f"✅ Forecast generated: Model [{selected_model}] chosen with backtest MAPE {comparison.winning_mape:.1f}%. "
            f"Next-month forecast: {forecast_points[0].predicted_units:,} units."
        )
        return result

    def _run_backtests(self, series: List[Dict[str, Any]]) -> BaselineModelComparison:
        """
        Splits series into train and holdout test set to evaluate 4 candidate baselines.
        """
        n = len(series)
        # Hold out last 2-3 months for testing, minimum 3 train months
        test_size = 3 if n >= 7 else (2 if n >= 5 else 1)
        train = series[:-test_size]
        test = series[-test_size:]

        train_y = [int(p["units"]) for p in train]
        test_y = [int(p["units"]) for p in test]
        test_periods = [p["period"] for p in test]

        candidates = [
            ("Naïve Baseline", self._predict_naive(train_y, len(test_y))),
            ("3-Month Moving Average (SMA-3)", self._predict_sma(train_y, len(test_y))),
            ("Holt Linear Trend (SES)", self._predict_holt(train_y, len(test_y))),
            ("Linear Autoregressive Trend", self._predict_linear_trend(train_y, len(test_y))),
        ]

        evaluated: List[BacktestMetrics] = []
        for name, preds in candidates:
            mae = sum(abs(a - p) for a, p in zip(test_y, preds)) / len(test_y)
            mape = (sum(abs(a - p) / a for a, p in zip(test_y, preds)) / len(test_y)) * 100.0
            rmse = math.sqrt(sum((a - p) ** 2 for a, p in zip(test_y, preds)) / len(test_y))

            evaluated.append(
                BacktestMetrics(
                    model_type=name,
                    test_periods=test_periods,
                    actual_units=test_y,
                    predicted_units=preds,
                    mae=round(mae, 1),
                    mape=round(mape, 2),
                    rmse=round(rmse, 1),
                )
            )

        # Select model with lowest MAPE
        evaluated.sort(key=lambda m: m.mape)
        winner = evaluated[0]

        summary = (
            f"Evaluated {len(evaluated)} baseline models on holdout test set {test_periods[0]} → {test_periods[-1]}. "
            f"Winning model: '{winner.model_type}' achieved lowest backtest error (MAPE: {winner.mape:.1f}%, MAE: {winner.mae:,.0f} units)."
        )

        return BaselineModelComparison(
            models_evaluated=evaluated,
            winning_model=winner.model_type,
            winning_mape=winner.mape,
            comparison_summary=summary,
        )

    def _project_horizon(
        self,
        series: List[Dict[str, Any]],
        model_type: str,
        horizon: int,
        scenario: Optional[Dict[str, Any]],
    ) -> Tuple[List[ForecastHorizonPoint], float]:
        """
        Applies selected model to full series and projects forward with uncertainty bounds.
        """
        y = [int(p["units"]) for p in series]
        last_period = series[-1]["period"]
        future_periods = self._generate_future_periods(last_period, horizon)

        # Raw baseline forecasts
        if "Naïve" in model_type:
            raw_preds = self._predict_naive(y, horizon)
        elif "Moving Average" in model_type or "SMA" in model_type:
            raw_preds = self._predict_sma(y, horizon)
        elif "Holt" in model_type:
            raw_preds = self._predict_holt(y, horizon)
        else:
            raw_preds = self._predict_linear_trend(y, horizon)

        # Compute in-sample residual standard deviation for prediction intervals
        in_sample_preds = self._compute_in_sample_fits(y, model_type)
        residuals = [actual - pred for actual, pred in zip(y[1:], in_sample_preds[1:])]
        residual_std = (
            math.sqrt(sum(r ** 2 for r in residuals) / len(residuals))
            if len(residuals) > 0
            else y[-1] * 0.10
        )

        # Scenario adjustments
        scenario_multiplier = 1.0
        scenario_notes = ""
        if scenario:
            scen_type = scenario.get("type", "").upper()
            if scen_type == "PRICE_REDUCTION":
                # Price elasticity of demand: % Delta Q = Elasticity * % Delta P
                # For price drop (-5%) and negative elasticity (-0.9): -0.05 * -0.9 = +0.045 (+4.5% volume uplift)
                pct_price_change = float(scenario.get("price_change_pct", -0.05))
                elasticity = float(scenario.get("elasticity", -0.9))
                volume_uplift = pct_price_change * elasticity
                scenario_multiplier = 1.0 + volume_uplift
                scenario_notes = f"Price reduction of {abs(pct_price_change)*100:.1f}% stimulated +{volume_uplift*100:.1f}% volume (Elasticity: {elasticity})."
            elif scen_type == "COMPETITOR_DISRUPTION":
                # Rival market share erosion: -5% to -12%
                market_share_erosion = float(scenario.get("volume_loss_pct", -0.08))
                scenario_multiplier = 1.0 + market_share_erosion
                scenario_notes = f"Competitor launch provoked {market_share_erosion*100:.1f}% volume contraction."
            elif scen_type == "FESTIVE_SEASON_UPLIFT":
                uplift = float(scenario.get("uplift_pct", 0.15))
                scenario_multiplier = 1.0 + uplift
                scenario_notes = f"Q3/Q4 festive seasonal surge (+{uplift*100:.1f}%)."

        points: List[ForecastHorizonPoint] = []
        for h, (p_str, base_val) in enumerate(zip(future_periods, raw_preds), start=1):
            scen_val = int(round(base_val * scenario_multiplier))
            delta = scen_val - base_val

            # Expanding prediction intervals with horizon step h: std * sqrt(h)
            h_std = residual_std * math.sqrt(h)
            low_80 = max(0, int(round(scen_val - 1.28 * h_std)))
            high_80 = int(round(scen_val + 1.28 * h_std))
            low_95 = max(0, int(round(scen_val - 1.96 * h_std)))
            high_95 = int(round(scen_val + 1.96 * h_std))

            points.append(
                ForecastHorizonPoint(
                    period=p_str,
                    predicted_units=scen_val,
                    lower_bound_80=low_80,
                    upper_bound_80=high_80,
                    lower_bound_95=low_95,
                    upper_bound_95=high_95,
                    is_scenario=scenario is not None,
                    scenario_delta_units=delta,
                    scenario_assumptions=scenario_notes if scenario else "",
                )
            )

        return points, residual_std

    # ── Baseline Modeling Primitives ─────────────────────────────────────────
    def _predict_naive(self, y: List[int], horizon: int) -> List[int]:
        """Naïve baseline: yt+h = yt."""
        return [y[-1]] * horizon

    def _predict_sma(self, y: List[int], horizon: int, window: int = 3) -> List[int]:
        """Moving average baseline over trailing window (default 3 months)."""
        w = min(window, len(y))
        avg_val = int(round(sum(y[-w:]) / w))
        return [avg_val] * horizon

    def _predict_holt(self, y: List[int], horizon: int, alpha: float = 0.4, beta: float = 0.2) -> List[int]:
        """Holt's Linear Trend Exponential Smoothing."""
        if len(y) < 2:
            return self._predict_naive(y, horizon)

        level = float(y[0])
        trend = float(y[1] - y[0])

        for val in y[1:]:
            prev_level = level
            level = alpha * float(val) + (1.0 - alpha) * (level + trend)
            trend = beta * (level - prev_level) + (1.0 - beta) * trend

        preds = []
        for h in range(1, horizon + 1):
            projected = int(round(max(0.0, level + h * trend)))
            preds.append(projected)
        return preds

    def _predict_linear_trend(self, y: List[int], horizon: int) -> List[int]:
        """Linear autoregressive drift regression: y = a + b * t."""
        n = len(y)
        if n < 2:
            return self._predict_naive(y, horizon)

        t_vals = list(range(n))
        t_mean = sum(t_vals) / n
        y_mean = sum(y) / n

        num = sum((t - t_mean) * (val - y_mean) for t, val in zip(t_vals, y))
        den = sum((t - t_mean) ** 2 for t in t_vals)
        slope = num / den if den != 0 else 0.0
        intercept = y_mean - slope * t_mean

        preds = []
        for h in range(1, horizon + 1):
            t_future = n - 1 + h
            projected = int(round(max(0.0, intercept + slope * t_future)))
            preds.append(projected)
        return preds

    def _compute_in_sample_fits(self, y: List[int], model_type: str) -> List[int]:
        """Computes in-sample fitted values to estimate residual variance."""
        fits = [y[0]]
        for i in range(1, len(y)):
            history = y[:i]
            if "Naïve" in model_type:
                fits.append(self._predict_naive(history, 1)[0])
            elif "Moving Average" in model_type or "SMA" in model_type:
                fits.append(self._predict_sma(history, 1)[0])
            elif "Holt" in model_type:
                fits.append(self._predict_holt(history, 1)[0])
            else:
                fits.append(self._predict_linear_trend(history, 1)[0])
        return fits

    def _generate_future_periods(self, last_period: str, horizon: int) -> List[str]:
        """Generates future YYYY-MM period strings from last observed period."""
        y_str, m_str = last_period.split("-")
        curr_y = int(y_str)
        curr_m = int(m_str)

        future = []
        for _ in range(horizon):
            curr_m += 1
            if curr_m > 12:
                curr_m = 1
                curr_y += 1
            future.append(f"{curr_y}-{curr_m:02d}")
        return future

    # ── Neo4j Graph Persistence (Action 4) ────────────────────────────────────
    def persist_forecast_to_graph(self, forecast: SalesForecastResult) -> Dict[str, int]:
        """
        Merges ForecastRun and SalesPrediction nodes into Neo4j.
        Segregates predictions from observed facts while connecting input provenance.
        """
        logger.info(f"💾 Persisting ForecastRun [{forecast.run_id}] to Neo4j...")
        nodes_created = 0
        rels_created = 0

        # 1. Merge ForecastRun node
        run_cypher = """
        MERGE (fr:ForecastRun {run_id: $run_id})
        SET fr.vehicle_model = $model,
            fr.model_version = $model_type,
            fr.run_date = $run_date,
            fr.historical_count = $hist_count,
            fr.history_start = $hist_start,
            fr.history_end = $hist_end,
            fr.backtest_mape = $mape,
            fr.is_scenario = $is_scenario,
            fr.scenario_event = $scen_event,
            fr.scenario_assumptions = $scen_assump
        RETURN fr.run_id AS id
        """
        self.client.query(run_cypher, {
            "run_id": forecast.run_id,
            "model": forecast.vehicle_model,
            "model_type": forecast.selected_model_type,
            "run_date": forecast.run_date,
            "hist_count": forecast.historical_count,
            "hist_start": forecast.history_start,
            "hist_end": forecast.history_end,
            "mape": forecast.model_comparison.winning_mape,
            "is_scenario": forecast.is_scenario,
            "scen_event": forecast.scenario_event,
            "scen_assump": forecast.scenario_assumptions,
        })
        nodes_created += 1

        # 2. Connect VehicleModel -[:HAS_FORECAST_RUN]-> ForecastRun
        veh_run_cypher = """
        MATCH (v:VehicleModel)
        WHERE toLower(v.name) = toLower($model)
        MATCH (fr:ForecastRun {run_id: $run_id})
        MERGE (v)-[r:HAS_FORECAST_RUN]->(fr)
        SET r.run_date = fr.run_date
        """
        self.client.query(veh_run_cypher, {"model": forecast.vehicle_model, "run_id": forecast.run_id})
        rels_created += 1

        # 3. Merge SalesPrediction nodes and connect to ForecastRun
        last_obs_period = forecast.history_end
        for p in forecast.forecast_points:
            pred_id = canonical_sales_prediction_id(forecast.run_id, p.period)

            pred_cypher = """
            MERGE (sp:SalesPrediction {prediction_id: $pred_id})
            SET sp.target_period = $period,
                sp.predicted_units = $units,
                sp.lower_bound_80 = $low_80,
                sp.upper_bound_80 = $high_80,
                sp.lower_bound_95 = $low_95,
                sp.upper_bound_95 = $high_95,
                sp.is_scenario = $is_scen,
                sp.scenario_delta_units = $scen_delta,
                sp.scenario_assumptions = $scen_assump
            """
            self.client.query(pred_cypher, {
                "pred_id": pred_id,
                "period": p.period,
                "units": p.predicted_units,
                "low_80": p.lower_bound_80,
                "high_80": p.upper_bound_80,
                "low_95": p.lower_bound_95,
                "high_95": p.upper_bound_95,
                "is_scen": p.is_scenario,
                "scen_delta": p.scenario_delta_units,
                "scen_assump": p.scenario_assumptions,
            })
            nodes_created += 1

            # Connect ForecastRun -[:PREDICTS]-> SalesPrediction
            pred_rel_cypher = """
            MATCH (fr:ForecastRun {run_id: $run_id})
            MATCH (sp:SalesPrediction {prediction_id: $pred_id})
            MERGE (fr)-[:PREDICTS]->(sp)
            """
            self.client.query(pred_rel_cypher, {"run_id": forecast.run_id, "pred_id": pred_id})
            rels_created += 1

            # Connect SalesPrediction -[:BASED_ON_OBSERVATION]-> SalesObservation (provenance trace)
            prov_cypher = """
            MATCH (sp:SalesPrediction {prediction_id: $pred_id})
            MATCH (so:SalesObservation {period_value: $last_period})<-[:HAS_SALES_OBSERVATION]-(v:VehicleModel)
            WHERE toLower(v.name) = toLower($model)
            MERGE (sp)-[:BASED_ON_OBSERVATION]->(so)
            """
            self.client.query(prov_cypher, {
                "pred_id": pred_id,
                "last_period": last_obs_period,
                "model": forecast.vehicle_model,
            })
            rels_created += 1

        # 4. If scenario affects rivals, link SalesPrediction -[:IMPACTS_COMPETITOR]-> Rival
        if forecast.is_scenario and forecast.affected_entities:
            for aff in forecast.affected_entities:
                aff_cypher = """
                MATCH (fr:ForecastRun {run_id: $run_id})-[:PREDICTS]->(sp:SalesPrediction)
                MATCH (rival:VehicleModel)
                WHERE toLower(rival.name) = toLower($rival_name)
                MERGE (sp)-[:IMPACTS_COMPETITOR]->(rival)
                """
                self.client.query(aff_cypher, {"run_id": forecast.run_id, "rival_name": aff})
                rels_created += 1

        logger.info(f"✅ Persisted {nodes_created} forecast nodes and {rels_created} relationships to Neo4j.")
        return {"nodes_created": nodes_created, "relationships_created": rels_created}
