# VITA — Machine Learning Model

This folder contains the training script for the VITA heart disease prediction prototype.
The model is a **Scikit-learn Logistic Regression pipeline** trained on the
[Kaggle Heart Failure Prediction Dataset](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction).
VITA is an **educational project**, not a clinically validated diagnostic system.

## Files

- `ml/train.py` — loads data, preprocesses features, trains/evaluates the model, and saves it.
- `data/heart.csv` — the training dataset (the public Kaggle dataset, committed for reproducibility).
- `models/vita_heart_model.joblib` — the trained pipeline used by the demo app (committed; regenerate with `python ml/train.py`).
- `requirements.txt` — the Python dependencies used by training.

## Dataset

The CSV contains **918 records**, **11 input features**, and one binary target,
`HeartDisease` (`0` = no heart disease; `1` = heart disease).

The model expects these input columns, with the same names and compatible values:

```text
Age, Sex, ChestPainType, RestingBP, Cholesterol, FastingBS,
RestingECG, MaxHR, ExerciseAngina, Oldpeak, ST_Slope
```

The target `HeartDisease` is used during training and **must not be passed to the
model as a prediction feature**.

## Setup and training

1. Use the repository's Python environment (`.python-version` specifies Python 3.12).
2. Install dependencies **from the VITA repository root**:

   ```bash
   python -m pip install -r requirements.txt
   ```

3. The dataset is already in the repository at **`data/heart.csv`**. To refresh it,
   download it from
   [Kaggle](https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction) and
   replace that file.
4. Run **from the repository root** (important because `train.py` uses relative paths):

   ```bash
   python ml/train.py
   ```

   In PyCharm, set the **Script path** to `VITA/ml/train.py` and the
   **Working directory** to the `VITA` repository root.

The trained pipeline will be saved to `models/vita_heart_model.joblib`.
The `models/` folder must exist or be created by `train.py` before saving.

## Training and preprocessing

The script performs a **stratified 80/20 train/test split** (`random_state=31`),
then fits preprocessing and Logistic Regression together inside a single Pipeline.

- `Cholesterol` and `RestingBP`: source CSV values of `0` are treated as missing,
  imputed with training-set medians, and standardized.
- `Age`, `MaxHR`, `Oldpeak`: standardized.
- `Sex`, `ChestPainType`, `RestingECG`, `ExerciseAngina`, `ST_Slope`:
  one-hot encoded with `handle_unknown="ignore"`.
- `FastingBS`: passed through unchanged.
- `Cholesterol`: a separate missingness indicator records whether the original
  value was `0`.
- Classifier: `LogisticRegression(max_iter=1000)`.

Preprocessing is fitted only on training data and, during **5-fold stratified
cross-validation**, independently within each fold to reduce data leakage.

## Evaluation

The script prints 5-fold cross-validation recall, then evaluates on
the held-out test set using accuracy, precision, recall, ROC-AUC, and a confusion
matrix. In a previous local run, the following test results were reported:

| Metric | Reproduced result |
| --- | ---: |
| Accuracy | 85.33% |
| Precision | 88.66% |
| Recall | 84.31% |
| ROC-AUC | 0.9297 |

Confusion matrix (`[[TN, FP], [FN, TP]]`): `[[71, 11], [16, 86]]`.
These are **preliminary results for this dataset and run**, not evidence of
clinical reliability. Rerun the script and update these figures if the data or
preprocessing differs.

## Using the saved model with FHIR data

FastAPI will load `models/vita_heart_model.joblib` with `joblib.load()` and use
`scripts/vita_mapping.py` to extract patient features from a FHIR R4 Bundle.
The features must be supplied as a **one-row Pandas DataFrame** with all 11
training column names and compatible value types/categories.

**Missing-value integration:** the FHIR parser returns `None` for an absent
observation. Immediately before model prediction, convert `None` to `0` **only
for `RestingBP` and `Cholesterol`**, because the saved pipeline was trained to
interpret zeros as missing for those two features. Missing values in other
required fields should be validated/rejected, not silently converted to zero.
Do not pass the known `HeartDisease` label from test Bundles as a feature.

The demo implementation of this contract is
[`app/fhir_parser.py`](../app/fhir_parser.py) (`bundle_to_model_input`) and
[`app/model.py`](../app/model.py) (`predict_bundle`). The FHIR conversion utilities are
separate from model training; predicting from the trained pipeline does **not** require
`heart.csv`.

## Sharing and reproducibility

`models/vita_heart_model.joblib` is committed (6 KB) so the demo runs after a clone;
it is reproducible with `python ml/train.py`. The `.gitignore` still ignores every other
`*.joblib` / `*.pkl` file. See [`models/README.md`](../models/README.md) for the
provenance, library versions and SHA-256. Load model artifacts only from trusted
sources and with compatible versions of Python and Scikit-learn.
