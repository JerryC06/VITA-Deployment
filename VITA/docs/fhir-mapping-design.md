# FHIR Mapping Design — VITA

**Project:** VITA — FHIR-based Heart Disease Prediction Dashboard (CS 6440, Group 31)
**Standard:** FHIR R4 (4.0.1)
**Dataset:** Kaggle *Heart Failure Prediction Dataset* (918 records, 11 features)
**Owner:** Yidan Sun

This document summarizes how the 11 clinical features of the dataset are represented in
FHIR R4. The executable specification is
[`mappings/vita-feature-mapping.json`](../mappings/vita-feature-mapping.json); the tables in
this document are generated from it.

---

## 1. Scope

Each dataset row becomes one FHIR `Bundle` containing a `Patient`, one `Observation` per
non-demographic feature, and optionally a `Condition` for the heart-disease label. The
mapping is used in both directions: the converter builds Bundles from CSV rows, and the
parser extracts the feature vector for the model.

The dataset contains a single encounter per patient, so all resources share one
`effectiveDateTime`. Patient identifiers are synthetic (`VITA-0001` …).

## 2. Resource model

```text
Bundle (type = collection)
├── Patient      ×1    age, sex
├── Observation  ×9    chest pain type, blood pressure, cholesterol, fasting glucose,
│                      resting ECG, max heart rate, exercise angina, ST deviation, ST slope
└── Condition    0..1  heart disease label
```

| Resource | Count | Carries | Reason |
| --- | --- | --- | --- |
| `Patient` | 1 | `birthDate`, `gender` | Age and sex are attributes of the person, not measurements |
| `Observation` | 9 | one feature each | One uniform shape: `code`, `value[x]`, `category`, `subject`, time |
| `Condition` | 0–1 | `HeartDisease` label | A diagnosis, not a measurement; presence of the Condition means label 1 |

Each Observation is identified by `(code.system, code.code)`, so the parser needs one lookup
rule rather than a special case per feature.

## 3. Feature mapping

| # | Dataset field | FHIR element | Code | Value type | Unit |
| --- | --- | --- | --- | --- | --- |
| 1 | `Age` | `Patient.birthDate` | — | `date` (year precision) | — |
| 2 | `Sex` | `Patient.gender` | — | `code` | — |
| 3 | `ChestPainType` | `Observation.valueCodeableConcept` | SNOMED `29857009` | CodeableConcept | — |
| 4 | `RestingBP` | `Observation.valueQuantity` | LOINC `8480-6` | Quantity | `mm[Hg]` |
| 5 | `Cholesterol` | `Observation.valueQuantity` | LOINC `2093-3` | Quantity | `mg/dL` |
| 6 | `FastingBS` | `Observation.valueQuantity` | LOINC `1558-6` | Quantity + comparator | `mg/dL` |
| 7 | `RestingECG` | `Observation.valueCodeableConcept` | LOINC `11524-6` | CodeableConcept | — |
| 8 | `MaxHR` | `Observation.valueQuantity` | SNOMED `428630002` | Quantity | `/min` |
| 9 | `ExerciseAngina` | `Observation.valueBoolean` | SNOMED `300995000` | boolean | — |
| 10 | `Oldpeak` | `Observation.valueQuantity` | LOINC `91546-2` | Quantity | `mV` |
| 11 | `ST_Slope` | `Observation.valueCodeableConcept` | VITA local `st-slope-peak` | CodeableConcept | — |
| label | `HeartDisease` | `Condition.code` | SNOMED `56265001` | Condition | — |

The coded values for the categorical features are SNOMED CT concepts, except `ST_Slope`
(see §4.2):

| Feature | Values |
| --- | --- |
| `ChestPainType` | `429559004` typical angina, `371807002` atypical angina, `274668005` non-cardiac chest pain, `84387000` asymptomatic |
| `RestingECG` | `164854000` ECG normal, `164930006` ECG: ST interval abnormal, `25488008` LVH by ECG |
| `ST_Slope` | local `up`, `flat`, `down` |

## 4. Design decisions

### 4.1 One Observation per feature

All nine non-demographic features use the same `Observation` skeleton: `status = final`,
`category`, `code`, `subject`, `effectiveDateTime`, `value[x]`. Categories follow the source
of the data: `vital-signs` for blood pressure, `laboratory` for cholesterol and fasting
glucose, `procedure` for ECG and exercise-test measurements, `survey` for symptoms.

Because the resource type and lookup key are identical for every feature, the FastAPI
validation and the parser stay simple and consistent.

### 4.2 Terminology: standard codes first

Eight of the eleven features use LOINC or SNOMED CT. Age and sex use native FHIR elements, and `ST_Slope` uses a local code system.
Every code was resolved on the public terminology server (`https://tx.fhir.org/r4`), and the
result is recorded in
[`mappings/terminology-verification.json`](../mappings/terminology-verification.json)
(34/34 codes, LOINC 2.83, SNOMED CT 2025-02-01, UCUM 2.2).

`ST_Slope` is the one gap: LOINC models ST slope per lead and quantitatively, and SNOMED CT
has no concept for the categorical direction at peak exercise. It therefore uses two small
local CodeSystems, published with the repository:

- [`vita-observation-codes`](../fhir/terminology/CodeSystem-vita-observation-codes.json) —
  `st-slope-peak`;
- [`vita-st-slope`](../fhir/terminology/CodeSystem-vita-st-slope.json) — `up`, `flat`, `down`.

The canonical base `https://vita.example.org/fhir` is a documentation placeholder
(RFC 2606); the definitions are the JSON files above.

### 4.3 Units and conversions

All quantities carry UCUM codes (`http://unitsofmeasure.org`). Two points need explicit
handling:

- **Oldpeak** is recorded in millimetres of ST depression, while LOINC `91546-2` is
  quantitative in mV. The value is converted with the standard calibration 10 mm = 1 mV on
  write and converted back on read; negative values (ST elevation) are preserved.
- **Cholesterol** is reported in mg/dL. The dataset description's unit ("mm Hg") is a
  documentation error, and the mapping uses mg/dL.

### 4.4 Missing values

The source uses `0` as a missing-value sentinel for `RestingBP` and `Cholesterol`, but `0`
is a real answer for `FastingBS`. The mapping distinguishes them:

- missing BP/cholesterol → no `value[x]` plus `dataAbsentReason = unknown` (FHIR invariant
  `obs-6`);
- `FastingBS` → a quantity of 120 mg/dL with comparator `>` (true) or `<=` (false), plus an
  interpretation (`H`/`N`);
- explicit negatives (`ExerciseAngina = N`, `ChestPainType = ASY`) are stored as values, not
  as absent resources.

The parser returns `None` for missing values; imputation is a separate modelling step.

### 4.5 Age and sex

- **Age** is stored as `birthDate` with year precision (`2024 − age`), because the dataset
  has no date of birth. Extraction re-derives the age at the fixed reference date
  `2024-01-01`.
- **Sex** maps to `Patient.gender`. Both the Kaggle (`M`/`F`) and the original UCI (`1`/`0`)
  encodings are accepted and normalized to `male`/`female`; the extracted feature is always
  `M`/`F`. No birthsex extension is used, since the source has only two values.

### 4.6 Resting ECG

The ECG is an `Observation` (code `11524-6`, SNOMED-coded impression) rather than a
`DiagnosticReport`, so that every non-demographic feature is read from one resource type.
`method.text` records that the study was a resting 12-lead ECG.

## 5. Bundle conventions

| Element | Value |
| --- | --- |
| `Bundle.type` | `collection` (read-only upload, no transaction semantics) |
| `fullUrl` | `https://vita.example.org/fhir/{ResourceType}/{id}` |
| References | absolute, identical to the target `fullUrl` |
| Patient id | `VITA-0001` … |
| Observation id | `vita-0001-<suffix>` |
| `status` | `final` |
| `effectiveDateTime` | `2024-01-01T09:00:00Z` |

## 6. Examples and verification

Three Bundles illustrate a complete record and the edge cases (missing BP/cholesterol,
negative Oldpeak, asymptomatic chest pain, numeric sex encoding):

- [`fhir/examples/Bundle-vita-0001.json`](../fhir/examples/Bundle-vita-0001.json)
- [`fhir/examples/Bundle-vita-0002.json`](../fhir/examples/Bundle-vita-0002.json)
- [`fhir/examples/Bundle-vita-0003.json`](../fhir/examples/Bundle-vita-0003.json)

The expected feature vector for each is in
[`expected-features.json`](../fhir/examples/expected-features.json).

Verification:

```bash
python scripts/validate_bundles.py   # 10/10 structural and round-trip checks
python -m pytest tests -q            # 16 tests
python scripts/verify_terminology.py # 34/34 codes on tx.fhir.org
```

The CSV → FHIR → CSV round trip reproduces every real value; the only differences are the
two intended normalizations described in §4.4 and §4.5.

## 7. Limitations and next steps

- `ST_Slope` relies on a project-local code system; it can be replaced by a standard concept
  if one becomes available.
- The converter is validated on three synthetic rows. Converting all 918 Kaggle records,
  with batch error reporting, is Task 7.
- Profile-level validation with the HL7 FHIR Validator / IG Publisher requires Java 17 and
  is scheduled for Task 14; the current checks are structural and model-based.

## 8. References

1. HL7 International. *FHIR Release 4 (v4.0.1)*. <https://hl7.org/fhir/R4/>
2. Regenstrief Institute. *LOINC* (2.83). <https://loinc.org/>
3. SNOMED International. *SNOMED CT International Edition* (2025-02-01). <https://www.snomed.org/>
4. HL7 International. *UCUM* unit codes. <https://terminology.hl7.org/CodeSystem-ucum.html>
5. fedesoriano. *Heart Failure Prediction Dataset*. Kaggle.
   <https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction>
