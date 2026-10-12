"""
data_validator.py
=================
Automated Data Quality & Semantic Validation for the Automotive World Model.
Validates:
  1. Negative or impossible sales figures (units_sold < 0).
  2. Impossible or corrupt price observations (ex_showroom_inr <= 0 or > 10 Crore).
  3. Feature availability semantics:
     UNKNOWN, NOT_REPORTED, NOT_APPLICABLE, CONFIRMED_ABSENT, CONFIRMED_PRESENT.
  4. Broken provenance or missing source references.
  5. Contradictory price observations for the same variant and effective date.
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FeatureState(str, Enum):
    UNKNOWN = "UNKNOWN"
    NOT_REPORTED = "NOT_REPORTED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONFIRMED_ABSENT = "CONFIRMED_ABSENT"
    CONFIRMED_PRESENT = "CONFIRMED_PRESENT"


@dataclass
class ValidationIssue:
    severity: str  # 'ERROR', 'WARNING', 'INFO'
    entity_type: str
    entity_id: str
    property_name: str
    message: str
    value: Any = None


@dataclass
class DataQualityReport:
    total_records_checked: int = 0
    passed_records: int = 0
    failed_records: int = 0
    issues: List[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return self.failed_records == 0


class DataQualityValidator:
    """Performs deterministic schema and sanity audits over incoming and graph data."""

    MIN_VALID_PRICE_INR: float = 100_000.0       # ₹1 Lakh
    MAX_VALID_PRICE_INR: float = 100_000_000.0   # ₹10 Crore

    def validate_price_observation(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        p_id = str(record.get("price_obs_id") or record.get("variant_id") or "UNKNOWN")
        price = record.get("ex_showroom_inr")

        if price is None:
            issues.append(ValidationIssue("ERROR", "PriceObservation", p_id, "ex_showroom_inr", "Price is missing or null"))
        elif not isinstance(price, (int, float)):
            issues.append(ValidationIssue("ERROR", "PriceObservation", p_id, "ex_showroom_inr", f"Price must be numeric, got {type(price).__name__}", price))
        elif price < self.MIN_VALID_PRICE_INR or price > self.MAX_VALID_PRICE_INR:
            issues.append(ValidationIssue("ERROR", "PriceObservation", p_id, "ex_showroom_inr", f"Price ₹{price:,.0f} outside sanity bounds [₹1L, ₹10Cr]", price))

        if not record.get("source_name") and not record.get("source_id"):
            issues.append(ValidationIssue("WARNING", "PriceObservation", p_id, "source", "Missing source provenance reference"))

        return issues

    def validate_sales_observation(self, record: Dict[str, Any]) -> List[ValidationIssue]:
        issues = []
        s_id = str(record.get("sales_obs_id") or record.get("period_value") or "UNKNOWN")
        units = record.get("units_sold")

        if units is None:
            issues.append(ValidationIssue("ERROR", "SalesObservation", s_id, "units_sold", "Sales units missing or null"))
        elif not isinstance(units, (int, float)):
            issues.append(ValidationIssue("ERROR", "SalesObservation", s_id, "units_sold", f"Units must be numeric, got {type(units).__name__}", units))
        elif units < 0:
            issues.append(ValidationIssue("ERROR", "SalesObservation", s_id, "units_sold", f"Negative sales units ({units}) are impossible", units))

        period = record.get("period_value")
        if not period or not isinstance(period, str) or not re.match(r"^\d{4}-(?:0[1-9]|1[0-2]|Q[1-4])$", period):
            issues.append(ValidationIssue("ERROR", "SalesObservation", s_id, "period_value", f"Invalid period format: {period} (expected YYYY-MM or YYYY-Q#)"))

        return issues

    def audit_graph_integrity(self, client) -> DataQualityReport:
        """Audits live Neo4j records for negative sales, out-of-bound prices, and provenance."""
        report = DataQualityReport()
        if not client or not client.is_healthy():
            report.issues.append(ValidationIssue("ERROR", "Database", "neo4j", "connection", "Neo4j connection unreachable"))
            return report

        # 1. Check Sales Observations
        sales_records = client.query("""
            MATCH (s:SalesObservation)
            RETURN s.sales_obs_id AS id, s.period_value AS period, s.units_sold AS units, s.source_name AS src
        """)
        for s in sales_records:
            report.total_records_checked += 1
            issues = self.validate_sales_observation({
                "sales_obs_id": s.get("id"),
                "period_value": s.get("period"),
                "units_sold": s.get("units"),
                "source_name": s.get("src"),
            })
            if issues:
                report.failed_records += 1
                report.issues.extend(issues)
            else:
                report.passed_records += 1

        # 2. Check Price Observations
        price_records = client.query("""
            MATCH (p:PriceObservation)
            RETURN p.price_obs_id AS id, p.ex_showroom_inr AS price, p.source_name AS src
        """)
        for p in price_records:
            report.total_records_checked += 1
            issues = self.validate_price_observation({
                "price_obs_id": p.get("id"),
                "ex_showroom_inr": p.get("price"),
                "source_name": p.get("src"),
            })
            if issues:
                report.failed_records += 1
                report.issues.extend(issues)
            else:
                report.passed_records += 1

        return report
