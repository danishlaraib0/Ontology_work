"""
source_registry.py
==================
Data Source Registry for the Automotive World Model.
Registers external and internal data sources, their refresh policies,
provenance metadata, validation schemas, and automated vs manual ingestion status.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any


@dataclass
class DataSourceRecord:
    source_id: str
    source_name: str
    source_type: str  # OEM_SPEC, PRICE_LADDER, SIAM_SALES, REVIEW_AGGREGATOR, SAFETY_AUDIT
    owner_or_provider: str
    supported_entities: List[str]
    refresh_policy: str  # AD_HOC, MONTHLY, QUARTERLY, REALTIME
    ingestion_mechanism: str  # MANUAL_FEED, AUTOMATED_API_CONNECTOR, SCHEDULED_SCRAPER, BATCH_FILE_INGESTION
    automation_verified: bool  # False if manual feed or unverified connector; True only if verified automated ingestion
    max_freshness_days: int
    expected_schema: Dict[str, str]
    reliability_notes: str
    licensing_or_usage_constraints: str
    retry_policy: Dict[str, Any] = field(default_factory=lambda: {"max_retries": 3, "backoff_seconds": 1.0})
    enabled: bool = True
    last_successful_ingestion: Optional[str] = None
    records_count: int = 0

    def is_fresh(self, as_of: Optional[datetime] = None) -> bool:
        """Determines if the source's data is within the maximum freshness threshold."""
        if not self.last_successful_ingestion:
            return False
        now_dt = as_of or datetime.now(timezone.utc)
        try:
            last_dt = datetime.fromisoformat(self.last_successful_ingestion.replace("Z", "+00:00"))
            return (now_dt - last_dt).days <= self.max_freshness_days
        except Exception:
            return False


class DataSourceRegistry:
    """Maintains official metadata, schema contracts, and freshness for data sources."""

    def __init__(self):
        self._sources: Dict[str, DataSourceRecord] = {}
        self._seed_registered_sources()

    def _seed_registered_sources(self):
        sources = [
            DataSourceRecord(
                source_id="SRC_OEM_OFFICIAL",
                source_name="OEM Technical Spec Sheet & Brochure",
                source_type="OEM_SPEC",
                owner_or_provider="Maruti Suzuki / Hyundai / Honda / Tata Official",
                supported_entities=["VehicleModel", "VehicleVariant", "Engine", "Powertrain", "Feature"],
                refresh_policy="QUARTERLY",
                ingestion_mechanism="MANUAL_FEED",  # Explicitly labeled manual: corporate brochures uploaded by analysts
                automation_verified=False,
                max_freshness_days=120,
                expected_schema={
                    "model": "str",
                    "variant": "str",
                    "engine_cc": "int",
                    "max_power_hp": "float",
                    "transmission": "str",
                },
                reliability_notes="Authoritative primary source for dimensions, safety equipment, and mechanical specs.",
                licensing_or_usage_constraints="Public corporate product literature.",
                enabled=True,
                last_successful_ingestion="2026-10-10T00:00:00Z",
                records_count=54,
            ),
            DataSourceRecord(
                source_id="SRC_SIAM_DISPATCHES",
                source_name="SIAM Monthly Wholesale Dispatches",
                source_type="SIAM_SALES",
                owner_or_provider="Society of Indian Automobile Manufacturers (SIAM)",
                supported_entities=["SalesObservation", "VehicleModel"],
                refresh_policy="MONTHLY",
                ingestion_mechanism="BATCH_FILE_INGESTION",  # Automated parser running over standardized monthly SIAM data dumps
                automation_verified=True,
                max_freshness_days=45,
                expected_schema={
                    "vehicle_model": "str",
                    "period_value": "str",
                    "units_sold": "int",
                },
                reliability_notes="Verified OEM factory-to-dealership wholesale dispatches in India.",
                licensing_or_usage_constraints="Industry dispatch reporting standards.",
                enabled=True,
                last_successful_ingestion="2026-08-31T00:00:00Z",
                records_count=57,
            ),
            DataSourceRecord(
                source_id="SRC_EX_SHOWROOM_PRICES",
                source_name="National Ex-Showroom Price Observations",
                source_type="PRICE_LADDER",
                owner_or_provider="OEM List Pricing (Delhi Baseline)",
                supported_entities=["PriceObservation", "VehicleVariant"],
                refresh_policy="MONTHLY",
                ingestion_mechanism="AUTOMATED_API_CONNECTOR",  # Automated feed syncing with published dealer price APIs
                automation_verified=True,
                max_freshness_days=35,
                expected_schema={
                    "variant_id": "str",
                    "ex_showroom_inr": "float",
                    "effective_date": "str",
                },
                reliability_notes="Standardized baseline ex-showroom price excluding state registration and insurance.",
                licensing_or_usage_constraints="Published list prices.",
                enabled=True,
                last_successful_ingestion="2026-09-01T00:00:00Z",
                records_count=31,
            ),
            DataSourceRecord(
                source_id="SRC_GLOBAL_NCAP",
                source_name="Global NCAP Safer Cars for India Crash Tests",
                source_type="SAFETY_AUDIT",
                owner_or_provider="Global NCAP / Towards Zero Foundation",
                supported_entities=["VehicleModel", "Opinion", "MarketChange"],
                refresh_policy="AD_HOC",
                ingestion_mechanism="MANUAL_FEED",  # Independent regulatory crash test reports ingested manually per crash batch
                automation_verified=False,
                max_freshness_days=730,
                expected_schema={
                    "model": "str",
                    "ncap_stars": "int",
                    "airbags_standard": "int",
                },
                reliability_notes="Independent crash test protocol.",
                licensing_or_usage_constraints="Public regulatory safety ratings.",
                enabled=True,
                last_successful_ingestion="2024-11-15T00:00:00Z",
                records_count=6,
            ),
        ]
        for s in sources:
            self._sources[s.source_id] = s

    def get_source(self, source_id: str) -> Optional[DataSourceRecord]:
        return self._sources.get(source_id)

    def list_sources(self) -> List[DataSourceRecord]:
        return list(self._sources.values())

    def record_ingestion(self, source_id: str, records_ingested: int):
        if source_id in self._sources:
            src = self._sources[source_id]
            src.last_successful_ingestion = datetime.now(timezone.utc).isoformat()
            src.records_count += records_ingested
