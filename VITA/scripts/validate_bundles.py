"""Validate the VITA FHIR mapping end to end.

Checks performed
1. The committed example Bundles match the mapping's structural rules
   (status, category, codes, UCUM units, subject references, unique ids).
2. CSV -> FHIR -> feature vector round-trips exactly, including missing values
   (sentinel 0 -> dataAbsentReason -> None) and the Oldpeak mm -> mV conversion.
3. The committed `expected-features.json` agrees with the source CSV.

Usage (from the repository root):

    python scripts/validate_bundles.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_examples import expected_vector  # noqa: E402
from vita_mapping import (  # noqa: E402
    SPEC_PATH,
    build_bundle,
    compare_expected,
    extract_features,
    extract_label,
    features,
    load_spec,
    validate_bundle,
)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "sample_rows.csv"
EXAMPLES_DIR = ROOT / "fhir" / "examples"
MANIFEST_PATH = EXAMPLES_DIR / "expected-features.json"


def check_spec(spec: dict) -> list[str]:
    problems: list[str] = []
    columns = [f["column"] for f in spec["features"]]
    if len(columns) != 11:
        problems.append(f"expected 11 feature mappings, found {len(columns)}")
    if len(set(columns)) != len(columns):
        problems.append("duplicate feature columns in the mapping")
    for feature in features(spec):
        fhir = feature["fhir"]
        if fhir["resource"] == "Observation":
            if not fhir.get("code", {}).get("system") or not fhir.get("code", {}).get("code"):
                problems.append(f"{feature['column']}: missing code system/code")
            if not fhir.get("category"):
                problems.append(f"{feature['column']}: missing category")
            if fhir["valueType"] == "Quantity" and not fhir.get("unit", {}).get("code"):
                problems.append(f"{feature['column']}: Quantity without UCUM unit")
        if "fromFhir" not in feature or "toFhir" not in feature:
            problems.append(f"{feature['column']}: missing toFhir/fromFhir rule")
    return problems


def format_vector(values: dict) -> str:
    return ", ".join(f"{key}={values[key]!r}" for key in values)


def main() -> int:
    spec = load_spec()
    rows = list(csv.DictReader(open(CSV_PATH, newline="", encoding="utf-8")))
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    failures = 0
    checks = 0

    print(f"Mapping spec : {SPEC_PATH.relative_to(ROOT)} (v{spec['version']}, FHIR {spec['fhirVersion']})")
    print(f"Sample rows  : {CSV_PATH.relative_to(ROOT)} ({len(rows)} synthetic records)")
    print(f"Examples     : {EXAMPLES_DIR.relative_to(ROOT)}")
    print()

    spec_problems = check_spec(spec)
    checks += 1
    if spec_problems:
        failures += 1
        print("[FAIL] mapping spec")
        for problem in spec_problems:
            print(f"       - {problem}")
    else:
        print("[PASS] mapping spec: 11 unique feature mappings, codes and units present")

    for index, row in enumerate(rows):
        patient_id = f"{spec['bundleConventions']['patientIdPrefix']}{index + 1:04d}"
        expected = expected_vector(row, spec)

        # 1. CSV -> FHIR (in memory) -> features
        bundle = build_bundle(row, patient_id, spec)
        problems = validate_bundle(bundle, spec)
        extracted = extract_features(bundle, spec)
        problems += compare_expected(extracted, expected)
        label = extract_label(bundle, spec)
        if label != int(row[spec["label"]["column"]]):
            problems.append(f"label: expected {row[spec['label']['column']]}, got {label}")
        checks += 1
        if problems:
            failures += 1
            print(f"[FAIL] {patient_id} in-memory round trip")
            for problem in problems:
                print(f"       - {problem}")
        else:
            print(f"[PASS] {patient_id} in-memory round trip (label={label})")
            print(f"       {format_vector(extracted)}")

        # 2. Committed JSON file -> features
        bundle_path = EXAMPLES_DIR / f"Bundle-{patient_id.lower()}.json"
        checks += 1
        if not bundle_path.exists():
            failures += 1
            print(f"[FAIL] {bundle_path.relative_to(ROOT)} is missing")
            continue
        file_bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        file_problems = validate_bundle(file_bundle, spec) + compare_expected(
            extract_features(file_bundle, spec), expected
        )
        if extract_label(file_bundle, spec) != int(row[spec["label"]["column"]]):
            file_problems.append("label does not match the source row")
        if file_problems:
            failures += 1
            print(f"[FAIL] {bundle_path.relative_to(ROOT)}")
            for problem in file_problems:
                print(f"       - {problem}")
        else:
            print(f"[PASS] {bundle_path.relative_to(ROOT)} matches the source row")

        # 3. Committed expected-features.json agrees with the CSV
        checks += 1
        record = next((r for r in manifest["records"] if r["patientId"] == patient_id), None)
        if record is None:
            failures += 1
            print(f"[FAIL] {patient_id} missing from expected-features.json")
        elif record["expectedFeatures"] != expected or record["label"] != int(row[spec["label"]["column"]]):
            failures += 1
            print(f"[FAIL] {patient_id} expected-features.json disagrees with the CSV")
        else:
            print(f"[PASS] {patient_id} expected-features.json agrees with the CSV")
        print()

    print(f"{checks - failures}/{checks} checks passed")
    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS - mapping is lossless for the sample records, including missing values")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
