"""
load_graph.py
=============
CLI tool to manage and query the Automotive World Ontology in Neo4j.

Usage Examples:
  # Initialize Schema (Constraints & Indexes)
  python load_graph.py --init

  # Ingest all collected vehicles into Neo4j
  python load_graph.py --load

  # Generate standalone Cypher dump file (graph_export.cypher)
  python load_graph.py --export

  # Traverse graph to answer strategic business questions
  python load_graph.py --why "Wagon R" --audience "Family"
  python load_graph.py --compare "Wagon R" "Tiago"
  python load_graph.py --summary "Wagon R"
"""
from __future__ import annotations

import argparse
import json
import sys
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from graph_db.neo4j_client import Neo4jClient
from graph_db.loader import load_all_collected_to_graph
from graph_db.query_engine import AutomotiveGraphQueryEngine
from export_cypher import generate_cypher_script

console = Console()


def main():
    parser = argparse.ArgumentParser(
        description="Automotive World Ontology — Neo4j Graph DB CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--init", action="store_true", help="Initialize schema (constraints & indexes) in Neo4j")
    parser.add_argument("--load", action="store_true", help="Ingest all collected vehicle datasets into Neo4j")
    parser.add_argument("--export", action="store_true", help="Generate graph_export.cypher standalone script")
    parser.add_argument("--why", metavar="MODEL", help="Model name for 'Why is vehicle popular' query")
    parser.add_argument("--audience", metavar="KEYWORD", help="Audience keyword (e.g. 'Family', 'Professional')")
    parser.add_argument("--compare", nargs=2, metavar=("MODEL_A", "MODEL_B"), help="Compare two competing models")
    parser.add_argument("--summary", metavar="MODEL", help="Get 360-degree graph profile for a vehicle")
    parser.add_argument("--gap", metavar="MODEL", help="Find market, feature, and sentiment gaps for a vehicle")

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        return

    # --- 1. Export Cypher ---
    if args.export:
        generate_cypher_script()

    # --- 2. Initialize Schema ---
    if args.init:
        client = Neo4jClient()
        if not client.is_healthy():
            console.print(f"[bold red]❌ Cannot connect to Neo4j at {client.uri}[/bold red]")
            console.print("[dim]Start Neo4j with `docker compose up -d` or verify .env[/dim]")
            return
        stats = client.init_schema()
        console.print(f"[bold green]✅ Schema initialized successfully:[/bold green] {stats}")

    # --- 3. Ingest Data ---
    if args.load:
        load_all_collected_to_graph()

    # --- 4. Traversal Queries ---
    if args.why:
        client = Neo4jClient()
        if not client.is_healthy():
            console.print(f"[bold red]❌ Cannot connect to Neo4j at {client.uri}[/bold red]")
            return
        engine = AutomotiveGraphQueryEngine(client)
        aud = args.audience or "Family"
        res = engine.why_popular_with_audience(args.why, aud)
        console.print(Panel(json.dumps(res, indent=2), title=f"🔍 Traversal: Why is {args.why} popular with {aud}?", border_style="cyan"))

    if args.compare:
        client = Neo4jClient()
        if not client.is_healthy():
            console.print(f"[bold red]❌ Cannot connect to Neo4j at {client.uri}[/bold red]")
            return
        engine = AutomotiveGraphQueryEngine(client)
        res = engine.competitor_comparison(args.compare[0], args.compare[1])
        console.print(Panel(json.dumps(res, indent=2), title=f"⚔️ Competitor Analysis: {args.compare[0]} vs {args.compare[1]}", border_style="magenta"))

    if args.summary:
        client = Neo4jClient()
        if not client.is_healthy():
            console.print(f"[bold red]❌ Cannot connect to Neo4j at {client.uri}[/bold red]")
            return
        engine = AutomotiveGraphQueryEngine(client)
        res = engine.get_vehicle_summary_graph(args.summary)
        console.print(Panel(json.dumps(res, indent=2), title=f"🚗 360° Profile: {args.summary}", border_style="green"))

    if args.gap:
        client = Neo4jClient()
        if not client.is_healthy():
            console.print(f"[bold red]❌ Cannot connect to Neo4j at {client.uri}[/bold red]")
            return
        engine = AutomotiveGraphQueryEngine(client)
        res = engine.find_product_gaps(args.gap)
        console.print(Panel(json.dumps(res, indent=2), title=f"🎯 Product & Market Gap Analysis: {args.gap}", border_style="yellow"))


if __name__ == "__main__":
    main()
