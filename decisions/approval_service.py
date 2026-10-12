"""
approval_service.py
===================
Deterministic Decision Lifecycle & Human Approval Service.
Enforces legal state transitions and policy approval gates:
    DRAFT -> INVESTIGATING -> READY_FOR_REVIEW -> APPROVED | REJECTED -> EXECUTING -> COMPLETED
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Set
from contracts.decision_contracts import (
    DecisionRecord,
    DecisionStatus,
    ApprovalRecord,
    ApprovalStatus,
    UnauthorizedAccessError,
    ConcurrencyConflictError,
)
from decisions.decision_repository import DecisionRepository
from security.authorization import authenticate_user, Permission

logger = logging.getLogger(__name__)


class InvalidStateTransitionError(Exception):
    """Raised when an illegal lifecycle transition is attempted on a DecisionRecord."""
    pass


# Allowed State Transitions
ALLOWED_TRANSITIONS: Dict[DecisionStatus, Set[DecisionStatus]] = {
    DecisionStatus.DRAFT: {DecisionStatus.INVESTIGATING, DecisionStatus.CANCELLED},
    DecisionStatus.INVESTIGATING: {DecisionStatus.READY_FOR_REVIEW, DecisionStatus.DRAFT, DecisionStatus.CANCELLED},
    DecisionStatus.READY_FOR_REVIEW: {DecisionStatus.APPROVED, DecisionStatus.REJECTED, DecisionStatus.CANCELLED},
    DecisionStatus.APPROVED: {DecisionStatus.EXECUTING, DecisionStatus.CANCELLED},
    DecisionStatus.REJECTED: {DecisionStatus.DRAFT, DecisionStatus.CANCELLED},
    DecisionStatus.EXECUTING: {DecisionStatus.COMPLETED, DecisionStatus.CANCELLED},
    DecisionStatus.COMPLETED: set(),
    DecisionStatus.CANCELLED: set(),
}


class ApprovalService:
    """Manages lifecycle validation and approval gates for decisions."""

    APPROVAL_VALIDITY_DAYS = 30

    def __init__(self, repo: Optional[DecisionRepository] = None):
        self.repo = repo or DecisionRepository()

    def transition_decision(self, decision_id: str, new_status: DecisionStatus, actor_id: str = "system") -> bool:
        """Transitions a decision to a new state if valid under lifecycle rules with optimistic concurrency."""
        data = self.repo.get_decision(decision_id)
        if not data:
            raise ValueError(f"Decision {decision_id} not found")

        current_status_str = data["decision"].get("status", "DRAFT")
        current_status = DecisionStatus(current_status_str)

        allowed = ALLOWED_TRANSITIONS.get(current_status, set())
        if new_status not in allowed:
            raise InvalidStateTransitionError(
                f"Illegal state transition: Cannot transition decision from {current_status.value} to {new_status.value}. Allowed: {[s.value for s in allowed]}"
            )

        # Atomic update in Neo4j with optimistic locking on current_status
        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})
        WHERE d.status = $current_status
        SET d.status = $new_status,
            d.updated_at = $updated_at,
            d.updated_by = $actor_id
        RETURN d.decision_id AS updated_id
        """
        res = self.repo.client.query(cypher, {
            "decision_id": decision_id,
            "current_status": current_status.value,
            "new_status": new_status.value,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "actor_id": actor_id,
        })
        if not res:
            raise ConcurrencyConflictError(
                f"Concurrency conflict: Decision [{decision_id}] was concurrently modified or no longer in status '{current_status.value}'."
            )

        logger.info(f"Decision [{decision_id}] transitioned from {current_status.value} to {new_status.value} by [{actor_id}]")
        return True

    def approve_decision(
        self,
        decision_id: str,
        reviewer_id: str,
        reason: str,
        alternative_id: Optional[str] = None,
        policy_version: str = "v1.0",
    ) -> ApprovalRecord:
        """Records human approval and transitions decision to APPROVED with strict RBAC enforcement."""
        # 1. Enforce Server-Side RBAC on Reviewer Identity
        user = authenticate_user(reviewer_id)
        if not user.has_permission(Permission.APPROVE_DECISION):
            raise UnauthorizedAccessError(
                f"Unauthorized: Principal '{reviewer_id}' (roles: {[r.value for r in user.roles]}) lacks 'APPROVE_DECISION' permission."
            )

        data = self.repo.get_decision(decision_id)
        if not data:
            raise ValueError(f"Decision {decision_id} not found")

        current_status = DecisionStatus(data["decision"].get("status", "DRAFT"))
        if current_status not in (DecisionStatus.READY_FOR_REVIEW, DecisionStatus.INVESTIGATING):
            raise InvalidStateTransitionError(
                f"Decision {decision_id} in status {current_status.value} cannot be approved. Must be READY_FOR_REVIEW."
            )

        if not alternative_id:
            alternative_id = data["decision"].get("recommended_alternative_id")
            if not alternative_id and data.get("alternatives"):
                alternative_id = data["alternatives"][0]["alternative_id"]
            if not alternative_id:
                raise ValueError(f"Cannot approve decision {decision_id}: No alternative specified or available.")

        now = datetime.now(timezone.utc)
        resolved_at_str = now.isoformat()
        expires_at_str = (now + timedelta(days=self.APPROVAL_VALIDITY_DAYS)).isoformat()

        # Create approval record
        approval = ApprovalRecord(
            approval_id=f"APPR_{decision_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            decision_id=decision_id,
            alternative_id=alternative_id,
            reviewer_id=user.user_id,
            status=ApprovalStatus.APPROVED,
            reason=reason,
            resolved_at=resolved_at_str,
            expires_at=expires_at_str,
            policy_version=policy_version,
        )
        self.repo.save_approval(approval)

        # Set recommended alternative and transition status with atomic concurrency check
        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})
        WHERE d.status IN ['READY_FOR_REVIEW', 'INVESTIGATING']
        SET d.recommended_alternative_id = $alternative_id,
            d.status = $new_status,
            d.updated_at = $updated_at,
            d.updated_by = $reviewer_id
        RETURN d.decision_id AS updated_id
        """
        res = self.repo.client.query(cypher, {
            "decision_id": decision_id,
            "alternative_id": alternative_id,
            "new_status": DecisionStatus.APPROVED.value,
            "updated_at": resolved_at_str,
            "reviewer_id": user.user_id,
        })
        if not res:
            raise ConcurrencyConflictError(
                f"Failed to atomically approve decision [{decision_id}]: State changed concurrently or record not found."
            )

        logger.info(f"Decision [{decision_id}] APPROVED for alternative [{alternative_id}] by [{user.user_id}] (expires: {expires_at_str})")
        return approval

    def reject_decision(
        self,
        decision_id: str,
        reviewer_id: str,
        reason: str,
        alternative_id: Optional[str] = None,
    ) -> ApprovalRecord:
        """Records rejection and transitions decision to REJECTED with strict RBAC enforcement."""
        user = authenticate_user(reviewer_id)
        if not user.has_permission(Permission.APPROVE_DECISION):
            raise UnauthorizedAccessError(
                f"Unauthorized: Principal '{reviewer_id}' lacks 'APPROVE_DECISION' permission."
            )

        data = self.repo.get_decision(decision_id)
        if not alternative_id and data:
            alternative_id = data["decision"].get("recommended_alternative_id")
            if not alternative_id and data.get("alternatives"):
                alternative_id = data["alternatives"][0]["alternative_id"]
        alternative_id = alternative_id or "ALT_REJECT"

        now_str = datetime.now(timezone.utc).isoformat()
        approval = ApprovalRecord(
            approval_id=f"REJ_{decision_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            decision_id=decision_id,
            alternative_id=alternative_id,
            reviewer_id=user.user_id,
            status=ApprovalStatus.REJECTED,
            reason=reason,
            resolved_at=now_str,
        )
        self.repo.save_approval(approval)

        cypher = """
        MATCH (d:Decision {decision_id: $decision_id})
        SET d.status = $new_status,
            d.updated_at = $updated_at,
            d.updated_by = $reviewer_id
        RETURN d.decision_id AS updated_id
        """
        self.repo.client.query(cypher, {
            "decision_id": decision_id,
            "new_status": DecisionStatus.REJECTED.value,
            "updated_at": now_str,
            "reviewer_id": user.user_id,
        })
        logger.info(f"Decision [{decision_id}] REJECTED by [{user.user_id}]: {reason}")
        return approval
