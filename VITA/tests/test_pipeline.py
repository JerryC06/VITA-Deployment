"""End-to-end tests: form -> FHIR Bundle -> features -> model input."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pd = pytest.importorskip("pandas")

from app.fhir_generator import FormError, form_to_bundle, normalize_form  # noqa: E402
from app.fhir_parser import (  # noqa: E402
    FEATURE_ORDER,
    bundle_to_feature_list,
    bundle_to_features,
    bundle_to_model_input,
)

FORM = {
    "Age": 54,
    "Sex": "M",
    "ChestPainType": "TA",
    "RestingBP": 140,
    "Cholesterol": 260,
    "FastingBS": 1,
    "RestingECG": "ST",
    "MaxHR": 150,
    "ExerciseAngina": "Y",
    "Oldpeak": 2.3,
    "ST_Slope": "Flat",
}


def test_form_builds_bundle_with_expected_resources():
    bundle = form_to_bundle(FORM)
    assert bundle["resourceType"] == "Bundle"
    kinds = [entry["resource"]["resourceType"] for entry in bundle["entry"]]
    assert kinds.count("Patient") == 1
    assert kinds.count("Observation") == 9
    assert kinds.count("Condition") == 0  # a form has no heart-disease label


def test_feature_roundtrip():
    bundle = form_to_bundle(FORM)
    features = bundle_to_features(bundle)
    for column in FEATURE_ORDER:
        expected = FORM[column]
        if isinstance(expected, float):
            assert features[column] == pytest.approx(expected)
        else:
            assert features[column] == expected


def test_model_input_columns_order_and_types():
    frame = bundle_to_model_input(form_to_bundle(FORM))
    assert list(frame.columns) == FEATURE_ORDER
    row = frame.iloc[0]
    assert int(row["Age"]) == 54
    assert str(row["Sex"]) == "M"
    assert float(row["Oldpeak"]) == pytest.approx(2.3)
    assert int(row["FastingBS"]) == 1


def test_missing_bp_and_cholesterol_become_zero_for_the_model():
    form = dict(FORM, RestingBP=0, Cholesterol=0)
    bundle = form_to_bundle(form)
    features = bundle_to_features(bundle)
    assert features["RestingBP"] is None and features["Cholesterol"] is None
    frame = bundle_to_model_input(bundle)
    assert int(frame.iloc[0]["RestingBP"]) == 0
    assert int(frame.iloc[0]["Cholesterol"]) == 0


def test_string_widget_values_are_coerced():
    form = {key: str(value) for key, value in FORM.items()}
    form["Oldpeak"] = "2.3"
    bundle = form_to_bundle(form)
    assert bundle_to_features(bundle)["Age"] == 54


def test_feature_list_has_eleven_values():
    values = bundle_to_feature_list(form_to_bundle(FORM))
    assert len(values) == 11
    assert values[0] == 54 and values[1] == "M"


@pytest.mark.parametrize("field,value", [("Age", 10), ("Sex", "X"), ("ST_Slope", "Sideways"), ("Oldpeak", 99)])
def test_invalid_form_values_are_rejected(field, value):
    with pytest.raises(FormError):
        form_to_bundle(dict(FORM, **{field: value}))


def test_model_scores_the_demo_record_when_artifact_exists():
    pytest.importorskip("sklearn")
    from app.model import MODEL_PATH, predict_bundle

    if not MODEL_PATH.exists():
        pytest.skip("model artifact not trained yet")
    result = predict_bundle(form_to_bundle(FORM))
    assert 0.0 <= result["probability"] <= 1.0
    assert result["label"] in (0, 1)


def test_predict_summary_is_json_serializable_when_model_exists():
    import json

    pytest.importorskip("sklearn")
    from app.model import MODEL_PATH, predict_summary

    if not MODEL_PATH.exists():
        pytest.skip("model artifact not trained yet")
    summary = predict_summary(form_to_bundle(FORM))
    json.dumps(summary)  # must not raise
    assert 0.0 <= summary["probability"] <= 1.0


def test_example_bundle_file_can_be_scored():
    import json

    pytest.importorskip("sklearn")
    from app.model import MODEL_PATH, predict_summary

    if not MODEL_PATH.exists():
        pytest.skip("model artifact not trained yet")
    bundle = json.loads((ROOT / "fhir" / "examples" / "Bundle-vita-0001.json").read_text(encoding="utf-8"))
    summary = predict_summary(bundle)
    assert 0.0 <= summary["probability"] <= 1.0
    assert summary["label"] in (0, 1)
