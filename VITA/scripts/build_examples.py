"""Generate the example FHIR Bundles from `data/sample_rows.csv`.

The examples are not hand-written: they are produced by the reference
implementation so that the committed JSON and the mapping can never disagree.
Run from the repository root:

    python scripts/build_examples.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vita_mapping import build_bundle, canonical_value, features, load_spec  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "sample_rows.csv"
OUT_DIR = ROOT / "fhir" / "examples"

INT_COLUMNS = {"Age", "RestingBP", "Cholesterol", "FastingBS", "MaxHR"}
FLOAT_COLUMNS = {"Oldpeak"}


def expected_vector(row: dict[str, str], spec: dict) -> dict:
    """The feature vector the source CSV row represents, with None for missing values."""
    expected: dict = {}
    for feature in features(spec):
        raw = row[feature["column"]].strip()
        sentinel = feature["toFhir"].get("sentinel")
        if sentinel and float(raw) == float(sentinel["value"]):
            expected[feature["column"]] = None
        elif feature["column"] in INT_COLUMNS:
            expected[feature["column"]] = int(raw)
        elif feature["column"] in FLOAT_COLUMNS:
            value = float(raw)
            expected[feature["column"]] = int(value) if value.is_integer() else value
        else:
            expected[feature["column"]] = canonical_value(feature, raw)
    return expected


def main() -> int:
    spec = load_spec()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    with open(CSV_PATH, newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))

    for index, row in enumerate(rows):
        patient_id = f"{spec['bundleConventions']['patientIdPrefix']}{index + 1:04d}"
        bundle = build_bundle(row, patient_id, spec)
        path = OUT_DIR / f"Bundle-{patient_id.lower()}.json"
        path.write_text(json.dumps(bundle, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        records.append(
            {
                "patientId": patient_id,
                "bundleFile": path.name,
                "sourceRow": row,
                "expectedFeatures": expected_vector(row, spec),
                "label": int(row[spec["label"]["column"]]),
            }
        )
        print(f"wrote {path.relative_to(ROOT)}")

    manifest = {
        "generatedBy": "scripts/build_examples.py",
        "specVersion": spec["version"],
        "referenceDate": spec["bundleConventions"]["referenceDate"],
        "records": records,
    }
    manifest_path = OUT_DIR / "expected-features.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
