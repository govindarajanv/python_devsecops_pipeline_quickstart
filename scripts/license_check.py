#!/usr/bin/env python3
"""Enforce an allowlist of approved license families for production dependencies.

Reads the CSV produced by ``pip-licenses`` and fails if any package uses a
license that is not in an approved family. Used by the GitHub Actions license
check stage to gate the pipeline.

The CSV header uses ``Name`` / ``Version`` / ``License`` (pip-licenses).
"""

from __future__ import annotations

import csv
import sys

# Approved license families (case-insensitive, substring matching against a
# normalized license string). SPDX identifiers and pip-licenses variants are
# both handled by normalization.
APPROVED_FAMILIES = (
    "mit",
    "bsd",
    "apache",
    "psf",
    "python software foundation",
    "isc",
    "mpl",
    "lgpl",
    "lesser general public",
)

CSV_PATH = sys.argv[1] if len(sys.argv) > 1 else "licenses.csv"


def normalize(license_name: str) -> str:
    """Lower-case and strip common suffixes/artifacts from a license string."""
    return (
        license_name.lower()
        .replace("(iscl)", "")
        .replace("(lgplv2+)", "")
        .replace("license", "")
        .strip()
    )


def is_approved(license_name: str) -> bool:
    normalized = normalize(license_name)
    return any(family in normalized for family in APPROVED_FAMILIES)


def main() -> int:
    violations: list[tuple[str, str]] = []
    unknown: list[tuple[str, str]] = []

    with open(CSV_PATH, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            name = row.get("Name", row.get("name", "unknown"))
            license_name = row.get("License", row.get("license", ""))
            if not license_name or license_name in ("UNKNOWN", "N/A", "UNLICENSED"):
                unknown.append((name, license_name))
            elif not is_approved(license_name):
                violations.append((name, license_name))

    failed = False
    if violations:
        print("BLOCKED: packages with disallowed licenses:", file=sys.stderr)
        for name, license_name in sorted(violations):
            print(f"  - {name}: {license_name}", file=sys.stderr)
        failed = True

    if unknown:
        print("WARNING: packages with unknown licenses (review manually):", file=sys.stderr)
        for name, license_name in sorted(unknown):
            print(f"  - {name}: {license_name}", file=sys.stderr)

    if failed:
        return 1
    print("License check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
