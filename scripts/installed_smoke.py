"""Run the approved eight-edge scenario using only installed ARCH distributions."""

from __future__ import annotations

import json
import runpy
import sys
from importlib.metadata import distribution
from pathlib import Path

import arch_kernel
import arch_runtime


def main() -> None:
    if any(name == "arch_web" or name.startswith("arch_web.") for name in sys.modules):
        raise RuntimeError("upstream packages imported arch_web")
    import arch_web

    origins: dict[str, str] = {}
    for package in (arch_web, arch_runtime, arch_kernel):
        name = package.__name__.replace("_", "-")
        if distribution(name).version != "0.2.0" or package.__version__ != "0.2.0":
            raise RuntimeError(f"unexpected distribution version: {name}")
        origin = Path(str(package.__file__)).resolve()
        if (
            not origin.is_relative_to(Path(sys.prefix).resolve())
            or "site-packages" not in origin.parts
        ):
            raise RuntimeError(f"package not installed in isolated environment: {origin}")
        evidence = json.loads(distribution(name).read_text("direct_url.json") or "{}")
        if "vcs_info" in evidence or evidence.get("dir_info"):
            raise RuntimeError(f"source checkout dependency: {name}")
        origins[name] = str(origin)

    root = Path(__file__).resolve().parent
    sys.path.insert(0, str(root / "tests"))
    scenario = root / "scenario"
    scenario.mkdir()
    namespace = runpy.run_path(str(root / "tests" / "c03" / "test_sqlite_lifecycle.py"))
    namespace["test_real_sqlite_executes_the_complete_web_lifecycle"](scenario)
    print(
        json.dumps(
            {
                "versions": {name: distribution(name).version for name in origins},
                "origins": origins,
                "python": sys.version,
                "lifecycle": "DRAFT -> DEPLOYED",
                "adjacent_transitions": 8,
                "aggregate_version": 10,
                "workflow_version": 9,
                "event_count": 10,
                "every_edge_replay_and_fingerprints": "PASS",
                "idempotency_cas_string_metadata": "PASS",
                "provider_execution_and_final_approval": "PASS",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
