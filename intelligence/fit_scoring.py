"""
fit_scoring.py
==============
Computes the Audience–Vehicle Fit Score:
    Fit(s, v) = (sum_i w_{s,i} * a_{v,i}) / (sum_i w_{s,i})
Ranks vehicles for any customer segment, providing grounded evidence and trade-offs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .evidence_aggregation import EvidenceAggregator
from .factor_mapping import FactorMapper, FactorEvaluation

logger = logging.getLogger(__name__)


@dataclass
class VehicleFitScore:
    """Scored evaluation result for a vehicle against an audience segment."""
    model_name: str
    brand_name: str
    fit_score: float              # Normalized 0.0 to 1.0 (or 0–100%)
    fit_percentage: float         # Formatted percentage
    rank: int = 1
    evaluations: List[FactorEvaluation] = field(default_factory=list)
    top_strengths: List[str] = field(default_factory=list)
    key_tradeoffs: List[str] = field(default_factory=list)
    data_completeness: float = 1.0  # Fraction of factors with verified data


@dataclass
class AudienceRankingResult:
    """Complete ranked recommendations for an audience segment."""
    segment_name: str
    segment_description: str
    total_vehicles_evaluated: int
    rankings: List[VehicleFitScore]
    segment_priorities: List[Dict[str, Any]]


class FitScoringEngine:
    """Computes mathematically rigorous, evidence-backed audience-vehicle rankings."""

    def __init__(
        self,
        aggregator: Optional[EvidenceAggregator] = None,
        mapper: Optional[FactorMapper] = None,
    ):
        self.aggregator = aggregator or EvidenceAggregator()
        self.mapper = mapper or FactorMapper()

    def evaluate_vehicle_for_segment(
        self,
        vehicle_evidence: Dict[str, Any],
        factors: List[Dict[str, Any]],
        segment_name: str = "",
    ) -> VehicleFitScore:
        """
        Computes Fit(s,v) for a single vehicle across prioritized buying factors.
        """
        model = vehicle_evidence.get("model", "Unknown")
        brand = vehicle_evidence.get("brand", "Unknown")

        weighted_sum = 0.0
        total_weight = 0.0
        observed_factors = 0
        evaluations: List[FactorEvaluation] = []
        all_drawbacks: List[str] = []
        strengths_candidates: List[Tuple[float, str]] = []

        for f_dict in factors:
            f_name = f_dict.get("factor")
            w = float(f_dict.get("weight") or 0.5)
            if not f_name or w <= 0:
                continue

            # Evaluate factor satisfaction a_{v,i}
            eval_result = self.mapper.evaluate_factor(vehicle_evidence, f_name, w, segment_name=segment_name)
            evaluations.append(eval_result)

            if not eval_result.is_missing:
                weighted_sum += eval_result.satisfaction_score * w
                total_weight += w
                observed_factors += 1
            else:
                # Missing data is not scored as 0 to avoid distortion
                pass

            # Track key strengths and drawbacks
            if eval_result.satisfaction_score >= 0.85:
                top_quote = eval_result.opinion_evidence[0] if eval_result.opinion_evidence else (
                    eval_result.spec_evidence[0] if eval_result.spec_evidence else f"High {f_name}"
                )
                strengths_candidates.append((eval_result.satisfaction_score * w, f"{f_name}: {top_quote}"))

            if eval_result.drawbacks:
                all_drawbacks.extend(eval_result.drawbacks)

        # Normalize score
        final_fit = (weighted_sum / total_weight) if total_weight > 0 else 0.5
        completeness = observed_factors / len(factors) if factors else 1.0

        # Sort strengths by impact
        strengths_candidates.sort(key=lambda x: x[0], reverse=True)
        top_strengths = [sc[1] for sc in strengths_candidates[:3]]

        return VehicleFitScore(
            model_name=model,
            brand_name=brand,
            fit_score=round(final_fit, 3),
            fit_percentage=round(final_fit * 100, 1),
            evaluations=evaluations,
            top_strengths=top_strengths,
            key_tradeoffs=all_drawbacks[:3],
            data_completeness=round(completeness, 2),
        )

    def rank_vehicles_for_segment(self, segment_name: str) -> AudienceRankingResult:
        """
        Ranks all active vehicles in the knowledge graph for a given customer segment.
        """
        seg_data = self.aggregator.get_segment_priorities(segment_name)
        if "error" in seg_data:
            raise ValueError(seg_data["error"])

        s_name = seg_data["segment_name"]
        s_desc = seg_data.get("description", "")
        factors = seg_data.get("factors", [])

        vehicles = self.aggregator.get_all_active_vehicles()
        scores: List[VehicleFitScore] = []

        for v in vehicles:
            score_obj = self.evaluate_vehicle_for_segment(v, factors, segment_name=s_name)
            scores.append(score_obj)

        # Sort descending by fit_score
        scores.sort(key=lambda x: x.fit_score, reverse=True)

        # Assign ranks
        for idx, score_obj in enumerate(scores, 1):
            score_obj.rank = idx

        return AudienceRankingResult(
            segment_name=s_name,
            segment_description=s_desc,
            total_vehicles_evaluated=len(scores),
            rankings=scores,
            segment_priorities=factors,
        )
