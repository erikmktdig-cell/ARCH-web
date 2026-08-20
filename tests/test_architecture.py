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
        "ApproveRequirementsCommand",
        "ApproveRequirementsResult",
        "CURRENT_WEB_CONTRACT_VERSION",
        "ContractRef",
        "DesignReference",
        "EvidenceRef",
        "FindingCode",
        "FindingSeverity",
        "ProjectKind",
        "PrepareRequirementsCommand",
        "PrepareRequirementsResult",
        "RequirementAnswer",
        "RequirementCategory",
        "RequirementFinding",
        "RequirementIntake",
        "RequirementPriority",
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
        "approve_requirements",
        "canonical_bytes",
        "contract_fingerprint",
        "decode_contract",
        "encode_contract",
        "prepare_requirements",
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
def test_no_w02_or_framework_modules_exist() -> None:
    names = {path.stem for path in SOURCE.rglob("*.py")}
    assert names.isdisjoint(
        {"agents", "cli", "deployment", "generator", "github", "http", "workflow"}
    )
