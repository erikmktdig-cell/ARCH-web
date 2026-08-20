"""Pure W03 preparation, coverage, and consistency analysis."""

from __future__ import annotations

from arch_web.application.architecture.errors import ArchitecturePreparationError
from arch_web.application.architecture.models import (
    PrepareArchitectureCommand,
    PrepareArchitectureResult,
)
from arch_web.application.architecture.planning import (
    plan_information_architecture,
    semantic_id,
)
from arch_web.contracts.versions import CURRENT_WEB_CONTRACT_VERSION
from arch_web.domain._base import WebContractRecord
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
    RequirementCategory,
    RequirementPriority,
    RouteVisibility,
    WebLifecycleStatus,
    WebRoute,
)
from arch_web.domain.information_architecture import WebInformationArchitectureContract
from arch_web.domain.navigation import NavigationModel, NavigationVisibility
from arch_web.domain.references import ContractRef
from arch_web.domain.requirements import WebRequirement, WebRequirementsContract


def _ref(target: WebContractRecord, contract_id: str) -> ContractRef:
    return ContractRef(
        target_contract_type=target.contract_type,
        contract_id=contract_id,
        contract_version=getattr(target, "contract_version", CURRENT_WEB_CONTRACT_VERSION),
        fingerprint=target.canonical_fingerprint(),
    )


def _coverage(
    requirement: WebRequirement, architecture_refs: tuple[str, ...]
) -> RequirementCoverage:
    if requirement.priority is RequirementPriority.WONT:
        return RequirementCoverage(
            requirement.requirement_id,
            CoverageDisposition.NOT_APPLICABLE_TO_IA,
            "Explicitly excluded from the approved scope.",
        )
    if requirement.category in {
        RequirementCategory.RESPONSIVE,
        RequirementCategory.ACCESSIBILITY,
    }:
        return RequirementCoverage(
            requirement.requirement_id,
            CoverageDisposition.DEFERRED_TO_W04,
            "Visual and interaction evidence belongs to design review.",
            "W04",
        )
    if requirement.category in {
        RequirementCategory.PERFORMANCE,
        RequirementCategory.OPERATIONAL,
        RequirementCategory.INTEGRATION,
    }:
        return RequirementCoverage(
            requirement.requirement_id,
            CoverageDisposition.DEFERRED_TO_W06_W07,
            "Implementation and repository evidence belongs downstream.",
            "W06/W07",
        )
    if architecture_refs:
        return RequirementCoverage(
            requirement.requirement_id,
            CoverageDisposition.COVERED,
            "Mapped to explicit architecture evidence.",
            architecture_refs=architecture_refs,
        )
    if requirement.category in {RequirementCategory.DATA, RequirementCategory.SECURITY}:
        return RequirementCoverage(
            requirement.requirement_id,
            CoverageDisposition.COVERED,
            "Recorded as an approved architecture constraint.",
            architecture_refs=("architecture:constraint",),
        )
    return RequirementCoverage(
        requirement.requirement_id,
        CoverageDisposition.UNRESOLVED,
        "No architecture disposition was derived.",
    )


def analyze_architecture(
    requirements: WebRequirementsContract,
    ia: WebInformationArchitectureContract,
    navigation: NavigationModel,
    *,
    expected_requirements_fingerprint: str,
) -> tuple[tuple[RequirementCoverage, ...], tuple[ArchitectureFinding, ...]]:
    refs: dict[str, set[str]] = {item.requirement_id: set() for item in requirements.requirements}
    for surface in ia.surfaces:
        for ref in surface.requirement_refs:
            refs.setdefault(ref, set()).add(surface.surface_id)
    for route in ia.routes:
        for ref in route.requirement_refs:
            refs.setdefault(ref, set()).add(route.route_id)
    coverage = tuple(
        _coverage(item, tuple(sorted(refs.get(item.requirement_id, ()))))
        for item in requirements.requirements
    )
    findings: list[ArchitectureFinding] = []

    def add(
        code: ArchitectureFindingCode,
        message: str,
        affected: tuple[str, ...] = (),
        requirement_refs: tuple[str, ...] = (),
        severity: ArchitectureFindingSeverity = ArchitectureFindingSeverity.BLOCKING,
    ) -> None:
        findings.append(
            ArchitectureFinding(
                semantic_id(
                    "AFD",
                    {
                        "code": code.value,
                        "affected": affected,
                        "requirements": requirement_refs,
                        "message": message,
                    },
                ),
                code,
                severity,
                message,
                affected,
                requirement_refs,
            )
        )

    if ia.project_id != requirements.project_id or navigation.project_id != requirements.project_id:
        add(
            ArchitectureFindingCode.PROJECT_MISMATCH,
            "Architecture records belong to another project.",
        )
    if requirements.canonical_fingerprint() != expected_requirements_fingerprint:
        add(
            ArchitectureFindingCode.STALE_REQUIREMENTS,
            "Requirements fingerprint is stale.",
        )
    for surface in ia.surfaces:
        if not surface.requirement_refs:
            add(
                ArchitectureFindingCode.MISSING_PROVENANCE,
                "Surface has no approved requirement provenance.",
                (surface.surface_id,),
                severity=ArchitectureFindingSeverity.WARNING,
            )
    unresolved = tuple(
        item.requirement_ref
        for item in coverage
        if item.disposition is CoverageDisposition.UNRESOLVED
    )
    if unresolved:
        add(
            ArchitectureFindingCode.UNCOVERED_REQUIREMENT,
            "Material requirements remain without architecture disposition.",
            requirement_refs=unresolved,
        )
    if ia.routes and not any(
        route.path_pattern == "/" and route.visibility is RouteVisibility.PUBLIC
        for route in ia.routes
    ):
        add(
            ArchitectureFindingCode.MISSING_PUBLIC_ENTRY,
            "A routed product requires a public entry point.",
        )
    node_routes = {node.route_ref for node in navigation.nodes}
    for route in ia.routes:
        if route.route_id not in node_routes and route.visibility is not RouteVisibility.HIDDEN:
            add(
                ArchitectureFindingCode.UNREACHABLE_SURFACE,
                "A visible route is absent from navigation.",
                (route.route_id,),
            )
    routes_by_id = {route.route_id: route for route in ia.routes}
    for node in navigation.nodes:
        if node.route_ref is None:
            continue
        nav_route = routes_by_id.get(node.route_ref)
        if nav_route is None:
            add(
                ArchitectureFindingCode.MISSING_SURFACE,
                "Navigation references a missing route.",
                (node.node_id,),
            )
        elif (
            nav_route.visibility is RouteVisibility.AUTHENTICATED
            and node.visibility is NavigationVisibility.PUBLIC
        ):
            add(
                ArchitectureFindingCode.PUBLIC_PROTECTED_MISMATCH,
                "Protected destination is exposed in public navigation.",
                (node.node_id, nav_route.route_id),
            )
    auth_approved = any(
        item.category is RequirementCategory.SECURITY and "auth" in item.statement.lower()
        for item in requirements.requirements
    )
    if not auth_approved and any(route.auth_requirement == "required" for route in ia.routes):
        add(
            ArchitectureFindingCode.UNAPPROVED_AUTH_INTENT,
            "Architecture invents authentication absent from approved requirements.",
        )
    data_approved = any(
        item.category is RequirementCategory.DATA for item in requirements.requirements
    )
    if not data_approved and any(surface.data_dependencies for surface in ia.surfaces):
        add(
            ArchitectureFindingCode.UNAPPROVED_BACKEND_DATA,
            "Architecture invents data behavior absent from approved requirements.",
        )
    exclusions = " ".join(requirements.exclusions).lower()
    for surface in ia.surfaces:
        if surface.surface_type.value in exclusions:
            add(
                ArchitectureFindingCode.CONTRADICTS_EXCLUSION,
                "Architecture contradicts an explicit exclusion.",
                (surface.surface_id,),
            )
    data_text = " ".join(
        item.statement
        for item in requirements.requirements
        if item.category is RequirementCategory.DATA
    ).lower()
    for route in (item for item in ia.routes if "{" in item.path_pattern):
        if not all(name.lower() in data_text for name, _ in route.parameter_contracts):
            add(
                ArchitectureFindingCode.UNJUSTIFIED_DYNAMIC_PARAMETER,
                "Dynamic parameter lacks approved data justification.",
                (route.route_id,),
            )
    return coverage, tuple(sorted(findings, key=lambda item: item.finding_id))


def prepare_architecture(command: PrepareArchitectureCommand) -> PrepareArchitectureResult:
    requirements = command.requirements_contract
    requirements_review = command.requirements_review
    if command.project_status is not WebLifecycleStatus.REQUIREMENTS_APPROVED:
        raise ArchitecturePreparationError(
            "Architecture preparation requires REQUIREMENTS_APPROVED"
        )
    if {requirements.project_id, requirements_review.project_id} != {command.project_id}:
        raise ArchitecturePreparationError("Approved requirements project identity mismatch")
    if requirements.canonical_fingerprint() != command.approved_requirements_fingerprint:
        raise ArchitecturePreparationError("Approved requirements fingerprint is stale")
    if (
        requirements_review.canonical_fingerprint()
        != command.approved_requirements_review_fingerprint
    ):
        raise ArchitecturePreparationError("Approved requirements review fingerprint is stale")
    requirements_review.requirements_contract_ref.verify(requirements, requirements.contract_id)
    if requirements.route is not command.route:
        raise ArchitecturePreparationError("Authoritative route mismatch")
    ia, navigation = plan_information_architecture(requirements)
    ia.validate_requirements(requirements)
    coverage, findings = analyze_architecture(
        requirements,
        ia,
        navigation,
        expected_requirements_fingerprint=command.approved_requirements_fingerprint,
    )
    if command.route is WebRoute.STANDARD and not navigation.journeys:
        findings += (
            ArchitectureFinding(
                semantic_id("AFD", "standard-journey"),
                ArchitectureFindingCode.INSUFFICIENT_ROUTE_EVIDENCE,
                ArchitectureFindingSeverity.BLOCKING,
                "Standard route requires a key user journey.",
            ),
        )
    if command.route is WebRoute.CRITICAL:
        categories = {item.category for item in requirements.requirements}
        missing = {RequirementCategory.SECURITY, RequirementCategory.DATA} - categories
        if missing:
            findings += (
                ArchitectureFinding(
                    semantic_id("AFD", {"critical": sorted(item.value for item in missing)}),
                    ArchitectureFindingCode.INSUFFICIENT_ROUTE_EVIDENCE,
                    ArchitectureFindingSeverity.BLOCKING,
                    "Critical route requires explicit security and data mapping.",
                ),
            )
    blockers = any(item.blocking for item in findings)
    review = ArchitectureReviewPackage(
        contract_version=CURRENT_WEB_CONTRACT_VERSION,
        review_id=semantic_id(
            "ARV",
            {
                "requirements": requirements.canonical_fingerprint(),
                "ia": ia.canonical_fingerprint(),
                "navigation": navigation.canonical_fingerprint(),
                "coverage": coverage,
                "findings": findings,
                "assumptions": command.assumptions,
            },
        ),
        project_id=command.project_id,
        requirements_contract_ref=_ref(requirements, requirements.contract_id),
        requirements_review_ref=_ref(requirements_review, requirements_review.review_id),
        information_architecture_ref=_ref(ia, ia.contract_id),
        navigation_model_ref=_ref(navigation, navigation.navigation_id),
        route=command.route,
        coverage=coverage,
        findings=findings,
        assumptions=command.assumptions,
        readiness=(
            ArchitectureReadiness.NOT_READY if blockers else ArchitectureReadiness.READY_FOR_REVIEW
        ),
    )
    return PrepareArchitectureResult(ia, navigation, review)


__all__ = ("analyze_architecture", "prepare_architecture")
