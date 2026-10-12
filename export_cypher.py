"""
export_cypher.py
================
Exports all collected vehicle datasets into a clean, standalone Cypher file (.cypher)
with constraints, indexes, and parameterized/literal MERGE statements.
"""
from __future__ import annotations

import json
from pathlib import Path
from rich.console import Console

from data_collector.config import DATA_DIR
from graph_db.cypher_schema import CYPHER_CONSTRAINTS, CYPHER_INDEXES
from graph_db.transformer import transform_vehicle_directory, GraphPayload

console = Console()


def _format_cypher_value(val: any) -> str:
    if val is None:
        return "null"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, (int, float)):
        return str(val)
    # String escaping
    escaped = str(val).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def _format_props_dict(props: dict) -> str:
    parts = []
    for k, v in props.items():
        if v is not None:
            parts.append(f"{k}: {_format_cypher_value(v)}")
    return "{" + ", ".join(parts) + "}"


def generate_cypher_script(output_file: Path = Path("graph_export.cypher")) -> Path:
    lines = []
    lines.append("// ==============================================================================")
    lines.append("// AUTOMOTIVE WORLD ONTOLOGY — NEO4J GRAPH DUMP")
    lines.append("// Generated from 12-layer normalized vehicle intelligence datasets")
    lines.append("// ==============================================================================\n")

    # 1. Constraints
    lines.append("// ── 1. UNIQUENESS CONSTRAINTS ───────────────────────────────────────────────")
    for c in CYPHER_CONSTRAINTS:
        lines.append(f"{c};")
    lines.append("")

    # 2. Indexes
    lines.append("// ── 2. SECONDARY INDEXES ───────────────────────────────────────────────────")
    for i in CYPHER_INDEXES:
        lines.append(f"{i};")
    lines.append("")

    # 3. Ingest All Vehicles
    total_vehicles = 0
    if DATA_DIR.exists():
        for brand_dir in sorted(DATA_DIR.iterdir()):
            if not brand_dir.is_dir():
                continue
            for model_dir in sorted(brand_dir.iterdir()):
                if not model_dir.is_dir():
                    continue

                total_vehicles += 1
                brand_title = brand_dir.name.replace("_", " ").title()
                model_title = model_dir.name.replace("_", " ").title()
                lines.append(f"// ── VEHICLE: {brand_title} {model_title} ─────────────────────────────")
                
                payload = transform_vehicle_directory(model_dir)

                # Nodes
                for label, key_map in payload.nodes.items():
                    key_prop = getattr(payload, "key_fields", {}).get(label) or (next(iter(next(iter(key_map.values())).keys())) if key_map else "id")
                    for key_val, props in key_map.items():
                        props_str = _format_props_dict(props)
                        lines.append(f"MERGE (n:{label} {{{key_prop}: {_format_cypher_value(key_val)}}}) SET n += {props_str};")

                # Relationships
                for rel in payload.relationships:
                    props_str = _format_props_dict(rel["props"]) if rel["props"] else "{}"
                    rel_line = (
                        f"MATCH (a:{rel['start_label']} {{{rel['start_key']}: {_format_cypher_value(rel['start_val'])}}}), "
                        f"(b:{rel['end_label']} {{{rel['end_key']}: {_format_cypher_value(rel['end_val'])}}}) "
                        f"MERGE (a)-[r:{rel['type']}]->(b) "
                        f"SET r += {props_str};"
                    )
                    lines.append(rel_line)

                lines.append("")

    output_file.write_text("\n".join(lines), encoding="utf-8")
    console.print(f"[bold green]✅ Exported complete Cypher graph dump for {total_vehicles} vehicles → [/bold green][cyan]{output_file.resolve()}[/cyan]")
    return output_file


if __name__ == "__main__":
    generate_cypher_script()
