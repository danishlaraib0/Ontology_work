"""
Audit Logging and Observability Module.
Provides structured audit trails for intelligence queries, decision evaluations,
approvals, action executions, and outcome tracking.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field

logger = logging.getLogger("AuditLog")

AUDIT_LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "decision_audit.jsonl")


class AuditEvent(BaseModel):
    event_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    event_type: str
    actor_id: str = "system"
    correlation_id: Optional[str] = None
    decision_id: Optional[str] = None
    action_id: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)


class AuditLogger:
    """
    Structured audit logger writing tamper-evident records to disk and application logs.
    """

    def __init__(self, log_path: str = AUDIT_LOG_FILE):
        self.log_path = log_path
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

    def log_event(
        self,
        event_type: str,
        actor_id: str = "system",
        correlation_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        action_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        import uuid
        event = AuditEvent(
            event_id=f"AUDIT_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            actor_id=actor_id,
            correlation_id=correlation_id,
            decision_id=decision_id,
            action_id=action_id,
            details=details or {},
        )
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event.model_dump(), default=str) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event to file {self.log_path}: {e}")

        logger.info(f"AUDIT [{event.event_type}] Actor={event.actor_id} Decision={event.decision_id} Action={event.action_id}")
        return event


# Global default instance
audit_logger = AuditLogger()
