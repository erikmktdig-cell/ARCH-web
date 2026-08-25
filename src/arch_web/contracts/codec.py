"""Explicit fail-closed codecs for approved ARCH Web records."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

from arch_web.contracts.canonical import canonical_bytes
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
from arch_web.domain.backend import (
    ApplicationDataContract,
    ApplicationMigrationPlan,
    ApplicationMigrationStep,
    AuthenticationContract,
    AuthorizationRule,
    BackendArtifact,
    BackendArtifactKind,
    BackendAssignmentPacket,
    BackendCompletionPackage,
    BackendDataBinding,
    BackendDisposition,
    BackendEngineeringCheck,
    BackendFinding,
    BackendFindingCode,
    BackendImplementationProposal,
    BackendInterfaceContract,
    BackendOperationContract,
    BackendReviewPackage,
    BackendUnitResult,
    BindingClosureStatus,
    DataEntitySpec,
    DataFieldSpec,
    DataLifecyclePolicy,
    DataOwnershipPolicy,
    DataSensitivity,
    DataSourceKind,
    ExternalIntegrationContract,
    FailureKind,
    FailurePolicy,
    PersistenceContract,
)
from arch_web.domain.design_intent import (
    DesignIntent,
    DesignProfileRecommendation,
    ReferenceDesignProfile,
)
from arch_web.domain.design_tokens import (
    ContrastPairSpec,
    PrimitiveToken,
    PrimitiveTokenKind,
    PrimitiveTokenSet,
    SemanticToken,
    SemanticTokenSet,
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
from arch_web.domain.errors import WebContractIntegrityError, WebContractValidationError
from arch_web.domain.frontend import (
    FrontendArtifact,
    FrontendArtifactKind,
    FrontendAssignmentPacket,
    FrontendCheckStatus,
    FrontendCompletionPackage,
    FrontendComponentBinding,
    FrontendDataBinding,
    FrontendDataDisposition,
    FrontendDependencyDecision,
    FrontendEngineeringCheck,
    FrontendExecutionAuthorization,
    FrontendFinding,
    FrontendFindingCode,
    FrontendImplementationProposal,
    FrontendReadiness,
    FrontendReviewPackage,
    FrontendRouteBinding,
    FrontendSurfaceBinding,
    FrontendTokenBinding,
    FrontendUnitResult,
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
from arch_web.domain.qa import (
    AccessibilityQAEvidence,
    BrowserSupportPolicy,
    FunctionalQAEvidence,
    IntegrationQAEvidence,
    PerformanceQAEvidence,
    PreviewEnvironmentEvidence,
    PreviewPlan,
    QABaselineProfile,
    QACandidateBaseline,
    QACoverageDisposition,
    QACoverageItem,
    QACoverageMatrix,
    QAEvidence,
    QAExecutionAuthorization,
    QAExpectation,
    QAFinding,
    QAFindingDisposition,
    QAReadiness,
    QAResult,
    QAReviewPackage,
    QARun,
    QAScenario,
    QAScope,
    QASeverity,
    QAStatus,
    QAStep,
    ReleaseReadinessPackage,
    ResponsiveQAEvidence,
    SecurityBehaviorEvidence,
    ViewportPolicy,
    ViewportSpec,
    VisualComparisonDisposition,
    VisualQAEvidence,
)
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
from arch_web.domain.ui_review import (
    DesignCoverageDisposition,
    DesignCoverageItem,
    DesignCoverageResult,
    DesignCoverageScope,
    DesignFinding,
    DesignFindingCode,
    DesignFindingSeverity,
    UIReadiness,
    UIReviewPackage,
)
from arch_web.domain.ui_specification import (
    AccessibilitySpec,
    BreakpointSpec,
    ComponentStateName,
    ComponentStateSpec,
    ComponentVariantSpec,
    InteractionSpec,
    LayoutSystem,
    MotionPolicy,
    MotionPurpose,
    MotionSpec,
    ResponsiveBehavior,
    ResponsivePolicy,
    ResponsiveRule,
    SurfaceUISpec,
    TypographyRole,
    TypographySystem,
    UIComponentSpec,
    WebDesignSystemContract,
    WebUISpecificationContract,
)
from arch_web.domain.workspace import (
    ExecutionOutcome,
    FileEvidence,
    ImplementationPlan,
    ImplementationUnit,
    ImplementationUnitKind,
    PathClaim,
    PathClaimMode,
    ReconciliationStatus,
    RepositoryBaseline,
    RepositoryEvidence,
    ResolvedStackManifest,
    ToolchainCapability,
    WorkspaceBaseline,
    WorkspaceChange,
    WorkspaceChangeSet,
    WorkspaceDryRun,
    WorkspaceExecutionPolicy,
    WorkspaceExecutionReceipt,
    WorkspaceFinding,
    WorkspaceFindingCode,
    WorkspaceKind,
    WorkspaceOperation,
    WorkspaceReadiness,
    WorkspaceReviewPackage,
    WorkspaceTarget,
)


def encode_contract(value: WebContractRecord) -> bytes:
    return canonical_bytes(value)


def decode_contract[ContractT: WebContractRecord](
    contract_class: type[ContractT], payload: bytes, *, expected_fingerprint: str | None = None
) -> ContractT:
    try:
        raw = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WebContractValidationError("Payload is not valid UTF-8 JSON") from error
    if not isinstance(raw, dict):
        raise WebContractValidationError("Contract payload must be a JSON object")
    result = decode_contract_data(contract_class, raw)
    canonical = encode_contract(result)
    if payload != canonical:
        raise WebContractIntegrityError("Payload is valid JSON but is not canonical")
    if expected_fingerprint is not None and result.canonical_fingerprint() != expected_fingerprint:
        raise WebContractIntegrityError("Contract fingerprint mismatch")
    return result


def _choice(value: str) -> str | ArchitectureChoice:
    return (
        ArchitectureChoice(value) if value in {item.value for item in ArchitectureChoice} else value
    )


def _contract_ref(value: Mapping[str, Any] | None) -> ContractRef | None:
    return None if value is None else ContractRef(**value)


def _evidence_ref(value: Mapping[str, Any] | None) -> EvidenceRef | None:
    if value is None:
        return None
    data = dict(value)
    data["created_at"] = _datetime(data.get("created_at"))
    return EvidenceRef(**data)


def _datetime(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value.replace("Z", "+00:00"))


def decode_contract_data[ContractT: WebContractRecord](
    contract_class: type[ContractT], value: Mapping[str, Any]
) -> ContractT:
    data = dict(value)
    try:
        if contract_class is ContractRef:
            result: WebContractRecord = ContractRef(**data)
        elif contract_class is DesignReference:
            data["captured_at"] = _datetime(data.get("captured_at"))
            result = DesignReference(**data)
        elif contract_class is EvidenceRef:
            data["created_at"] = _datetime(data.get("created_at"))
            result = EvidenceRef(**data)
        elif contract_class is WebStackProfile:
            choice_fields = set(data) - {"contract_version", "profile_id", "constraints"}
            for field_name in choice_fields:
                data[field_name] = _choice(data[field_name])
            result = WebStackProfile(**data)
        elif contract_class is WebRequirement:
            data["category"] = RequirementCategory(data["category"])
            data["priority"] = RequirementPriority(data["priority"])
            data["route_requirement"] = WebRoute(data["route_requirement"])
            data["status"] = RequirementStatus(data["status"])
            result = WebRequirement(**data)
        elif contract_class is WebRequirementsContract:
            data["route"] = WebRoute(data["route"])
            data["requirements"] = tuple(
                WebRequirement.from_data(item) for item in data["requirements"]
            )
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = WebRequirementsContract(**data)
        elif contract_class is WebSurface:
            data["surface_type"] = SurfaceType(data["surface_type"])
            result = WebSurface(**data)
        elif contract_class is WebRouteContract:
            data["visibility"] = RouteVisibility(data["visibility"])
            result = WebRouteContract(**data)
        elif contract_class is WebInformationArchitectureContract:
            data["surfaces"] = tuple(WebSurface.from_data(item) for item in data["surfaces"])
            data["routes"] = tuple(WebRouteContract.from_data(item) for item in data["routes"])
            result = WebInformationArchitectureContract(**data)
        elif contract_class is NavigationNode:
            data["navigation_kind"] = NavigationKind(data["navigation_kind"])
            data["visibility"] = NavigationVisibility(data["visibility"])
            result = NavigationNode(**data)
        elif contract_class is NavigationEdge:
            data["relationship"] = NavigationRelationship(data["relationship"])
            result = NavigationEdge(**data)
        elif contract_class is UserJourney:
            result = UserJourney(**data)
        elif contract_class is NavigationModel:
            data["nodes"] = tuple(NavigationNode.from_data(item) for item in data["nodes"])
            data["edges"] = tuple(NavigationEdge.from_data(item) for item in data["edges"])
            data["journeys"] = tuple(UserJourney.from_data(item) for item in data["journeys"])
            result = NavigationModel(**data)
        elif contract_class is RequirementCoverage:
            data["disposition"] = CoverageDisposition(data["disposition"])
            result = RequirementCoverage(**data)
        elif contract_class is ArchitectureFinding:
            data["code"] = ArchitectureFindingCode(data["code"])
            data["severity"] = ArchitectureFindingSeverity(data["severity"])
            result = ArchitectureFinding(**data)
        elif contract_class is ArchitectureReviewPackage:
            for field_name in (
                "requirements_contract_ref",
                "requirements_review_ref",
                "information_architecture_ref",
                "navigation_model_ref",
            ):
                data[field_name] = cast(ContractRef, _contract_ref(data[field_name]))
            data["route"] = WebRoute(data["route"])
            data["coverage"] = tuple(
                RequirementCoverage.from_data(item) for item in data["coverage"]
            )
            data["findings"] = tuple(
                ArchitectureFinding.from_data(item) for item in data["findings"]
            )
            data["readiness"] = ArchitectureReadiness(data["readiness"])
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = ArchitectureReviewPackage(**data)
        elif contract_class is DesignIntent:
            data["reference_refs"] = tuple(
                DesignReference.from_data(item) for item in data["reference_refs"]
            )
            result = DesignIntent(**data)
        elif contract_class is ReferenceDesignProfile:
            data["supported_routes"] = tuple(WebRoute(item) for item in data["supported_routes"])
            data["primitive_tokens"] = tuple(tuple(item) for item in data["primitive_tokens"])
            data["semantic_tokens"] = tuple(tuple(item) for item in data["semantic_tokens"])
            result = ReferenceDesignProfile(**data)
        elif contract_class is DesignProfileRecommendation:
            data["route"] = WebRoute(data["route"])
            result = DesignProfileRecommendation(**data)
        elif contract_class is PrimitiveToken:
            data["kind"] = PrimitiveTokenKind(data["kind"])
            result = PrimitiveToken(**data)
        elif contract_class is PrimitiveTokenSet:
            data["tokens"] = tuple(PrimitiveToken.from_data(item) for item in data["tokens"])
            result = PrimitiveTokenSet(**data)
        elif contract_class is SemanticToken:
            result = SemanticToken(**data)
        elif contract_class is SemanticTokenSet:
            data["primitive_set_ref"] = cast(ContractRef, _contract_ref(data["primitive_set_ref"]))
            data["tokens"] = tuple(SemanticToken.from_data(item) for item in data["tokens"])
            result = SemanticTokenSet(**data)
        elif contract_class is ContrastPairSpec:
            result = ContrastPairSpec(**data)
        elif contract_class is TypographyRole:
            result = TypographyRole(**data)
        elif contract_class is TypographySystem:
            data["roles"] = tuple(TypographyRole.from_data(item) for item in data["roles"])
            result = TypographySystem(**data)
        elif contract_class is LayoutSystem:
            result = LayoutSystem(**data)
        elif contract_class is BreakpointSpec:
            result = BreakpointSpec(**data)
        elif contract_class is ResponsiveRule:
            data["behavior"] = ResponsiveBehavior(data["behavior"])
            result = ResponsiveRule(**data)
        elif contract_class is ResponsivePolicy:
            data["breakpoints"] = tuple(
                BreakpointSpec.from_data(item) for item in data["breakpoints"]
            )
            data["rules"] = tuple(ResponsiveRule.from_data(item) for item in data["rules"])
            result = ResponsivePolicy(**data)
        elif contract_class is MotionSpec:
            data["purpose"] = MotionPurpose(data["purpose"])
            result = MotionSpec(**data)
        elif contract_class is MotionPolicy:
            data["motions"] = tuple(MotionSpec.from_data(item) for item in data["motions"])
            result = MotionPolicy(**data)
        elif contract_class is ComponentStateSpec:
            data["state"] = ComponentStateName(data["state"])
            result = ComponentStateSpec(**data)
        elif contract_class is ComponentVariantSpec:
            result = ComponentVariantSpec(**data)
        elif contract_class is InteractionSpec:
            result = InteractionSpec(**data)
        elif contract_class is AccessibilitySpec:
            result = AccessibilitySpec(**data)
        elif contract_class is UIComponentSpec:
            data["variants"] = tuple(
                ComponentVariantSpec.from_data(item) for item in data["variants"]
            )
            data["states"] = tuple(ComponentStateSpec.from_data(item) for item in data["states"])
            data["interaction"] = InteractionSpec.from_data(data["interaction"])
            data["accessibility"] = AccessibilitySpec.from_data(data["accessibility"])
            result = UIComponentSpec(**data)
        elif contract_class is SurfaceUISpec:
            result = SurfaceUISpec(**data)
        elif contract_class is WebDesignSystemContract:
            data["design_intent_ref"] = cast(ContractRef, _contract_ref(data["design_intent_ref"]))
            data["selected_profile_ref"] = _contract_ref(data.get("selected_profile_ref"))
            data["primitive_tokens"] = PrimitiveTokenSet.from_data(data["primitive_tokens"])
            data["semantic_tokens"] = SemanticTokenSet.from_data(data["semantic_tokens"])
            data["contrast_pairs"] = tuple(
                ContrastPairSpec.from_data(item) for item in data["contrast_pairs"]
            )
            data["typography"] = TypographySystem.from_data(data["typography"])
            data["layout"] = LayoutSystem.from_data(data["layout"])
            data["responsive"] = ResponsivePolicy.from_data(data["responsive"])
            data["motion"] = MotionPolicy.from_data(data["motion"])
            result = WebDesignSystemContract(**data)
        elif contract_class is WebUISpecificationContract:
            data["architecture_ref"] = cast(ContractRef, _contract_ref(data["architecture_ref"]))
            data["design_system_ref"] = cast(ContractRef, _contract_ref(data["design_system_ref"]))
            data["components"] = tuple(
                UIComponentSpec.from_data(item) for item in data["components"]
            )
            data["surfaces"] = tuple(SurfaceUISpec.from_data(item) for item in data["surfaces"])
            data["design_evidence_refs"] = tuple(
                DesignReference.from_data(item) for item in data["design_evidence_refs"]
            )
            result = WebUISpecificationContract(**data)
        elif contract_class is DesignCoverageItem:
            data["scope"] = DesignCoverageScope(data["scope"])
            data["disposition"] = DesignCoverageDisposition(data["disposition"])
            result = DesignCoverageItem(**data)
        elif contract_class is DesignCoverageResult:
            data["items"] = tuple(DesignCoverageItem.from_data(item) for item in data["items"])
            result = DesignCoverageResult(**data)
        elif contract_class is DesignFinding:
            data["code"] = DesignFindingCode(data["code"])
            data["severity"] = DesignFindingSeverity(data["severity"])
            result = DesignFinding(**data)
        elif contract_class is UIReviewPackage:
            for field_name in (
                "requirements_ref",
                "architecture_ref",
                "architecture_review_ref",
                "design_intent_ref",
                "design_system_ref",
                "ui_specification_ref",
                "coverage_ref",
            ):
                data[field_name] = cast(ContractRef, _contract_ref(data[field_name]))
            data["selected_profile_ref"] = _contract_ref(data.get("selected_profile_ref"))
            data["route"] = WebRoute(data["route"])
            data["profile_recommendation"] = DesignProfileRecommendation.from_data(
                data["profile_recommendation"]
            )
            data["findings"] = tuple(DesignFinding.from_data(item) for item in data["findings"])
            data["readiness"] = UIReadiness(data["readiness"])
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = UIReviewPackage(**data)
        elif contract_class is WorkspaceTarget:
            data["kind"] = WorkspaceKind(data["kind"])
            data["route"] = WebRoute(data["route"])
            result = WorkspaceTarget(**data)
        elif contract_class is FileEvidence:
            result = FileEvidence(**data)
        elif contract_class is RepositoryBaseline:
            result = RepositoryBaseline(**data)
        elif contract_class is WorkspaceBaseline:
            data["files"] = tuple(FileEvidence.from_data(item) for item in data["files"])
            data["repository"] = RepositoryBaseline.from_data(data["repository"])
            data["toolchain_capabilities"] = tuple(
                ToolchainCapability.from_data(item)
                for item in data.get("toolchain_capabilities", ())
            )
            result = WorkspaceBaseline(**data)
        elif contract_class is ToolchainCapability:
            result = ToolchainCapability(**data)
        elif contract_class is ResolvedStackManifest:
            data["source_profile_ref"] = cast(
                ContractRef, _contract_ref(data["source_profile_ref"])
            )
            result = ResolvedStackManifest(**data)
        elif contract_class is PathClaim:
            data["mode"] = PathClaimMode(data["mode"])
            result = PathClaim(**data)
        elif contract_class is ImplementationUnit:
            data["kind"] = ImplementationUnitKind(data["kind"])
            result = ImplementationUnit(**data)
        elif contract_class is ImplementationPlan:
            for field_name in (
                "requirements_ref",
                "architecture_ref",
                "design_system_ref",
                "ui_specification_ref",
                "ui_review_ref",
                "stack_ref",
            ):
                data[field_name] = cast(ContractRef, _contract_ref(data[field_name]))
            data["units"] = tuple(ImplementationUnit.from_data(item) for item in data["units"])
            data["path_claims"] = tuple(PathClaim.from_data(item) for item in data["path_claims"])
            result = ImplementationPlan(**data)
        elif contract_class is WorkspaceChange:
            data["operation"] = WorkspaceOperation(data["operation"])
            result = WorkspaceChange(**data)
        elif contract_class is WorkspaceChangeSet:
            data["changes"] = tuple(WorkspaceChange.from_data(item) for item in data["changes"])
            result = WorkspaceChangeSet(**data)
        elif contract_class is WorkspaceExecutionPolicy:
            result = WorkspaceExecutionPolicy(**data)
        elif contract_class is WorkspaceDryRun:
            result = WorkspaceDryRun(**data)
        elif contract_class is RepositoryEvidence:
            result = RepositoryEvidence(**data)
        elif contract_class is WorkspaceExecutionReceipt:
            data["repository_evidence"] = RepositoryEvidence.from_data(data["repository_evidence"])
            data["changed_paths"] = tuple(
                FileEvidence.from_data(item) for item in data["changed_paths"]
            )
            data["outcome"] = ExecutionOutcome(data["outcome"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            result = WorkspaceExecutionReceipt(**data)
        elif contract_class is WorkspaceFinding:
            data["code"] = WorkspaceFindingCode(data["code"])
            result = WorkspaceFinding(**data)
        elif contract_class is WorkspaceReviewPackage:
            for field_name in ("plan_ref", "stack_ref", "change_set_ref"):
                data[field_name] = cast(ContractRef, _contract_ref(data[field_name]))
            data["receipt_ref"] = _contract_ref(data.get("receipt_ref"))
            data["route"] = WebRoute(data["route"])
            data["findings"] = tuple(WorkspaceFinding.from_data(item) for item in data["findings"])
            data["readiness"] = WorkspaceReadiness(data["readiness"])
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = WorkspaceReviewPackage(**data)
        elif contract_class is DataFieldSpec:
            data["sensitivity"] = DataSensitivity(data["sensitivity"])
            result = DataFieldSpec(**data)
        elif contract_class is DataOwnershipPolicy:
            data["source_kind"] = DataSourceKind(data["source_kind"])
            result = DataOwnershipPolicy(**data)
        elif contract_class is DataLifecyclePolicy:
            result = DataLifecyclePolicy(**data)
        elif contract_class is DataEntitySpec:
            data["fields"] = tuple(DataFieldSpec.from_data(item) for item in data["fields"])
            data["ownership"] = DataOwnershipPolicy.from_data(data["ownership"])
            data["lifecycle"] = DataLifecyclePolicy.from_data(data["lifecycle"])
            result = DataEntitySpec(**data)
        elif contract_class is ApplicationDataContract:
            data["entities"] = tuple(DataEntitySpec.from_data(item) for item in data["entities"])
            result = ApplicationDataContract(**data)
        elif contract_class is FailurePolicy:
            data["failure"] = FailureKind(data["failure"])
            result = FailurePolicy(**data)
        elif contract_class is BackendOperationContract:
            data["failure_kinds"] = tuple(FailureKind(item) for item in data["failure_kinds"])
            data["sensitivity"] = DataSensitivity(data["sensitivity"])
            result = BackendOperationContract(**data)
        elif contract_class is BackendInterfaceContract:
            data["operations"] = tuple(
                BackendOperationContract.from_data(item) for item in data["operations"]
            )
            data["failure_policies"] = tuple(
                FailurePolicy.from_data(item) for item in data["failure_policies"]
            )
            result = BackendInterfaceContract(**data)
        elif contract_class is BackendDataBinding:
            data["status"] = BindingClosureStatus(data["status"])
            result = BackendDataBinding(**data)
        elif contract_class is AuthenticationContract:
            result = AuthenticationContract(**data)
        elif contract_class is AuthorizationRule:
            result = AuthorizationRule(**data)
        elif contract_class is PersistenceContract:
            result = PersistenceContract(**data)
        elif contract_class is ApplicationMigrationStep:
            result = ApplicationMigrationStep(**data)
        elif contract_class is ApplicationMigrationPlan:
            data["steps"] = tuple(
                ApplicationMigrationStep.from_data(item) for item in data["steps"]
            )
            result = ApplicationMigrationPlan(**data)
        elif contract_class is ExternalIntegrationContract:
            result = ExternalIntegrationContract(**data)
        elif contract_class is BackendArtifact:
            data["kind"] = BackendArtifactKind(data["kind"])
            result = BackendArtifact(**data)
        elif contract_class is BackendAssignmentPacket:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            result = BackendAssignmentPacket(**data)
        elif contract_class is BackendFinding:
            data["code"] = BackendFindingCode(data["code"])
            result = BackendFinding(**data)
        elif contract_class is BackendEngineeringCheck:
            data["status"] = FrontendCheckStatus(data["status"])
            result = BackendEngineeringCheck(**data)
        elif contract_class is BackendImplementationProposal:
            data["artifacts"] = tuple(BackendArtifact.from_data(item) for item in data["artifacts"])
            data["bindings"] = tuple(
                BackendDataBinding.from_data(item) for item in data["bindings"]
            )
            data["interface"] = BackendInterfaceContract.from_data(data["interface"])
            data["data_contract"] = ApplicationDataContract.from_data(data["data_contract"])
            data["authentication"] = AuthenticationContract.from_data(data["authentication"])
            data["authorization_rules"] = tuple(
                AuthorizationRule.from_data(item) for item in data["authorization_rules"]
            )
            data["persistence"] = PersistenceContract.from_data(data["persistence"])
            data["migrations"] = ApplicationMigrationPlan.from_data(data["migrations"])
            data["integrations"] = tuple(
                ExternalIntegrationContract.from_data(item) for item in data["integrations"]
            )
            data["findings"] = tuple(BackendFinding.from_data(item) for item in data["findings"])
            result = BackendImplementationProposal(**data)
        elif contract_class is BackendUnitResult:
            result = BackendUnitResult(**data)
        elif contract_class is BackendCompletionPackage:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            data["disposition"] = BackendDisposition(data["disposition"])
            data["frontend_completion_ref"] = cast(
                ContractRef, _contract_ref(data["frontend_completion_ref"])
            )
            data["binding_closures"] = tuple(
                BackendDataBinding.from_data(item) for item in data["binding_closures"]
            )
            data["unit_results"] = tuple(
                BackendUnitResult.from_data(item) for item in data["unit_results"]
            )
            receipt = data.get("workspace_receipt")
            data["workspace_receipt"] = (
                None if receipt is None else WorkspaceExecutionReceipt.from_data(receipt)
            )
            data["engineering_checks"] = tuple(
                BackendEngineeringCheck.from_data(item) for item in data["engineering_checks"]
            )
            data["findings"] = tuple(BackendFinding.from_data(item) for item in data["findings"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            result = BackendCompletionPackage(**data)
        elif contract_class is BackendReviewPackage:
            data["completion_ref"] = cast(ContractRef, _contract_ref(data["completion_ref"]))
            data["findings"] = tuple(BackendFinding.from_data(item) for item in data["findings"])
            data["disposition"] = BackendDisposition(data["disposition"])
            result = BackendReviewPackage(**data)
        elif contract_class is FrontendExecutionAuthorization:
            result = FrontendExecutionAuthorization(**data)
        elif contract_class is FrontendAssignmentPacket:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            result = FrontendAssignmentPacket(**data)
        elif contract_class is FrontendArtifact:
            data["kind"] = FrontendArtifactKind(data["kind"])
            result = FrontendArtifact(**data)
        elif contract_class is FrontendSurfaceBinding:
            result = FrontendSurfaceBinding(**data)
        elif contract_class is FrontendRouteBinding:
            result = FrontendRouteBinding(**data)
        elif contract_class is FrontendComponentBinding:
            result = FrontendComponentBinding(**data)
        elif contract_class is FrontendDataBinding:
            data["disposition"] = FrontendDataDisposition(data["disposition"])
            result = FrontendDataBinding(**data)
        elif contract_class is FrontendTokenBinding:
            result = FrontendTokenBinding(**data)
        elif contract_class is FrontendDependencyDecision:
            result = FrontendDependencyDecision(**data)
        elif contract_class is FrontendFinding:
            data["code"] = FrontendFindingCode(data["code"])
            result = FrontendFinding(**data)
        elif contract_class is FrontendEngineeringCheck:
            data["status"] = FrontendCheckStatus(data["status"])
            result = FrontendEngineeringCheck(**data)
        elif contract_class is FrontendImplementationProposal:
            data["artifacts"] = tuple(
                FrontendArtifact.from_data(item) for item in data["artifacts"]
            )
            data["surface_bindings"] = tuple(
                FrontendSurfaceBinding.from_data(item) for item in data["surface_bindings"]
            )
            data["route_bindings"] = tuple(
                FrontendRouteBinding.from_data(item) for item in data["route_bindings"]
            )
            data["component_bindings"] = tuple(
                FrontendComponentBinding.from_data(item) for item in data["component_bindings"]
            )
            data["data_bindings"] = tuple(
                FrontendDataBinding.from_data(item) for item in data["data_bindings"]
            )
            data["token_bindings"] = tuple(
                FrontendTokenBinding.from_data(item) for item in data["token_bindings"]
            )
            data["dependency_decisions"] = tuple(
                FrontendDependencyDecision.from_data(item) for item in data["dependency_decisions"]
            )
            data["findings"] = tuple(FrontendFinding.from_data(item) for item in data["findings"])
            result = FrontendImplementationProposal(**data)
        elif contract_class is FrontendUnitResult:
            result = FrontendUnitResult(**data)
        elif contract_class is FrontendCompletionPackage:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            data["authorization_ref"] = cast(ContractRef, _contract_ref(data["authorization_ref"]))
            data["receipt"] = WorkspaceExecutionReceipt.from_data(data["receipt"])
            data["unit_results"] = tuple(
                FrontendUnitResult.from_data(item) for item in data["unit_results"]
            )
            data["engineering_checks"] = tuple(
                FrontendEngineeringCheck.from_data(item) for item in data["engineering_checks"]
            )
            data["findings"] = tuple(FrontendFinding.from_data(item) for item in data["findings"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            data["readiness"] = FrontendReadiness(data["readiness"])
            result = FrontendCompletionPackage(**data)
        elif contract_class is FrontendReviewPackage:
            data["completion_ref"] = cast(ContractRef, _contract_ref(data["completion_ref"]))
            data["findings"] = tuple(FrontendFinding.from_data(item) for item in data["findings"])
            data["readiness"] = FrontendReadiness(data["readiness"])
            result = FrontendReviewPackage(**data)
        elif contract_class is BrowserSupportPolicy:
            result = BrowserSupportPolicy(**data)
        elif contract_class is ViewportSpec:
            result = ViewportSpec(**data)
        elif contract_class is ViewportPolicy:
            data["viewports"] = tuple(ViewportSpec.from_data(item) for item in data["viewports"])
            result = ViewportPolicy(**data)
        elif contract_class is QABaselineProfile:
            data["route"] = WebRoute(data["route"])
            data["browser_policy"] = BrowserSupportPolicy.from_data(data["browser_policy"])
            data["viewport_policy"] = ViewportPolicy.from_data(data["viewport_policy"])
            data["visual_baseline_ref"] = _evidence_ref(data.get("visual_baseline_ref"))
            data["performance_budgets"] = tuple(tuple(item) for item in data["performance_budgets"])
            result = QABaselineProfile(**data)
        elif contract_class is QACandidateBaseline:
            data["route"] = WebRoute(data["route"])
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            result = QACandidateBaseline(**data)
        elif contract_class is QAExpectation:
            result = QAExpectation(**data)
        elif contract_class is QAStep:
            data["expectations"] = tuple(
                QAExpectation.from_data(item) for item in data["expectations"]
            )
            result = QAStep(**data)
        elif contract_class is QAScenario:
            data["steps"] = tuple(QAStep.from_data(item) for item in data["steps"])
            result = QAScenario(**data)
        elif contract_class is QAScope:
            data["route"] = WebRoute(data["route"])
            data["scenarios"] = tuple(QAScenario.from_data(item) for item in data["scenarios"])
            result = QAScope(**data)
        elif contract_class is QAExecutionAuthorization:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            result = QAExecutionAuthorization(**data)
        elif contract_class is PreviewPlan:
            result = PreviewPlan(**data)
        elif contract_class is PreviewEnvironmentEvidence:
            result = PreviewEnvironmentEvidence(**data)
        elif contract_class is QAResult:
            data["status"] = QAStatus(data["status"])
            data["attempt_statuses"] = tuple(QAStatus(item) for item in data["attempt_statuses"])
            result = QAResult(**data)
        elif contract_class is QARun:
            data["results"] = tuple(QAResult.from_data(item) for item in data["results"])
            result = QARun(**data)
        elif contract_class in {
            QAEvidence,
            FunctionalQAEvidence,
            IntegrationQAEvidence,
            AccessibilityQAEvidence,
            ResponsiveQAEvidence,
            PerformanceQAEvidence,
            SecurityBehaviorEvidence,
        }:
            data["status"] = QAStatus(data["status"])
            evidence_class = cast(type[QAEvidence], contract_class)
            result = evidence_class(**data)
        elif contract_class is VisualQAEvidence:
            data["status"] = QAStatus(data["status"])
            data["comparison"] = VisualComparisonDisposition(data["comparison"])
            result = VisualQAEvidence(**data)
        elif contract_class is QAFinding:
            data["severity"] = QASeverity(data["severity"])
            data["disposition"] = QAFindingDisposition(data["disposition"])
            result = QAFinding(**data)
        elif contract_class is QACoverageItem:
            data["disposition"] = QACoverageDisposition(data["disposition"])
            result = QACoverageItem(**data)
        elif contract_class is QACoverageMatrix:
            data["items"] = tuple(QACoverageItem.from_data(item) for item in data["items"])
            result = QACoverageMatrix(**data)
        elif contract_class is QAReviewPackage:
            for field_name in ("candidate_ref", "scope_ref", "run_ref", "preview_ref"):
                data[field_name] = cast(ContractRef, _contract_ref(data[field_name]))
            data["evidence_refs"] = tuple(
                cast(ContractRef, _contract_ref(item)) for item in data["evidence_refs"]
            )
            data["coverage_matrix"] = QACoverageMatrix.from_data(data["coverage_matrix"])
            data["findings"] = tuple(QAFinding.from_data(item) for item in data["findings"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            data["readiness"] = QAReadiness(data["readiness"])
            data["approval_evidence"] = _evidence_ref(data.get("approval_evidence"))
            result = QAReviewPackage(**data)
        elif contract_class is ReleaseReadinessPackage:
            data["runtime_state"] = WebLifecycleStatus(data["runtime_state"])
            data["findings"] = tuple(QAFinding.from_data(item) for item in data["findings"])
            data["reconciliation_status"] = ReconciliationStatus(data["reconciliation_status"])
            data["approval_evidence"] = cast(EvidenceRef, _evidence_ref(data["approval_evidence"]))
            result = ReleaseReadinessPackage(**data)
        elif contract_class is WebProjectProfile:
            data["route"] = WebRoute(data["route"])
            data["project_kind"] = ProjectKind(data["project_kind"])
            data["status"] = WebLifecycleStatus(data["status"])
            data["stack_profile_ref"] = cast(ContractRef, _contract_ref(data["stack_profile_ref"]))
            data["requirements_ref"] = _contract_ref(data.get("requirements_ref"))
            data["information_architecture_ref"] = _contract_ref(
                data.get("information_architecture_ref")
            )
            data["design_system_ref"] = _contract_ref(data.get("design_system_ref"))
            data["created_at"] = _datetime(data.get("created_at"))
            result = WebProjectProfile(**data)
        elif contract_class is WebProductBrief:
            data["project_kind_hypothesis"] = ProjectKind(data["project_kind_hypothesis"])
            data["route"] = WebRoute(data["route"])
            data["source_refs"] = tuple(
                cast(EvidenceRef, _evidence_ref(item)) for item in data["source_refs"]
            )
            data["approval_evidence_ref"] = _evidence_ref(data.get("approval_evidence_ref"))
            result = WebProductBrief(**data)
        elif contract_class is RequirementFinding:
            data["code"] = FindingCode(data["code"])
            data["severity"] = FindingSeverity(data["severity"])
            result = RequirementFinding(**data)
        elif contract_class is RouteRecommendation:
            data["recommended_route"] = WebRoute(data["recommended_route"])
            result = RouteRecommendation(**data)
        elif contract_class is RequirementsReviewPackage:
            data["product_brief_ref"] = cast(ContractRef, _contract_ref(data["product_brief_ref"]))
            data["requirements_contract_ref"] = cast(
                ContractRef, _contract_ref(data["requirements_contract_ref"])
            )
            data["gap_findings"] = tuple(
                RequirementFinding.from_data(item) for item in data["gap_findings"]
            )
            data["conflict_findings"] = tuple(
                RequirementFinding.from_data(item) for item in data["conflict_findings"]
            )
            data["route_recommendation"] = RouteRecommendation.from_data(
                data["route_recommendation"]
            )
            data["readiness"] = RequirementsReadiness(data["readiness"])
            data["source_evidence_refs"] = tuple(
                cast(EvidenceRef, _evidence_ref(item)) for item in data["source_evidence_refs"]
            )
            data["created_at"] = _datetime(data.get("created_at"))
            result = RequirementsReviewPackage(**data)
        else:
            raise WebContractValidationError(f"No approved decoder for {contract_class!r}")
        return cast(ContractT, result)
    except (KeyError, TypeError, ValueError) as error:
        if isinstance(error, WebContractValidationError):
            raise
        raise WebContractValidationError(
            "Contract payload does not match its approved schema"
        ) from error


__all__ = ("decode_contract", "encode_contract")
