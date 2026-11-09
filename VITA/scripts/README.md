# Scripts

Reference implementation of the VITA FHIR mapping: conversion in both directions,
validation, and the generated mapping artifacts.

- **Runtime:** Python 3.9+ (3.12 recommended), **standard library only**. No `pip install`
  is needed to run the conversion or validation scripts.
- **Working directory:** run from the repository root, e.g. `python scripts/validate_bundles.py`.
- **Specification:** every script reads [`mappings/vita-feature-mapping.json`](../mappings/vita-feature-mapping.json);
  none of them hard-code clinical codes, units or transforms.

| Script | Type | Purpose | Network |
| --- | --- | --- | --- |
| [`vita_mapping.py`](vita_mapping.py) | library | Shared CSV → FHIR and FHIR → feature logic; imported by the other scripts | no |
| [`csv_to_fhir.py`](csv_to_fhir.py) | CLI | Convert a dataset CSV into one FHIR R4 Bundle per patient | no |
| [`fhir_to_csv.py`](fhir_to_csv.py) | CLI | Extract the 11 features + label from Bundles and write CSV rows | no |
| [`build_examples.py`](build_examples.py) | script | Regenerate `fhir/examples/` from `data/sample_rows.csv` and `expected-features.json` | no |
| [`validate_bundles.py`](validate_bundles.py) | script | Structural + round-trip validation (10 checks); exits 1 on failure | no |
| [`verify_terminology.py`](verify_terminology.py) | script | Resolve every code on `tx.fhir.org` and write `mappings/terminology-verification.json` | yes |
| [`export_mapping_csv.py`](export_mapping_csv.py) | script | Regenerate `mappings/vita-feature-mapping.csv` and `vita-terminology.csv` | no |

Typical order after changing the mapping:

```bash
python scripts/verify_terminology.py     # only when codes change
python scripts/export_mapping_csv.py
python scripts/build_examples.py
python scripts/validate_bundles.py
python -m pytest tests -q
```

## vita_mapping.py (library)

The executable form of the mapping specification. It exposes:

| Function | Use |
| --- | --- |
| `load_spec(path)` | Load the JSON specification |
| `build_bundle(row, patient_id, spec)` | One CSV row → one `Bundle` (Patient + 9 Observations + optional Condition) |
| `extract_features(bundle, spec)` | Bundle → `{column: value}`, with `None` for missing values |
| `extract_label(bundle, spec)` | Bundle → `0`/`1` heart-disease label |
| `validate_bundle(bundle, spec)` | Structural and range checks, returns a list of problems |
| `canonical_value(feature, raw)` | Normalize a source token (e.g. sex `1` → `M`) |

It has no command-line entry point; run it through the CLIs below.

## csv_to_fhir.py

```bash
python scripts/csv_to_fhir.py data/sample_rows.csv --out build/bundles
python scripts/csv_to_fhir.py data/raw/heart.csv --out build/bundles --prefix VITA-
```

- Input: CSV with the 12 dataset columns (`Age` … `HeartDisease`).
- Output: `build/bundles/Bundle-vita-0001.json`, `…-0002.json`, … (one per row).
- Patient IDs are assigned from the row order (`VITA-0001` …); the source rows are not
  modified.
- Exit codes: `0` success, `2` missing columns or empty CSV.
- Verified on the full dataset: 918 rows produce 918 Bundles, and the parser returns
  every value unchanged (apart from the documented `0` → missing normalization).

## fhir_to_csv.py

```bash
python scripts/fhir_to_csv.py build/bundles --out build/roundtrip.csv
python scripts/fhir_to_csv.py fhir/examples/Bundle-vita-0001.json
```

- Input: Bundle files, or a directory containing `Bundle-*.json`.
- Output: CSV with the same 12 columns (stdout if `--out` is omitted).
- Missing values are written as empty cells, not `0`; `Oldpeak` keeps one decimal place.
- Exit codes: `0` success, `2` no Bundles found.
- Full-dataset check: `csv_to_fhir.py` → `fhir_to_csv.py` reproduces all 918 records with
  no mismatches for `Age`, `Sex`, the categorical fields, `Oldpeak`, `FastingBS` or the label.

## build_examples.py

```bash
python scripts/build_examples.py
```

Regenerates the committed examples from `data/sample_rows.csv`:
`fhir/examples/Bundle-vita-0001.json` … `-0003.json` and `expected-features.json`
(source row, expected feature vector, label). Run it after changing the mapping or the
sample rows, then commit the regenerated files.

## validate_bundles.py

```bash
python scripts/validate_bundles.py
```

Checks the mapping specification, each Bundle's structure (status, category, code, UCUM
unit, subject reference, unique ids) and the CSV → FHIR → feature round trip, including
missing values and the `mm`/`mV` conversion. It runs in CI; exit code `1` means at least
one check failed.

## verify_terminology.py

```bash
python scripts/verify_terminology.py            # verify and rewrite the report
python scripts/verify_terminology.py --offline  # reuse the committed report
```

Resolves every LOINC, SNOMED CT, HL7 and UCUM code with `$lookup` / `$validate-code` on
`https://tx.fhir.org/r4`, compares the server display with the mapping, and writes
`mappings/terminology-verification.json` (server version, display, links, timestamp).
Requires network access; the committed report is the evidence used by reviewers and tests.

## export_mapping_csv.py

```bash
python scripts/export_mapping_csv.py
```

Regenerates the two review tables from the JSON specification and the verification report:

- `mappings/vita-feature-mapping.csv` — one row per feature, with codes, units, transforms
  and validation ranges;
- `mappings/vita-terminology.csv` — one row per code, with display, version, a
  human-readable page (`lookup_url`) and an API lookup (`api_url`).

Do not edit the CSVs by hand; change the JSON and re-run this script.
