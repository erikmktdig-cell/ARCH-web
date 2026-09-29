"""Gate actual branch coverage, independently of combined line/branch coverage."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    totals = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["totals"]
    branches = totals["num_branches"]
    covered = totals["covered_branches"]
    if branches <= 0 or not 0 <= covered <= branches:
        raise SystemExit("Invalid branch coverage evidence")
    percentage = covered / branches * 100
    if percentage < 90:
        raise SystemExit(f"FAIL: actual branch coverage {percentage:.2f}%")
    print(f"PASS: actual branch coverage {percentage:.2f}% ({covered}/{branches})")


if __name__ == "__main__":
    main()
