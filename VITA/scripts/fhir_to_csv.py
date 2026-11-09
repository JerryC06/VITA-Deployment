"""Extract the 11 clinical features from FHIR Bundles and write CSV rows.

This is the inverse of `csv_to_fhir.py` and the reference implementation of the
Task 10 parser: the output has the same 12 columns as the source dataset, so the
round trip can be checked with a plain diff.

    python scripts/fhir_to_csv.py build/bundles --out build/roundtrip.csv
    python scripts/fhir_to_csv.py fhir/examples/Bundle-vita-0001.json

Missing values are written as empty cells, not as 0: the sentinel 0 in the
source data is not a clinical value, so the CSV round trip intentionally does
not restore it (see design document §9).
"""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vita_mapping import extract_features, extract_label, features, load_spec  # noqa: E402


def bundle_to_row(bundle: dict, spec: dict | None = None) -> dict[str, str]:
    """Return one CSV row (dataset columns + label) for one Bundle."""
    spec = spec or load_spec()
    values = extract_features(bundle, spec)
    row: dict[str, str] = {}
    for feature in features(spec):
        value = values.get(feature["column"])
        if value is None:
            row[feature["column"]] = ""
        elif feature["fromFhir"].get("round") is not None:
            # keep the dataset's decimal precision (e.g. Oldpeak -1.0)
            row[feature["column"]] = f"{float(value):.{feature['fromFhir']['round']}f}"
        else:
            row[feature["column"]] = str(value)
    row[spec["label"]["column"]] = str(extract_label(bundle, spec))
    return row


def _bundle_paths(targets: list[pathlib.Path]) -> list[pathlib.Path]:
    paths: list[pathlib.Path] = []
    for target in targets:
        if target.is_dir():
            paths.extend(sorted(target.glob("Bundle-*.json")))
        else:
            paths.append(target)
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="+", type=pathlib.Path, help="Bundle files or a directory")
    parser.add_argument("--out", type=pathlib.Path, help="write CSV here instead of stdout")
    args = parser.parse_args()

    spec = load_spec()
    paths = _bundle_paths(args.bundles)
    if not paths:
        print("error: no Bundle-*.json files found", file=sys.stderr)
        return 2

    columns = [f["column"] for f in features(spec)] + [spec["label"]["column"]]
    rows = [bundle_to_row(json.loads(path.read_text(encoding="utf-8")), spec) for path in paths]

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=columns, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        print(f"wrote {len(rows)} row(s) -> {args.out}")
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
