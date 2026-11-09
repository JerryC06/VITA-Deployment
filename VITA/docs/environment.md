# Development Environment and Version Policy


## 1. Reference environment (demo, v1.2)

| Component | Version | Used by | Required now? |
| --- | --- | --- | --- |
| Python | **3.12** (tested 3.9.6, 3.12.14) | converter, parser, validator, tests | yes |
| pytest | **9.1.1** (pinned in `requirements-dev.txt`) | `tests/` | dev |
| pandas | **3.1.0** (`requirements.txt`) | training, parser, demo | yes |
| scikit-learn | **1.9.1** (`requirements.txt`) | training, inference | yes |
| joblib | **1.6.0** (`requirements.txt`) | model serialization | yes |
| Streamlit | **1.66.1** (`requirements.txt`) | demo dashboard | yes |
| FHIR | **R4 (4.0.1)** | all resources | yes |
| LOINC | **2.83** (via `tx.fhir.org`) | BP, cholesterol, glucose, ECG, ST deviation | yes (verified) |
| SNOMED CT | **International 2025-02-01** (via `tx.fhir.org`) | chest pain, ECG impression, max HR, angina, label | yes (verified) |
| UCUM | **2.2** (via `tx.fhir.org`) | all units | yes (verified) |
| Git | ≥ 2.30 | version control | yes |
| GitHub Actions | `runs-on: ubuntu-latest` in `ci.yml.disabled` | CI (disabled) | no — no runner on the course GHES |
| Java | **17 (LTS)** — Temurin or OpenJDK | HL7 FHIR Validator / IG Publisher | **not now** (Task 14) |
| Node.js | not required | — | no |

> Java is **not** needed for the Task 4 deliverables. It becomes necessary only when we run
> `validator_cli.jar` or the IG Publisher (Task 14). The local development machine currently
> has no Java runtime, which is why full profile validation is deferred; this is recorded as
> a known limitation in the design overview §7 and in the Task 4 report §7.

### 1.1 Planned application stack (pin at the task that introduces it)

| Component | Target | Introduced in |
| --- | --- | --- |
| FastAPI | 0.115.x | Task 8 (prediction endpoints) |
| uvicorn | 0.32.x | Task 8 |
| pydantic | 2.x | Task 8 (request/response models) |
| httpx | 0.27.x | Task 8 (API tests) |

These are **targets**, not installs: they are added to `requirements.txt` and frozen with
`pip freeze` when the corresponding task starts, so we never carry an unused dependency or
an unverified version.

---

## 2. Local setup (macOS / Linux / WSL)

```bash
# 1. Python 3.12 (pick one)
brew install python@3.12            # macOS
# or: pyenv install 3.12.14 && pyenv local 3.12   (the repo already has .python-version)

# 2. Virtual environment (never install into the system Python)
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 3. Dependencies
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

# 4. Smoke test
python scripts/validate_bundles.py        # expect: 10/10 checks passed
python -m pytest tests -q                 # expect: 31 passed
```

Homebrew Python 3.12.16 was used for the demo environment (`.venv`). The mapping code is
standard-library only and also runs on Python 3.9, but the demo dependencies require 3.12.

### 2.1 Java (only for Task 14)

```bash
brew install --cask temurin@17      # or: brew install openjdk@17
java -version                       # expect: openjdk version "17.x"
```

Then:

```bash
java -jar validator_cli.jar fhir/examples/Bundle-vita-0001.json -version 4.0.1 -tx n/a
```

### 2.2 Kaggle data

The public dataset is committed at `data/heart.csv` (918 records, 12 columns) so training
and the demo are reproducible without a Kaggle account. To refresh it:

```bash
# download heart.csv from
# https://www.kaggle.com/datasets/fedesoriano/heart-failure-prediction
cp ~/Downloads/heart.csv data/heart.csv
python -c "import pandas as pd; d=pd.read_csv('data/heart.csv'); print(d.shape, list(d.columns))"
# expect: (918, 12) ['Age','Sex','ChestPainType','RestingBP','Cholesterol','FastingBS',
#                    'RestingECG','MaxHR','ExerciseAngina','Oldpeak','ST_Slope','HeartDisease']
```

---

## 3. CI status

The course GitHub Enterprise instance (`github.gatech.edu`) does not provide a runner, so
the workflow is kept as `.github/workflows/ci.yml.disabled`. Until a self-hosted runner is
available, run the validator and the tests locally before every push:

```bash
python scripts/validate_bundles.py
python -m pytest tests -q
```

If a runner becomes available, rename the file back and set `runs-on` to the runner label
(usually `self-hosted`).

---

## 4. Version policy

1. **Pin exact versions** in `requirements.txt` / `requirements-dev.txt` (`==`, not `>=`).
   Lower bounds are acceptable only while a task is in progress.
2. **Python version is pinned** in `.python-version` (3.12).
3. **Record terminology versions** in `mappings/terminology-verification.json`
   (`LOINC 2.83`, `SNOMED CT 2025-02-01`, `UCUM 2.2`). Re-run
   `python scripts/verify_terminology.py` whenever the mapping changes or a year passes.
4. **Upgrade deliberately**: bump the pin, run `validate_bundles.py` + `pytest`, update this
   document and the verification report, and mention the upgrade in the PR.
5. **Do not commit** `.venv/`, `__pycache__/`, `.pytest_cache/` or global-site-packages
   artifacts (already in `.gitignore`).
6. **No global installs** and no `pip install` without a pin in the final deliverable.

---

## 5. What goes in the Sprint report

- The reference environment table (§1) — one short table is enough.
- The exact commands used to verify the deliverable (§2).
- The terminology versions and the verification result
  (`34/34 codes verified against tx.fhir.org`, see
  [`terminology-verification.json`](../mappings/terminology-verification.json)).
- Any version you could not install (e.g. Java) and the mitigation (validation deferred to
  Task 14, structural validation used instead).
