"""Approved ARCH Web domain surface."""

from arch_web.domain.architecture_review import (
    ArchitectureFinding,
    ArchitectureFindingCode,
    ArchitectureFindingSeverity,
    ArchitectureReadiness,
    ArchitectureReviewPackage,
    CoverageDisposition,
    RequirementCoverage,
)
from arch_web.domain.enums import (
    ArchitectureChoice,
    ProjectKind,
    RequirementCategory,
    RequirementPriority,
    RequirementStatus,
    RouteVisibility,
    SurfaceType,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.domain.errors import (
    UnsupportedWebContractVersionError,
    WebContractError,
    WebContractIntegrityError,
    WebContractReferenceError,
    WebContractValidationError,
)
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.navigation import (
    NavigationEdge,
    NavigationKind,
    NavigationModel,
    NavigationNode,
    NavigationRelationship,
    NavigationVisibility,
    UserJourney,
)
from arch_web.domain.product_brief import WebProductBrief
from arch_web.domain.project import WebProjectProfile
from arch_web.domain.references import ContractRef, DesignReference, EvidenceRef
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract
from arch_web.domain.requirements_review import (
    FindingCode,
    FindingSeverity,
    RequirementFinding,
    RequirementsReadiness,
    RequirementsReviewPackage,
    RouteRecommendation,
)
from arch_web.domain.stack import WebStackProfile
from arch_web.domain.surfaces import WebRouteContract, WebSurface

__all__ = (
    "ArchitectureChoice",
    "ArchitectureFinding",
    "ArchitectureFindingCode",
    "ArchitectureFindingSeverity",
    "ArchitectureReadiness",
    "ArchitectureReviewPackage",
    "ContractRef",
    "CoverageDisposition",
    "DesignReference",
    "EvidenceRef",
    "FindingCode",
    "FindingSeverity",
    "NavigationEdge",
    "NavigationKind",
    "NavigationModel",
    "NavigationNode",
    "NavigationRelationship",
    "NavigationVisibility",
    "ProjectKind",
    "RequirementCategory",
    "RequirementCoverage",
    "RequirementFinding",
    "RequirementPriority",
    "RequirementStatus",
    "RequirementsReadiness",
    "RequirementsReviewPackage",
    "RouteRecommendation",
    "RouteVisibility",
    "SurfaceType",
    "UnsupportedWebContractVersionError",
    "UserJourney",
    "WebContractError",
    "WebContractIntegrityError",
    "WebContractReferenceError",
    "WebContractValidationError",
    "WebInformationArchitectureContract",
    "WebLifecycleStatus",
    "WebProductBrief",
    "WebProjectProfile",
    "WebRequirement",
    "WebRequirementsContract",
    "WebRoute",
    "WebRouteContract",
    "WebStackProfile",
    "WebSurface",
)
