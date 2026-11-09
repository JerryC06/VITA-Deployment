"""Pytest tests for the VITA FHIR feature mapping.

Run from the repository root:

    python -m pytest tests -q
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from build_examples import expected_vector  # noqa: E402
from vita_mapping import (  # noqa: E402
    build_bundle,
    compare_expected,
    extract_features,
    extract_label,
    features,
    load_spec,
    validate_bundle,
)

SPEC = load_spec()
ROWS = list(csv.DictReader(open(ROOT / "data" / "sample_rows.csv", newline="", encoding="utf-8")))


def _patient_id(index: int) -> str:
    return f"{SPEC['bundleConventions']['patientIdPrefix']}{index + 1:04d}"


def test_spec_covers_eleven_features():
    assert len(features(SPEC)) == 11
    assert [f["column"] for f in features(SPEC)] == [
        "Age",
        "Sex",
        "ChestPainType",
        "RestingBP",
        "Cholesterol",
        "FastingBS",
        "RestingECG",
        "MaxHR",
        "ExerciseAngina",
        "Oldpeak",
        "ST_Slope",
    ]


@pytest.mark.parametrize("index", range(len(ROWS)))
def test_csv_to_fhir_to_features_is_lossless(index):
    row = ROWS[index]
    bundle = build_bundle(row, _patient_id(index), SPEC)
    assert validate_bundle(bundle, SPEC) == []
    assert compare_expected(extract_features(bundle, SPEC), expected_vector(row, SPEC)) == []
    assert extract_label(bundle, SPEC) == int(row["HeartDisease"])


@pytest.mark.parametrize("index", range(len(ROWS)))
def test_committed_example_bundles_are_valid(index):
    patient_id = _patient_id(index)
    path = ROOT / "fhir" / "examples" / f"Bundle-{patient_id.lower()}.json"
    bundle = json.loads(path.read_text(encoding="utf-8"))
    assert validate_bundle(bundle, SPEC) == []
    assert compare_expected(extract_features(bundle, SPEC), expected_vector(ROWS[index], SPEC)) == []


def test_missing_values_use_data_absent_reason():
    bundle = build_bundle(ROWS[1], "VITA-0002", SPEC)
    for observation in (e["resource"] for e in bundle["entry"]):
        if observation["id"].endswith(("-bp", "-cholesterol")):
            assert "valueQuantity" not in observation
            assert observation["dataAbsentReason"]["coding"][0]["code"] == "unknown"


def test_oldpeak_uses_millivolts_and_keeps_sign():
    bundle = build_bundle(ROWS[1], "VITA-0002", SPEC)
    obs = next(e["resource"] for e in bundle["entry"] if e["resource"]["id"].endswith("st-deviation"))
    assert obs["valueQuantity"] == {"value": -0.1, "unit": "mV", "system": "http://unitsofmeasure.org", "code": "mV"}
    assert extract_features(bundle, SPEC)["Oldpeak"] == -1


def test_fasting_bs_uses_comparator_not_a_glucose_result():
    high = build_bundle(ROWS[0], "VITA-0001", SPEC)
    normal = build_bundle(ROWS[1], "VITA-0002", SPEC)
    high_obs = next(e["resource"] for e in high["entry"] if e["resource"]["id"].endswith("fasting-glucose"))
    normal_obs = next(e["resource"] for e in normal["entry"] if e["resource"]["id"].endswith("fasting-glucose"))
    assert high_obs["valueQuantity"]["value"] == 120
    assert high_obs["valueQuantity"]["comparator"] == ">"
    assert high_obs["interpretation"][0]["coding"][0]["code"] == "H"
    assert normal_obs["valueQuantity"]["comparator"] == "<="
    assert normal_obs["interpretation"][0]["coding"][0]["code"] == "N"


def test_label_uses_condition_presence():
    positive = build_bundle(ROWS[0], "VITA-0001", SPEC)
    negative = build_bundle(ROWS[1], "VITA-0002", SPEC)
    assert any(e["resource"]["resourceType"] == "Condition" for e in positive["entry"])
    assert not any(e["resource"]["resourceType"] == "Condition" for e in negative["entry"])


def test_out_of_range_value_is_rejected():
    row = dict(ROWS[0])
    row["RestingBP"] = "400"
    problems = validate_bundle(build_bundle(row, "VITA-0001", SPEC), SPEC)
    assert any("RestingBP" in problem and "outside" in problem for problem in problems)


def test_missing_observation_is_detected():
    bundle = build_bundle(ROWS[0], "VITA-0001", SPEC)
    bundle["entry"] = [e for e in bundle["entry"] if not e["resource"]["id"].endswith("-st-slope")]
    problems = validate_bundle(bundle, SPEC)
    assert any("ST_Slope" in problem and "missing" in problem for problem in problems)


def test_sex_accepts_numeric_encoding():
    row = dict(ROWS[0])
    row["Sex"] = "1"
    bundle = build_bundle(row, "VITA-0009", SPEC)
    patient = next(e["resource"] for e in bundle["entry"] if e["resource"]["resourceType"] == "Patient")
    assert patient["gender"] == "male"
    assert extract_features(bundle, SPEC)["Sex"] == "M"


def test_every_mapping_code_appears_in_the_verification_report():
    report = json.loads((ROOT / "mappings" / "terminology-verification.json").read_text(encoding="utf-8"))
    entries = {(e["system"], e["code"]) for e in report["entries"]}
    assert report["summary"]["failed"] == 0
    for feature in features(SPEC):
        fhir = feature["fhir"]
        if fhir["resource"] == "Observation":
            assert (fhir["code"]["system"], fhir["code"]["code"]) in entries
        for mapped in feature["toFhir"].get("map", {}).values():
            if isinstance(mapped, dict) and "system" in mapped and "vita.example.org" not in mapped["system"]:
                assert (mapped["system"], mapped["code"]) in entries
    label = SPEC["label"]["fhir"]["code"]
    assert (label["system"], label["code"]) in entries


def test_csv_to_fhir_and_back_cli_roundtrip(tmp_path):
    from csv_to_fhir import convert_file
    from fhir_to_csv import bundle_to_row

    paths = convert_file(ROOT / "data" / "sample_rows.csv", tmp_path, spec=SPEC)
    assert len(paths) == 3
    rows = [bundle_to_row(json.loads(path.read_text(encoding="utf-8")), SPEC) for path in paths]
    assert rows[0]["Age"] == "54" and rows[0]["Oldpeak"] == "2.3" and rows[0]["Sex"] == "M"
    assert rows[1]["RestingBP"] == "" and rows[1]["Cholesterol"] == ""
    assert rows[1]["Oldpeak"] == "-1.0"
    assert rows[2]["Sex"] == "M"  # source value was 1
    assert [row["HeartDisease"] for row in rows] == ["1", "0", "1"]
