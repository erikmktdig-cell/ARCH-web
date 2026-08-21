"""Executable W00/W01 dependency boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from arch_kernel.contracts import Route

import arch_web

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "arch_web"


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.architecture
def test_domain_has_no_framework_infrastructure_or_io_imports() -> None:
    forbidden = {
        "django",
        "fastapi",
        "flask",
        "httpx",
        "next",
        "pathlib",
        "react",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
    violations: list[str] = []
    for path in sorted((SOURCE / "domain").glob("*.py")):
        for imported in _imports(path):
            if imported.split(".", 1)[0] in forbidden:
                violations.append(f"{path.name}: {imported}")
    assert violations == []


@pytest.mark.architecture
def test_package_does_not_import_runtime_or_kernel_internals() -> None:
    imports = {imported for path in SOURCE.rglob("*.py") for imported in _imports(path)}
    assert not any(name.startswith("arch_runtime.") for name in imports)
    kernel_imports = {name for name in imports if name.startswith("arch_kernel.")}
    assert kernel_imports <= {"arch_kernel.contracts"}


@pytest.mark.architecture
def test_arch_route_compatibility_is_exact() -> None:
    assert {item.value for item in arch_web.WebRoute} == {item.value for item in Route}


@pytest.mark.architecture
def test_public_api_is_deliberately_closed() -> None:
    assert set(arch_web.__all__) == {
        "ArchitectureChoice",
        "ArchitectureFinding",
        "ArchitectureFindingCode",
        "ArchitectureFindingSeverity",
        "ArchitectureReadiness",
        "ArchitectureReviewPackage",
        "ArchitectureApprovalError",
        "ArchitecturePreparationError",
        "ArchitectureWorkflowError",
        "ApproveArchitectureCommand",
        "ApproveArchitectureResult",
        "ApproveRequirementsCommand",
        "ApproveRequirementsResult",
        "CURRENT_WEB_CONTRACT_VERSION",
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
        "PrepareArchitectureCommand",
        "PrepareArchitectureResult",
        "PrepareRequirementsCommand",
        "PrepareRequirementsResult",
        "RequirementAnswer",
        "RequirementCategory",
        "RequirementFinding",
        "RequirementIntake",
        "RequirementPriority",
        "RequirementCoverage",
        "RequirementSource",
        "RequirementSourceKind",
        "RequirementStatus",
        "RequirementsApprovalError",
        "RequirementsConflictError",
        "RequirementsIncompleteError",
        "RequirementsReadiness",
        "RequirementsReviewPackage",
        "RequirementsWorkflowError",
        "RouteRecommendation",
        "RouteVisibility",
        "SUPPORTED_WEB_CONTRACT_VERSIONS",
        "SurfaceType",
        "UnsupportedWebContractVersionError",
        "UserJourney",
        "WebContractError",
        "WebContractIntegrityError",
        "WebContractReferenceError",
        "WebContractValidationError",
        "WebInformationArchitectureContract",
        "WebLifecycleStatus",
        "WebProjectProfile",
        "WebProductBrief",
        "WebRequirement",
        "WebRequirementsContract",
        "WebRoute",
        "WebRouteContract",
        "WebStackProfile",
        "WebSurface",
        "__version__",
        "analyze_architecture",
        "approve_architecture",
        "approve_requirements",
        "canonical_bytes",
        "contract_fingerprint",
        "decode_contract",
        "encode_contract",
        "normalize_route_path",
        "plan_information_architecture",
        "prepare_architecture",
        "prepare_requirements",
    } | {
        "AccessibilitySpec",
        "ApproveUISpecificationCommand",
        "ApproveUISpecificationResult",
        "BreakpointSpec",
        "ComponentStateName",
        "ComponentStateSpec",
        "ComponentVariantSpec",
        "ContrastPairSpec",
        "DesignCoverageDisposition",
        "DesignCoverageItem",
        "DesignCoverageResult",
        "DesignCoverageScope",
        "DesignFinding",
        "DesignFindingCode",
        "DesignFindingSeverity",
        "DesignIntent",
        "DesignProfileRecommendation",
        "InteractionSpec",
        "LayoutSystem",
        "MotionPolicy",
        "MotionPurpose",
        "MotionSpec",
        "PrepareUISpecificationCommand",
        "PrepareUISpecificationResult",
        "PrimitiveToken",
        "PrimitiveTokenKind",
        "PrimitiveTokenSet",
        "ReferenceDesignProfile",
        "ResponsiveBehavior",
        "ResponsivePolicy",
        "ResponsiveRule",
        "SemanticToken",
        "SemanticTokenSet",
        "SurfaceUISpec",
        "TypographyRole",
        "TypographySystem",
        "UIComponentSpec",
        "UIDesignApprovalError",
        "UIDesignPreparationError",
        "UIDesignWorkflowError",
        "UIReadiness",
        "UIReviewPackage",
        "WebDesignSystemContract",
        "WebUISpecificationContract",
        "analyze_ui_design",
        "approve_ui_specification",
        "build_design_coverage",
        "get_reference_profile",
        "prepare_ui_specification",
        "recommend_reference_profile",
        "reference_design_profiles",
    } | {
        "ApplyWorkspaceCommand",
        "ApplyWorkspaceResult",
        "ApproveImplementationReadinessCommand",
        "ApproveImplementationReadinessResult",
        "ExecutionOutcome",
        "FileEvidence",
        "ImplementationPlan",
        "ImplementationReadinessApprovalError",
        "ImplementationUnit",
        "ImplementationUnitKind",
        "PathClaim",
        "PathClaimMode",
        "PrepareWorkspaceCommand",
        "PrepareWorkspaceResult",
        "ReconciliationStatus",
        "RepositoryBaseline",
        "RepositoryEvidence",
        "ResolvedStackManifest",
        "ToolchainCapability",
        "WorkspaceBaseline",
        "WorkspaceChange",
        "WorkspaceChangeSet",
        "WorkspaceDryRun",
        "WorkspaceExecutionError",
        "WorkspaceExecutionPolicy",
        "WorkspaceExecutionReceipt",
        "WorkspaceExecutor",
        "WorkspaceFinding",
        "WorkspaceFindingCode",
        "WorkspaceIdempotencyConflictError",
        "WorkspaceKind",
        "WorkspaceOperation",
        "WorkspacePreparationError",
        "WorkspaceReadiness",
        "WorkspaceReviewPackage",
        "WorkspaceTarget",
        "approve_implementation_readiness",
        "dry_run_workspace",
        "prepare_workspace",
        "resolve_stack",
    } | {
        "ApplyFrontendUnitCommand",
        "ApplyFrontendUnitResult",
        "AuthorizeFrontendCommand",
        "AuthorizeFrontendResult",
        "FrontendArtifact",
        "FrontendArtifactKind",
        "FrontendAssignmentPacket",
        "FrontendAuthorizationError",
        "FrontendCheckStatus",
        "FrontendCompletionPackage",
        "FrontendComponentBinding",
        "FrontendDataBinding",
        "FrontendDataDisposition",
        "FrontendDependencyDecision",
        "FrontendEngineeringCheck",
        "FrontendEngineeringError",
        "FrontendExecutionAuthorization",
        "FrontendFinding",
        "FrontendFindingCode",
        "FrontendImplementationProposal",
        "FrontendPreparationError",
        "FrontendProposalError",
        "FrontendReadiness",
        "FrontendReviewPackage",
        "FrontendRouteBinding",
        "FrontendSurfaceBinding",
        "FrontendTokenBinding",
        "FrontendUnitResult",
        "PrepareFrontendCommand",
        "PrepareFrontendResult",
        "StaticFrontendAdapter",
        "UnsupportedFrontendStackError",
        "VerifyFrontendCommand",
        "VerifyFrontendResult",
        "apply_frontend_unit",
        "authorize_frontend",
        "prepare_frontend",
        "proposal_findings",
        "proposal_to_change_set",
        "verify_frontend",
    } | {
        "ApplicationDataContract",
        "ApplicationMigrationPlan",
        "ApplicationMigrationStep",
        "ApplicationSQLiteHarness",
        "ApplyBackendUnitCommand",
        "ApplyBackendUnitResult",
        "AuthenticationContract",
        "AuthorizationRule",
        "BackendArtifact",
        "BackendArtifactKind",
        "BackendAssignmentPacket",
        "BackendCompletionPackage",
        "BackendDataBinding",
        "BackendDisposition",
        "BackendEngineeringCheck",
        "BackendEngineeringError",
        "BackendFinding",
        "BackendFindingCode",
        "BackendImplementationProposal",
        "BackendInterfaceContract",
        "BackendOperationContract",
        "BackendPreparationError",
        "BackendProposalError",
        "BackendReviewPackage",
        "BackendUnitResult",
        "BindingClosureStatus",
        "DataEntitySpec",
        "DataFieldSpec",
        "DataLifecyclePolicy",
        "DataOwnershipPolicy",
        "DataSensitivity",
        "DataSourceKind",
        "ExternalIntegrationContract",
        "FailureKind",
        "FailurePolicy",
        "LocalIntegrationDouble",
        "PersistenceContract",
        "PrepareBackendCommand",
        "PrepareBackendResult",
        "PythonSQLiteBackendAdapter",
        "UnsupportedBackendStackError",
        "VerifyBackendCommand",
        "VerifyBackendResult",
        "apply_backend_unit",
        "backend_proposal_findings",
        "backend_proposal_to_change_set",
        "prepare_backend",
        "verify_backend",
    }
    assert not hasattr(arch_web, "decode_contract_data")
    assert not hasattr(arch_web, "to_canonical_data")


@pytest.mark.architecture
def test_reverse_dependencies_do_not_exist_in_installed_arch_packages() -> None:
    for package_name in ("arch_kernel", "arch_runtime"):
        package = __import__(package_name)
        assert package.__file__ is not None
        package_root = Path(package.__file__).parent
        imports = {imported for path in package_root.rglob("*.py") for imported in _imports(path)}
        assert not any(name == "arch_web" or name.startswith("arch_web.") for name in imports)


@pytest.mark.architecture
def test_no_forbidden_framework_or_delivery_modules_exist() -> None:
    names = {path.stem for path in SOURCE.rglob("*.py")}
    assert names.isdisjoint({"agents", "cli", "deployment", "generator", "github", "http"})
