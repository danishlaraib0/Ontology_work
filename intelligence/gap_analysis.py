"""
gap_analysis.py
===============
Analyzes competitive vulnerabilities and unmet product opportunities:
  1. Identifies customer needs where rivals outperform the target vehicle
  2. Finds feature discrepancies (what rivals possess that target vehicle lacks)
  3. Computes opportunity scores for prospective features and variant upgrades
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .evidence_aggregation import EvidenceAggregator
from .factor_mapping import FactorMapper, FactorEvaluation
from .fit_scoring import FitScoringEngine

logger = logging.getLogger(__name__)


@dataclass
class CompetitorFactorDelta:
    """Comparison of target vehicle vs rival on a single buying factor."""
    buying_factor: str
    target_score: float
    rival_score: float
    gap_delta: float  # rival_score - target_score
    is_vulnerability: bool  # True if rival has significant advantage
    advantage_explanation: str


@dataclass
class VehicleCompetitiveGaps:
    """Full competitive gap analysis for a target model against its rivals."""
    target_model: str
    target_brand: str
    target_overall_fit: float
    rival_model: str
    rival_brand: str
    rival_overall_fit: float
    factor_deltas: List[CompetitorFactorDelta] = field(default_factory=list)
    vulnerabilities: List[str] = field(default_factory=list)
    advantages: List[str] = field(default_factory=list)


@dataclass
class ProductOpportunity:
    """An unaddressed need or missing feature with estimated market ROI."""
    dimension_name: str
    buying_factor: str
    importance_weight: float
    current_satisfaction: float
    opportunity_gap: float  # (1.0 - current_satisfaction) * importance
    recommended_action: str
    friction_evidence: List[str] = field(default_factory=list)


class CompetitiveGapEngine:
    """Calculates competitive deltas and product opportunities."""

    def __init__(
        self,
        aggregator: Optional[EvidenceAggregator] = None,
        mapper: Optional[FactorMapper] = None,
        fit_engine: Optional[FitScoringEngine] = None,
    ):
        self.aggregator = aggregator or EvidenceAggregator()
        self.mapper = mapper or FactorMapper()
        self.fit_engine = fit_engine or FitScoringEngine(self.aggregator, self.mapper)

    def compare_vehicle_to_rival(
        self,
        target_model_name: str,
        rival_model_name: str,
        segment_name: str = "Small Urban Families",
    ) -> VehicleCompetitiveGaps:
        """
        Calculates head-to-head factor deltas between target model and a competitor.
        """
        seg_data = self.aggregator.get_segment_priorities(segment_name)
        factors = seg_data.get("factors", [])

        target_ev = self.aggregator.get_vehicle_evidence(target_model_name)
        rival_ev = self.aggregator.get_vehicle_evidence(rival_model_name)

        if "error" in target_ev:
            raise ValueError(target_ev["error"])
        if "error" in rival_ev:
            raise ValueError(rival_ev["error"])

        target_fit = self.fit_engine.evaluate_vehicle_for_segment(target_ev, factors)
        rival_fit = self.fit_engine.evaluate_vehicle_for_segment(rival_ev, factors)

        target_evals = {e.factor_name: e for e in target_fit.evaluations}
        rival_evals = {e.factor_name: e for e in rival_fit.evaluations}

        deltas: List[CompetitorFactorDelta] = []
        vulnerabilities: List[str] = []
        advantages: List[str] = []

        for f_dict in factors:
            f_name = f_dict["factor"]
            t_eval = target_evals.get(f_name)
            r_eval = rival_evals.get(f_name)
            if not t_eval or not r_eval:
                continue

            delta = round(r_eval.satisfaction_score - t_eval.satisfaction_score, 3)
            is_vuln = delta >= 0.10

            adv_str = ""
            if delta > 0.05:
                adv_str = f"{rival_ev.get('model')} leads by +{delta*100:.0f}%"
                if is_vuln:
                    vulnerabilities.append(f"{f_name}: {adv_str} ({r_eval.spec_evidence[0] if r_eval.spec_evidence else ''})")
            elif delta < -0.05:
                adv_str = f"{target_ev.get('model')} leads by +{abs(delta)*100:.0f}%"
                advantages.append(f"{f_name}: {adv_str} ({t_eval.spec_evidence[0] if t_eval.spec_evidence else ''})")
            else:
                adv_str = "Parity / Close match"

            deltas.append(CompetitorFactorDelta(
                buying_factor=f_name,
                target_score=t_eval.satisfaction_score,
                rival_score=r_eval.satisfaction_score,
                gap_delta=delta,
                is_vulnerability=is_vuln,
                advantage_explanation=adv_str,
            ))

        return VehicleCompetitiveGaps(
            target_model=target_ev.get("model", target_model_name),
            target_brand=target_ev.get("brand", "Unknown"),
            target_overall_fit=target_fit.fit_percentage,
            rival_model=rival_ev.get("model", rival_model_name),
            rival_brand=rival_ev.get("brand", "Unknown"),
            rival_overall_fit=rival_fit.fit_percentage,
            factor_deltas=deltas,
            vulnerabilities=vulnerabilities,
            advantages=advantages,
        )

    def find_product_opportunities(
        self,
        model_name: str,
        segment_name: str = "Small Urban Families",
    ) -> List[ProductOpportunity]:
        """
        Discovers unmet customer needs where improvement produces maximum commercial impact.
        """
        seg_data = self.aggregator.get_segment_priorities(segment_name)
        factors = seg_data.get("factors", [])
        evidence = self.aggregator.get_vehicle_evidence(model_name)
        if "error" in evidence:
            raise ValueError(evidence["error"])

        fit = self.fit_engine.evaluate_vehicle_for_segment(evidence, factors)
        opportunities: List[ProductOpportunity] = []

        for ev in fit.evaluations:
            # Opportunity size = importance * (1 - satisfaction)
            opp_size = ev.importance_weight * (1.0 - ev.satisfaction_score)
            if opp_size >= 0.15 or ev.drawbacks:
                # Formulate concrete engineering / product action
                dim = ev.canonical_dimension
                if dim == "SAFETY":
                    rec = "Standardize 6 airbags and ESC across all trims; reinforce crash structure."
                elif dim == "FEATURE_TECH":
                    rec = "Introduce 8-inch/9-inch infotainment with wireless Android Auto/Apple CarPlay and 360 camera."
                elif dim == "CABIN_SPACE_COMFORT":
                    rec = "Improve acoustic NVH insulation and add rear AC vents / adjustable headrests."
                elif dim == "PERFORMANCE_HANDLING":
                    rec = "Tune suspension dampening and steering center feel to reduce highway body float."
                elif dim == "FUEL_EFFICIENCY":
                    rec = "Expand factory CNG variant to top trims and tune low-end torque delivery."
                else:
                    rec = f"Address friction points in {ev.factor_name}."

                opportunities.append(ProductOpportunity(
                    dimension_name=dim,
                    buying_factor=ev.factor_name,
                    importance_weight=ev.importance_weight,
                    current_satisfaction=ev.satisfaction_score,
                    opportunity_gap=round(opp_size, 3),
                    recommended_action=rec,
                    friction_evidence=ev.drawbacks,
                ))

        # Sort descending by opportunity gap
        opportunities.sort(key=lambda x: x.opportunity_gap, reverse=True)
        return opportunities
