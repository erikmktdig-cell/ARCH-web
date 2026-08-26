"""Generate final external release evidence after the exact commit is known."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.release_tools import inspect_artifacts, release_manifest, sha256, write_json


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
    args = parser.parse_args()
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
    )
    write_json(args.output, manifest)
    print(f"{sha256(args.output)}  {args.output.name}")


if __name__ == "__main__":
    main()
