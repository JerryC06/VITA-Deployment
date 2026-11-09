# Mapping artifacts

This directory defines how the 11 clinical features of the Kaggle Heart Failure Prediction
Dataset are represented in FHIR R4.

| File | Role | Generated? |
| --- | --- | --- |
| [`vita-feature-mapping.json`](vita-feature-mapping.json) | Specification: resource, element, code, unit, transform, extraction rule and validation range for each feature and for the label | no — **source of truth** |
| [`vita-feature-mapping.csv`](vita-feature-mapping.csv) | One row per feature, for review and for reports | yes |
| [`vita-terminology.csv`](vita-terminology.csv) | One row per code, with display, version and links | yes |
| [`terminology-verification.json`](terminology-verification.json) | Provenance of every code: terminology server, version, display, verification time | yes |

The JSON file is the only hand-edited artifact. The two CSVs and the verification report are
produced by the scripts, so the tables cannot drift away from the specification.

## Feature CSV columns

| Column | Meaning |
| --- | --- |
| `dataset_column` | Source column in the Kaggle dataset |
| `fhir_resource`, `fhir_element` | Where the value lives in the Bundle |
| `code_system_name`, `code_system_uri` | Terminology and its canonical identifier |
| `code`, `code_display` | Concept used for the feature |
| `unit_ucum` | Unit code when the value is a `Quantity` |
| `code_lookup_url`, `code_lookup_api_url` | Human-readable page and machine-readable lookup |
| `terminology_verified` | Server and version that verified the code |
| `transform`, `extract` | Rule used in each direction |
| `validation` | Allowed values or plausible range |

## Identifiers and links

`code_system_uri` is a FHIR canonical identifier (`http://loinc.org`,
`http://snomed.info/sct`, …). It identifies a code system, not a single concept, so it is
not a browsable page. Two link columns are provided instead:

- `code_lookup_url` — a page for a person (LOINC page, SNOMED CT browser, terminology
  server lookup, or the repository file for local code systems);
- `code_lookup_api_url` — the `$lookup` / `$validate-code` request that returns the
  authoritative JSON for the code.

The local CodeSystems use `https://vita.example.org/...` as their canonical base. That
domain is reserved for documentation (RFC 2606) and is intentionally not resolvable; the
definitions are in [`../fhir/terminology/`](../fhir/terminology).

## Local terminology

Only `ST_Slope` needs a local code system, because LOINC models ST slope per lead and
quantitatively, and SNOMED CT has no concept for the categorical direction at peak exercise:

- [`vita-observation-codes`](../fhir/terminology/CodeSystem-vita-observation-codes.json) —
  code `st-slope-peak` (what was measured);
- [`vita-st-slope`](../fhir/terminology/CodeSystem-vita-st-slope.json) — codes `up`,
  `flat`, `down` (the answer).

Both are version `1.0.0`. If the canonical base changes, update `canonicalBase` in the JSON
specification and regenerate the artifacts.

## Regenerating

```bash
python scripts/verify_terminology.py   # refresh the verification report (network)
python scripts/export_mapping_csv.py   # rebuild both CSVs
```
