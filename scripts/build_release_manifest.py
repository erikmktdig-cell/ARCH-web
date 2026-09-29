"""Generate final external release evidence after the exact commit is known."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_tools import ROOT, inspect_artifacts, release_manifest, sha256, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tests", type=int, required=True)
    parser.add_argument("--skips", type=int, required=True)
    parser.add_argument("--coverage", type=float, required=True)
    parser.add_argument("--dist", type=Path, default=Path("dist"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--clean-install", type=json.loads, required=True)
    parser.add_argument("--hosted-ci", type=json.loads, required=True)
    parser.add_argument("--security-audit", required=True)
    parser.add_argument("--governance", type=json.loads, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
    if head != args.commit or dirty:
        raise SystemExit("manifest requires the exact clean final commit")
    evidence = json.loads(args.evidence.read_text(encoding="utf-8"))
    required = {
        "quality_gates",
        "released_dependencies",
        "workflow_integration",
        "reproducibility",
        "known_limitations",
    }
    if not isinstance(evidence, dict) or not required <= evidence.keys():
        raise SystemExit("missing explicit release evidence")
    manifest = release_manifest(
        final_commit=args.commit,
        tests=args.tests,
        skips=args.skips,
        branch_coverage=args.coverage,
        artifacts=inspect_artifacts(args.dist),
        clean_install=args.clean_install,
        hosted_ci=args.hosted_ci,
        security_audit=args.security_audit,
        governance=args.governance,
        quality_gates=evidence.pop("quality_gates"),
    )
    if evidence.keys() & manifest.keys():
        raise SystemExit("evidence cannot override release identity")
    manifest.update(evidence)
    write_json(args.output, manifest)
    print(f"{sha256(args.output)}  {args.output.name}")


if __name__ == "__main__":
    main()
