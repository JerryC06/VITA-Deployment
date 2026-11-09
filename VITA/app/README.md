# Demo application

The demo turns form values into a FHIR R4 `Bundle`, extracts the 11 clinical features and
scores the record with the trained Scikit-learn pipeline.

```text
Streamlit form
   │  form_to_bundle()          app/fhir_generator.py
   ▼
FHIR Bundle (Patient + 9 Observations)
   │  bundle_to_features()      app/fhir_parser.py
   │  bundle_to_model_input()   → one-row DataFrame, canonical column order
   ▼
Scikit-learn pipeline            app/model.py  (models/vita_heart_model.joblib)
   │
   ▼
probability + label              app/streamlit_app.py
```

## Files

| File | Purpose |
| --- | --- |
| `fhir_generator.py` | Validates and normalizes form values (numbers, ranges, allowed tokens) and builds the Bundle; also runnable as a script to print an example Bundle |
| `fhir_parser.py` | Bundle → feature dict / 11-value list / model DataFrame; missing BP or cholesterol becomes `0` (the training pipeline's missing marker) |
| `model.py` | Loads the joblib pipeline and returns probability, label and the model input row |
| `streamlit_app.py` | The dashboard: form tab, **FHIR Bundle upload tab**, prediction card, feature table, Bundle JSON download |

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
streamlit run app/streamlit_app.py
```

The model is committed at `models/vita_heart_model.joblib`; if it is missing, train it with
`python ml/train.py` (the dataset is at `data/heart.csv`).

## Input rules

| Field | Type | Allowed |
| --- | --- | --- |
| `Age` | integer | 18–120 |
| `Sex` | token | `M`, `F` |
| `ChestPainType` | token | `TA`, `ATA`, `NAP`, `ASY` |
| `RestingBP` | integer (mmHg) | 0–300; `0` = missing |
| `Cholesterol` | integer (mg/dL) | 0–600; `0` = missing |
| `FastingBS` | integer | 0, 1 |
| `RestingECG` | token | `Normal`, `ST`, `LVH` |
| `MaxHR` | integer (beats/min) | 30–250 |
| `ExerciseAngina` | token | `Y`, `N` |
| `Oldpeak` | float (mm) | −3.0–7.0 |
| `ST_Slope` | token | `Up`, `Flat`, `Down` |

Invalid values raise `FormError` and are shown as a UI error instead of producing a
malformed Bundle.

## Input paths

1. **Form tab** — the 11 fields with validation (see the table below); the Bundle is generated
   from the values.
2. **Upload FHIR Bundle tab** — any Bundle that follows the mapping (one `Patient` + the 9
   Observations) is parsed and scored; an example Bundle can be downloaded from the same tab.

Both paths end in `predict_bundle()` and the same result view.

## Verification

`tests/test_pipeline.py` covers form → Bundle → features → model input, including string
widget values and the `0` sentinel; `tests/test_app.py` drives the Streamlit script
headlessly. The underlying converter and parser were also checked on all 918 dataset rows
with no mismatches.

## Notes

- The form-generated Bundle has no `Condition` (the heart-disease label is unknown at
  prediction time); the parser ignores the label.
- `RestingBP` / `Cholesterol` are the only fields that may be missing. Any other missing
  feature raises `ValueError` rather than silently becoming zero.
- The app is a course prototype; do not use it for clinical decisions.
