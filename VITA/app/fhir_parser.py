"""Extract model input from a FHIR R4 Bundle.

The parser is the inverse of `fhir_generator.py`. It returns the 11 feature
values in the canonical order defined by `mappings/vita-feature-mapping.json`
and builds the one-row DataFrame expected by the trained Scikit-learn pipeline.

Missing values (FHIR `dataAbsentReason`) become `None`. For `RestingBP` and
`Cholesterol` the training pipeline treats 0 as "missing", so these two are
converted to 0 here; a missing value in any other feature is an error, not a
silent zero.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.vita_mapping import extract_features, features, load_spec  # noqa: E402

SPEC = load_spec()
FEATURE_ORDER: list[str] = [feature["column"] for feature in features(SPEC)]
MISSING_AS_ZERO = {"RestingBP", "Cholesterol"}
INTEGER_COLUMNS = ("Age", "RestingBP", "Cholesterol", "FastingBS", "MaxHR")
CATEGORICAL_COLUMNS = ("Sex", "ChestPainType", "RestingECG", "ExerciseAngina", "ST_Slope")


def bundle_to_features(bundle: dict[str, Any]) -> dict[str, Any]:
    """Return {column: value} with None for values absent from the Bundle."""
    return extract_features(bundle, SPEC)


def bundle_to_feature_list(bundle: dict[str, Any]) -> list[Any]:
    """Return the 11 values in canonical order, e.g. [54, 'M', 'TA', 140, ...]."""
    values = bundle_to_features(bundle)
    missing = [column for column in FEATURE_ORDER if values.get(column) is None and column not in MISSING_AS_ZERO]
    if missing:
        raise ValueError(f"Bundle is missing required feature(s): {', '.join(missing)}")
    return [0 if values.get(column) is None else values[column] for column in FEATURE_ORDER]


def bundle_to_model_input(bundle: dict[str, Any]) -> pd.DataFrame:
    """Build the one-row DataFrame the trained pipeline expects."""
    values = bundle_to_features(bundle)
    row: dict[str, Any] = {}
    for column in FEATURE_ORDER:
        value = values.get(column)
        if value is None:
            if column in MISSING_AS_ZERO:
                value = 0
            else:
                raise ValueError(f"Bundle is missing required feature: {column}")
        row[column] = value

    frame = pd.DataFrame([row], columns=FEATURE_ORDER)
    for column in INTEGER_COLUMNS:
        frame[column] = frame[column].astype("int64")
    frame["Oldpeak"] = frame["Oldpeak"].astype("float64")
    for column in CATEGORICAL_COLUMNS:
        frame[column] = frame[column].astype("string")
    return frame


def bundle_to_text_row(bundle: dict[str, Any]) -> str:
    """Comma-separated feature row for the dashboard (missing shown as 'missing')."""
    values = bundle_to_features(bundle)
    return ", ".join("missing" if values.get(column) is None else str(values[column]) for column in FEATURE_ORDER)
