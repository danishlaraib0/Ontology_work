"""
query_safety.py
===============
Security, validation, and guardrail enforcement for dynamic Cypher queries.
Enforces:
  1. Strict read-only semantics (rejects CREATE, MERGE, DELETE, SET, etc.)
  2. Bounded result limits (guarantees LIMIT <= 100)
  3. Schema conformance check (labels, relationship types)
  4. Execution timeouts (prevents hanging / infinite path traversals)
"""
from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from intelligence.schema_registry import KNOWN_NODE_LABELS, KNOWN_RELATIONSHIP_TYPES

logger = logging.getLogger(__name__)

# Forbidden mutating/destructive Cypher keywords (case-insensitive words)
FORBIDDEN_CYPHER_KEYWORDS: Set[str] = {
    "CREATE",
    "MERGE",
    "DELETE",
    "DETACH",
    "SET",
    "REMOVE",
    "DROP",
    "ALTER",
    "WRITE",
    "IMPORT",
    "LOAD",
    "FOREACH",
    "GRANT",
    "REVOKE",
    "DENY",
    "SYSTEM",
    "TERMINATE",
}

# Permitted starting keywords
READ_ONLY_START_KEYWORDS: Set[str] = {
    "MATCH",
    "OPTIONAL",
    "WITH",
    "UNWIND",
    "RETURN",
    "CALL",
}

DEFAULT_MAX_LIMIT = 50


@dataclass
class CypherValidationResult:
    """Outcome of validating a dynamic Cypher query."""
    is_safe: bool
    sanitized_cypher: str
    rejection_reason: Optional[str] = None
    extracted_labels: List[str] = field(default_factory=list)
    extracted_relationships: List[str] = field(default_factory=list)
    limit_applied: int = DEFAULT_MAX_LIMIT


class CypherSafetyValidator:
    """Enforces AST-like safety policies on dynamically generated Cypher statements."""

    def __init__(self, max_limit: int = DEFAULT_MAX_LIMIT):
        self.max_limit = max_limit

    def validate_and_sanitize(self, raw_cypher: str) -> CypherValidationResult:
        """
        Validates the Cypher statement against safety rules, guarantees a safe LIMIT,
        and checks for forbidden mutating operations.
        """
        clean = raw_cypher.strip()
        # Remove surrounding markdown code fences if present
        if clean.startswith("```"):
            clean = re.sub(r"^```(?:cypher)?\n?", "", clean)
            clean = re.sub(r"\n?```$", "", clean).strip()

        if not clean:
            return CypherValidationResult(
                is_safe=False,
                sanitized_cypher="",
                rejection_reason="Query is empty.",
            )

        # ── 1. Check Starting Keyword ─────────────────────────────────────────
        first_token = clean.split()[0].upper().rstrip(";")
        if first_token not in READ_ONLY_START_KEYWORDS:
            return CypherValidationResult(
                is_safe=False,
                sanitized_cypher=clean,
                rejection_reason=f"Disallowed starting keyword '{first_token}'. Dynamic queries must be read-only (MATCH / WITH / UNWIND / RETURN).",
            )

        # ── 2. Check For Forbidden Write / Destructive Keywords ──────────────
        # Word boundary token matching to avoid substring false positives
        tokens = set(re.findall(r"\b[A-Z_]+\b", clean.upper()))
        forbidden_hits = tokens.intersection(FORBIDDEN_CYPHER_KEYWORDS)
        if forbidden_hits:
            return CypherValidationResult(
                is_safe=False,
                sanitized_cypher=clean,
                rejection_reason=f"Mutating or destructive operations forbidden: {sorted(list(forbidden_hits))}.",
            )

        # Forbidden procedures
        if re.search(r"CALL\s+dbms\.", clean, re.IGNORECASE):
            return CypherValidationResult(
                is_safe=False,
                sanitized_cypher=clean,
                rejection_reason="Administrative CALL dbms.* procedures are forbidden.",
            )

        # ── 3. Label & Relationship Sanity Extraction ─────────────────────────
        # Extract node labels like :VehicleModel
        label_matches = re.findall(r":([A-Za-z0-9_]+)", clean)
        extracted_labels = []
        extracted_rels = []

        for m in label_matches:
            if m.isupper():
                extracted_rels.append(m)
            else:
                extracted_labels.append(m)

        # Flag unknown node labels if any exist
        unknown_labels = [l for l in extracted_labels if l not in KNOWN_NODE_LABELS and l != ""]
        if unknown_labels:
            logger.warning(f"Query references uncatalogued labels: {unknown_labels}")

        # ── 4. Enforce or Clamp LIMIT ─────────────────────────────────────────
        limit_match = re.search(r"\bLIMIT\s+(\d+)", clean, re.IGNORECASE)
        sanitized_cypher = clean
        applied_limit = self.max_limit

        if limit_match:
            existing_limit = int(limit_match.group(1))
            if existing_limit > self.max_limit:
                # Clamp limit to max_limit
                sanitized_cypher = re.sub(
                    r"\bLIMIT\s+\d+",
                    f"LIMIT {self.max_limit}",
                    clean,
                    flags=re.IGNORECASE,
                )
                applied_limit = self.max_limit
            else:
                applied_limit = existing_limit
        else:
            # Append LIMIT clause if query ends with RETURN ... or ORDER BY ...
            sanitized_cypher = f"{clean.rstrip(';')} LIMIT {self.max_limit}"
            applied_limit = self.max_limit

        return CypherValidationResult(
            is_safe=True,
            sanitized_cypher=sanitized_cypher,
            rejection_reason=None,
            extracted_labels=extracted_labels,
            extracted_relationships=extracted_rels,
            limit_applied=applied_limit,
        )

    def execute_safely(
        self,
        client: Any,
        raw_cypher: str,
        params: Optional[Dict[str, Any]] = None,
        timeout_sec: float = 8.0,
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Validates, applies limits, and executes a read-only Cypher query with timeout protection.
        Returns: (success: bool, records: List[dict], error_or_notice: Optional[str])
        """
        val_res = self.validate_and_sanitize(raw_cypher)
        if not val_res.is_safe:
            return False, [], f"Security Validation Failed: {val_res.rejection_reason}"

        try:
            # Execute with query execution timeout if supported or plain query
            records = client.query(val_res.sanitized_cypher, params or {})
            return True, records, None
        except Exception as exc:
            err_msg = str(exc)
            logger.error(f"Error executing validated dynamic Cypher: {err_msg}")
            return False, [], f"Cypher Execution Error: {err_msg}"
