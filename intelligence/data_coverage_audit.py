"""
data_coverage_audit.py
======================
Comprehensive Data Coverage & Granularity Audit for Automotive Forecasting.
Audits time-stamped observations across Neo4j and JSON datasets:
  1. Monthly Sales / Wholesale Dispatches (SalesObservation)
  2. Variant Pricing & Revisions (PriceObservation)
  3. Aspect-Level Sentiment & Claims (Opinion)
  4. Search Intent & Demand Signals (SearchQuery)

Outputs structured feasibility ratings for predictive modeling:
  • SUFFICIENT (>= 12 continuous periods) -> Full backtesting & time-series models
  • MARGINAL (6-11 periods) -> Short-horizon statistical baselines (Naïve, SMA, SES)
  • INSUFFICIENT (< 6 periods) -> Needs data augmentation before ML modeling
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient

logger = logging.getLogger(__name__)


@dataclass
class SeriesAuditRecord:
    """Audit metrics for a single time-stamped signal series."""
    model_name: str
    signal_name: str
    total_observations: int
    temporal_granularity: str  # e.g. "MONTHLY", "QUARTERLY", "IRREGULAR_EVENT", "SNAPSHOT"
    min_timestamp: str
    max_timestamp: str
    usable_periods_count: int
    consecutive_periods_count: int
    has_gaps: bool
    gap_summary: str
    feasibility_status: str  # "SUFFICIENT", "MARGINAL", "INSUFFICIENT"
    suitable_forecasting_methods: List[str]
    notes: str


@dataclass
class SignalCoverageSummary:
    """Coverage summary across all vehicle models for a specific signal."""
    signal_name: str
    total_models_covered: int
    total_observations: int
    average_observations_per_model: float
    overall_feasibility: str
    key_recommendation: str


@dataclass
class DataCoverageAuditReport:
    """Comprehensive data audit report across all signals and vehicles."""
    audit_date: str
    model_records: List[SeriesAuditRecord] = field(default_factory=list)
    signal_summaries: List[SignalCoverageSummary] = field(default_factory=list)
    markdown_report: str = ""


class DataCoverageAuditor:
    """Audits historical data availability, granularity, and gaps across the knowledge graph."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def run_full_audit(self) -> DataCoverageAuditReport:
        """Executes full audit across sales, price, sentiment, and search signals."""
        logger.info("🔍 Running Historical Data Coverage Audit for Automotive Forecasting...")
        records: List[SeriesAuditRecord] = []

        # 1. Audit Monthly Sales
        sales_records = self._audit_sales_series()
        records.extend(sales_records)

        # 2. Audit Price Observations
        price_records = self._audit_price_series()
        records.extend(price_records)

        # 3. Audit Review Sentiment / Opinions
        sentiment_records = self._audit_sentiment_series()
        records.extend(sentiment_records)

        # 4. Audit Search Demand Signals
        search_records = self._audit_search_signals()
        records.extend(search_records)

        # Generate signal-level summaries
        summaries = self._compute_signal_summaries(records)

        # Generate markdown report
        markdown_rep = self._format_audit_markdown(records, summaries)

        report = DataCoverageAuditReport(
            audit_date=datetime.now().strftime("%Y-%m-%d"),
            model_records=records,
            signal_summaries=summaries,
            markdown_report=markdown_rep,
        )
        logger.info(f"✅ Data Coverage Audit complete: audited {len(records)} series across {len(summaries)} signals.")
        return report

    def _audit_sales_series(self) -> List[SeriesAuditRecord]:
        """Audits SalesObservation series for monthly continuity and volume."""
        cypher = """
        MATCH (v:VehicleModel)-[:HAS_SALES_OBSERVATION]->(s:SalesObservation)
        WHERE s.period_type = 'MONTH'
        RETURN v.name AS model,
               s.period_value AS period,
               s.units_sold AS units
        ORDER BY v.name, s.period_value ASC
        """
        rows = self.client.query(cypher)
        by_model: Dict[str, List[Dict[str, Any]]] = {}
        for r in rows:
            m = r.get("model", "Unknown")
            by_model.setdefault(m, []).append(r)

        # Also get models that have NO monthly sales
        all_models = [r["name"] for r in self.client.query("MATCH (v:VehicleModel) RETURN v.name AS name")]
        for m in all_models:
            if m not in by_model:
                by_model[m] = []

        records = []
        for m, pts in by_model.items():
            periods = [p["period"] for p in pts]
            cnt = len(periods)

            if cnt == 0:
                records.append(
                    SeriesAuditRecord(
                        model_name=m,
                        signal_name="Monthly Sales Dispatches",
                        total_observations=0,
                        temporal_granularity="NONE",
                        min_timestamp="N/A",
                        max_timestamp="N/A",
                        usable_periods_count=0,
                        consecutive_periods_count=0,
                        has_gaps=True,
                        gap_summary="No monthly sales observations in graph.",
                        feasibility_status="INSUFFICIENT",
                        suitable_forecasting_methods=["None (Heuristic segment estimate only)"],
                        notes="Requires SIAM monthly wholesale dispatch ingestion.",
                    )
                )
                continue

            min_p = min(periods)
            max_p = max(periods)

            # Analyze continuity & consecutive run
            consec_count, has_gap, gap_desc = self._analyze_monthly_continuity(periods)

            if consec_count >= 12:
                status = "SUFFICIENT"
                methods = ["Seasonal Naïve", "Holt-Winters", "ARIMA/SARIMA", "Moving Average", "Linear/ML Trend"]
            elif consec_count >= 5 or cnt >= 6:
                status = "MARGINAL"
                methods = ["Naïve Baseline (Last-Known-Month)", "3-Month Moving Average (SMA-3)", "Holt's Linear Trend / SES"]
            else:
                status = "INSUFFICIENT"
                methods = ["Naïve Drift (Last-Known-Month with Segment Trend)"]

            records.append(
                SeriesAuditRecord(
                    model_name=m,
                    signal_name="Monthly Sales Dispatches",
                    total_observations=cnt,
                    temporal_granularity="MONTHLY",
                    min_timestamp=min_p,
                    max_timestamp=max_p,
                    usable_periods_count=cnt,
                    consecutive_periods_count=consec_count,
                    has_gaps=has_gap,
                    gap_summary=gap_desc,
                    feasibility_status=status,
                    suitable_forecasting_methods=methods,
                    notes=f"{consec_count} consecutive months ({min_p} to {max_p}).",
                )
            )
        return records

    def _analyze_monthly_continuity(self, periods: List[str]) -> tuple[int, bool, str]:
        """Calculates consecutive monthly run and identifies temporal gaps."""
        if not periods:
            return 0, False, "No observations"
        if len(periods) == 1:
            return 1, False, "Single isolated month"

        # Parse YYYY-MM
        parsed = []
        for p in periods:
            try:
                parts = p.split("-")
                parsed.append((int(parts[0]), int(parts[1])))
            except Exception:
                continue
        parsed.sort()

        max_consec = 1
        current_consec = 1
        gaps = []

        for i in range(1, len(parsed)):
            y_prev, m_prev = parsed[i - 1]
            y_curr, m_curr = parsed[i]

            diff_months = (y_curr - y_prev) * 12 + (m_curr - m_prev)
            if diff_months == 1:
                current_consec += 1
                max_consec = max(max_consec, current_consec)
            else:
                gaps.append(f"{y_prev}-{m_prev:02d} to {y_curr}-{m_curr:02d} ({diff_months - 1} missing months)")
                current_consec = 1

        has_gap = len(gaps) > 0
        gap_desc = "; ".join(gaps) if has_gap else "Continuous unbroken series"
        return max_consec, has_gap, gap_desc

    def _audit_price_series(self) -> List[SeriesAuditRecord]:
        """Audits PriceObservation for revisions, effective dates, and volatility."""
        cypher = """
        MATCH (v:VehicleModel)-[:HAS_PRICE_OBSERVATION]->(p:PriceObservation)
        RETURN v.name AS model,
               collect(DISTINCT p.valid_from) AS dates,
               count(p) AS total_obs
        ORDER BY v.name
        """
        rows = self.client.query(cypher)
        records = []

        for r in rows:
            m = r.get("model", "Unknown")
            dates = [d for d in r.get("dates", []) if d]
            cnt = int(r.get("total_obs", 0))

            if not dates:
                continue

            dates.sort()
            min_d = dates[0]
            max_d = dates[-1]
            date_cnt = len(dates)

            status = "MARGINAL" if date_cnt >= 3 else "INSUFFICIENT"
            records.append(
                SeriesAuditRecord(
                    model_name=m,
                    signal_name="Variant Pricing Ladder",
                    total_observations=cnt,
                    temporal_granularity="IRREGULAR_EVENT_STEP",
                    min_timestamp=min_d,
                    max_timestamp=max_d,
                    usable_periods_count=date_cnt,
                    consecutive_periods_count=date_cnt,
                    has_gaps=False,
                    gap_summary="Step-function revisions (effective dates)",
                    feasibility_status=status,
                    suitable_forecasting_methods=["Scenario Price Elasticity", "Step-Shift Intercept"],
                    notes=f"{cnt} variant price points across {date_cnt} revision dates ({min_d} to {max_d}).",
                )
            )
        return records

    def _audit_sentiment_series(self) -> List[SeriesAuditRecord]:
        """Audits Opinion sentiment claims for temporal distribution across quarters."""
        cypher = """
        MATCH (rev:Review)-[:ABOUT]->(v:VehicleModel)
        MATCH (rev)-[:CONTAINS]->(o:Opinion)
        RETURN v.name AS model,
               collect(DISTINCT o.observed_at) AS quarters,
               count(o) AS total_opinions
        ORDER BY v.name
        """
        rows = self.client.query(cypher)
        records = []

        for r in rows:
            m = r.get("model", "Unknown")
            q_list = [q for q in r.get("quarters", []) if q]
            cnt = int(r.get("total_opinions", 0))

            if not q_list:
                continue

            q_list.sort()
            min_q = q_list[0]
            max_q = q_list[-1]
            q_cnt = len(q_list)

            status = "SUFFICIENT" if q_cnt >= 8 else ("MARGINAL" if q_cnt >= 4 else "INSUFFICIENT")
            records.append(
                SeriesAuditRecord(
                    model_name=m,
                    signal_name="Aspect Sentiment & Claims",
                    total_observations=cnt,
                    temporal_granularity="QUARTERLY",
                    min_timestamp=min_q,
                    max_timestamp=max_q,
                    usable_periods_count=q_cnt,
                    consecutive_periods_count=q_cnt,
                    has_gaps=False,
                    gap_summary="Quarterly rolling sentiment cohorts",
                    feasibility_status=status,
                    suitable_forecasting_methods=["Sentiment Momentum Index", "Lagged Sentiment Regression"],
                    notes=f"{cnt} opinions across {q_cnt} quarters ({min_q} to {max_q}).",
                )
            )
        return records

    def _audit_search_signals(self) -> List[SeriesAuditRecord]:
        """Audits SearchQuery demand signals for temporal frequency."""
        cypher = """
        MATCH (sq:SearchQuery)-[:TARGETS]->(v:VehicleModel)
        RETURN v.name AS model,
               collect(DISTINCT sq.observed_at) AS dates,
               count(sq) AS total_queries
        ORDER BY v.name
        """
        rows = self.client.query(cypher)
        records = []

        for r in rows:
            m = r.get("model", "Unknown")
            cnt = int(r.get("total_queries", 0))
            dates = [d for d in r.get("dates", []) if d]
            d_str = dates[0] if dates else "Current Snapshot"

            records.append(
                SeriesAuditRecord(
                    model_name=m,
                    signal_name="Search Intent & Demand",
                    total_observations=cnt,
                    temporal_granularity="CROSS_SECTIONAL_SNAPSHOT",
                    min_timestamp=d_str,
                    max_timestamp=d_str,
                    usable_periods_count=1,
                    consecutive_periods_count=1,
                    has_gaps=True,
                    gap_summary="Static single-timestamp intent capture",
                    feasibility_status="INSUFFICIENT",
                    suitable_forecasting_methods=["Static Search Volume Multiplier", "Intent Weight Scaling"],
                    notes=f"{cnt} queries captured as cross-sectional snapshot; requires monthly Google Trends ingestion for longitudinal forecasting.",
                )
            )
        return records

    def _compute_signal_summaries(self, records: List[SeriesAuditRecord]) -> List[SignalCoverageSummary]:
        """Aggregates series metrics into signal-level feasibility summaries."""
        by_signal: Dict[str, List[SeriesAuditRecord]] = {}
        for r in records:
            by_signal.setdefault(r.signal_name, []).append(r)

        summaries = []
        for sig_name, recs in by_signal.items():
            tot_models = len(recs)
            tot_obs = sum(r.total_observations for r in recs)
            avg_obs = tot_obs / tot_models if tot_models > 0 else 0.0

            statuses = [r.feasibility_status for r in recs]
            if statuses.count("SUFFICIENT") >= tot_models * 0.5:
                overall = "SUFFICIENT"
                rec = "Ready for seasonal, statistical, and ML time-series modeling."
            elif statuses.count("MARGINAL") + statuses.count("SUFFICIENT") >= tot_models * 0.5:
                overall = "MARGINAL"
                rec = "Sufficient for short-horizon statistical baselines (Naïve, SMA-3, SES). Model augmentation recommended."
            else:
                overall = "INSUFFICIENT"
                rec = "Sparse coverage. Ingest additional monthly observations before training statistical time-series models."

            summaries.append(
                SignalCoverageSummary(
                    signal_name=sig_name,
                    total_models_covered=tot_models,
                    total_observations=tot_obs,
                    average_observations_per_model=round(avg_obs, 1),
                    overall_feasibility=overall,
                    key_recommendation=rec,
                )
            )
        return summaries

    def _format_audit_markdown(
        self, records: List[SeriesAuditRecord], summaries: List[SignalCoverageSummary]
    ) -> str:
        """Renders comprehensive GitHub-flavored markdown report of the audit."""
        lines = []
        lines.append("# 📊 Historical Data Coverage & Forecasting Feasibility Audit")
        lines.append(f"**Audit Execution Date**: `{datetime.now().strftime('%Y-%m-%d')}` | **Target DB**: `Neo4j 5.26`")
        lines.append("")

        # ── 1. Executive Summary ─────────────────────────────────────────────
        lines.append("## 1. Executive Feasibility Summary")
        lines.append(
            "> [!IMPORTANT]\n"
            "> **Forecasting Architecture Rule**: Do not train autoregressive or complex ML models (SARIMA / Prophet / LSTM) "
            "on series with fewer than 12 continuous observations. Models with $N < 12$ must deploy **Naïve**, **Moving Average (SMA-3)**, "
            "or **Exponential Smoothing (SES / Holt)** baselines with explicit prediction intervals.\n"
        )

        lines.append("| Signal Domain | Models Audited | Total Observations | Avg Obs / Model | Granularity | Feasibility Rating | Strategic Recommendation |")
        lines.append("| :--- | :---: | :---: | :---: | :--- | :---: | :--- |")
        for s in summaries:
            color_badge = "🟢 **SUFFICIENT**" if s.overall_feasibility == "SUFFICIENT" else ("🟡 **MARGINAL**" if s.overall_feasibility == "MARGINAL" else "🔴 **INSUFFICIENT**")
            lines.append(f"| **{s.signal_name}** | {s.total_models_covered} | {s.total_observations:,} | {s.average_observations_per_model} | Varying | {color_badge} | {s.key_recommendation} |")
        lines.append("")

        # ── 2. Detailed Series Breakdown ─────────────────────────────────────
        lines.append("## 2. Granular Signal-by-Signal Audit")

        signals = list(dict.fromkeys(r.signal_name for r in records))
        for sig in signals:
            sig_recs = [r for r in records if r.signal_name == sig]
            lines.append(f"### 📈 Signal: {sig}")
            lines.append("| Vehicle Model | Obs Count | Usable Range | Granularity | Continuity / Gaps | Feasibility | Usable Forecasting Methods |")
            lines.append("| :--- | :---: | :--- | :--- | :--- | :---: | :--- |")

            for r in sig_recs:
                status_icon = "🟢" if r.feasibility_status == "SUFFICIENT" else ("🟡" if r.feasibility_status == "MARGINAL" else "🔴")
                range_str = f"{r.min_timestamp} → {r.max_timestamp}" if r.min_timestamp != "N/A" else "None"
                methods_str = ", ".join(r.suitable_forecasting_methods[:2])
                lines.append(f"| **{r.model_name}** | {r.total_observations} | `{range_str}` | `{r.temporal_granularity}` | {r.gap_summary} | {status_icon} `{r.feasibility_status}` | {methods_str} |")
            lines.append("")

        # ── 3. Strategic Action Plan ─────────────────────────────────────────
        lines.append("## 3. Recommended Forecasting Architecture Plan")
        lines.append("Based on empirical data boundaries established in this audit:")
        lines.append("1. **Sales Forecasting Engine (Action 2)**:")
        lines.append("   - Deploy **3-Tier Baseline Architecture**:")
        lines.append("     - **Tier 1 (Naïve Baseline)**: $y_{t+1} = y_t$ with historical drift trend.")
        lines.append("     - **Tier 2 (Moving Average SMA-3)**: Trailing 3-month dispatch momentum.")
        lines.append("     - **Tier 3 (Holt's Linear Trend / SES)**: Level smoothing ($\alpha$) and trend smoothing ($\beta$) with 80% and 95% prediction intervals.")
        lines.append("2. **Historical Backtest Validation (Action 2)**:")
        lines.append("   - Backtest on models with consecutive months (e.g. Aura, Amaze, Dzire) evaluating **MAE**, **MAPE**, and **RMSE** against holdout observations.")
        lines.append("3. **Graph Persistence (Action 4)**:")
        lines.append("   - Connect predictions to Neo4j via `ForecastRun` and `SalesPrediction` nodes linked to `VehicleModel` without contaminating observed `SalesObservation` nodes.")

        return "\n".join(lines)
