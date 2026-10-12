"""
Policy Engine: Enforces governance, compliance checks, and operational safety rules.
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from security.authorization import UserPrincipal, Permission, Role


class PolicyCheckResult(BaseModel):
    allowed: bool
    policy_name: str
    reasons: List[str] = []
    warnings: List[str] = []


class PolicyEngine:
    """
    Enforces governance rules, authorization requirements, and business safety policies.
    """

    @classmethod
    def check_decision_approval_policy(
        cls,
        user: UserPrincipal,
        decision_type: str,
        price_reduction_pct: float = 0.0,
    ) -> PolicyCheckResult:
        """
        Validates whether a user can approve a given decision under governance rules.
        """
        reasons = []
        warnings = []

        if not user.has_permission(Permission.APPROVE_DECISION):
            reasons.append(f"User '{user.user_id}' lacks Permission.APPROVE_DECISION.")
            return PolicyCheckResult(allowed=False, policy_name="DECISION_APPROVAL_GATE", reasons=reasons)

        # High-impact policy: price reduction > 10% requires Executive or Admin role
        if price_reduction_pct > 10.0 and Role.EXECUTIVE not in user.roles and Role.ADMIN not in user.roles:
            reasons.append(
                f"Price reduction of {price_reduction_pct:.1f}% exceeds 10% threshold. "
                "Policy requires approval by an Executive or Admin."
            )
            return PolicyCheckResult(allowed=False, policy_name="HIGH_IMPACT_PRICING_POLICY", reasons=reasons)

        if price_reduction_pct >= 5.0:
            warnings.append(f"Notice: Price reduction of {price_reduction_pct:.1f}% triggers formal pricing committee notification.")

        return PolicyCheckResult(allowed=True, policy_name="DECISION_APPROVAL_GATE", warnings=warnings)

    @classmethod
    def check_action_execution_policy(
        cls,
        user: UserPrincipal,
        action_type: str,
        target_system: str,
    ) -> PolicyCheckResult:
        """
        Validates whether an action execution is permitted by policy.
        """
        reasons = []
        if not user.has_permission(Permission.EXECUTE_ACTION):
            reasons.append(f"User '{user.user_id}' lacks Permission.EXECUTE_ACTION.")
            return PolicyCheckResult(allowed=False, policy_name="ACTION_EXECUTION_GATE", reasons=reasons)

        # External updates disabled by default for safety
        if target_system not in ("LOCAL_WORLD_MODEL", "INTERNAL_DECISION_RECORD", "INTERNAL_PRICING_CATALOG", "SIMULATED_PRICING_SYSTEM", "MARKETING_CAMPAIGN_SYSTEM"):
            reasons.append(f"Target system '{target_system}' is not in allowlisted execution connectors.")
            return PolicyCheckResult(allowed=False, policy_name="ALLOWLIST_CONNECTOR_POLICY", reasons=reasons)

        return PolicyCheckResult(allowed=True, policy_name="ACTION_EXECUTION_GATE")

    @classmethod
    def check_demographic_data_policy(
        cls,
        query: str,
        available_demographic_sources: List[str],
    ) -> PolicyCheckResult:
        """
        Enforces data minimization and privacy rules for protected demographic characteristics (e.g. gender).
        Prohibits proxy inferences or unsubstantiated demographic assumptions.
        """
        query_lower = query.lower()
        demographic_terms = ["gender", "female", "male", "women", "men", "caste", "religion"]
        matched_terms = [t for t in demographic_terms if t in query_lower]

        if matched_terms:
            if not available_demographic_sources:
                return PolicyCheckResult(
                    allowed=True,  # Allowed to investigate, but strictly constrained
                    policy_name="DEMOGRAPHIC_DATA_MINIMIZATION_POLICY",
                    warnings=[
                        f"Query references demographic attributes ({', '.join(matched_terms)}) but no empirical demographic survey sources are registered in the world model.",
                        "System must report explicit data gap and MUST NOT infer or fabricate demographic preferences from names or proxies."
                    ]
                )
        return PolicyCheckResult(allowed=True, policy_name="DEMOGRAPHIC_DATA_MINIMIZATION_POLICY")
