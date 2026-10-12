"""
loader.py
=========
Orchestrates loading collected automotive JSON layers into Neo4j.
"""
from __future__ import annotations

import logging
from pathlib import Path
from rich.console import Console
from rich.table import Table

from data_collector.config import DATA_DIR
from .neo4j_client import Neo4jClient
from .transformer import transform_vehicle_directory, GraphPayload

logger = logging.getLogger(__name__)
console = Console()


def load_vehicle_to_graph(brand_dir_name: str, model_dir_name: str, client: Neo4jClient | None = None) -> dict:
    """Load all 12 layers of a single vehicle model into Neo4j."""
    v_dir = DATA_DIR / brand_dir_name / model_dir_name
    if not v_dir.exists():
        raise FileNotFoundError(f"Directory does not exist: {v_dir}")

    client = client or Neo4jClient()
    payload = transform_vehicle_directory(v_dir)
    return client.ingest_payload(payload)


def load_all_collected_to_graph() -> dict:
    """Scan data_collector/output, initialize schema, and ingest all vehicle datasets."""
    client = Neo4jClient()
    if not client.is_healthy():
        console.print("[bold red]❌ Cannot connect to Neo4j instance at [/bold red]" f"[yellow]{client.uri}[/yellow]")
        console.print("[dim]Ensure Neo4j is running via `docker compose up -d` or check NEO4J_URI in .env[/dim]")
        return {"status": "CONNECTION_FAILED"}

    # 1. Initialize schema
    console.print("\n[bold cyan]🔧 Initializing Neo4j Schema (Constraints & Indexes)...[/bold cyan]")
    schema_stats = client.init_schema()

    # 2. Ingest vehicles
    table = Table(title="🚗 Neo4j Ingestion Summary", show_header=True, header_style="bold magenta")
    table.add_column("Brand", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Nodes Merged", justify="right")
    table.add_column("Relationships Merged", justify="right")
    table.add_column("Status", justify="center")

    total_nodes = 0
    total_rels = 0

    if not DATA_DIR.exists():
        console.print(f"[yellow]No data found in {DATA_DIR}[/yellow]")
        return {"status": "NO_DATA"}

    for brand_dir in sorted(DATA_DIR.iterdir()):
        if not brand_dir.is_dir():
            continue
        for model_dir in sorted(brand_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            
            try:
                payload = transform_vehicle_directory(model_dir)
                metrics = client.ingest_payload(payload)
                n_count = metrics["nodes_merged"]
                r_count = metrics["relationships_merged"]
                total_nodes += n_count
                total_rels += r_count

                table.add_row(
                    brand_dir.name.replace("_", " ").title(),
                    model_dir.name.replace("_", " ").title(),
                    str(n_count),
                    str(r_count),
                    "[green]✅ Ingested[/green]",
                )
            except Exception as exc:
                logger.error(f"Failed to ingest {brand_dir.name}/{model_dir.name}: {exc}")
                table.add_row(
                    brand_dir.name,
                    model_dir.name,
                    "-",
                    "-",
                    f"[red]❌ {exc}[/red]",
                )

    console.print(table)
    console.print(f"\n[bold green]🎉 Total Ingested:[/bold green] {total_nodes} nodes, {total_rels} relationships.\n")
    return {
        "status": "SUCCESS",
        "total_nodes": total_nodes,
        "total_relationships": total_rels,
        "schema": schema_stats,
    }
