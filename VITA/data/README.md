# Data

| File | What it is |
| --- | --- |
| `heart.csv` | The public *Heart Failure Prediction Dataset* from Kaggle ([source](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction)): 918 records, 11 features, 1 binary label. Committed for course reproducibility; refer to the Kaggle page for its licence. |
| `sample_rows.csv` | Three **synthetic** records written for the FHIR mapping tests; no real patient data. |

## `heart.csv`

```text
Age, Sex, ChestPainType, RestingBP, Cholesterol, FastingBS, RestingECG,
MaxHR, ExerciseAngina, Oldpeak, ST_Slope, HeartDisease
```

Used by `ml/train.py` to train the model. `HeartDisease` is the label and must not be
passed to the model as a feature. `RestingBP = 0` and `Cholesterol = 0` are missing-value
sentinels, not measurements.

## `sample_rows.csv`

The three rows exercise the edge cases of the FHIR mapping:

1. `VITA-0001` — complete record, positive label, `Oldpeak = 2.3` (mm).
2. `VITA-0002` — missing `RestingBP` and `Cholesterol` (sentinel `0`), `ASY`, `N`,
   negative `Oldpeak`, negative label.
3. `VITA-0003` — missing `Cholesterol`, `NAP`, `LVH`, `Down` slope, positive label, and
   `Sex = 1` (the original UCI numeric encoding) to exercise the `1/0` → `male/female`
   normalization.

| Column | Description |
| --- | --- |
| `Age`, `Sex`, `ChestPainType`, `RestingBP`, `Cholesterol` | see the mapping design, §2 |
| `FastingBS`, `RestingECG`, `MaxHR`, `ExerciseAngina`, `Oldpeak`, `ST_Slope` | see the mapping design, §2 |
| `HeartDisease` | target label (`1` = heart disease present) |

## Regenerating the examples

```bash
python scripts/build_examples.py    # writes fhir/examples/Bundle-*.json
python scripts/validate_bundles.py  # round-trip check
```
