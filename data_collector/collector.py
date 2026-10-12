"""
collector.py
=============
Main orchestrator: runs all 12 layers in sequence for a given vehicle.

Usage (CLI):
    python -m data_collector --brand "Maruti Suzuki" --model "Dzire"

Usage (Python):
    from data_collector import run_collection
    result = run_collection("Maruti Suzuki", "Dzire")
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich import print as rprint

from .config import DATA_DIR
from .layers import (
    collect_vehicle_master,
    collect_spec_master,
    collect_feature_taxonomy,
    collect_competitor_master,
    collect_audience_segments,
    collect_buying_factors,
    collect_reviews,
    collect_opinion_dataset,
    collect_search_intent,
    collect_sales_data,
    collect_pricing_data,
    collect_ontology_summary,
)
from .storage import vehicle_dir

console = Console()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Layer registry ─────────────────────────────────────────────────────────
LAYERS = [
    ("L01", "Vehicle Master",         collect_vehicle_master,      False),
    ("L02", "Spec & Features Master", collect_spec_master,         True),
    ("L03", "Feature Taxonomy",       collect_feature_taxonomy,    True),
    ("L04", "Competitor Master",      collect_competitor_master,   True),
    ("L05", "Audience Segments",      collect_audience_segments,   True),
    ("L06", "Buying Factors",         collect_buying_factors,      True),
    ("L07", "Reviews",                collect_reviews,             True),
    ("L08", "Opinion Dataset",        collect_opinion_dataset,     True),
    ("L09", "Search & Intent Data",   collect_search_intent,       True),
    ("L10", "Sales & Registration",   collect_sales_data,          True),
    ("L11", "Pricing & Offers",       collect_pricing_data,        True),
    ("L12", "Ontology Summary",       collect_ontology_summary,    True),
]


def run_collection(
    brand: str,
    model: str,
    *,
    force: bool = False,
    layers_to_run: list[str] | None = None,
    progress_callback: Optional[Callable[[str, str, int, int, str], None]] = None,
) -> dict[str, Any]:
    """
    Run the full data collection pipeline for a vehicle.

    Args:
        brand:             Vehicle brand (e.g. "Maruti Suzuki")
        model:             Vehicle model (e.g. "Dzire")
        force:             Re-collect even if cached data exists
        layers_to_run:     Optional list of layer IDs to run (e.g. ["L01","L02"]).
                           If None, all 12 layers are run.
        progress_callback: Optional callback(layer_id, layer_name, step_idx, total_steps, message)

    Returns:
        Dict mapping layer_id → collected data.
    """
    console.print(Panel.fit(
        f"[bold cyan]🚗 Automotive Data Collector[/bold cyan]\n"
        f"[yellow]Brand:[/yellow] {brand}   [yellow]Model:[/yellow] {model}\n"
        f"[dim]Output: {vehicle_dir(brand, model)}[/dim]",
        border_style="cyan",
    ))

    vehicle_id: str | None = None
    results: dict[str, Any] = {}
    start_time = time.time()

    table = Table(show_header=True, header_style="bold magenta", expand=True)
    table.add_column("Layer", style="dim", width=6)
    table.add_column("Name", min_width=25)
    table.add_column("Status", width=10)
    table.add_column("Records", justify="right", width=10)

    active_layers = [
        (lid, name, fn, needs_vid)
        for lid, name, fn, needs_vid in LAYERS
        if layers_to_run is None or lid in layers_to_run
    ]

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Collecting data...", total=len(active_layers))

        for idx, (layer_id, layer_name, fn, needs_vehicle_id) in enumerate(active_layers, start=1):
            progress.update(task, description=f"[cyan]{layer_id}[/cyan] {layer_name}")
            if progress_callback:
                progress_callback(layer_id, layer_name, idx, len(active_layers), f"Collecting {layer_name}...")

            try:
                if needs_vehicle_id:
                    if vehicle_id is None:
                        # L01 must have run first; derive vehicle_id as fallback
                        vehicle_id = f"{brand.upper().replace(' ', '')}-{model.upper().replace(' ', '')}"
                    data = fn(brand, model, vehicle_id, force=force)
                else:
                    data = fn(brand, model, force=force)
                    # Extract vehicle_id from L01 result
                    if layer_id == "L01" and isinstance(data, dict):
                        vehicle_id = data.get("vehicle_id") or vehicle_id

                results[layer_id] = data
                record_count = len(data) if isinstance(data, list) else (1 if data else 0)
                table.add_row(layer_id, layer_name, "[green]✅ Done[/green]", str(record_count))
                if progress_callback:
                    progress_callback(layer_id, layer_name, idx, len(active_layers), f"Completed {layer_name} ({record_count} records)")

            except Exception as exc:
                logger.error(f"[{layer_id}] FAILED: {exc}", exc_info=True)
                results[layer_id] = {"_error": str(exc)}
                table.add_row(layer_id, layer_name, "[red]❌ Error[/red]", "-")
                if progress_callback:
                    progress_callback(layer_id, layer_name, idx, len(active_layers), f"Error in {layer_name}: {exc}")

            progress.advance(task)
            time.sleep(2.5)  # Safe rate-pacing for 15 RPM limits

    elapsed = time.time() - start_time
    console.print(table)
    console.print(
        f"\n[bold green]✅ Collection complete[/bold green]  "
        f"({elapsed:.1f}s)  "
        f"Output: [cyan]{vehicle_dir(brand, model)}[/cyan]"
    )

    # Print quick summary card if available
    summary = results.get("L12")
    if summary and isinstance(summary, dict):
        card = summary.get("intelligence_card", {})
        if card:
            console.print(Panel(
                f"[bold]{card.get('one_line_summary', '')}[/bold]\n\n"
                f"[dim]{card.get('positioning_statement', '')}[/dim]",
                title="🏆 Intelligence Card",
                border_style="green",
            ))

    return results


# ── CLI entrypoint ─────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(
        description="Automotive Data Collector — build layered vehicle intelligence datasets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m data_collector --brand "Maruti Suzuki" --model "Dzire"
  python -m data_collector --brand "Hyundai" --model "Creta" --force
  python -m data_collector --brand "Tata" --model "Nexon" --layers L01 L02 L04
        """,
    )
    parser.add_argument("--brand",  required=True,  help='Vehicle brand, e.g. "Maruti Suzuki"')
    parser.add_argument("--model",  required=True,  help='Vehicle model, e.g. "Dzire"')
    parser.add_argument("--force",  action="store_true", help="Re-collect even if cached")
    parser.add_argument(
        "--layers",
        nargs="*",
        metavar="LAYER_ID",
        help="Run only specific layers (e.g. L01 L02 L04). Default: all.",
    )

    args = parser.parse_args()
    run_collection(
        brand=args.brand,
        model=args.model,
        force=args.force,
        layers_to_run=args.layers if args.layers else None,
    )


if __name__ == "__main__":
    main()
