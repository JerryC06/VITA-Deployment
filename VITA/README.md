# VITA — FHIR-based Heart Disease Prediction Dashboard

VITA is an educational prototype that predicts the presence of heart disease from
standardized clinical data. A patient record is entered in a form (or uploaded as a FHIR
R4 `Bundle`), converted to FHIR, validated, and reduced to the 11 clinical features used by
a **Scikit-learn** classifier; the probability is shown in a **Streamlit** dashboard. The
project explores how FHIR can make clinical data reusable across systems and how that
standardized data can feed a machine-learning model.

```text
form values  →  FHIR Bundle  →  11 features  →  ML model  →  prediction dashboard
```

VITA is a CS 6440 (Georgia Tech OMS Practicum) course project. It is an educational
prototype, not a medical device, and must not be used for clinical decisions.

## Repository layout

| Path | Contents |
| --- | --- |
| [`docs/`](docs) | Design documentation: [FHIR mapping design](docs/fhir-mapping-design.md), [development environment](docs/environment.md) |
| [`mappings/`](mappings) | The machine-readable [mapping specification](mappings/vita-feature-mapping.json), the review tables ([feature mapping](mappings/vita-feature-mapping.csv), [terminology](mappings/vita-terminology.csv)) and the [terminology verification report](mappings/terminology-verification.json) |
| [`fhir/`](fhir) | FHIR artifacts: two local CodeSystems for the ST-slope terminology gap, and example patient Bundles with their expected feature vectors |
| [`scripts/`](scripts) | Conversion and validation tooling: CSV → FHIR, FHIR → features, example generation, validation, terminology verification ([scripts README](scripts/README.md)) |
| [`ml/`](ml) | Model training: `train.py` (preprocessing pipeline + logistic regression), metrics and instructions ([ML README](ml/README.md)) |
| [`app/`](app) | Demo application: form → FHIR generator, FHIR parser, model loader and the Streamlit UI ([app README](app/README.md)) |
| [`models/`](models) | The trained pipeline used by the demo ([model README](models/README.md)) |
| [`tests/`](tests) | Automated tests for the mapping, the converter and the end-to-end form → prediction pipeline |
| [`data/`](data) | The public Kaggle dataset (`heart.csv`) and synthetic sample records ([data README](data/README.md)) |
| [`.github/`](.github) | Issue / pull-request templates. The CI workflow is kept as `ci.yml.disabled`: the course GitHub Enterprise instance has no runner |

## FHIR data model

One patient record is one `Bundle` (`type = collection`):

```text
Patient      ×1    age (birthDate) and sex (gender)
Observation  ×9    chest pain type, blood pressure, cholesterol, fasting glucose,
                   resting ECG, maximum heart rate, exercise angina, ST deviation, ST slope
Condition    0..1  heart disease label (absent for form-generated records)
```

Each Observation is identified by its `(code.system, code.code)` pair (LOINC or SNOMED CT)
and carries a UCUM unit when it is a measurement. Missing values are encoded with
`dataAbsentReason` instead of a zero. The full mapping is described in
[`docs/fhir-mapping-design.md`](docs/fhir-mapping-design.md).

## Run the demo

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

streamlit run app/streamlit_app.py

# checks
python scripts/validate_bundles.py
python -m pytest tests -q
```

Open the local URL printed by Streamlit. You can either fill in the form and press
**Generate FHIR Bundle and predict**, or switch to **Upload FHIR Bundle** and score an
existing Bundle. Both paths show the generated Bundle (downloadable), the extracted
features and the model probability.

The trained model is included at `models/vita_heart_model.joblib`. To retrain it:

```bash
python ml/train.py
```

## Data and privacy

- `data/heart.csv` is the public *Heart Failure Prediction Dataset* from Kaggle
  ([source](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction)), included
  for course reproducibility. Refer to the Kaggle page for its licence.
- The patient Bundles in `fhir/examples/` and the form are **synthetic** (`VITA-0001` …);
  there is no protected health information.
- VITA is an educational prototype and must not be used for clinical decisions.

## Team

CS 6440 Practicum, Group 31 — Yidan Sun, Hong Cai.
