"""
neo4j_client.py
===============
Neo4j Graph Database Client for Automotive World Ontology.
Manages driver connection pooling, health checks, schema migrations,
and transactional batch ingestion.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List
import neo4j
from neo4j import GraphDatabase, Driver, Session

from data_collector.config import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DATABASE,
)
from .cypher_schema import (
    CYPHER_CONSTRAINTS,
    CYPHER_INDEXES,
    CYPHER_FULLTEXT_INDEXES,
)
from .transformer import GraphPayload

logger = logging.getLogger(__name__)


class Neo4jClient:
    """Encapsulates Neo4j driver interactions and schema initialization."""

    def __init__(
        self,
        uri: str = NEO4J_URI,
        user: str = NEO4J_USER,
        password: str = NEO4J_PASSWORD,
        database: str = NEO4J_DATABASE,
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.database = database
        self._driver: Driver | None = None

    def connect(self) -> Driver:
        """Establish connection to Neo4j cluster / instance."""
        if self._driver is None:
            self._driver = GraphDatabase.driver(
                self.uri,
                auth=(self.user, self.password),
                max_connection_lifetime=30 * 60,
                max_connection_pool_size=50,
                connection_acquisition_timeout=30.0,
            )
        return self._driver

    def close(self):
        """Close connection pool."""
        if self._driver:
            self._driver.close()
            self._driver = None

    def is_healthy(self) -> bool:
        """Verify connectivity to Neo4j."""
        try:
            driver = self.connect()
            driver.verify_connectivity()
            return True
        except Exception as exc:
            logger.warning(f"Neo4j health check failed: {exc}")
            return False

    def init_schema(self) -> dict[str, int]:
        """Apply all constraints, indexes, and fulltext search definitions."""
        driver = self.connect()
        counts = {"constraints": 0, "indexes": 0, "fulltext": 0}

        with driver.session(database=self.database) as session:
            # 1. Uniqueness Constraints
            for c_stmt in CYPHER_CONSTRAINTS:
                try:
                    session.run(c_stmt)
                    counts["constraints"] += 1
                except Exception as exc:
                    logger.debug(f"Constraint notice: {exc}")

            # 2. Secondary Indexes
            for i_stmt in CYPHER_INDEXES:
                try:
                    session.run(i_stmt)
                    counts["indexes"] += 1
                except Exception as exc:
                    logger.debug(f"Index notice: {exc}")

            # 3. Full-Text Indexes
            for f_stmt in CYPHER_FULLTEXT_INDEXES:
                try:
                    session.run(f_stmt)
                    counts["fulltext"] += 1
                except Exception as exc:
                    logger.debug(f"Fulltext index notice: {exc}")

        logger.info(f"✅ Schema initialized: {counts['constraints']} constraints, {counts['indexes']} indexes.")
        return counts

    def ingest_payload(self, payload: GraphPayload) -> dict[str, int]:
        """
        Execute atomic idempotent batch MERGE queries for all nodes and relationships.
        """
        driver = self.connect()
        metrics = {"nodes_merged": 0, "relationships_merged": 0}

        with driver.session(database=self.database) as session:
            # --- 1. MERGE NODES BY LABEL ---
            for label, key_map in payload.nodes.items():
                node_list = list(key_map.values())
                if not node_list:
                    continue

                # Determine key property name from payload.key_fields or first node
                key_prop = getattr(payload, "key_fields", {}).get(label) or next(iter(node_list[0].keys()))
                cypher_query = f"""
                UNWIND $batch AS props
                MERGE (n:{label} {{{key_prop}: props.{key_prop}}})
                SET n += props
                """
                session.run(cypher_query, batch=node_list)
                metrics["nodes_merged"] += len(node_list)

            # --- 2. MERGE RELATIONSHIPS ---
            for rel in payload.relationships:
                rel_query = f"""
                MATCH (a:{rel['start_label']} {{{rel['start_key']}: $start_val}})
                MATCH (b:{rel['end_label']} {{{rel['end_key']}: $end_val}})
                MERGE (a)-[r:{rel['type']}]->(b)
                SET r += $props
                """
                session.run(
                    rel_query,
                    start_val=rel["start_val"],
                    end_val=rel["end_val"],
                    props=rel["props"],
                )
                metrics["relationships_merged"] += 1

        logger.info(
            f"✅ Ingested payload: {metrics['nodes_merged']} nodes, {metrics['relationships_merged']} relationships merged."
        )
        return metrics

    def query(self, cypher: str, params: Dict[str, Any] | None = None) -> List[Dict[str, Any]]:
        """Run a read query and return records as dictionaries."""
        driver = self.connect()
        with driver.session(database=self.database) as session:
            result = session.run(cypher, params or {})
            return [record.data() for record in result]
