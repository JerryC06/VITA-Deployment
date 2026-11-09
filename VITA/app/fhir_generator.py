"""Turn demo form values into a FHIR R4 Bundle.

The form is the only place where user input enters the system. This module
normalizes the values (numeric strings, ranges, categorical tokens), maps them to
the 11 dataset columns and delegates Bundle construction to
`scripts/vita_mapping.build_bundle`, so the demo and the offline converter share
exactly one implementation of the mapping.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:  # allow `python app/streamlit_app.py` and tests
    sys.path.insert(0, str(ROOT))

from scripts.vita_mapping import build_bundle, load_spec  # noqa: E402

SPEC = load_spec()

SEX = ("M", "F")
CHEST_PAIN = ("TA", "ATA", "NAP", "ASY")
RESTING_ECG = ("Normal", "ST", "LVH")
ST_SLOPE = ("Up", "Flat", "Down")
YES_NO = ("Y", "N")


class FormError(ValueError):
    """Raised when a form value cannot be converted into a valid Bundle."""


def _number(name: str, value: Any, low: float, high: float) -> float:
    try:
        number = float(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise FormError(f"{name} must be a number, got {value!r}") from exc
    if not (low <= number <= high):
        raise FormError(f"{name} must be between {low:g} and {high:g}, got {number:g}")
    return number


def _integer(name: str, value: Any, low: int, high: int) -> int:
    number = _number(name, value, low, high)
    if not number.is_integer():
        raise FormError(f"{name} must be a whole number, got {number:g}")
    return int(number)


def _choice(name: str, value: Any, allowed: tuple[str, ...]) -> str:
    text = str(value).strip()
    if text not in allowed:
        raise FormError(f"{name} must be one of {', '.join(allowed)}, got {text!r}")
    return text


def normalize_form(form: dict[str, Any]) -> dict[str, str]:
    """Validate form values and return a dataset row (all values as strings)."""
    row = {
        "Age": str(_integer("Age", form.get("Age"), 18, 120)),
        "Sex": _choice("Sex", form.get("Sex"), SEX),
        "ChestPainType": _choice("ChestPainType", form.get("ChestPainType"), CHEST_PAIN),
        # 0 is the dataset's missing-value sentinel for BP and cholesterol.
        "RestingBP": str(_integer("RestingBP", form.get("RestingBP"), 0, 300)),
        "Cholesterol": str(_integer("Cholesterol", form.get("Cholesterol"), 0, 600)),
        "FastingBS": str(_integer("FastingBS", form.get("FastingBS"), 0, 1)),
        "RestingECG": _choice("RestingECG", form.get("RestingECG"), RESTING_ECG),
        "MaxHR": str(_integer("MaxHR", form.get("MaxHR"), 30, 250)),
        "ExerciseAngina": _choice("ExerciseAngina", form.get("ExerciseAngina"), YES_NO),
        "Oldpeak": f"{_number('Oldpeak', form.get('Oldpeak'), -3.0, 7.0):.1f}",
        "ST_Slope": _choice("ST_Slope", form.get("ST_Slope"), ST_SLOPE),
    }
    return row


def form_to_bundle(form: dict[str, Any], patient_id: str = "VITA-DEMO-0001") -> dict:
    """Build a complete FHIR Bundle (Patient + 9 Observations) from form values."""
    row = normalize_form(form)
    return build_bundle(row, patient_id, SPEC)


if __name__ == "__main__":
    import json

    demo = {
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
    print(json.dumps(form_to_bundle(demo), indent=2))
