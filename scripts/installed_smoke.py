"""Exercise installed ARCH Web, Runtime, and Kernel distributions in isolation."""

from __future__ import annotations

import json
import sys
from importlib.metadata import distribution
from pathlib import Path

import arch_kernel
import arch_runtime
from arch_kernel.contracts import Route
from arch_runtime import CreateProjectCommand, Runtime, RuntimeConfig


def _is_inside(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _verify_tag_source(package: str, tag_object: str) -> None:
    direct_url = distribution(package).read_text("direct_url.json")
    if direct_url is None:
        raise RuntimeError(f"{package} has no direct release-source evidence")
    evidence = json.loads(direct_url)
    vcs_info = evidence.get("vcs_info", {})
    if vcs_info.get("requested_revision") != "v0.1.0":
        raise RuntimeError(f"{package} was not installed from the v0.1.0 tag")
    if vcs_info.get("commit_id") != tag_object:
        raise RuntimeError(
            f"{package} tag object is {vcs_info.get('commit_id')!r}, expected {tag_object!r}"
        )


def main(database: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    if any(name == "arch_web" or name.startswith("arch_web.") for name in sys.modules):
        raise RuntimeError("Runtime or Kernel imported arch_web before the public web import")

    import arch_web
    from arch_web import ArchitectureChoice, WebStackProfile, decode_contract

    if arch_web.__version__ != "0.1.0":
        raise RuntimeError(f"unexpected arch-web version: {arch_web.__version__}")
    if arch_runtime.__version__ != "0.1.0":
        raise RuntimeError(f"unexpected arch-runtime version: {arch_runtime.__version__}")
    if arch_kernel.__version__ != "0.1.0":
        raise RuntimeError(f"unexpected arch-kernel version: {arch_kernel.__version__}")
    _verify_tag_source("arch-runtime", "16e2426e61a19bf695f36f01b94a93f8b0276e18")
    _verify_tag_source("arch-kernel", "08b9c9bd57d90ee12a6b40e350431ca1c3bb8bc0")

    for package in (arch_web, arch_runtime, arch_kernel):
        origin = Path(str(package.__file__)).resolve()
        if _is_inside(origin, repository):
            raise RuntimeError(f"package imported from checkout: {origin}")
    if any(_is_inside(Path(entry), repository) for entry in sys.path if entry):
        raise RuntimeError("repository checkout leaked onto sys.path")

    stack = WebStackProfile(
        contract_version="0.1.0",
        profile_id="installed-smoke",
        language="python",
        frontend_framework=ArchitectureChoice.UNSPECIFIED,
        rendering_mode=ArchitectureChoice.UNSPECIFIED,
        package_manager=ArchitectureChoice.UNSPECIFIED,
        backend_model=ArchitectureChoice.NONE,
        database_provider=ArchitectureChoice.NONE,
        auth_provider=ArchitectureChoice.NONE,
        unit_test_runner=ArchitectureChoice.UNSPECIFIED,
        e2e_test_runner=ArchitectureChoice.UNSPECIFIED,
        deployment_target=ArchitectureChoice.UNSPECIFIED,
        runtime_requirement=ArchitectureChoice.UNSPECIFIED,
        constraints=("installed-distributions-only",),
    )
    if decode_contract(WebStackProfile, stack.canonical_bytes()) != stack:
        raise RuntimeError("canonical contract round trip failed")

    command = CreateProjectCommand.model_validate(
        {
            "idempotency_key": "release:web-smoke:create",
            "name": "ARCH Web Installed Integration",
            "slug": "arch-web-installed-integration",
            "summary": "Verify ARCH Web with the released Runtime and Kernel chain.",
            "owner": "release-team",
            "project_type": "web",
            "criticality": "medium",
            "default_route": Route.QUICK,
            "objectives": ("Verify installed release compatibility.",),
            "constraints": ("Use public imports only.",),
            "success_criteria": ("Persist and reload Runtime evidence.",),
            "actor_id": "release:arch-web-smoke",
        },
        strict=True,
    )
    with Runtime.open(RuntimeConfig(database, initialize_schema=True)) as runtime:
        created = runtime.create_project(command)
        loaded = runtime.get_project(created.project_id)
    if loaded.record_version != 1:
        raise RuntimeError("Runtime integration returned an unexpected aggregate version")
    print(
        arch_web.__version__, arch_runtime.__version__, arch_kernel.__version__, created.project_id
    )


if __name__ == "__main__":
    main(Path(sys.argv[1]))
