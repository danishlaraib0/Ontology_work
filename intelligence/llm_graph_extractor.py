"""
llm_graph_extractor.py
======================
Intelligent Open-Schema Knowledge Graph Extractor.
Uses GenAI to dynamically discover nodes, entities, and semantic relationships
from raw/semi-structured vehicle dossiers without hardcoded schema constraints.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from graph_db.neo4j_client import Neo4jClient
from config_loader import get_prompt
from data_collector.search_tools import gemini_plain_call
from data_collector.config import GEMINI_MODEL

logger = logging.getLogger(__name__)


class LLMGraphExtractor:
    """Extracts dynamic, schema-free nodes and relationships using LLM reasoning."""

    def __init__(self, client: Optional[Neo4jClient] = None):
        self.client = client or Neo4jClient()

    def build_vehicle_dossier(self, brand: str, model: str) -> str:
        """Collates collected layer JSONs for a vehicle into an integrated dossier."""
        brand_slug = brand.lower().replace(" ", "_").replace("-", "_")
        model_slug = model.lower().replace(" ", "_").replace("-", "_")
        target_dir = Path("data_collector/output") / brand_slug / model_slug

        dossier_sections = []
        if target_dir.exists():
            for json_file in sorted(target_dir.glob("*.json")):
                if json_file.name == "12_ontology_summary.json":
                    continue
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    layer_name = json_file.stem
                    dossier_sections.append(f"### {layer_name.upper()}\n{json.dumps(data, indent=2)[:2000]}")
                except Exception as e:
                    logger.warning(f"Could not read {json_file}: {e}")

        if not dossier_sections:
            return f"Vehicle: {brand} {model}\nCollect and extract comprehensive automotive graph for this vehicle."

        return "\n\n".join(dossier_sections)

    def extract_graph_from_dossier(self, brand: str, model: str, dossier_text: Optional[str] = None) -> Dict[str, Any]:
        """Invokes LLM to extract open-schema nodes and relationships."""
        if not dossier_text:
            dossier_text = self.build_vehicle_dossier(brand, model)

        prompt_template = get_prompt("intelligence", "graph_extractor")
        if not prompt_template:
            raise ValueError("Prompt 'graph_extractor' not found in prompts.yaml")

        prompt = prompt_template.format(
            brand=brand,
            model=model,
            vehicle_dossier=dossier_text[:12000],
        )

        logger.info(f"Extracting intelligent graph for {brand} {model} via {GEMINI_MODEL}...")
        raw_resp = gemini_plain_call(prompt, model=GEMINI_MODEL, max_tokens=3500)

        if not raw_resp:
            raise ValueError(f"Empty response from LLM for {brand} {model}")

        # Clean JSON markdown if wrapped
        cleaned = raw_resp.strip()
        cleaned = re.sub(r"^```json\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r"^```\s*", "", cleaned, flags=re.MULTILINE)
        cleaned = cleaned.rstrip("`").strip()

        try:
            graph_data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            # Fallback regex search for JSON object
            match = re.search(r"(\{.*\})", cleaned, re.DOTALL)
            if match:
                graph_data = json.loads(match.group(1))
            else:
                raise ValueError(f"Failed to parse LLM graph extraction JSON: {exc}\nRaw: {raw_resp[:500]}")

        return graph_data

    def ingest_dynamic_graph(self, graph_data: Dict[str, Any]) -> Dict[str, int]:
        """Ingests open-schema nodes and relationships dynamically into Neo4j."""
        nodes = graph_data.get("nodes", [])
        relationships = graph_data.get("relationships", [])

        nodes_created = 0
        rels_created = 0

        # Ingest Nodes
        for node in nodes:
            node_id = str(node.get("id", "")).strip()
            label = str(node.get("label", "AutomotiveEntity")).strip()
            name = str(node.get("name", node_id)).strip()
            # Clean label to valid Cypher identifier
            clean_label = re.sub(r"[^a-zA-Z0-9_]", "", label) or "AutomotiveEntity"
            props = node.get("properties", {})
            if not isinstance(props, dict):
                props = {}

            if not node_id:
                continue

            query = f"""
            MERGE (n:`{clean_label}` {{id: $id}})
            SET n.name = $name,
                n += $props
            """
            try:
                self.client.query(query, {"id": node_id, "name": name, "props": props})
                nodes_created += 1
            except Exception as e:
                logger.warning(f"Failed to insert dynamic node {node_id} ({clean_label}): {e}")

        # Ingest Relationships
        for rel in relationships:
            src_id = str(rel.get("source_id", "")).strip()
            tgt_id = str(rel.get("target_id", "")).strip()
            rel_type = str(rel.get("type", "RELATED_TO")).strip()
            clean_rel = re.sub(r"[^a-zA-Z0-9_]", "", rel_type).upper() or "RELATED_TO"
            props = rel.get("properties", {})
            if not isinstance(props, dict):
                props = {}

            if not src_id or not tgt_id:
                continue

            rel_query = f"""
            MATCH (a {{id: $src_id}})
            MATCH (b {{id: $tgt_id}})
            MERGE (a)-[r:`{clean_rel}`]->(b)
            SET r += $props
            """
            try:
                self.client.query(rel_query, {"src_id": src_id, "tgt_id": tgt_id, "props": props})
                rels_created += 1
            except Exception as e:
                logger.warning(f"Failed to insert relationship ({src_id})-[{clean_rel}]->({tgt_id}): {e}")

        logger.info(f"Dynamic Ingestion Complete: {nodes_created} nodes, {rels_created} relationships.")
        return {"nodes_created": nodes_created, "relationships_created": rels_created}

    def process_vehicle(self, brand: str, model: str) -> Dict[str, Any]:
        """Full pipeline: collates dossier, extracts dynamic graph, ingests to Neo4j."""
        graph_data = self.extract_graph_from_dossier(brand, model)
        stats = self.ingest_dynamic_graph(graph_data)
        return {
            "brand": brand,
            "model": model,
            "nodes_count": len(graph_data.get("nodes", [])),
            "relationships_count": len(graph_data.get("relationships", [])),
            "ingestion_stats": stats,
        }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Intelligent Open-Schema Knowledge Graph Extractor")
    parser.add_argument("--brand", default="Maruti Suzuki", help="Vehicle Brand")
    parser.add_argument("--model", default="Dzire", help="Vehicle Model")
    parser.add_argument("--all", action="store_true", help="Process all available output vehicles")
    args = parser.parse_args()

    extractor = LLMGraphExtractor()
    if args.all:
        output_base = Path("data_collector/output")
        for b_dir in output_base.iterdir():
            if b_dir.is_dir():
                for m_dir in b_dir.iterdir():
                    if m_dir.is_dir():
                        brand_name = b_dir.name.replace("_", " ").title()
                        model_name = m_dir.name.replace("_", " ").title()
                        print(f"\nProcessing {brand_name} {model_name}...")
                        try:
                            res = extractor.process_vehicle(brand_name, model_name)
                            print(f"Result: {res}")
                        except Exception as e:
                            print(f"Failed {brand_name} {model_name}: {e}")
    else:
        res = extractor.process_vehicle(args.brand, args.model)
        print(f"\nCompleted: {res}")
