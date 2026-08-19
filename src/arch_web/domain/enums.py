"""Closed web-domain vocabularies approved by W00/W01."""

from enum import StrEnum, unique


@unique
class WebRoute(StrEnum):
    QUICK = "quick"
    STANDARD = "standard"
    CRITICAL = "critical"


@unique
class WebLifecycleStatus(StrEnum):
    DRAFT = "DRAFT"
    REQUIREMENTS_APPROVED = "REQUIREMENTS_APPROVED"
    ARCHITECTURE_APPROVED = "ARCHITECTURE_APPROVED"
    UI_APPROVED = "UI_APPROVED"
    IMPLEMENTATION_READY = "IMPLEMENTATION_READY"
    IMPLEMENTING = "IMPLEMENTING"
    TESTING = "TESTING"
    RELEASE_READY = "RELEASE_READY"
    DEPLOYED = "DEPLOYED"


@unique
class ProjectKind(StrEnum):
    STATIC_SITE = "static_site"
    FRONTEND_APP = "frontend_app"
    FULL_STACK_MONOLITH = "full_stack_monolith"
    FRONTEND_EXTERNAL_API = "frontend_external_api"
    FRONTEND_INDEPENDENT_BACKEND = "frontend_independent_backend"
    INTERNAL_ADMIN_TOOL = "internal_admin_tool"


@unique
class ArchitectureChoice(StrEnum):
    NONE = "none"
    UNSPECIFIED = "unspecified"


@unique
class RequirementCategory(StrEnum):
    FUNCTIONAL = "functional"
    CONTENT = "content"
    NAVIGATION = "navigation"
    RESPONSIVE = "responsive"
    ACCESSIBILITY = "accessibility"
    PERFORMANCE = "performance"
    SECURITY = "security"
    DATA = "data"
    INTEGRATION = "integration"
    OPERATIONAL = "operational"


@unique
class RequirementPriority(StrEnum):
    MUST = "must"
    SHOULD = "should"
    COULD = "could"
    WONT = "wont"


@unique
class RequirementStatus(StrEnum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"


@unique
class SurfaceType(StrEnum):
    PAGE = "page"
    DASHBOARD = "dashboard"
    MODAL_FLOW = "modal_flow"
    SETTINGS = "settings"
    WORKSPACE = "workspace"
    ADMIN = "admin"


@unique
class RouteVisibility(StrEnum):
    PUBLIC = "public"
    AUTHENTICATED = "authenticated"
    INTERNAL = "internal"
    HIDDEN = "hidden"


__all__ = (
    "ArchitectureChoice",
    "ProjectKind",
    "RequirementCategory",
    "RequirementPriority",
    "RequirementStatus",
    "RouteVisibility",
    "SurfaceType",
    "WebLifecycleStatus",
    "WebRoute",
)
