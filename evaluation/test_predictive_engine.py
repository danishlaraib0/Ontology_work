"""
test_predictive_engine.py
=========================
Automated test suite validating the Predictive Layer of the Automotive World Model:
  1. Historical Data Coverage Audit (Action 1)
  2. Multi-model Baseline Selection & Backtesting (Action 2)
  3. Prediction Intervals & Multi-Month Horizons (Action 2)
  4. Scenario Engine Counterfactuals (Action 3)
  5. Neo4j Graph Persistence & Provenance Segregation (Action 4)
  6. Calibration & Reality Evaluation (Action 5)
"""
import unittest
import sys
from pathlib import Path

# Add project root to sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from graph_db.neo4j_client import Neo4jClient
from intelligence.data_coverage_audit import DataCoverageAuditor, DataCoverageAuditReport
from intelligence.sales_forecasting import SalesForecastingEngine, SalesForecastResult
from intelligence.forecast_evaluator import ForecastEvaluator, ForecastEvaluationSummary


class TestAutomotivePredictiveEngine(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = Neo4jClient()
        cls.auditor = DataCoverageAuditor(cls.client)
        cls.forecaster = SalesForecastingEngine(cls.client)
        cls.evaluator = ForecastEvaluator(cls.client)

    # ── Test 1: Historical Data Audit (Action 1) ─────────────────────────────
    def test_01_historical_data_coverage_audit(self):
        report = self.auditor.run_full_audit()
        self.assertIsInstance(report, DataCoverageAuditReport)
        self.assertGreaterEqual(len(report.model_records), 20)
        self.assertEqual(len(report.signal_summaries), 4)

        # Verify Dzire has sufficient monthly observations
        dzire_sales = next(
            (r for r in report.model_records if r.model_name == "Dzire" and r.signal_name == "Monthly Sales Dispatches"),
            None,
        )
        self.assertIsNotNone(dzire_sales)
        self.assertEqual(dzire_sales.total_observations, 12)
        self.assertEqual(dzire_sales.consecutive_periods_count, 12)
        self.assertEqual(dzire_sales.feasibility_status, "SUFFICIENT")

        # Verify Wagon R has sufficient observations
        wagon_sales = next(
            (r for r in report.model_records if r.model_name == "Wagon R" and r.signal_name == "Monthly Sales Dispatches"),
            None,
        )
        self.assertIsNotNone(wagon_sales)
        self.assertGreaterEqual(wagon_sales.total_observations, 12)
        self.assertEqual(wagon_sales.feasibility_status, "SUFFICIENT")

    # ── Test 2: Baseline Model Selection & Backtesting (Action 2) ────────────
    def test_02_baseline_model_selection_and_backtest(self):
        result = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        self.assertIsInstance(result, SalesForecastResult)
        self.assertEqual(result.vehicle_model, "Dzire")
        self.assertGreaterEqual(result.historical_count, 12)

        # Backtest model comparison exists
        cmp = result.model_comparison
        self.assertGreaterEqual(len(cmp.models_evaluated), 3)
        self.assertIn(cmp.winning_model, [m.model_type for m in cmp.models_evaluated])
        self.assertGreater(cmp.winning_mape, 0.0)

        # Assert all models have valid metrics
        for m in cmp.models_evaluated:
            self.assertGreater(m.mae, 0.0)
            self.assertGreater(m.mape, 0.0)
            self.assertGreater(m.rmse, 0.0)
            self.assertEqual(len(m.actual_units), len(m.predicted_units))

    # ── Test 3: Multi-Month Forecast & Prediction Intervals (Action 2) ───────
    def test_03_multi_month_forecast_and_intervals(self):
        result = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        self.assertEqual(len(result.forecast_points), 3)

        # Verify chronological periods
        periods = [p.period for p in result.forecast_points]
        self.assertEqual(periods, ["2025-01", "2025-02", "2025-03"])

        # Verify prediction intervals widen with horizon
        span_m1 = result.forecast_points[0].upper_bound_95 - result.forecast_points[0].lower_bound_95
        span_m3 = result.forecast_points[2].upper_bound_95 - result.forecast_points[2].lower_bound_95
        self.assertGreater(span_m3, span_m1, "Uncertainty interval must expand with horizon step")

        for pt in result.forecast_points:
            self.assertGreater(pt.predicted_units, 5000)
            self.assertLess(pt.lower_bound_80, pt.predicted_units)
            self.assertGreater(pt.upper_bound_80, pt.predicted_units)
            self.assertLess(pt.lower_bound_95, pt.lower_bound_80)
            self.assertGreater(pt.upper_bound_95, pt.upper_bound_80)

    # ── Test 4: Scenario Engine Price Reduction (Action 3) ───────────────────
    def test_04_scenario_engine_price_reduction(self):
        baseline = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        base_m1 = baseline.forecast_points[0].predicted_units

        scen = {
            "type": "PRICE_REDUCTION",
            "event": "GST 2.0 Price Reduction of 5%",
            "price_change_pct": -0.05,
            "elasticity": -0.9,
            "assumptions": "5% price drop stimulates +4.5% volume elasticity",
            "affected_entities": ["Aura", "Amaze"],
        }
        scen_result = self.forecaster.generate_forecast("Dzire", horizon_months=3, scenario=scen)
        scen_m1 = scen_result.forecast_points[0].predicted_units

        self.assertTrue(scen_result.is_scenario)
        self.assertGreater(scen_m1, base_m1, "Price reduction must increase forecasted volume")
        self.assertGreater(scen_result.forecast_points[0].scenario_delta_units, 0)
        self.assertIn("Aura", scen_result.affected_entities)

    # ── Test 5: Scenario Engine Competitor Disruption (Action 3) ─────────────
    def test_05_scenario_engine_competitor_disruption(self):
        baseline = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        base_m1 = baseline.forecast_points[0].predicted_units

        scen = {
            "type": "COMPETITOR_DISRUPTION",
            "event": "Rival Compact Sedan Refresh Launch",
            "volume_loss_pct": -0.08,
            "assumptions": "Rival launch causes 8% share loss",
            "affected_entities": ["Amaze"],
        }
        scen_result = self.forecaster.generate_forecast("Dzire", horizon_months=3, scenario=scen)
        scen_m1 = scen_result.forecast_points[0].predicted_units

        self.assertLess(scen_m1, base_m1, "Competitor disruption must decrease forecasted volume")
        self.assertLess(scen_result.forecast_points[0].scenario_delta_units, 0)

    # ── Test 6: Neo4j Graph Persistence & Provenance Segregation (Action 4) ──
    def test_06_neo4j_forecast_persistence_and_separation(self):
        forecast = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        persist_stats = self.forecaster.persist_forecast_to_graph(forecast)

        self.assertGreaterEqual(persist_stats["nodes_created"], 4)
        self.assertGreaterEqual(persist_stats["relationships_created"], 7)

        # Verify ForecastRun node exists in Neo4j
        run_record = self.client.query(
            "MATCH (fr:ForecastRun {run_id: $rid}) RETURN fr.vehicle_model AS model, fr.model_version AS ver",
            {"rid": forecast.run_id},
        )
        self.assertEqual(len(run_record), 1)
        self.assertEqual(run_record[0]["model"], "Dzire")

        # Verify Predictions are linked to ForecastRun and have provenance
        pred_records = self.client.query(
            """
            MATCH (fr:ForecastRun {run_id: $rid})-[:PREDICTS]->(sp:SalesPrediction)
            OPTIONAL MATCH (sp)-[:BASED_ON_OBSERVATION]->(so:SalesObservation)
            RETURN sp.target_period AS period, sp.predicted_units AS units, so.period_value AS last_obs
            ORDER BY sp.target_period ASC
            """,
            {"rid": forecast.run_id},
        )
        self.assertEqual(len(pred_records), 3)
        self.assertEqual(pred_records[0]["period"], "2025-01")
        self.assertEqual(pred_records[0]["last_obs"], "2024-12")

        # Invariant: SalesObservation count must NOT have changed (predictions separated from facts)
        obs_count = self.client.query(
            "MATCH (v:VehicleModel {name: 'Dzire'})-[:HAS_SALES_OBSERVATION]->(s:SalesObservation) WHERE s.period_type = 'MONTH' RETURN count(s) AS c"
        )[0]["c"]
        self.assertEqual(obs_count, 12, "SalesObservation nodes must remain strictly observed facts")

    # ── Test 7: Calibration & Reality Evaluation (Action 5) ───────────────────
    def test_07_reality_evaluation_and_calibration(self):
        forecast = self.forecaster.generate_forecast("Dzire", horizon_months=3)
        mock_actuals = {
            "2025-01": 16200,
            "2025-02": 15100,
            "2025-03": 16800,
        }
        eval_res = self.evaluator.evaluate_forecast(forecast, known_actuals=mock_actuals)

        self.assertIsInstance(eval_res, ForecastEvaluationSummary)
        self.assertEqual(eval_res.vehicle_model, "Dzire")
        self.assertGreater(eval_res.overall_mae, 0.0)
        self.assertLess(eval_res.overall_mape, 15.0)  # Accurate within 15%
        self.assertEqual(eval_res.coverage_95_pct, 100.0)
        self.assertFalse(eval_res.is_drift_detected)
        self.assertEqual(eval_res.drift_verdict, "WELL_CALIBRATED")

    # ── Test 8: Wagon R Forecasting Validation ───────────────────────────────
    def test_08_wagon_r_forecasting(self):
        forecast = self.forecaster.generate_forecast("Wagon R", horizon_months=3)
        self.assertEqual(forecast.vehicle_model, "Wagon R")
        self.assertGreaterEqual(forecast.historical_count, 12)
        self.assertEqual(len(forecast.forecast_points), 3)
        self.assertGreater(forecast.forecast_points[0].predicted_units, 10000)


if __name__ == "__main__":
    unittest.main(verbosity=2)
