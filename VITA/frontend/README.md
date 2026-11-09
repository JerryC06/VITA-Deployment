# VITA combined frontend

This update keeps Yidan's existing `app/` files unchanged. It adds your VITA-branded frontend and a separate prediction results page.

Copy these paths into the existing VITA project:

- `frontend/web.py`
- `frontend/pages/results.py`
- `frontend/assets/heart-pulse.png`

Required existing files (already provided by Yidan):

- `app/__init__.py`
- `app/fhir_generator.py`
- `app/fhir_parser.py`
- `app/model.py`
- `scripts/vita_mapping.py` and `mappings/vita-feature-mapping.json`
- `models/vita_heart_model.joblib` (generate with `python ml/train.py` if missing)

Run from the VITA repository root:

```bash
python -m streamlit run frontend/web.py
```

**Two inputs, one inference path:**

- Upload FHIR Bundle: JSON -> `app.model.predict_summary()`
- Enter patient data: form -> `app.fhir_generator.form_to_bundle()` -> `app.model.predict_summary()`

Both inputs switch to the complete `frontend/pages/results.py` page after a successful prediction. Failed or missing model inputs show an error; no invented scores are shown.

**FastAPI:** This version reuses Yidan's direct model integration rather than making HTTP calls. It is functional locally if the saved model exists. If the course/team requires FastAPI in the architecture, the inference call can later be replaced by a `POST /predict` API request, while retaining the same UI.

**Validation:** `resourceType == 'Bundle'` and an `entry` list are preliminary checks only. The parser validates the feature mapping; complete FHIR standard compliance and clinical safety are not claimed.

**Required one-time bug fix in Yidan's mapping module:** The uploaded `form_to_bundle()` calls `build_bundle()` without `HeartDisease`. The uploaded `scripts/vita_mapping.py` requires the target label in `build_condition()` and raises `KeyError`. Apply the small change in `PATCH-vita_mapping.diff` (or ask Yidan to merge it) so an unknown prediction label creates **no Condition**. This does not add a fake negative label to the FHIR output.
