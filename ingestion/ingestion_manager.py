"""
ingestion_manager.py
====================
Manages background vehicle ingestion jobs with real-time status tracking,
progress reporting, log streaming, and Neo4j graph synchronization.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_collector.config import DATA_DIR
from data_collector.collector import run_collection
from data_collector.storage import _slugify
from graph_db.loader import load_vehicle_to_graph, load_all_collected_to_graph
from export_cypher import generate_cypher_script

logger = logging.getLogger(__name__)

JOBS_FILE = DATA_DIR / "ingestion_jobs.json"


@dataclass
class IngestionJob:
    job_id: str
    make: str
    model: str
    status: str = "QUEUED"  # QUEUED, RUNNING, COMPLETED, FAILED
    progress_pct: int = 0
    current_step: str = "Queued for processing"
    total_steps: int = 13  # 12 layers + 1 Neo4j graph load
    completed_steps: int = 0
    logs: List[Dict[str, Any]] = field(default_factory=list)
    stats: Dict[str, Any] = field(default_factory=dict)
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    error: Optional[str] = None

    def add_log(self, message: str, level: str = "info", layer_id: Optional[str] = None):
        entry = {
            "timestamp": datetime.now(timezone.utc).strftime("%H:%M:%S"),
            "layer_id": layer_id,
            "message": message,
            "level": level,
        }
        self.logs.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IngestionManager:
    """Singleton manager tracking asynchronous car ingestion tasks."""

    _instance: Optional[IngestionManager] = None
    _lock = threading.Lock()

    def __new__(cls) -> IngestionManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._jobs = {}
                cls._instance._load_persisted_jobs()
            return cls._instance

    def _load_persisted_jobs(self):
        try:
            if JOBS_FILE.exists():
                with open(JOBS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        job = IngestionJob(**item)
                        self._jobs[job.job_id] = job
        except Exception as e:
            logger.warning(f"Could not load persisted ingestion jobs: {e}")

    def _save_jobs(self):
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(JOBS_FILE, "w", encoding="utf-8") as f:
                json.dump([j.to_dict() for j in self._jobs.values()], f, indent=2)
        except Exception as e:
            logger.warning(f"Could not persist ingestion jobs: {e}")

    def create_job(self, make: str, model: str) -> IngestionJob:
        clean_make = make.strip().title()
        clean_model = model.strip().title()
        timestamp = int(time.time())
        job_id = f"ingest_{timestamp}_{_slugify(clean_make)}_{_slugify(clean_model)}"

        job = IngestionJob(
            job_id=job_id,
            make=clean_make,
            model=clean_model,
            status="QUEUED",
            progress_pct=0,
            current_step="Queued for autonomous ingestion",
            total_steps=13,
            completed_steps=0,
        )
        job.add_log(f"Job registered for {clean_make} {clean_model}", level="info")

        with self._lock:
            self._jobs[job_id] = job
            self._save_jobs()

        return job

    def get_job(self, job_id: str) -> Optional[IngestionJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[IngestionJob]:
        with self._lock:
            # Sort newest first
            return sorted(self._jobs.values(), key=lambda j: j.started_at, reverse=True)

    def run_job_synchronous(self, job_id: str):
        """Worker executing collection and graph loading for a specific job."""
        job = self.get_job(job_id)
        if not job:
            logger.error(f"Job {job_id} not found.")
            return

        job.status = "RUNNING"
        job.progress_pct = 5
        job.current_step = "Initializing Automotive Intelligence Pipelines"
        job.add_log(f"Starting autonomous pipeline execution for {job.make} {job.model}")
        self._save_jobs()

        def progress_callback(layer_id: str, layer_name: str, step_idx: int, total_layers: int, msg: str):
            # 12 layers map to 5% -> 88%
            pct = int(5 + (step_idx / total_layers) * 83)
            job.progress_pct = min(pct, 88)
            job.completed_steps = step_idx
            job.current_step = f"Layer {step_idx}/{total_layers}: {layer_name}"
            job.add_log(msg, layer_id=layer_id)
            self._save_jobs()

        try:
            # Step 1: Collect 12 data layers
            logger.info(f"▶ IngestionManager starting 12-layer collection for {job.make} {job.model}")
            run_collection(job.make, job.model, force=False, progress_callback=progress_callback)

            # Step 2: Neo4j Ingestion
            job.progress_pct = 90
            job.current_step = "Neo4j Knowledge Graph Ingestion"
            job.add_log("Merging nodes, relationships, and price observations into Neo4j graph...", layer_id="GRAPH")
            self._save_jobs()

            nodes_merged = 0
            rels_merged = 0
            try:
                metrics = load_vehicle_to_graph(_slugify(job.make), _slugify(job.model))
                nodes_merged = metrics.get("nodes_merged", 0)
                rels_merged = metrics.get("relationships_merged", 0)
                job.stats = metrics
                job.add_log(f"Direct graph merge succeeded: {nodes_merged} nodes, {rels_merged} relationships merged.")
            except Exception as graph_err:
                job.add_log(f"Targeted merge notice: {graph_err}. Running full graph sync...", level="warn")
                all_metrics = load_all_collected_to_graph()
                job.stats = all_metrics
                job.add_log("Full graph sync complete.")

            # Step 3: Refresh Cypher Export & Schema
            job.progress_pct = 96
            job.current_step = "Generating Cypher Export & Refreshing Schema"
            job.add_log("Refreshing Cypher scripts and query planner cache...")
            try:
                generate_cypher_script()
            except Exception as cypher_err:
                logger.warning(f"Cypher script export notice: {cypher_err}")

            # Refresh Schema Registry Cache so new car is immediately recognized
            try:
                from intelligence.schema_registry import GraphSchemaRegistry
                reg = GraphSchemaRegistry()
                reg._cached_vehicles = None
                reg._cached_brands = None
                reg.get_known_vehicles()
                reg.get_known_brands()
            except Exception:
                pass

            job.status = "COMPLETED"
            job.progress_pct = 100
            job.completed_steps = 13
            job.current_step = "Ingestion Complete"
            job.completed_at = datetime.now(timezone.utc).isoformat()
            job.add_log(f"Successfully integrated {job.make} {job.model} into the Automotive World Model!", level="success")
            logger.info(f"✅ IngestionManager completed job {job_id}")

        except Exception as e:
            logger.error(f"❌ IngestionManager job {job_id} failed: {e}", exc_info=True)
            job.status = "FAILED"
            job.error = str(e)
            job.current_step = f"Failed: {str(e)}"
            job.add_log(f"Error during ingestion: {str(e)}", level="error")
            job.completed_at = datetime.now(timezone.utc).isoformat()

        finally:
            with self._lock:
                self._save_jobs()


# Global accessor
def get_ingestion_manager() -> IngestionManager:
    return IngestionManager()
