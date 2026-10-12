"""
Authorization and Role-Based Access Control (RBAC) Module.
Defines security principals, roles, and granular permissions for the Automotive World Model.
"""

from enum import Enum
from typing import Set, Dict, List, Optional
from pydantic import BaseModel, Field


class Role(str, Enum):
    ADMIN = "admin"
    EXECUTIVE = "executive"
    ANALYST = "analyst"
    DECISION_REVIEWER = "decision_reviewer"
    ACTION_EXECUTOR = "action_executor"
    READ_ONLY = "read_only"


class Permission(str, Enum):
    READ_MARKET_DATA = "read_market_data"
    READ_CUSTOMER_DATA = "read_customer_data"
    RUN_ANALYSIS = "run_analysis"
    CREATE_DECISION = "create_decision"
    APPROVE_DECISION = "approve_decision"
    PROPOSE_ACTION = "propose_action"
    EXECUTE_ACTION = "execute_action"
    MANAGE_SOURCES = "manage_sources"
    MANAGE_POLICIES = "manage_policies"


ROLE_PERMISSIONS: Dict[Role, Set[Permission]] = {
    Role.ADMIN: set(Permission),
    Role.EXECUTIVE: {
        Permission.READ_MARKET_DATA,
        Permission.READ_CUSTOMER_DATA,
        Permission.RUN_ANALYSIS,
        Permission.CREATE_DECISION,
        Permission.APPROVE_DECISION,
        Permission.PROPOSE_ACTION,
        Permission.EXECUTE_ACTION,
    },
    Role.ANALYST: {
        Permission.READ_MARKET_DATA,
        Permission.READ_CUSTOMER_DATA,
        Permission.RUN_ANALYSIS,
        Permission.CREATE_DECISION,
        Permission.PROPOSE_ACTION,
    },
    Role.DECISION_REVIEWER: {
        Permission.READ_MARKET_DATA,
        Permission.RUN_ANALYSIS,
        Permission.APPROVE_DECISION,
    },
    Role.ACTION_EXECUTOR: {
        Permission.READ_MARKET_DATA,
        Permission.PROPOSE_ACTION,
        Permission.EXECUTE_ACTION,
    },
    Role.READ_ONLY: {
        Permission.READ_MARKET_DATA,
    },
}


class AuthenticationFailedError(Exception):
    """Raised when caller identity cannot be verified against trusted directory."""
    pass


class UserPrincipal(BaseModel):
    user_id: str
    name: str
    email: Optional[str] = None
    roles: List[Role] = Field(default_factory=lambda: [Role.ANALYST])
    is_active: bool = True
    auth_token_hash: Optional[str] = None

    def get_effective_permissions(self) -> Set[Permission]:
        if not self.is_active:
            return set()
        perms: Set[Permission] = set()
        for role in self.roles:
            perms.update(ROLE_PERMISSIONS.get(role, set()))
        return perms

    def has_permission(self, permission: Permission) -> bool:
        return permission in self.get_effective_permissions()


import logging
from contracts.decision_contracts import UnauthorizedAccessError

logger = logging.getLogger(__name__)


class TrustedPrincipalRegistry:
    """
    Authoritative server-side registry of trusted principals and their assigned roles.
    Caller-supplied roles are NEVER trusted. Roles must be derived from this registry.
    """
    _REGISTRY: Dict[str, UserPrincipal] = {}

    @classmethod
    def _init_default_directory(cls):
        defaults = [
            UserPrincipal(user_id="admin", name="System Administrator", roles=[Role.ADMIN]),
            UserPrincipal(user_id="admin_user", name="Security Admin", roles=[Role.ADMIN]),
            UserPrincipal(user_id="executive", name="Executive Leadership", roles=[Role.EXECUTIVE]),
            UserPrincipal(user_id="exec", name="Executive Leadership", roles=[Role.EXECUTIVE]),
            UserPrincipal(user_id="vp_pricing", name="VP of Pricing & Revenue", roles=[Role.EXECUTIVE]),
            UserPrincipal(user_id="cmo", name="Chief Marketing Officer", roles=[Role.EXECUTIVE]),
            UserPrincipal(user_id="reviewer", name="Senior Decision Reviewer", roles=[Role.DECISION_REVIEWER]),
            UserPrincipal(user_id="lead_reviewer", name="Lead Risk Reviewer", roles=[Role.DECISION_REVIEWER]),
            UserPrincipal(user_id="risk_committee", name="Enterprise Risk Committee", roles=[Role.DECISION_REVIEWER]),
            UserPrincipal(user_id="analyst", name="Market Intelligence Analyst", roles=[Role.ANALYST]),
            UserPrincipal(user_id="pricing_analyst", name="Strategic Pricing Analyst", roles=[Role.ANALYST]),
            UserPrincipal(user_id="action_runner", name="Automated Action Executor", roles=[Role.ACTION_EXECUTOR]),
            UserPrincipal(user_id="readonly_auditor", name="Compliance Auditor", roles=[Role.READ_ONLY]),
            UserPrincipal(user_id="guest", name="Guest User", roles=[Role.READ_ONLY]),
            UserPrincipal(user_id="system", name="System Internal Daemon", roles=[Role.ADMIN]),
        ]
        cls._REGISTRY = {p.user_id.lower(): p for p in defaults}

    @classmethod
    def get_principal(cls, user_id: str) -> Optional[UserPrincipal]:
        if not cls._REGISTRY:
            cls._init_default_directory()
        return cls._REGISTRY.get(user_id.lower())

    @classmethod
    def register_principal(cls, principal: UserPrincipal) -> None:
        if not cls._REGISTRY:
            cls._init_default_directory()
        cls._REGISTRY[principal.user_id.lower()] = principal

    @classmethod
    def list_principals(cls) -> List[UserPrincipal]:
        if not cls._REGISTRY:
            cls._init_default_directory()
        return list(cls._REGISTRY.values())


# Initialize registry on import
TrustedPrincipalRegistry._init_default_directory()


def authenticate_user(
    user_id: Optional[str],
    claimed_roles: Optional[List[str]] = None,
    auth_token: Optional[str] = None,
    strict_spoof_check: bool = True,
) -> UserPrincipal:
    """
    Authenticates a user principal against the trusted service directory.
    CRITICAL: Caller-supplied roles are NEVER trusted as authentication.
    Permissions are derived strictly from the trusted directory.

    Requires a valid, registered principal. Unregistered identities are rejected.
    If the caller attempts role spoofing (supplying roles not granted to the principal),
    raises UnauthorizedAccessError.
    """
    if not user_id or not str(user_id).strip():
        raise AuthenticationFailedError("Authentication credentials required: Principal identity cannot be empty.")

    clean_id = str(user_id).strip().lower()
    trusted = TrustedPrincipalRegistry.get_principal(clean_id)

    if not trusted:
        raise AuthenticationFailedError(
            f"Authentication failed: Principal '{clean_id}' is not a registered or authorized identity."
        )

    if not trusted.is_active:
        raise AuthenticationFailedError(
            f"Authentication failed: Principal '{clean_id}' identity is disabled or revoked."
        )

    # Check for role spoofing attempts
    if claimed_roles:
        claimed_set = {r.lower() for r in claimed_roles}
        trusted_set = {r.value.lower() for r in trusted.roles}
        unauthorized_claims = claimed_set - trusted_set

        if unauthorized_claims:
            logger.warning(
                f"🚨 SECURITY ALERT: Role spoofing detected for principal '{clean_id}'! "
                f"Attempted to claim unauthorized roles {list(unauthorized_claims)}. "
                f"Authorized roles: {list(trusted_set)}. Spoofed roles REJECTED."
            )
            if strict_spoof_check:
                raise UnauthorizedAccessError(
                    f"Role spoofing rejected: Principal '{clean_id}' is not authorized for roles {list(unauthorized_claims)}."
                )

    return trusted
