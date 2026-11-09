# Model artifacts

`vita_heart_model.joblib` is the trained Scikit-learn pipeline used by the demo app.
It is a **joblib-serialized** `Pipeline` (preprocessing + logistic regression), about
6 KB, committed so the demo runs without retraining.

| | |
| --- | --- |
| Trained by | `ml/train.py` (Hong Cai) |
| Training data | `data/heart.csv` (918 records) |
| Random seed | 31 (`train_test_split`, `StratifiedKFold`) |
| Library versions | pandas 3.1.0 · scikit-learn 1.9.1 · joblib 1.6.0 |
| Test accuracy | 0.8533 |
| Test ROC-AUC | 0.9297 |
| SHA-256 | `9ec050e5f1512064c96cf082114e47848fc3f6bd382181a82eff3f1a306bbbcf` |

Regenerate with:

```bash
python ml/train.py
```

Load it with:

```bash
python -c "import joblib; m = joblib.load('models/vita_heart_model.joblib'); print(m)"
```

The pipeline expects a one-row DataFrame with these 11 columns, in any order but with
the exact names: `Age, Sex, ChestPainType, RestingBP, Cholesterol, FastingBS,
RestingECG, MaxHR, ExerciseAngina, Oldpeak, ST_Slope`. Values of `0` in `RestingBP`
and `Cholesterol` are treated as missing by the pipeline and imputed with the training
median. See `app/fhir_parser.py` for the conversion from a FHIR Bundle.

Model files are version-sensitive: load this artifact with the pinned versions above.
Do not use it for clinical decisions.
