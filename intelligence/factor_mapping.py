"""
factor_mapping.py
=================
Maps raw automotive evidence (specifications, features, reviews) to defensible
satisfaction scores a_{v,i} in [0.0, 1.0] for each customer buying factor.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FactorEvaluation:
    """Detailed evaluation of how well a vehicle satisfies a single buying factor."""
    factor_name: str
    canonical_dimension: str
    satisfaction_score: float  # a_{v,i} normalized to [0.0, 1.0]
    importance_weight: float   # w_{s,i}
    spec_evidence: List[str] = field(default_factory=list)
    opinion_evidence: List[str] = field(default_factory=list)
    drawbacks: List[str] = field(default_factory=list)
    is_missing: bool = False


class FactorMapper:
    """Evaluates vehicle evidence against customer buying factors."""

    DIMENSION_KEYWORDS = {
        "FUEL_EFFICIENCY": ["mileage", "fuel", "cng", "efficiency", "kmpl"],
        "AFFORDABILITY": ["price", "emi", "affordability", "cost", "value for money", "budget"],
        "CABIN_SPACE_COMFORT": ["space", "cabin", "comfort", "tall-boy", "boot", "seating", "legroom", "headroom", "capacity"],
        "SAFETY": ["safety", "airbag", "abs", "ncap", "crash", "structural"],
        "SERVICE_RELIABILITY_RESALE": ["service", "reliability", "resale", "maintenance", "network", "brand"],
        "FEATURE_TECH": ["feature", "infotainment", "technology", "touchscreen", "connectivity", "gadgets"],
        "GROUND_CLEARANCE": ["ground clearance", "rough road", "suspension", "clearance"],
        "PERFORMANCE_HANDLING": ["performance", "engine power", "stability", "highway", "handling"],
    }

    def canonicalize_dimension(self, factor_name: str) -> str:
        """Maps a natural language buying factor into a canonical dimension."""
        f_lower = factor_name.lower()
        # Explicit priority check for resale before generic value
        if "resale" in f_lower:
            return "SERVICE_RELIABILITY_RESALE"
        for dim, keywords in self.DIMENSION_KEYWORDS.items():
            if any(kw in f_lower for kw in keywords):
                return dim
        return "GENERAL_UTILITY"

    def evaluate_factor(
        self,
        vehicle_evidence: Dict[str, Any],
        factor_name: str,
        importance_weight: float,
        segment_name: str = "",
    ) -> FactorEvaluation:
        """
        Calculates a_{v,i} using base specifications/features, adjusted by review claims
        and segment-specific constraints (e.g. 7-seater capacity for large families).
        """
        dim = self.canonicalize_dimension(factor_name)
        model = vehicle_evidence.get("model", "Unknown")
        brand = vehicle_evidence.get("brand", "Unknown")
        mileages = vehicle_evidence.get("mileages", [])
        powertrains = vehicle_evidence.get("powertrains", [])
        features = vehicle_evidence.get("features", [])
        opinions = vehicle_evidence.get("opinions", [])
        is_large_family = any(k in segment_name.lower() for k in ["large", "joint", "7-seater", "multi-gen"])

        # Filter opinions matching this dimension
        matching_opinions = self._filter_opinions_by_dimension(opinions, dim)

        spec_evidence: List[str] = []
        opinion_evidence: List[str] = []
        drawbacks: List[str] = []
        is_missing = False

        # ── 1. FUEL EFFICIENCY & CNG ECONOMY ───────────────────────────────
        if dim == "FUEL_EFFICIENCY":
            numeric_mileages = self._extract_mileages(mileages)
            has_cng = any("CNG" in pt.upper() for pt in powertrains) or any("cng" in m.lower() for m in mileages)
            best_mileage = max(numeric_mileages) if numeric_mileages else None

            if best_mileage is not None:
                spec_evidence.append(f"Claimed fuel economy: {best_mileage} kmpl/kg (Powertrains: {', '.join(powertrains)})")
                if has_cng or best_mileage >= 28.0:
                    base_score = 0.94
                elif best_mileage >= 24.0:
                    base_score = 0.88
                elif best_mileage >= 21.0:
                    base_score = 0.80
                else:
                    base_score = 0.70
            else:
                base_score = 0.75
                is_missing = True
                spec_evidence.append("No explicit numerical fuel economy recorded.")

        # ── 2. PRICE & AFFORDABILITY ────────────────────────────────────────
        elif dim == "AFFORDABILITY":
            min_price = float(vehicle_evidence.get("min_price") or 0.0)
            max_price = float(vehicle_evidence.get("max_price") or min_price or 0.0)
            body_type = str(vehicle_evidence.get("body_type", "")).lower()

            if min_price > 0:
                if is_large_family:
                    if 700000 <= min_price <= 1350000:
                        base_score = 0.90
                        spec_evidence.append(f"Optimally aligned with large family budget band (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
                    elif min_price < 700000:
                        base_score = 0.88
                        spec_evidence.append(f"Accessible entry pricing for budget-conscious families (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L).")
                    else:
                        base_score = 0.72
                        spec_evidence.append(f"Upper-tier family pricing (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
                else:
                    if min_price <= 600000:
                        base_score = 0.94
                        spec_evidence.append(f"Entry tier pricing (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
                    elif min_price <= 750000:
                        base_score = 0.86
                        spec_evidence.append(f"Sub-compact value tier (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
                    elif min_price <= 1000000:
                        base_score = 0.78
                        spec_evidence.append(f"Mid-tier compact pricing (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
                    else:
                        base_score = 0.70
                        spec_evidence.append(f"Premium segment pricing (₹{min_price/100000:.1f}L–₹{max_price/100000:.1f}L ex-showroom).")
            else:
                # Dynamic fallback based on body type category
                if "hatchback" in body_type:
                    base_score = 0.92
                    spec_evidence.append("Hatchback positioning prioritizing entry accessibility.")
                elif "sedan" in body_type:
                    base_score = 0.84
                    spec_evidence.append("Compact Sedan positioning balancing value and boot utility.")
                elif "mpv" in body_type:
                    base_score = 0.76
                    spec_evidence.append("Multi-purpose utility vehicle positioning.")
                else:
                    base_score = 0.75
                    spec_evidence.append("Standard market price positioning.")

        # ── 3. CABIN SPACE & COMFORT (SEATING CAPACITY / BOOT SPACE) ────────
        elif dim == "CABIN_SPACE_COMFORT":
            seating = int(vehicle_evidence.get("seating_capacity") or 5)
            boot = float(vehicle_evidence.get("boot_space_litres") or 350)
            body_type = str(vehicle_evidence.get("body_type", "")).lower()

            if is_large_family:
                if seating >= 6:
                    base_score = 0.96
                    spec_evidence.append(f"Dedicated {seating}-seater multi-row capacity accommodating 6+ family members with flexible cargo.")
                else:
                    base_score = 0.35
                    spec_evidence.append(f"Standard {seating}-seater capacity (insufficient for large families requiring 6+ seats).")
                    drawbacks.append(f"Severe capacity deficit: {seating}-seater layout cannot legally or comfortably seat a large family of 6+ members.")
            else:
                if seating >= 6:
                    base_score = 0.94
                    spec_evidence.append(f"Spacious {seating}-seater multi-row interior.")
                elif boot >= 380:
                    base_score = 0.86
                    spec_evidence.append(f"Generous {boot:.0f}L boot space and balanced 5-passenger cabin comfort.")
                elif boot >= 330:
                    base_score = 0.82
                    spec_evidence.append(f"Practical {boot:.0f}L boot capacity with ergonomic passenger layout.")
                else:
                    base_score = 0.75
                    spec_evidence.append(f"Compact urban cabin with {boot:.0f}L cargo capacity.")

            # Feature bonuses
            comfort_features = [f for f in features if any(k in f.lower() for k in ["ac", "armrest", "seat", "headrest", "rear vent"])]
            if comfort_features:
                spec_evidence.append(f"Equipped with {len(comfort_features)} comfort amenities: {', '.join(comfort_features[:3])}")

        # ── 4. SAFETY (NCAP, AIRBAGS, STRUCTURAL INTEGRITY) ─────────────────
        elif dim == "SAFETY":
            ncap = str(vehicle_evidence.get("ncap_rating") or "Not Rated")
            airbags = int(vehicle_evidence.get("airbags") or 2)
            safety_features = [f for f in features if any(k in f.lower() for k in ["airbag", "abs", "ebd", "esc", "isofix", "hill hold", "sensor", "camera"])]

            # Dynamically extract NCAP star rating
            star_match = re.search(r"(\d)\s*[- ]?[Ss]tar", ncap)
            stars = int(star_match.group(1)) if star_match else None

            if stars is not None:
                if stars >= 5:
                    base_score = 0.96
                    spec_evidence.append(f"Verified {ncap} crash safety rating with {airbags} airbags.")
                elif stars == 4:
                    base_score = 0.88
                    spec_evidence.append(f"Strong {ncap} crash rating with {airbags} airbags.")
                elif stars == 3:
                    base_score = 0.74
                    spec_evidence.append(f"{ncap} baseline crash rating.")
                elif stars == 2:
                    base_score = 0.60
                    spec_evidence.append(f"{ncap} crash rating with {airbags} airbags.")
                    drawbacks.append(f"Sub-par {ncap} crash structure performance under updated Global NCAP protocols.")
                else:
                    base_score = 0.40
                    spec_evidence.append(f"{ncap} crash structure rating; {airbags} airbags.")
                    drawbacks.append(f"Severe safety vulnerability: {ncap} rating; body shell unstable under crash loads.")
            else:
                # Unrated crash rating: score dynamically by passive and active kit
                if airbags >= 6:
                    base_score = 0.84
                    spec_evidence.append(f"Equipped with {airbags} standard airbags and active stability controls (crash test pending).")
                else:
                    base_score = 0.65
                    spec_evidence.append(f"Baseline {airbags} airbags; unrated under independent NCAP protocols.")

            if safety_features:
                spec_evidence.append(f"Active safety kit includes: {', '.join(safety_features[:4])}")

        # ── 5. SERVICE NETWORK & BRAND RELIABILITY / RESALE VALUE ───────────
        elif dim == "SERVICE_RELIABILITY_RESALE":
            b_lower = brand.lower()
            if any(k in b_lower for k in ["maruti", "suzuki"]):
                base_score = 0.96
                spec_evidence.append(f"{brand} nationwide service network (4,500+ touchpoints) & unmatched resale velocity.")
            elif "hyundai" in b_lower:
                base_score = 0.86
                spec_evidence.append(f"{brand} pan-India presence (1,500+ service centers) and proven customer trust.")
            elif "tata" in b_lower:
                base_score = 0.84
                spec_evidence.append(f"{brand} extensive passenger vehicle network and growing resale stability.")
            elif "honda" in b_lower:
                base_score = 0.78
                spec_evidence.append(f"{brand} mechanical longevity with established Tier-1/2 network footprint.")
            else:
                base_score = 0.75
                spec_evidence.append(f"{brand} authorized service network and standard OEM warranty coverage.")

        # ── 6. FEATURE & TECHNOLOGY (INFOTAINMENT, CONNECTIVITY) ─────────────
        elif dim == "FEATURE_TECH":
            tech_features = [f for f in features if any(k in f.lower() for k in ["display", "screen", "touchscreen", "carplay", "android", "wireless", "camera", "hud", "charging"])]
            if len(tech_features) >= 4:
                base_score = 0.90
                spec_evidence.append(f"Modern tech suite ({len(tech_features)} items): {', '.join(tech_features[:4])}")
            elif len(tech_features) >= 2:
                base_score = 0.82
                spec_evidence.append(f"Core digital infotainment suite: {', '.join(tech_features[:2])}")
            else:
                base_score = 0.68
                spec_evidence.append(f"Basic audio/infotainment; limited connected equipment ({len(tech_features)} items).")

        # ── 7. GROUND CLEARANCE & ROUGH ROAD ABILITY ────────────────────────
        elif dim == "GROUND_CLEARANCE":
            gc = float(vehicle_evidence.get("ground_clearance_mm") or 165)
            if gc >= 190:
                base_score = 0.92
                spec_evidence.append(f"{gc:.0f}mm high ground clearance suited for rough roads and uneven surfaces.")
            elif gc >= 175:
                base_score = 0.82
                spec_evidence.append(f"{gc:.0f}mm ground clearance suited for semi-urban driving conditions.")
            elif gc >= 165:
                base_score = 0.74
                spec_evidence.append(f"{gc:.0f}mm standard clearance suitable for urban driving.")
            else:
                base_score = 0.68
                spec_evidence.append(f"{gc:.0f}mm low stance optimized for aerodynamic efficiency.")

        # ── 8. PERFORMANCE & STABILITY ──────────────────────────────────────
        elif dim == "PERFORMANCE_HANDLING":
            hp_list = vehicle_evidence.get("horsepower_list", [])
            max_hp = max([float(h) for h in hp_list if h is not None] or [85.0])
            body_type = str(vehicle_evidence.get("body_type", "")).lower()

            spec_evidence.append(f"Engine output: {max_hp:.1f} HP across powertrain options.")
            if max_hp >= 95.0:
                base_score = 0.88
                spec_evidence.append(f"High power output ({max_hp:.1f} HP) delivering responsive highway acceleration.")
            elif max_hp >= 78.0:
                base_score = 0.80
                spec_evidence.append(f"Balanced performance ({max_hp:.1f} HP) tuned for mixed urban and cruising driving.")
            else:
                base_score = 0.68
                spec_evidence.append(f"Economy-oriented calibration ({max_hp:.1f} HP) prioritizing fuel economy.")

            if "tall-boy" in body_type or (vehicle_evidence.get("height_mm") and float(vehicle_evidence.get("height_mm") or 0) > 1660 and "mpv" not in body_type):
                drawbacks.append("Tall stance profile may induce highway body roll above 90 km/h.")
        else:
            base_score = 0.75

        # ── OPINION SENTIMENT MODIFIER ──────────────────────────────────────
        # Incorporate customer reviews as corroboration or friction penalty
        sentiment_mod = 0.0
        if matching_opinions:
            scores = [op.get("score", 0.0) for op in matching_opinions if op.get("score") is not None]
            if scores:
                avg_score = sum(scores) / len(scores)
                # Influence satisfaction score by up to +/- 0.08
                sentiment_mod = avg_score * 0.08

            for op in matching_opinions:
                claim = op.get("claim", "")
                if op.get("barrier") or op.get("score", 0.0) < -0.2:
                    drawbacks.append(f"Review barrier [{op.get('aspect')}]: \"{claim}\"")
                elif op.get("driver") or op.get("score", 0.0) > 0.4:
                    opinion_evidence.append(f"Review endorsement [{op.get('aspect')}]: \"{claim}\"")

        satisfaction_score = max(0.05, min(1.0, base_score + sentiment_mod))

        return FactorEvaluation(
            factor_name=factor_name,
            canonical_dimension=dim,
            satisfaction_score=round(satisfaction_score, 3),
            importance_weight=importance_weight,
            spec_evidence=spec_evidence,
            opinion_evidence=opinion_evidence[:2],
            drawbacks=drawbacks[:2],
            is_missing=is_missing,
        )

    def _filter_opinions_by_dimension(self, opinions: List[Dict[str, Any]], dim: str) -> List[Dict[str, Any]]:
        """Filter reviews whose aspect relates to the evaluated dimension."""
        keywords = self.DIMENSION_KEYWORDS.get(dim, [])
        matches = []
        for op in opinions:
            aspect = str(op.get("aspect", "")).lower()
            claim = str(op.get("claim", "")).lower()
            if any(kw in aspect for kw in keywords) or any(kw in claim for kw in keywords):
                matches.append(op)
        return matches

    def _extract_mileages(self, mileages: List[Any]) -> List[float]:
        """Extract float kmpl numbers from claimed efficiency strings."""
        nums = []
        for m in mileages:
            found = re.findall(r"(\d+(?:\.\d+)?)", str(m))
            for n in found:
                val = float(n)
                if val > 5.0 and val < 45.0:  # Valid kmpl range
                    nums.append(val)
        return nums
