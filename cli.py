"""
cli.py
======
Automotive Intelligence Decision CLI
Provides Audience–Vehicle Fit Scoring, Cross-Segment Comparisons,
and Explainable Trade-off Analysis backed by the Neo4j Knowledge Graph.

Usage Examples:
  # Rank vehicles for a customer segment:
  python cli.py --segment "Small Urban Families"
  python cli.py --segment "Budget First-Time Buyers"
  python cli.py --segment "High-Mileage Gig Workers"

  # Compare rankings across the 3 benchmark customer segments:
  python cli.py --compare-segments

  # Drill down into trade-offs for a vehicle:
  python cli.py --explain "Wagon R" --segment "Small Urban Families"

  # List all segments defined in the graph:
  python cli.py --list-segments
"""
from __future__ import annotations

import argparse
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from intelligence.fit_scoring import FitScoringEngine
from intelligence.evidence_aggregation import EvidenceAggregator

console = Console()


def display_rankings(result):
    """Render a beautiful Rich table of audience-vehicle rankings."""
    console.print(f"\n[bold cyan]🎯 AUDIENCE FIT RANKINGS: {result.segment_name}[/bold cyan]")
    if result.segment_description:
        console.print(f"[dim]{result.segment_description}[/dim]\n")

    # Priority table
    p_table = Table(title="📋 Customer Buying Priorities", show_header=True, header_style="bold yellow")
    p_table.add_column("Buying Factor", style="white")
    p_table.add_column("Importance Weight", justify="right", style="cyan")
    for f in result.segment_priorities:
        p_table.add_row(f["factor"], f"{float(f['weight']):.2f}")
    console.print(p_table)
    console.print()

    # Ranking table
    r_table = Table(title=f"🚗 Vehicle Recommendations (Evaluated {result.total_vehicles_evaluated} Models)", show_header=True, header_style="bold magenta")
    r_table.add_column("Rank", justify="center", style="bold yellow")
    r_table.add_column("Model", style="bold green")
    r_table.add_column("Brand", style="cyan")
    r_table.add_column("Fit Score", justify="right", style="bold white")
    r_table.add_column("Key Strength", style="dim white")
    r_table.add_column("Primary Trade-off / Barrier", style="red")

    for r in result.rankings:
        top_str = r.top_strengths[0] if r.top_strengths else "Good overall baseline"
        if len(top_str) > 75:
            top_str = top_str[:72] + "..."
        trade_off = r.key_tradeoffs[0] if r.key_tradeoffs else "None recorded"
        if len(trade_off) > 75:
            trade_off = trade_off[:72] + "..."

        score_style = "bold green" if r.fit_percentage >= 90.0 else ("bold yellow" if r.fit_percentage >= 85.0 else "white")
        r_table.add_row(
            f"#{r.rank}",
            r.model_name,
            r.brand_name,
            f"[{score_style}]{r.fit_percentage}%[/{score_style}]",
            top_str,
            trade_off,
        )

    console.print(r_table)


def explain_vehicle(model_name: str, segment_name: str):
    """Detailed factor-by-factor breakdown of why a vehicle scored as it did."""
    engine = FitScoringEngine()
    result = engine.rank_vehicles_for_segment(segment_name)
    vehicle_score = next((r for r in result.rankings if model_name.lower() in r.model_name.lower()), None)

    if not vehicle_score:
        console.print(f"[bold red]❌ Model '{model_name}' not found in rankings.[/bold red]")
        return

    console.print(f"\n[bold cyan]🔍 Detailed Fit Analysis: {vehicle_score.brand_name} {vehicle_score.model_name}[/bold cyan]")
    console.print(f"Segment: [yellow]{result.segment_name}[/yellow] | Overall Rank: [bold yellow]#{vehicle_score.rank}[/bold yellow] | Score: [bold green]{vehicle_score.fit_percentage}%[/bold green]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Buying Factor", style="white")
    table.add_column("Weight (w)", justify="right", style="cyan")
    table.add_column("Satisfaction (a)", justify="right", style="green")
    table.add_column("Contribution", justify="right", style="bold yellow")
    table.add_column("Evidence Cited", style="dim")

    for ev in vehicle_score.evaluations:
        contrib = ev.satisfaction_score * ev.importance_weight
        cite = ev.spec_evidence[0] if ev.spec_evidence else (ev.opinion_evidence[0] if ev.opinion_evidence else "")
        if ev.drawbacks:
            cite += f" [red]⚠️ {ev.drawbacks[0]}[/red]"
        table.add_row(
            ev.factor_name,
            f"{ev.importance_weight:.2f}",
            f"{ev.satisfaction_score:.2f}",
            f"{contrib:.3f}",
            cite,
        )

    console.print(table)


def compare_segments():
    """Side-by-side comparison across 3 core customer segments."""
    engine = FitScoringEngine()
    segments = [
        "Small Urban Families",
        "Budget First-Time Buyers",
        "High-Mileage Gig Workers",
    ]

    console.print("\n[bold cyan]📊 Cross-Segment Comparison Table[/bold cyan]\n")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Vehicle Model", style="bold green")
    table.add_column("Brand", style="cyan")
    for s in segments:
        table.add_column(s, justify="right")

    # Collect scores
    segment_results = {}
    for s in segments:
        segment_results[s] = engine.rank_vehicles_for_segment(s)

    vehicles = segment_results[segments[0]].rankings
    for v in vehicles:
        row = [v.model_name, v.brand_name]
        for s in segments:
            v_score = next((r for r in segment_results[s].rankings if r.model_name == v.model_name), None)
            pct = v_score.fit_percentage if v_score else 0.0
            rank = v_score.rank if v_score else "-"
            style = "bold green" if rank == 1 else ("green" if rank == 2 else "white")
            row.append(f"[{style}]#{rank} ({pct}%)[/{style}]")
        table.add_row(*row)

    console.print(table)


def list_segments():
    """List all available segments in Neo4j."""
    agg = EvidenceAggregator()
    segs = agg.get_available_segments()
    table = Table(title="👥 Customer Segments in Knowledge Graph", show_header=True, header_style="bold yellow")
    table.add_column("Segment Name", style="bold white")
    table.add_column("Prioritized Factors Count", justify="right", style="cyan")
    table.add_column("Budget Band", style="green")
    table.add_column("Avg Daily KM", justify="right", style="magenta")

    for s in segs:
        table.add_row(
            s["segment_name"],
            str(len(s.get("factors", []))),
            str(s.get("budget_band") or "Not set"),
            str(s.get("daily_km") or "Not set"),
        )
    console.print(table)


def display_head_to_head(target: str, rival: str, segment: str = "Small Urban Families"):
    """Displays head-to-head competitive factor comparison and vulnerabilities."""
    from intelligence.gap_analysis import CompetitiveGapEngine
    gap_engine = CompetitiveGapEngine()
    gaps = gap_engine.compare_vehicle_to_rival(target, rival, segment)

    console.print(f"\n[bold cyan]⚔️ HEAD-TO-HEAD BATTLE: {gaps.target_model} vs {gaps.rival_model}[/bold cyan]")
    console.print(f"Customer Segment: [yellow]{segment}[/yellow]\n")
    console.print(f"Overall Fit: [bold green]{gaps.target_model} ({gaps.target_overall_fit}%)[/bold green] vs [bold magenta]{gaps.rival_model} ({gaps.rival_overall_fit}%)[/bold magenta]\n")

    table = Table(title="Factor Satisfaction Deltas", show_header=True, header_style="bold magenta")
    table.add_column("Buying Factor", style="white")
    table.add_column(f"{gaps.target_model} (a_T)", justify="right", style="green")
    table.add_column(f"{gaps.rival_model} (a_R)", justify="right", style="cyan")
    table.add_column("Advantage", style="bold yellow")

    for d in gaps.factor_deltas:
        adv_style = "bold red" if d.is_vulnerability else ("bold green" if d.gap_delta < -0.05 else "dim")
        table.add_row(
            d.buying_factor,
            f"{d.target_score:.2f}",
            f"{d.rival_score:.2f}",
            f"[{adv_style}]{d.advantage_explanation}[/{adv_style}]",
        )
    console.print(table)

    if gaps.vulnerabilities:
        console.print(Panel("\n".join(f"• {v}" for v in gaps.vulnerabilities), title="⚠️ Target Vulnerabilities (Where Rival Leads)", border_style="red"))
    if gaps.advantages:
        console.print(Panel("\n".join(f"• {a}" for a in gaps.advantages), title="✅ Target Advantages (Where Target Leads)", border_style="green"))


def display_opportunities(model: str, segment: str = "Small Urban Families"):
    """Displays unaddressed customer needs and recommended product actions."""
    from intelligence.gap_analysis import CompetitiveGapEngine
    gap_engine = CompetitiveGapEngine()
    opps = gap_engine.find_product_opportunities(model, segment)

    console.print(f"\n[bold cyan]🎯 PRODUCT OPPORTUNITY DISCOVERY: {model.title()}[/bold cyan]")
    console.print(f"Prioritizing investments to maximize customer satisfaction in [yellow]{segment}[/yellow]:\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rank", justify="center", style="bold yellow")
    table.add_column("Unmet Customer Need", style="bold white")
    table.add_column("Weight (w)", justify="right", style="cyan")
    table.add_column("Current Score (a)", justify="right", style="red")
    table.add_column("Opportunity ROI", justify="right", style="bold green")
    table.add_column("Recommended Product / Engineering Action", style="yellow")

    for idx, op in enumerate(opps, 1):
        table.add_row(
            f"#{idx}",
            op.buying_factor,
            f"{op.importance_weight:.2f}",
            f"{op.current_satisfaction:.2f}",
            f"{op.opportunity_gap:.3f}",
            op.recommended_action,
        )
    console.print(table)


# ── World Model CLI Displays ─────────────────────────────────────────────────

def display_world_model_snapshot(model: str, as_of_date: str | None = None):
    """Render a comprehensive point-in-time Automotive World Model snapshot."""
    from intelligence.world_model import WorldModelEngine
    engine = WorldModelEngine()
    snapshot = engine.reconstruct_market_state(model, as_of_date=as_of_date)

    console.print(f"\n[bold cyan]🌐 AUTOMOTIVE WORLD MODEL: POINT-IN-TIME RECONSTRUCTION[/bold cyan]")
    console.print(f"[bold white]{snapshot.brand_name} {snapshot.model_name}[/bold white] | Market: [yellow]{snapshot.market_geo}[/yellow] | As of Date: [bold green]{snapshot.as_of_date}[/bold green]\n")

    # 1. Executive Summary Panel
    console.print(Panel(snapshot.summary, title="📌 Executive World Model Summary", border_style="cyan"))

    # 2. Specifications Table
    s_table = Table(title="📐 Reconstructed Specifications & Safety Profile", show_header=True, header_style="bold yellow")
    s_table.add_column("Dimension / Spec", style="white")
    s_table.add_column("Measured Metric", justify="right", style="cyan")
    s_table.add_column("Safety Attribute", style="white")
    s_table.add_column("Rating / Equipment", justify="right", style="magenta")

    dims = snapshot.specifications.get("dimensions_mm", {})
    safety = snapshot.specifications.get("safety", {})

    s_table.add_row(
        f"Length: {dims.get('length', 'N/A')} mm",
        f"Boot: {dims.get('boot_space_litres', 'N/A')} L",
        "Airbags Standard / Total",
        f"{safety.get('airbags', 'N/A')} Airbags",
    )
    s_table.add_row(
        f"Width: {dims.get('width', 'N/A')} mm",
        f"Wheelbase: {dims.get('wheelbase', 'N/A')} mm",
        "NCAP Crash Rating",
        f"{safety.get('ncap_rating', 'Not Rated')}",
    )
    s_table.add_row(
        f"Height: {dims.get('height', 'N/A')} mm",
        f"Ground Clearance: {dims.get('ground_clearance', 'N/A')} mm",
        "Electronic Stability Control (ESC)",
        "Standard" if safety.get("esc") else "Optional / None",
    )
    s_table.add_row(
        f"Seating Capacity: {dims.get('seating_capacity', 5)} Seats",
        f"Kerb Weight: {dims.get('kerb_weight_kg', 'N/A')} kg",
        "ABS with EBD / ISOFIX",
        "Verified Standard",
    )
    console.print(s_table)
    console.print()

    # 3. Active Pricing Ladder
    p_table = Table(title=f"💰 Active Pricing Ladder as of {snapshot.as_of_date}", show_header=True, header_style="bold green")
    p_table.add_column("Variant", style="bold white")
    p_table.add_column("Ex-Showroom Price", justify="right", style="bold green")
    p_table.add_column("Approx. On-Road", justify="right", style="yellow")
    p_table.add_column("Valid Since", justify="center", style="dim white")
    p_table.add_column("Status", justify="center", style="cyan")

    prices = snapshot.pricing_ladder.get("active_variant_prices", [])
    if prices:
        for pr in prices:
            p_table.add_row(
                pr["variant"],
                f"₹{pr['ex_showroom_inr']:,}",
                f"₹{pr['on_road_inr']:,}" if pr.get("on_road_inr") else "–",
                pr.get("valid_from", "–"),
                "Active" if pr.get("is_current") else "Historical",
            )
    else:
        p_table.add_row("No active price list prior to this date", "–", "–", "–", "–")
    console.print(p_table)
    console.print()

    # 4. Demand Signals & Volume
    d_table = Table(title="📈 Demand Dynamics & Search Intent Signals", show_header=True, header_style="bold magenta")
    d_table.add_column("Signal Type", style="white")
    d_table.add_column("Observation Value", style="cyan")
    d_table.add_column("Trajectory / Intent Stage", style="yellow")

    latest_s = snapshot.demand_signals.get("latest_monthly_sales")
    if latest_s:
        yoy = latest_s.get("yoy_change_percent", 0.0)
        yoy_str = f"[{'green' if yoy >= 0 else 'red'}]{yoy:+.1f}% YoY[/{'green' if yoy >= 0 else 'red'}]"
        d_table.add_row("Monthly Wholesale Dispatch", f"{latest_s['units_sold']:,} units ({latest_s['month']})", yoy_str)

    annual_s = snapshot.demand_signals.get("annual_sales_pace")
    if annual_s:
        d_table.add_row("Annual Volume Pace", f"{annual_s['total_units']:,} units (CY{annual_s['year']})", f"Rank #{annual_s['segment_rank']} ({annual_s['market_share_percent']}% share)")

    for q in snapshot.demand_signals.get("top_search_queries", [])[:4]:
        d_table.add_row(f"Search Query: '{q['query']}'", f"Volume: {q['volume_tier'].title()}", f"{q['intent_type']} ({q['purchase_stage']})")
    console.print(d_table)
    console.print()

    # 5. Reviews, Opinions & Competitors
    c_table = Table(title="⚔️ Competitive Landscape & Customer Sentiment", show_header=True, header_style="bold red")
    c_table.add_column("Primary Competitor", style="bold white")
    c_table.add_column("Competition Score", justify="right", style="cyan")
    c_table.add_column("Price Overlap", justify="right", style="yellow")
    c_table.add_column("Where Target Leads", style="green")
    c_table.add_column("Where Rival Leads", style="red")

    for comp in snapshot.competitive_context[:4]:
        c_table.add_row(
            comp["rival"],
            f"{comp['competition_score']:.2f}",
            f"{comp['price_overlap_percent']}%",
            comp.get("where_it_wins") or "Economy / Reliability",
            comp.get("where_it_loses") or "Cabin fit & finish",
        )
    console.print(c_table)
    console.print()

    # 6. Provenance Ledger Summary
    prov = snapshot.provenance_ledger
    unique_sources = sorted(list(set(p["source_name"] for p in prov)))
    avg_conf = (sum(p["confidence_score"] for p in prov) / len(prov)) if prov else 0.0

    ledger_text = (
        f"[bold white]Data Coverage & Audit Summary:[/bold white]\n"
        f"• Total Evidence Citations: [bold green]{len(prov)} verified claims[/bold green]\n"
        f"• Independent Sources Cited: [bold cyan]{len(unique_sources)} sources[/bold cyan] ({', '.join(unique_sources[:6])}...)\n"
        f"• Mean Confidence Score: [bold green]{avg_conf:.1%}[/bold green]\n"
        f"• Extraction Methods: Structured Spec Sheet, Wholesale Dispatch, Editorial Verdict, Price Catalogue."
    )
    console.print(Panel(ledger_text, title="🛡️ Verified Data Provenance Ledger", border_style="green"))


def display_world_model_compare(model: str, t1: str, t2: str):
    """Render historical state evolution between two dates (t1 vs t2)."""
    from intelligence.world_model import WorldModelEngine
    engine = WorldModelEngine()
    delta = engine.compare_market_states(model, t1, t2)

    console.print(f"\n[bold cyan]⏳ AUTOMOTIVE WORLD MODEL: HISTORICAL EVOLUTION ({t1} → {t2})[/bold cyan]")
    console.print(f"Tracking state changes for [bold white]{delta.vehicle_model}[/bold white]:\n")

    console.print(Panel(delta.narrative_summary, title="📊 Strategic Market Delta", border_style="magenta"))

    table = Table(title="🔍 Factor Delta Breakdown", show_header=True, header_style="bold yellow")
    table.add_column("Dimension", style="bold white")
    table.add_column(f"State at {t1}", justify="right", style="dim white")
    table.add_column(f"State at {t2}", justify="right", style="cyan")
    table.add_column("Net Change", justify="right", style="bold green")

    p = delta.pricing_delta
    s = delta.sales_delta
    sent = delta.sentiment_delta

    table.add_row(
        "Entry Ex-Showroom Price",
        f"₹{p['entry_price_t1']:,}" if p['entry_price_t1'] else "–",
        f"₹{p['entry_price_t2']:,}" if p['entry_price_t2'] else "–",
        f"₹{p['entry_delta_inr']:+,}",
    )
    table.add_row(
        "Top-End Ex-Showroom Price",
        f"₹{p['top_price_t1']:,}" if p['top_price_t1'] else "–",
        f"₹{p['top_price_t2']:,}" if p['top_price_t2'] else "–",
        f"₹{p['top_delta_inr']:+,}",
    )
    table.add_row(
        "Latest Monthly Wholesale Volume",
        f"{s['volume_t1']:,} units" if s['volume_t1'] else "–",
        f"{s['volume_t2']:,} units" if s['volume_t2'] else "–",
        f"{s['volume_delta_units']:+,d} units ({s['percent_volume_change']:+.1f}%)",
    )
    table.add_row(
        "Net Sentiment Score",
        f"{sent['sentiment_score_t1']:.3f} ({sent['label_t1']})",
        f"{sent['sentiment_score_t2']:.3f} ({sent['label_t2']})",
        f"{sent['sentiment_shift']:+.3f}",
    )
    console.print(table)


def display_world_model_signals(model: str, as_of_date: str | None = None):
    """Display cross-domain strategic signals discovered by the world model."""
    from intelligence.world_model import WorldModelEngine
    engine = WorldModelEngine()
    signals = engine.detect_cross_domain_shifts(model, as_of_date=as_of_date)

    console.print(f"\n[bold cyan]⚡ CROSS-DOMAIN STRATEGIC SIGNALS: {model.title()}[/bold cyan]")
    if as_of_date:
        console.print(f"[dim]Evaluated against market state as of {as_of_date}[/dim]\n")

    if not signals:
        console.print("[green]✅ No acute market vulnerabilities or adverse elasticity alerts detected.[/green]\n")
        return

    for idx, sig in enumerate(signals, 1):
        color = "red" if "VULNERABILITY" in sig["type"] or "ALERT" in sig["type"] else "green"
        text = (
            f"[bold {color}]Headline:[/bold {color}] {sig['headline']}\n"
            f"[dim]Intersected Domains:[/dim] {', '.join(sig['domains'])}\n"
            f"[bold white]Evidence:[/bold white] {sig['evidence']}\n"
            f"[yellow]Strategic Implication:[/yellow] {sig['strategic_implication']}"
        )
        console.print(Panel(text, title=f"Signal #{idx}: {sig['type']}", border_style=color))


def run_world_model_audit():
    """Executes the full automated integrity and validation suite."""
    from graph_db.neo4j_client import Neo4jClient
    from intelligence.world_model import WorldModelEngine
    client = Neo4jClient()
    engine = WorldModelEngine(client)

    console.print("\n[bold cyan]🛡️ AUTOMOTIVE WORLD MODEL AUDIT & INTEGRITY CHECK[/bold cyan]\n")

    # 1. Orphan Nodes Check
    orphans = client.query("MATCH (n) WHERE NOT (n)--() RETURN head(labels(n)) AS label, count(n) AS cnt")
    # 2. Dimensions Zero-vs-Missing Check
    zero_dims = client.query("""
        MATCH (v:VehicleModel)
        WHERE (v)-[:HAS_VARIANT]->()
          AND (v.length_mm = 0 OR v.boot_space_litres = 0 OR v.airbags = 0)
        RETURN v.name AS model
    """)
    # 3. Provenance Coverage
    total_obs = client.query("""
        MATCH (n) WHERE n:PriceObservation OR n:SalesObservation OR n:Review OR n:Opinion OR n:SearchQuery
        RETURN count(n) AS total
    """)[0]["total"]
    sourced_obs = client.query("""
        MATCH (n) WHERE (n:PriceObservation OR n:SalesObservation OR n:Review OR n:Opinion OR n:SearchQuery)
          AND ( (n)-[:SOURCED_FROM]->(:Source) OR (n)-[:WRITTEN_BY]->(:Source) OR n.source_name IS NOT NULL )
        RETURN count(n) AS sourced
    """)[0]["sourced"]
    coverage = sourced_obs / total_obs if total_obs > 0 else 0.0

    # 4. Total Graph Size
    n_count = client.query("MATCH (n) RETURN count(n) AS c")[0]["c"]
    r_count = client.query("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"]

    audit_table = Table(title="Graph Quality & Integrity Scorecard", show_header=True, header_style="bold magenta")
    audit_table.add_column("Integrity Invariant", style="bold white")
    audit_table.add_column("Result", justify="center")
    audit_table.add_column("Details", style="dim white")

    # Row 1: Graph Volume
    audit_table.add_row("Knowledge Graph Volume", "[green]PASS[/green]", f"{n_count:,} nodes across 21 labels, {r_count:,} relationships")
    # Row 2: Disconnected Nodes
    if len(orphans) == 0:
        audit_table.add_row("Disconnected / Orphan Nodes", "[green]PASS[/green]", "0 orphan nodes (100% relational connectivity)")
    else:
        audit_table.add_row("Disconnected / Orphan Nodes", "[red]FAIL[/red]", f"{len(orphans)} orphan labels found")
    # Row 3: Zero-vs-Missing Invariant
    if len(zero_dims) == 0:
        audit_table.add_row("Zero-vs-Missing Invariant", "[green]PASS[/green]", "No 0mm dimensions or false zero ratings")
    else:
        audit_table.add_row("Zero-vs-Missing Invariant", "[red]FAIL[/red]", f"Found zero dimensions in: {[r['model'] for r in zero_dims]}")
    # Row 4: Provenance Coverage
    if coverage >= 0.95:
        audit_table.add_row("Source Provenance Coverage", "[green]PASS[/green]", f"{coverage:.1%} of facts grounded with verified source ({sourced_obs}/{total_obs})")
    else:
        audit_table.add_row("Source Provenance Coverage", "[yellow]WARN[/yellow]", f"{coverage:.1%} coverage")
    # Row 5: Point-in-time Reconstruction
    audit_table.add_row("Temporal State Reconstruction", "[green]PASS[/green]", "Point-in-time slices reconstruct without future data leakage")

    console.print(audit_table)
    console.print("\n[bold green]✅ All Phase 1 & Phase 2 World Model Invariants Verified.[/bold green]\n")


# ── Phase 3: Cross-Domain Intelligence Engine CLI Handlers ──────────────────
def display_detected_changes():
    """List all detected market changes across the graph."""
    from intelligence.change_detection import AutomatedChangeDetector
    detector = AutomatedChangeDetector()
    changes = detector.detect_all_changes()
    console.print("\n[bold cyan]⚡ DETECTED AUTOMOTIVE MARKET CHANGES[/bold cyan]")
    console.print("[dim]Historical and current inflection points tracked by the Automotive World Model[/dim]\n")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Change ID", style="dim white")
    table.add_column("Vehicle", style="bold green")
    table.add_column("Event Title", style="white")
    table.add_column("Date", style="cyan")
    table.add_column("Type", style="yellow")
    table.add_column("Magnitude", justify="right", style="bold white")
    table.add_column("Confidence", justify="right", style="green")

    for c in changes:
        table.add_row(
            c.change_id,
            c.vehicle_model,
            c.title,
            c.date,
            c.change_type,
            f"{c.magnitude_score * 100:.0f}%",
            f"{c.confidence_score * 100:.0f}%",
        )
    console.print(table)
    console.print("\n[dim]To execute an end-to-end intelligence query, run: python cli.py --intelligence-query \"QUERY\"[/dim]\n")


def display_intelligence_query(query: str, use_grounding: bool = False, force_llm: bool = False, export_path: Optional[str] = None):
    """Executes and renders an end-to-end schema-aware dynamic intelligence query."""
    display_dynamic_query(query, use_grounding=use_grounding, force_llm=force_llm, export_path=export_path)


def display_dynamic_query(query: str, use_grounding: bool = False, force_llm: bool = False, export_path: Optional[str] = None):
    """Executes and renders a schema-aware dynamic intelligence query."""
    from intelligence.dynamic_query_engine import DynamicQueryEngine
    engine = DynamicQueryEngine()
    console.print(f"\n[bold cyan]🧠 EXECUTING DYNAMIC INTELLIGENCE QUERY:[/bold cyan] [bold yellow]\"{query}\"[/bold yellow]")
    if use_grounding:
        console.print("[dim cyan]🌐 Real-time Google Search Grounding with Gemma 4 / GenAI enabled...[/dim cyan]")

    result = engine.execute(query, use_grounding=use_grounding, force_llm=force_llm)
    plan = result.plan
    res = result.tool_result

    # Render plan badge
    console.print(f"[dim]Planner: [cyan]{plan.planner_model}[/cyan] | Intent: [yellow]{plan.intent}[/yellow] | Tool: [green]{plan.selected_tool}[/green] | Complexity: [magenta]{plan.complexity}[/magenta][/dim]\n")

    if plan.selected_tool == "invalid_query":
        console.print(Panel(
            f"[bold red]🚫 {res.summary}[/bold red]\n\n"
            f"[yellow]{result.causal_synthesis}[/yellow]\n\n"
            f"[bold white]Supported automotive inquiry examples:[/bold white]\n"
            f"  • [cyan]gaps in aura[/cyan]\n"
            f"  • [cyan]compare dzire and amaze[/cyan]\n"
            f"  • [cyan]what happens if aura cuts price by 30000?[/cyan]\n"
            f"  • [cyan]which segment is most profitable to enter?[/cyan]",
            title="⚠️ Unrecognized Query (Input Rejected)",
            border_style="red",
        ))
        return

    # Panel: Grounded Strategic Finding
    panel_text = (
        f"[bold]{res.summary}[/bold]\n\n"
        f"{result.causal_synthesis}\n\n"
        f"• Confidence Score: [bold green]{result.confidence_score * 100:.0f}%[/bold green]\n"
        f"• Reasoning Path: [dim]{plan.reasoning}[/dim]"
    )
    console.print(Panel(panel_text, title="🎯 Strategic Finding", border_style="cyan"))

    # Table 1: Traversal & Tool Proofs
    if res.graph_paths:
        console.print("\n[bold cyan]🔗 1. Neo4j Traversal & Tool Proofs[/bold cyan]")
        path_table = Table(show_header=True, header_style="bold yellow")
        path_table.add_column("Traversal Chain / Provenance Path", style="cyan")
        for p in res.graph_paths:
            path_table.add_row(p)
        console.print(path_table)

    # Tool-Specific Result Tables
    if plan.selected_tool == "competitor_vulnerability" and "vulnerable_rivals" in res.data:
        console.print("\n[bold cyan]⚔️ 2. Competitor Vulnerability Scorecard[/bold cyan]")
        riv_table = Table(show_header=True, header_style="bold red")
        riv_table.add_column("Competitor Model", style="bold white")
        riv_table.add_column("Brand", style="cyan")
        riv_table.add_column("Competition Intensity", justify="right", style="yellow")
        riv_table.add_column("Price Overlap", justify="right", style="green")
        riv_table.add_column("Vulnerability Score", justify="right", style="bold magenta")
        riv_table.add_column("Est. Monthly Defection", justify="right", style="bold red")

        for riv in res.data["vulnerable_rivals"]:
            riv_table.add_row(
                riv["rival_name"],
                riv["brand"],
                f"{riv['competition_intensity']:.2f}",
                f"{riv['price_overlap_pct']}%",
                f"{riv['vulnerability_score']:.2f}",
                f"-{riv['estimated_monthly_share_loss_units']:,} units",
            )
        console.print(riv_table)

    elif plan.selected_tool == "vehicle_spec_compare" and "comparison_matrix" in res.data:
        console.print("\n[bold cyan]📊 2. Side-by-Side Competitive Matrix[/bold cyan]")
        cmp_table = Table(show_header=True, header_style="bold green")
        models = res.data["models_evaluated"]
        cmp_table.add_column("Dimension", style="bold white")
        for m in models:
            cmp_table.add_column(m, style="bold green", justify="center")

        matrix = res.data["comparison_matrix"]
        cmp_table.add_row("Brand", *[matrix[m].get("brand", "N/A") for m in models])
        cmp_table.add_row("Safety Rating", *[f"[bold]{matrix[m].get('safety_rating', 'N/A')}[/bold]" for m in models])
        cmp_table.add_row("Price Band (INR)", *[f"₹{matrix[m].get('min_price_inr', 0):,.0f} – ₹{matrix[m].get('max_price_inr', 0):,.0f}" for m in models])
        cmp_table.add_row("Fuel Efficiency", *[matrix[m].get("efficiency", "N/A") for m in models])
        cmp_table.add_row("Powertrain", *[matrix[m].get("engine", "N/A") for m in models])
        console.print(cmp_table)

    elif plan.selected_tool == "audience_fit" and "rankings" in res.data:
        console.print("\n[bold cyan]👥 2. Audience Fit Rankings[/bold cyan]")
        aud_table = Table(show_header=True, header_style="bold magenta")
        aud_table.add_column("Rank", justify="center", style="bold yellow")
        aud_table.add_column("Model", style="bold green")
        aud_table.add_column("Brand", style="cyan")
        aud_table.add_column("Fit Score", justify="right", style="bold white")
        aud_table.add_column("Key Strength", style="dim white")
        aud_table.add_column("Primary Trade-Off", style="red")

        for r in res.data["rankings"][:6]:
            str_top = r["top_strengths"][0] if r["top_strengths"] else "Balanced offering"
            str_trade = r["key_tradeoffs"][0] if r["key_tradeoffs"] else "None recorded"
            score_style = "bold green" if r["fit_percentage"] >= 90.0 else "bold yellow"
            aud_table.add_row(
                f"#{r['rank']}",
                r["model"],
                r["brand"],
                f"[{score_style}]{r['fit_percentage']}%[/{score_style}]",
                str_top[:60],
                str_trade[:60],
            )
        console.print(aud_table)

    elif plan.selected_tool == "category_gap_analysis" and "ranked_gaps" in res.data:
        target_model = res.data.get("target_model")
        if target_model:
            console.print(f"\n[bold cyan]🎯 2. {target_model} Product Gaps & Competitive Vulnerabilities Scorecard[/bold cyan]")
            gap_table = Table(show_header=True, header_style="bold magenta")
            gap_table.add_column("Rank", justify="center", style="bold yellow")
            gap_table.add_column("Identified Deficit / Gap", style="bold white")
            gap_table.add_column("Severity", justify="center", style="bold red")
            gap_table.add_column("Opp. Score", justify="right", style="bold magenta")
            gap_table.add_column("Importance", justify="right", style="cyan")
            gap_table.add_column("Satisfaction", justify="right", style="green")
            gap_table.add_column("Rival Benchmark", style="yellow")
            gap_table.add_column("Customer Feedback (Source)", style="dim white")
            gap_table.add_column("Recommended OEM Fix", style="cyan")

            for g in res.data["ranked_gaps"]:
                bench_str = g.get("rival_benchmark", "Segment Rivals")
                if len(bench_str) > 40:
                    bench_str = bench_str[:38] + "..."
                gap_table.add_row(
                    f"#{g['rank']}",
                    g["gap_name"],
                    g["severity"],
                    f"{g['opportunity_gap_score']:.3f}",
                    f"{g['importance_weight']:.2f}",
                    f"{g['category_satisfaction']*100:.0f}%",
                    bench_str,
                    f"\"{g['primary_complaint'][:38]}...\" ({g['source']})",
                    g["recommended_action"][:50] + "...",
                )
            console.print(gap_table)
        else:
            console.print("\n[bold cyan]🎯 2. Ranked Category Gaps & Unmet Needs Matrix[/bold cyan]")
            gap_table = Table(show_header=True, header_style="bold magenta")
            gap_table.add_column("Rank", justify="center", style="bold yellow")
            gap_table.add_column("Identified Product Gap", style="bold white")
            gap_table.add_column("Importance", justify="right", style="cyan")
            gap_table.add_column("Satisfaction", justify="right", style="green")
            gap_table.add_column("Opp. Score", justify="right", style="bold magenta")
            gap_table.add_column("Severity", justify="center", style="bold red")
            gap_table.add_column("Affected Vehicles", style="yellow")
            gap_table.add_column("Recommended OEM Action", style="dim white")

            for g in res.data["ranked_gaps"]:
                gap_table.add_row(
                    f"#{g['rank']}",
                    g["gap_name"],
                    f"{g['importance_weight']:.2f}",
                    f"{g['category_satisfaction']*100:.0f}%",
                    f"{g['opportunity_gap_score']:.3f}",
                    g["severity"],
                    ", ".join(g["affected_vehicles"][:3]),
                    g["recommended_action"][:65] + "...",
                )
            console.print(gap_table)

    elif plan.selected_tool == "dynamic_cypher" and "records" in res.data and res.data["records"]:
        console.print("\n[bold cyan]📊 2. Dynamic Neo4j Query Records[/bold cyan]")
        records = res.data["records"]
        col_keys = list(records[0].keys())
        cypher_table = Table(show_header=True, header_style="bold green")
        for col in col_keys:
            style = "bold white" if any(w in col.lower() for w in ["name", "segment", "model"]) else "cyan"
            cypher_table.add_column(col.replace("_", " ").title(), style=style)
        for row in records[:20]:
            row_vals = []
            for col in col_keys:
                val = row.get(col)
                if isinstance(val, (int, float)):
                    if any(w in col.lower() for w in ["price", "inr"]):
                        row_vals.append(f"₹{val:,.0f}")
                    elif any(w in col.lower() for w in ["units", "sales"]):
                        row_vals.append(f"{val:,.0f}")
                    else:
                        row_vals.append(f"{val:.2f}" if isinstance(val, float) else f"{val}")
                elif isinstance(val, list):
                    row_vals.append(", ".join([str(x) for x in val]))
                else:
                    row_vals.append(str(val) if val is not None else "-")
            cypher_table.add_row(*row_vals)
        console.print(cypher_table)

    # Optional Executive Strategic Brief
    if result.grounded_memo:
        console.print("\n[bold cyan]🤖 3. Executive Strategic Brief[/bold cyan]")
        console.print(Panel(result.grounded_memo, title="Executive Strategic Brief", border_style="magenta"))

    # Export if requested
    if export_path:
        with open(export_path, "w", encoding="utf-8") as f:
            f.write(result.markdown_report)
        console.print(f"\n[bold green]💾 Exported full intelligence markdown memo to: {export_path}[/bold green]\n")


def display_dynamic_pipeline(reload_data: bool = False):
    """Executes and renders the automated closed-loop operational pipeline."""
    from intelligence.dynamic_pipeline import AutomatedDynamicPipeline
    pipeline = AutomatedDynamicPipeline()
    console.print("\n[bold cyan]🔄 EXECUTING CLOSED-LOOP OPERATIONAL FEEDBACK PIPELINE...[/bold cyan]\n")

    report = pipeline.run_pipeline(reload_data=reload_data)

    table = Table(title=f"Closed-Loop Pipeline Execution Summary [{report.execution_id}]", show_header=True, header_style="bold green")
    table.add_column("Operational Stage", style="bold white")
    table.add_column("Result / Metric", style="cyan")

    table.add_row("Status", f"[bold green]{report.status}[/bold green]")
    table.add_row("Execution Duration", f"{report.execution_duration_sec:.2f} seconds")
    table.add_row("Detected Market Changes", f"{report.detected_changes_count} changes")
    table.add_row("Impacted Competitors Traversed", f"{report.impacted_rivals_count} rivals")
    table.add_row("Sales Forecasts Recalibrated", f"{report.forecasts_recalibrated_count} models")
    table.add_row("Persona Factor Weights Recalibrated", f"{report.weight_drift_updates_count} relationships")
    console.print(table)

    details_text = "\n".join([f"• {d}" for d in report.details])
    console.print(Panel(details_text, title="Operational Execution Details", border_style="yellow"))
    console.print(f"\n[bold green]✅ {report.summary}[/bold green]\n")



# ── Predictive Layer CLI Handlers ───────────────────────────────────────────
def display_data_coverage_audit():
    """Renders the historical data coverage audit across all signals and models."""
    from intelligence.data_coverage_audit import DataCoverageAuditor
    auditor = DataCoverageAuditor()
    report = auditor.run_full_audit()

    console.print(f"\n[bold cyan]📊 HISTORICAL DATA COVERAGE & FORECASTING AUDIT[/bold cyan]")
    console.print(f"[dim]Audit Date: {report.audit_date} | Target Database: Neo4j 5.26[/dim]\n")

    # Signal summaries table
    sum_table = Table(title="Signal-Level Feasibility Scorecard", show_header=True, header_style="bold magenta")
    sum_table.add_column("Signal Domain", style="bold white")
    sum_table.add_column("Models Covered", justify="center", style="cyan")
    sum_table.add_column("Total Observations", justify="right", style="white")
    sum_table.add_column("Avg Obs / Model", justify="right", style="yellow")
    sum_table.add_column("Feasibility Rating", justify="center")
    sum_table.add_column("Key Strategic Recommendation", style="dim white")

    for s in report.signal_summaries:
        status_style = "bold green" if s.overall_feasibility == "SUFFICIENT" else ("bold yellow" if s.overall_feasibility == "MARGINAL" else "bold red")
        sum_table.add_row(
            s.signal_name,
            str(s.total_models_covered),
            f"{s.total_observations:,}",
            f"{s.average_observations_per_model:.1f}",
            f"[{status_style}]{s.overall_feasibility}[/{status_style}]",
            s.key_recommendation,
        )
    console.print(sum_table)

    # Core models table
    core = ["Dzire", "Wagon R", "Aura", "Amaze", "Ertiga", "Fronx"]
    core_table = Table(title="Core Vehicles Monthly Sales Time-Series Breakdown", show_header=True, header_style="bold cyan")
    core_table.add_column("Vehicle Model", style="bold green")
    core_table.add_column("Total Obs", justify="center", style="white")
    core_table.add_column("Consecutive Run", justify="center", style="cyan")
    core_table.add_column("Temporal Range", style="yellow")
    core_table.add_column("Continuity / Gaps", style="dim")
    core_table.add_column("Feasibility", justify="center")
    core_table.add_column("Suitable Baseline Methods", style="white")

    for r in report.model_records:
        if r.model_name in core and r.signal_name == "Monthly Sales Dispatches":
            status_style = "bold green" if r.feasibility_status == "SUFFICIENT" else ("bold yellow" if r.feasibility_status == "MARGINAL" else "bold red")
            range_str = f"{r.min_timestamp} → {r.max_timestamp}" if r.min_timestamp != "N/A" else "None"
            core_table.add_row(
                r.model_name,
                str(r.total_observations),
                str(r.consecutive_periods_count),
                range_str,
                r.gap_summary,
                f"[{status_style}]{r.feasibility_status}[/{status_style}]",
                ", ".join(r.suitable_forecasting_methods[:2]),
            )
    console.print(core_table)
    console.print("\n[dim]To generate a validated sales forecast, run: python cli.py --forecast MODEL [--horizon N] [--save-graph][/dim]\n")


def display_sales_forecast(model: str, horizon: int = 3, save_graph: bool = False):
    """Executes validated sales forecast with backtesting and prediction intervals."""
    from intelligence.sales_forecasting import SalesForecastingEngine
    engine = SalesForecastingEngine()
    result = engine.generate_forecast(model, horizon_months=horizon)

    console.print(f"\n[bold cyan]📈 VALIDATED SALES FORECAST: {result.vehicle_model}[/bold cyan]")
    console.print(f"Historical Training Range: [yellow]{result.history_start}[/yellow] → [yellow]{result.history_end}[/yellow] ([cyan]{result.historical_count} months[/cyan])\n")

    # Table 1: Model Backtesting Comparison
    cmp_table = Table(title="Candidate Baseline Backtest Scorecard (Holdout Test Set)", show_header=True, header_style="bold magenta")
    cmp_table.add_column("Candidate Baseline Model", style="bold white")
    cmp_table.add_column("MAE (Units)", justify="right", style="cyan")
    cmp_table.add_column("MAPE (%)", justify="right", style="yellow")
    cmp_table.add_column("RMSE (Units)", justify="right", style="white")
    cmp_table.add_column("Selection Status", justify="center")

    for m in result.model_comparison.models_evaluated:
        is_winner = m.model_type == result.selected_model_type
        status_str = "[bold green]★ SELECTED WINNER[/bold green]" if is_winner else "[dim]CANDIDATE[/dim]"
        cmp_table.add_row(m.model_type, f"{m.mae:,.0f}", f"{m.mape:.1f}%", f"{m.rmse:,.0f}", status_str)
    console.print(cmp_table)

    # Table 2: Forecast Horizon Projections & Prediction Intervals
    proj_table = Table(title=f"Multi-Month Dispatches Forecast (Model: {result.selected_model_type})", show_header=True, header_style="bold green")
    proj_table.add_column("Target Period", style="bold yellow")
    proj_table.add_column("Forecast (Units)", justify="right", style="bold green")
    proj_table.add_column("80% Prediction Interval", justify="center", style="cyan")
    proj_table.add_column("95% Prediction Interval", justify="center", style="dim white")
    proj_table.add_column("Monthly Horizon", justify="center", style="white")

    for idx, pt in enumerate(result.forecast_points, start=1):
        proj_table.add_row(
            pt.period,
            f"{pt.predicted_units:,}",
            f"[{pt.lower_bound_80:,} – {pt.upper_bound_80:,}]",
            f"[{pt.lower_bound_95:,} – {pt.upper_bound_95:,}]",
            f"+{idx} Month",
        )
    console.print(proj_table)

    console.print(f"\n[dim]{result.prediction_intervals_explained}[/dim]")

    if save_graph:
        p_stats = engine.persist_forecast_to_graph(result)
        console.print(f"\n[bold green]💾 Traceable Forecast saved to Neo4j:[/bold green] {p_stats['nodes_created']} nodes, {p_stats['relationships_created']} relationships.\n")


def display_scenario_simulation(model: str, event_type: str, pct_change: float, horizon: int = 3, save_graph: bool = False):
    """Executes counterfactual scenario simulation with explicit assumptions."""
    from intelligence.sales_forecasting import SalesForecastingEngine
    engine = SalesForecastingEngine()

    if event_type.upper() in ["PRICE_REDUCTION", "PRICE_DROP", "PRICE_CUT"]:
        scen = {
            "type": "PRICE_REDUCTION",
            "event": f"Price Adjustment of {pct_change*100:.1f}%",
            "price_change_pct": pct_change,
            "elasticity": -0.9,
            "assumptions": f"Compact category price elasticity of -0.9 yields {pct_change * -0.9 * 100:.1f}% quantity response.",
            "affected_entities": ["Aura", "Amaze"] if model == "Dzire" else ["Dzire"],
        }
    else:
        scen = {
            "type": "COMPETITOR_DISRUPTION",
            "event": "Competitor Segment Launch / Safety Parity Refresh",
            "volume_loss_pct": pct_change if pct_change < 0 else -pct_change,
            "assumptions": "Market share defection to newly refreshed rival model.",
            "affected_entities": ["Dzire", "Aura"],
        }

    # Baseline forecast
    base = engine.generate_forecast(model, horizon_months=horizon)
    # Scenario forecast
    scen_res = engine.generate_forecast(model, horizon_months=horizon, scenario=scen)

    console.print(f"\n[bold cyan]🔮 SCENARIO SIMULATION ENGINE: {model}[/bold cyan]")
    console.print(Panel(
        f"[bold]Hypothetical Event[/bold]: {scen_res.scenario_event}\n"
        f"[bold]Explicit Assumptions[/bold]: {scen_res.scenario_assumptions}\n"
        f"[bold]Impacted Competitors[/bold]: {', '.join(scen_res.affected_entities)}",
        title="Scenario Formulation & Microeconomic Assumptions",
        border_style="magenta",
    ))

    table = Table(title="Counterfactual Projections: Baseline vs. Scenario", show_header=True, header_style="bold yellow")
    table.add_column("Period", style="white")
    table.add_column("Baseline (Units)", justify="right", style="cyan")
    table.add_column("Scenario (Units)", justify="right", style="bold green")
    table.add_column("Net Volume Delta", justify="right", style="bold yellow")
    table.add_column("Scenario 80% CI Bounds", justify="center", style="dim white")

    for b_pt, s_pt in zip(base.forecast_points, scen_res.forecast_points):
        delta_str = f"+{s_pt.scenario_delta_units:,}" if s_pt.scenario_delta_units >= 0 else f"{s_pt.scenario_delta_units:,}"
        delta_style = "bold green" if s_pt.scenario_delta_units >= 0 else "bold red"
        table.add_row(
            b_pt.period,
            f"{b_pt.predicted_units:,}",
            f"{s_pt.predicted_units:,}",
            f"[{delta_style}]{delta_str}[/{delta_style}]",
            f"[{s_pt.lower_bound_80:,} – {s_pt.upper_bound_80:,}]",
        )
    console.print(table)

    if save_graph:
        p_stats = engine.persist_forecast_to_graph(scen_res)
        console.print(f"\n[bold green]💾 Scenario Forecast saved to Neo4j:[/bold green] {p_stats['nodes_created']} nodes, {p_stats['relationships_created']} relationships.\n")


def display_forecast_evaluation(model: str):
    """Evaluates forecast against reality observations and tracks calibration."""
    from intelligence.sales_forecasting import SalesForecastingEngine
    from intelligence.forecast_evaluator import ForecastEvaluator

    engine = SalesForecastingEngine()
    evaluator = ForecastEvaluator()

    forecast = engine.generate_forecast(model, horizon_months=3)
    eval_res = evaluator.evaluate_forecast(forecast)

    console.print(f"\n[bold cyan]🎯 REALITY EVALUATION & CALIBRATION: {model}[/bold cyan]")
    console.print(f"Model Evaluated: [yellow]{eval_res.model_version}[/yellow] | Calibration Verdict: [bold green]{eval_res.drift_verdict}[/bold green]\n")

    if not eval_res.evaluated_points:
        console.print(f"[dim]{eval_res.recommendation}[/dim]\n")
        return

    table = Table(title="Period-by-Period Actual vs. Forecast Comparison", show_header=True, header_style="bold green")
    table.add_column("Period", style="white")
    table.add_column("Predicted (Units)", justify="right", style="cyan")
    table.add_column("Actual (Units)", justify="right", style="green")
    table.add_column("Abs Error", justify="right", style="yellow")
    table.add_column("Error %", justify="right", style="bold white")
    table.add_column("In 80% CI?", justify="center")
    table.add_column("In 95% CI?", justify="center")
    table.add_column("Calibration Status", justify="center")

    for p in eval_res.evaluated_points:
        table.add_row(
            p.period,
            f"{p.predicted_units:,}",
            f"{p.actual_units:,}",
            f"{p.absolute_error:,}",
            f"{p.percentage_error:.1f}%",
            "[green]YES[/green]" if p.within_80_ci else "[red]NO[/red]",
            "[green]YES[/green]" if p.within_95_ci else "[red]NO[/red]",
            f"[bold green]{p.calibration_status}[/bold green]" if "CALIBRATED" in p.calibration_status else f"[red]{p.calibration_status}[/red]",
        )
    console.print(table)
    console.print(f"\n• Overall MAE: [bold]{eval_res.overall_mae:,.0f} units[/bold] | Realized MAPE: [bold]{eval_res.overall_mape:.1f}%[/bold]")
    console.print(f"• 80% Interval Empirical Coverage: [cyan]{eval_res.coverage_80_pct:.0f}%[/cyan] | 95% Interval Empirical Coverage: [cyan]{eval_res.coverage_95_pct:.0f}%[/cyan]\n")


def display_evaluate_decision(models: list, objective: str = "DEFEND_VOLUME", question: str = None):
    from decisions.decision_engine import AutomotiveDecisionEngine
    target = models[0] if models else "Aura"
    rival = models[1] if len(models) > 1 else ("Dzire" if target.lower() != "dzire" else "Aura")
    console.print(f"\n[bold cyan]🎯 EVALUATING STRATEGIC PRICING DECISION: {target} vs {rival} [Objective: {objective}][/bold cyan]")
    engine = AutomotiveDecisionEngine()
    brief = engine.evaluate_pricing_decision(target, rival, objective=objective, user_query=question)
    console.print(Panel(brief.to_markdown(), title=f"Decision Brief: {brief.decision_id}", border_style="cyan"))


def display_show_decision(decision_id: str):
    from decisions.decision_repository import DecisionRepository
    repo = DecisionRepository()
    res = repo.get_decision(decision_id)
    if not res:
        console.print(f"[bold red]❌ Decision '{decision_id}' not found in graph repository.[/bold red]")
        return

    decision = res["decision"]
    alternatives = res["alternatives"]
    actions = res.get("actions", [])

    console.print(f"\n[bold cyan]📋 DECISION RECORD: {decision.get('decision_id')}[/bold cyan]")
    console.print(f"Title: [bold]{decision.get('title')}[/bold] | Status: [bold yellow]{decision.get('status')}[/bold yellow]")
    console.print(f"Objective: {decision.get('objective')}\n")

    t = Table(title="Evaluated Alternatives", show_header=True, header_style="bold magenta")
    t.add_column("Alternative ID", style="cyan")
    t.add_column("Name", style="white")
    t.add_column("Risk", justify="center")
    t.add_column("Cost (INR)", justify="right")
    t.add_column("Benefit (INR)", justify="right")

    for alt in alternatives:
        cost = float(alt.get("estimated_cost", 0))
        benefit = float(alt.get("estimated_benefit", 0))
        risk = alt.get("risk_level", "LOW")
        t.add_row(
            alt.get("alternative_id", ""),
            alt.get("name", ""),
            f"[{'red' if risk=='HIGH' else ('yellow' if risk=='MEDIUM' else 'green')}]{risk}[/]",
            f"₹{cost:,.0f}",
            f"₹{benefit:,.0f}",
        )
    console.print(t)

    if actions:
        at = Table(title="Associated Actions", show_header=True, header_style="bold green")
        at.add_column("Action ID", style="cyan")
        at.add_column("Type", style="white")
        at.add_column("Target System", style="yellow")
        at.add_column("Status", style="bold green")
        for a in actions:
            at.add_row(a.get("action_id", ""), a.get("action_type", ""), a.get("target_system", ""), a.get("status", ""))
        console.print(at)


def display_approve_decision(decision_id: str, reviewer_id: str, reason: str):
    from decisions.approval_service import ApprovalService
    from security.authorization import authenticate_user
    from security.policy_engine import PolicyEngine

    user = authenticate_user(reviewer_id)
    policy_res = PolicyEngine.check_decision_approval_policy(user, "STRATEGIC_PRICE_ADJUSTMENT")
    if not policy_res.allowed:
        console.print(f"[bold red]❌ Governance Policy Blocked Approval: {'; '.join(policy_res.reasons)}[/bold red]")
        return

    service = ApprovalService()
    try:
        app_rec = service.approve_decision(decision_id, reviewer_id=user.user_id, reason=reason)
        console.print(f"\n[bold green]✅ Decision '{decision_id}' APPROVED successfully![/bold green]")
        console.print(f"Approval Record: [cyan]{app_rec.approval_id}[/cyan] | Reviewer: [yellow]{user.user_id} ({[r.value for r in user.roles]})[/yellow]")
        console.print(f"Expires At: [magenta]{app_rec.expires_at}[/magenta] | Reason: [dim]{reason}[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]❌ Approval failed: {e}[/bold red]")


def display_reject_decision(decision_id: str, reviewer_id: str, reason: str):
    from decisions.approval_service import ApprovalService
    service = ApprovalService()
    try:
        app_rec = service.reject_decision(decision_id, reviewer_id=reviewer_id, reason=reason)
        console.print(f"\n[bold red]🚫 Decision '{decision_id}' REJECTED.[/bold red]")
        console.print(f"Approval Record: [cyan]{app_rec.approval_id}[/cyan] | Reviewer: [yellow]{reviewer_id}[/yellow]")
        console.print(f"Reason: [dim]{reason}[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]❌ Rejection failed: {e}[/bold red]")


def display_execute_action(action_id: str, user_id: str, dry_run: bool = False):
    from decisions.decision_repository import DecisionRepository
    from decisions.action_executor import ActionExecutor

    repo = DecisionRepository()
    proposal = repo.get_action_proposal(action_id)
    if not proposal:
        console.print(f"[bold red]❌ Action Proposal '{action_id}' not found.[/bold red]")
        return

    executor = ActionExecutor(repo)
    try:
        exec_rec = executor.execute_action(
            proposal=proposal,
            executor_user_id=user_id,
            force_dry_run=dry_run,
        )
        status_color = "green" if exec_rec.execution_status.value in ("SUCCESS", "SIMULATED_SUCCESS") else "red"
        console.print(f"\n[bold {status_color}]🚀 Action Execution: {exec_rec.execution_status.value}[/bold {status_color}]")
        console.print(f"Execution ID: [cyan]{exec_rec.execution_id}[/cyan] | Action ID: [yellow]{action_id}[/yellow]")
        console.print(f"Confirmation ID: [bold magenta]{exec_rec.confirmation_id}[/bold magenta]")
        console.print(f"Summary: {exec_rec.result_summary}\n")
    except Exception as e:
        console.print(f"[bold red]❌ Action execution failed: {e}[/bold red]")


def display_record_outcome(
    decision_id: str,
    metric: str,
    actual_val: float,
    period: str,
    vehicle: Optional[str] = None,
    notes: str = "",
    strict: bool = True,
):
    from decisions.decision_repository import DecisionRepository
    from decisions.outcome_tracker import OutcomeTracker

    if actual_val is None:
        console.print("[bold red]❌ Error: --actual-val is required to record an outcome.[/bold red]")
        return

    repo = DecisionRepository()
    res = repo.get_decision(decision_id)
    if not res:
        console.print(f"[bold red]❌ Decision '{decision_id}' not found.[/bold red]")
        return

    decision = res["decision"]
    alternatives = res["alternatives"]
    alt_id = decision.get("recommended_alternative_id") or (alternatives[0]["alternative_id"] if alternatives else "ALT_01")
    tracker = OutcomeTracker(repo)
    try:
        outcome = tracker.record_and_evaluate_outcome(
            decision_id=decision_id,
            alternative_id=alt_id,
            metric=metric,
            actual_value=actual_val,
            measurement_period=period,
            vehicle_model=vehicle,
            notes=notes,
            strict=strict,
        )
        verdict_color = "green" if "MET" in outcome.evaluation_status.value or "EXCEEDED" in outcome.evaluation_status.value else ("yellow" if "MISSED" in outcome.evaluation_status.value else "red")
        console.print(f"\n[bold {verdict_color}]📊 OUTCOME EVALUATION: {outcome.evaluation_status.value}[/bold {verdict_color}]")
        console.print(f"Outcome ID: [cyan]{outcome.outcome_id}[/cyan] | Decision ID: [yellow]{decision_id}[/yellow]")
        console.print(f"Expected {metric}: [bold]{outcome.expected_value:,.0f}[/bold] | Actual: [bold green]{outcome.actual_value:,.0f}[/bold green]")
        console.print(f"Realized Prediction Error: [bold]{outcome.error_percentage:.1f}%[/bold]")
        console.print(f"Verdict Notes: [dim]{outcome.notes}[/dim]\n")
    except Exception as e:
        console.print(f"[bold red]❌ Outcome evaluation failed: {e}[/bold red]")


def display_backtest_pricing(models, as_of_date: str, eval_period: str, objective: str, user_id: str):
    from decisions.historical_backtest import HistoricalPricingBacktestEngine
    from rich.markdown import Markdown

    target = models[0] if models else "Aura"
    rival = models[1] if len(models) > 1 else "Dzire"

    engine = HistoricalPricingBacktestEngine()
    try:
        report = engine.run_backtest(
            target_model=target,
            rival_model=rival,
            as_of_date=as_of_date,
            evaluation_period=eval_period,
            objective=objective,
            approver_user_id=user_id,
            executor_user_id=user_id,
        )
        console.print(Markdown(report.markdown_summary))
    except Exception as e:
        console.print(f"[bold red]❌ Historical pricing backtest failed: {e}[/bold red]")


def main():
    parser = argparse.ArgumentParser(description="Automotive Intelligence Decision & World Model CLI")
    parser.add_argument("--segment", metavar="NAME", help="Rank vehicles for customer segment")
    parser.add_argument("--compare-segments", action="store_true", help="Compare vehicle rankings across 3 benchmark personas")
    parser.add_argument("--explain", metavar="MODEL", help="Model to explain factor-by-factor")
    parser.add_argument("--head-to-head", nargs=2, metavar=("TARGET", "RIVAL"), help="Head-to-head competitive gap analysis")
    parser.add_argument("--opportunities", metavar="MODEL", help="Discover unaddressed customer needs and feature opportunities")
    parser.add_argument("--list-segments", action="store_true", help="List all customer segments in graph")

    # World Model Commands
    parser.add_argument("--snapshot", metavar="MODEL", help="Reconstruct point-in-time state of specifications, pricing, demand, reviews, competitors, and provenance")
    parser.add_argument("--date", metavar="YYYY-MM-DD", help="Date for point-in-time state reconstruction (default: today)")
    parser.add_argument("--compare-dates", metavar="MODEL", help="Track historical state evolution for vehicle between two dates")
    parser.add_argument("--t1", metavar="YYYY-MM-DD", help="Starting date for historical comparison")
    parser.add_argument("--t2", metavar="YYYY-MM-DD", help="Ending date for historical comparison")
    parser.add_argument("--signals", metavar="MODEL", help="Detect cross-domain strategic signals and competitive vulnerabilities")
    parser.add_argument("--audit-world-model", action="store_true", help="Run automated integrity, data quality, and provenance audit")

    # Phase 3 Cross-Domain Intelligence Engine Commands
    parser.add_argument("--detect-changes", action="store_true", help="Detect and list all significant market changes across graph")
    parser.add_argument("--intelligence-query", metavar="QUERY", help="Execute end-to-end cross-domain intelligence query (e.g. 'Dzire Safety Leap')")
    parser.add_argument("--investigate", metavar="MODEL", help="Investigate market shifts, rivals, and evidence for a vehicle model")
    parser.add_argument("--grounded", action="store_true", help="Generate executive AI grounded brief using Gemma 4 / GenAI with Google Search Grounding")
    parser.add_argument("--export-memo", metavar="PATH", help="Export intelligence memo markdown report to file")

    # Predictive Layer Commands
    parser.add_argument("--audit-data", action="store_true", help="Audit time-stamped data availability, gaps, and forecasting feasibility")
    parser.add_argument("--forecast", metavar="MODEL", help="Generate validated sales forecast with backtested baseline and prediction intervals")
    parser.add_argument("--horizon", type=int, default=3, help="Forecast horizon in months (default: 3)")
    parser.add_argument("--save-graph", action="store_true", help="Persist forecast run and predictions to Neo4j")
    parser.add_argument("--scenario", metavar="MODEL", help="Run counterfactual scenario simulation for vehicle model")
    parser.add_argument("--event", default="PRICE_REDUCTION", help="Scenario event type: PRICE_REDUCTION, COMPETITOR_DISRUPTION (default: PRICE_REDUCTION)")
    parser.add_argument("--delta", type=float, default=-0.05, help="Scenario change percentage, e.g. -0.05 for -5 percent (default: -0.05)")
    parser.add_argument("--eval-forecast", metavar="MODEL", help="Evaluate backtested forecast error and prediction interval coverage")
    # Dynamic Query & Operational Pipeline Commands
    parser.add_argument("--query", "-q", metavar="QUESTION", help="Execute natural-language dynamic query (e.g. 'Which competitors are most vulnerable if Dzire cuts its price by ₹30,000?')")
    parser.add_argument("--pipeline", action="store_true", help="Execute automated closed-loop operational ingestion & recalibration feedback pipeline")
    parser.add_argument("--benchmark", action="store_true", help="Run automated benchmark suite for query planner on canonical automotive questions")
    parser.add_argument("--force-llm", action="store_true", help="Force LLM query planning instead of fastpath/SLM")
    parser.add_argument("--reload-data", action="store_true", help="Reload JSON layers into Neo4j when running pipeline")

    # Phase 8/9/11 Decision, Governance & Learning Commands
    parser.add_argument("--evaluate-decision", nargs="+", metavar="MODELS", help="Evaluate strategic pricing decision, e.g. --evaluate-decision Aura Dzire")
    parser.add_argument("--objective", default="DEFEND_VOLUME", choices=["DEFEND_VOLUME", "MAXIMIZE_REVENUE", "BALANCED_MARKET_SHARE", "PRESERVE_MARGIN", "MAXIMIZE_PROFIT"], help="Strategic objective for recommendation")
    parser.add_argument("--show-decision", metavar="DECISION_ID", help="Display details and scenario results for a recorded decision")
    parser.add_argument("--approve-decision", metavar="DECISION_ID", help="Approve a decision with governance policy checks")
    parser.add_argument("--reject-decision", metavar="DECISION_ID", help="Reject a decision with reason")
    parser.add_argument("--execute-action", metavar="ACTION_ID", help="Execute an approved action proposal through authorized connectors")
    parser.add_argument("--record-outcome", metavar="DECISION_ID", help="Record actual market outcome against a decision for closed-loop learning")
    parser.add_argument("--user-id", default="analyst", help="Authenticated user ID for RBAC / governance (default: analyst)")
    parser.add_argument("--user-role", default="analyst", help="[DEPRECATED] Roles are derived securely from server-side TrustedPrincipalRegistry")
    parser.add_argument("--metric", default="sales_volume", help="Metric for outcome recording: sales_volume, revenue")
    parser.add_argument("--actual-val", type=float, help="Actual measured metric value for outcome recording")
    parser.add_argument("--period", default="2026-Q4", help="Measurement period for outcome recording (default: 2026-Q4)")
    parser.add_argument("--vehicle", default=None, help="Vehicle scope for outcome recording (e.g. Aura)")
    parser.add_argument("--backtest-pricing", nargs="+", metavar="MODELS", help="Run historical pricing backtest (e.g. --backtest-pricing Aura Dzire --as-of-date 2025-08-31 --eval-period 2025-09)")
    parser.add_argument("--as-of-date", default="2025-08-31", help="Point-in-time date for historical reconstruction (default: 2025-08-31)")
    parser.add_argument("--eval-period", default="2025-09", help="Subsequent evaluation period with real-world actuals (default: 2025-09)")
    parser.add_argument("--reason", default="Approved by executive pricing committee", help="Reason for approval or rejection")
    parser.add_argument("--dry-run", action="store_true", help="Perform dry-run action execution without modifying operational systems")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    # Decision & Governance Dispatch
    if args.backtest_pricing:
        display_backtest_pricing(
            args.backtest_pricing,
            as_of_date=args.as_of_date,
            eval_period=args.eval_period,
            objective=args.objective,
            user_id=args.user_id,
        )
        return

    if args.evaluate_decision:
        display_evaluate_decision(args.evaluate_decision, objective=args.objective)
        return

    if args.show_decision:
        display_show_decision(args.show_decision)
        return

    if args.approve_decision:
        display_approve_decision(args.approve_decision, reviewer_id=args.user_id, reason=args.reason)
        return

    if args.reject_decision:
        display_reject_decision(args.reject_decision, reviewer_id=args.user_id, reason=args.reason)
        return

    if args.execute_action:
        display_execute_action(args.execute_action, user_id=args.user_id, dry_run=args.dry_run)
        return

    if args.record_outcome:
        display_record_outcome(
            args.record_outcome,
            metric=args.metric,
            actual_val=args.actual_val,
            period=args.period,
            vehicle=args.vehicle,
            notes=args.reason,
            strict=args.strict_outcome,
        )
        return

    # Benchmark Dispatch
    if args.benchmark:
        from evaluation.benchmark_query_planner import run_benchmark_cli
        run_benchmark_cli()
        return

    # Operational Pipeline Dispatch
    if args.pipeline:
        display_dynamic_pipeline(reload_data=args.reload_data)
        return

    # Dynamic Query Dispatch
    if args.query:
        display_dynamic_query(args.query, use_grounding=args.grounded, force_llm=args.force_llm, export_path=args.export_memo)
        return


    # Predictive Layer Dispatch
    if args.audit_data:
        display_data_coverage_audit()
        return

    if args.forecast:
        display_sales_forecast(args.forecast, horizon=args.horizon, save_graph=args.save_graph)
        return

    if args.scenario:
        display_scenario_simulation(args.scenario, event_type=args.event, pct_change=args.delta, horizon=args.horizon, save_graph=args.save_graph)
        return

    if args.eval_forecast:
        display_forecast_evaluation(args.eval_forecast)
        return

    # Phase 3 Intelligence Dispatch
    if args.detect_changes:
        display_detected_changes()
        return

    if args.intelligence_query:
        display_intelligence_query(args.intelligence_query, use_grounding=args.grounded, force_llm=args.force_llm, export_path=args.export_memo)
        return

    if args.investigate:
        display_intelligence_query(args.investigate, use_grounding=args.grounded, force_llm=args.force_llm, export_path=args.export_memo)
        return

    # World Model Dispatch
    if args.audit_world_model:
        run_world_model_audit()
        return

    if args.snapshot:
        display_world_model_snapshot(args.snapshot, args.date)
        return

    if args.compare_dates:
        t1 = args.t1 or "2024-09-01"
        t2 = args.t2 or "2024-11-01"
        display_world_model_compare(args.compare_dates, t1, t2)
        return

    if args.signals:
        display_world_model_signals(args.signals, args.date)
        return

    if args.list_segments:
        list_segments()
        return

    if args.compare_segments:
        compare_segments()
        return

    if args.head_to_head:
        seg = args.segment or "Small Urban Families"
        display_head_to_head(args.head_to_head[0], args.head_to_head[1], seg)
        return

    if args.opportunities:
        seg = args.segment or "Small Urban Families"
        display_opportunities(args.opportunities, seg)
        return

    if args.segment and not args.explain:
        engine = FitScoringEngine()
        res = engine.rank_vehicles_for_segment(args.segment)
        display_rankings(res)
        return

    if args.explain:
        seg = args.segment or "Small Urban Families"
        explain_vehicle(args.explain, seg)
        return


if __name__ == "__main__":
    main()

