"""Load the trained Scikit-learn pipeline and score a FHIR Bundle."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.fhir_parser import bundle_to_features, bundle_to_model_input  # noqa: E402

MODEL_PATH = ROOT / "models" / "vita_heart_model.joblib"
DECISION_THRESHOLD = 0.5


class ModelNotReady(RuntimeError):
    """Raised when the trained model artifact is not available."""


@lru_cache(maxsize=1)
def load_model(path: str | Path = MODEL_PATH):
    import joblib

    path = Path(path)
    if not path.exists():
        raise ModelNotReady(
            f"Model artifact not found at {path}. Train it with `python ml/train.py` "
            "(the dataset is in data/heart.csv)."
        )
    return joblib.load(path)


def predict_bundle(bundle: dict[str, Any], model=None) -> dict[str, Any]:
    """Return the feature values, positive-class probability and label."""
    model = model or load_model()
    frame = bundle_to_model_input(bundle)
    probability = float(model.predict_proba(frame)[0, 1])
    return {
        "features": bundle_to_features(bundle),
        "model_input": frame,
        "probability": probability,
        "label": int(probability >= DECISION_THRESHOLD),
        "threshold": DECISION_THRESHOLD,
    }


def predict_summary(bundle: dict[str, Any], model=None) -> dict[str, Any]:
    """JSON-serializable result for an API response (no DataFrame)."""
    result = predict_bundle(bundle, model=model)
    return {
        "probability": round(result["probability"], 4),
        "label": result["label"],
        "threshold": result["threshold"],
        "features": result["features"],
    }
