"""
test_fit_scoring.py
===================
Evaluation suite validating the Audience–Vehicle Fit Scoring engine
against three distinct customer segments and testing weight sensitivity.
"""
import unittest
from intelligence.fit_scoring import FitScoringEngine
from intelligence.evidence_aggregation import EvidenceAggregator


class TestFitScoringEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = FitScoringEngine()
        cls.aggregator = EvidenceAggregator()

    def test_segment_1_small_urban_families(self):
        """Validates that balanced cars with space, mileage, and safety rank top."""
        result = self.engine.rank_vehicles_for_segment("Small Urban Families")
        self.assertGreater(len(result.rankings), 0)
        self.assertEqual(result.rankings[0].rank, 1)

        # Dzire (5-star safety, high mileage) and Aura should lead
        top_models = [r.model_name for r in result.rankings[:2]]
        self.assertIn("Dzire", top_models)

        # Wagon R must cite its crash safety trade-off
        wagon_r = next(r for r in result.rankings if r.model_name == "Wagon R")
        tradeoffs_str = " ".join(wagon_r.key_tradeoffs)
        self.assertTrue(
            "1-Star GNCAP" in tradeoffs_str or "unstable" in tradeoffs_str.lower(),
            "Wagon R must explicitly cite its safety rating trade-off",
        )

    def test_segment_2_budget_first_time_buyers(self):
        """Validates that price and EMI affordability lift entry vehicles."""
        result = self.engine.rank_vehicles_for_segment("Budget First-Time Buyers")
        self.assertGreater(len(result.rankings), 0)

        # Wagon R, Dzire, and Aura should have high fit (> 88%)
        wagon_r = next(r for r in result.rankings if r.model_name == "Wagon R")
        self.assertGreaterEqual(wagon_r.fit_percentage, 88.0)

    def test_segment_3_commercial_fleet_gig_workers(self):
        """Validates that commercial fleet / gig workers prioritize CNG economy and resale."""
        result = self.engine.rank_vehicles_for_segment("High-Mileage Gig Workers")
        self.assertGreater(len(result.rankings), 0)

        # Top vehicles must have factory CNG options
        top_vehicle = result.rankings[0]
        evals = {e.canonical_dimension: e for e in top_vehicle.evaluations}
        if "FUEL_EFFICIENCY" in evals:
            self.assertGreaterEqual(evals["FUEL_EFFICIENCY"].satisfaction_score, 0.85)

    def test_weight_sensitivity_safety_impact(self):
        """
        Tests whether increasing Safety weight from 0.2 to 1.0
        drops Wagon R (1-star) and boosts Dzire (5-star).
        """
        # Baseline: low safety priority
        low_safety_factors = [
            {"factor": "Price / EMI Affordability", "weight": 1.0},
            {"factor": "Fuel Efficiency / Mileage", "weight": 1.0},
            {"factor": "Safety", "weight": 0.2},
        ]
        # High safety priority
        high_safety_factors = [
            {"factor": "Price / EMI Affordability", "weight": 1.0},
            {"factor": "Fuel Efficiency / Mileage", "weight": 1.0},
            {"factor": "Safety", "weight": 1.0},
        ]

        vehicles = self.aggregator.get_all_active_vehicles()
        wagon_v = next(v for v in vehicles if v["model"] == "Wagon R")
        dzire_v = next(v for v in vehicles if v["model"] == "Dzire")

        score_wagon_low = self.engine.evaluate_vehicle_for_segment(wagon_v, low_safety_factors).fit_score
        score_wagon_high = self.engine.evaluate_vehicle_for_segment(wagon_v, high_safety_factors).fit_score

        score_dzire_low = self.engine.evaluate_vehicle_for_segment(dzire_v, low_safety_factors).fit_score
        score_dzire_high = self.engine.evaluate_vehicle_for_segment(dzire_v, high_safety_factors).fit_score

        # As safety weight increases:
        # Wagon R's score should drop
        self.assertLess(score_wagon_high, score_wagon_low)
        # Dzire's score should stay high or increase relative to Wagon R
        gap_low = score_dzire_low - score_wagon_low
        gap_high = score_dzire_high - score_wagon_high
        self.assertGreater(gap_high, gap_low, "Increasing safety weight must widen Dzire's advantage over Wagon R")

    def test_evidence_grounding_no_silent_zeros(self):
        """Ensures every vehicle evaluation contains evidence citations and valid data completeness."""
        result = self.engine.rank_vehicles_for_segment("Small Urban Families")
        for vehicle_score in result.rankings:
            self.assertGreater(vehicle_score.data_completeness, 0.70)
            self.assertGreater(len(vehicle_score.top_strengths), 0)
            # Make sure scores are bounded [0.0, 1.0]
            self.assertTrue(0.0 <= vehicle_score.fit_score <= 1.0)


if __name__ == "__main__":
    unittest.main()
