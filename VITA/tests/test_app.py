"""Smoke tests for the Streamlit demo (run the script headlessly)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402


def _button(app, label: str):
    return next(button for button in app.button if button.label == label)


def test_demo_app_loads_and_predicts():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    assert not app.exception

    _button(app, "Generate FHIR Bundle and predict").click().run()
    assert not app.exception
    assert not list(app.error)
    assert len(app.metric) == 1
    assert app.metric[0].label == "Heart disease probability"
    assert app.metric[0].value.endswith("%")


def test_sample_prediction_button():
    app = AppTest.from_file(str(ROOT / "app" / "streamlit_app.py"), default_timeout=60).run()
    _button(app, "Predict sample now").click().run()
    assert not app.exception
    assert len(app.metric) == 1
    assert 0.0 <= float(app.metric[0].value.rstrip("%")) <= 100.0
