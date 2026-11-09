"""Convert a CSV of dataset rows into FHIR R4 Bundles.

This is the thin command-line wrapper around `vita_mapping.build_bundle`; it is
the reference implementation of Task 7's converter, limited to what the mapping
needs (no batch progress reporting, no retry, no database).

    python scripts/csv_to_fhir.py data/sample_rows.csv --out build/bundles
    python scripts/csv_to_fhir.py data/raw/heart.csv --out build/bundles --prefix VITA-
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vita_mapping import MappingError, build_bundle, features, load_spec  # noqa: E402


def convert_file(csv_path: pathlib.Path, out_dir: pathlib.Path, prefix: str = "VITA-", spec: dict | None = None) -> list[pathlib.Path]:
    """Convert every row of `csv_path` into a Bundle file; return the written paths."""
    spec = spec or load_spec()
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(csv_path, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise MappingError(f"{csv_path} contains no data rows")

    missing = [f["column"] for f in features(spec) if f["column"] not in rows[0]]
    if missing:
        raise MappingError(f"{csv_path} is missing column(s): {', '.join(missing)}")

    written: list[pathlib.Path] = []
    for index, row in enumerate(rows):
        patient_id = f"{prefix}{index + 1:04d}"
        bundle = build_bundle(row, patient_id, spec)
        path = out_dir / f"Bundle-{patient_id.lower()}.json"
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=pathlib.Path, help="CSV with the 12 dataset columns")
    parser.add_argument("--out", type=pathlib.Path, required=True, help="output directory for Bundles")
    parser.add_argument("--prefix", default="VITA-", help="patient id prefix (default VITA-)")
    args = parser.parse_args()

    try:
        written = convert_file(args.csv, args.out, args.prefix)
    except MappingError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"converted {len(written)} row(s) -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
