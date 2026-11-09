"""Reference implementation of the VITA FHIR feature mapping.

This module is deliberately small and dependency-free. It is the executable
form of `mappings/vita-feature-mapping.json` and exists so that the mapping can
be tested end to end (CSV row -> FHIR Bundle -> feature vector) before the
production converter (Task 7) and parser (Task 10) are written.

The JSON mapping file is the single source of truth: resource types, codes,
units, transforms and validation ranges are all read from it, so a change to
the mapping cannot silently drift away from the code.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC_PATH = ROOT / "mappings" / "vita-feature-mapping.json"

OBSERVATION_CATEGORY_SYSTEM = "http://terminology.hl7.org/CodeSystem/observation-category"
DATA_ABSENT_REASON_SYSTEM = "http://terminology.hl7.org/CodeSystem/data-absent-reason"


# --------------------------------------------------------------------------- #
# Spec loading
# --------------------------------------------------------------------------- #
def load_spec(path: pathlib.Path | str = SPEC_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def features(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(spec["features"], key=lambda f: f["order"])


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _num(value: float) -> int | float:
    """Return an int when the float is integral so JSON stays readable."""
    value = round(float(value), 6)
    return int(value) if value.is_integer() else value


def canonical_value(feature: dict[str, Any], raw: str) -> str:
    """Normalize a source token to the canonical token used by the model.

    Only Sex needs this today: the Kaggle edition uses M/F, the original UCI
    encoding uses 1/0, and both must become the same feature value (M/F).
    """
    return feature["toFhir"].get("canonicalValue", {}).get(raw, raw)


def _codes(*codings: dict[str, str]) -> dict[str, Any]:
    return {"coding": list(codings)}


def _coding(system: str, code: str, display: str) -> dict[str, str]:
    return {"system": system, "code": code, "display": display}


def _iso_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MappingError(ValueError):
    """Raised when a source value cannot be mapped to FHIR."""


# --------------------------------------------------------------------------- #
# CSV -> FHIR
# --------------------------------------------------------------------------- #
def _patient_id(index: int, spec: dict[str, Any]) -> str:
    return f"{spec['bundleConventions']['patientIdPrefix']}{index + 1:04d}"


def _patient_url(patient_id: str, spec: dict[str, Any]) -> str:
    return spec["bundleConventions"]["subjectReferenceTemplate"].format(patientId=patient_id)


def _reference(patient_id: str, spec: dict[str, Any]) -> dict[str, str]:
    return {"reference": _patient_url(patient_id, spec)}


def build_patient(row: dict[str, str], patient_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    conv = spec["bundleConventions"]
    patient: dict[str, Any] = {
        "resourceType": "Patient",
        "id": patient_id,
        "identifier": [{"system": conv["identifierSystem"], "value": patient_id}],
    }
    for feature in features(spec):
        if feature["fhir"]["resource"] != "Patient":
            continue
        raw = row[feature["column"]].strip()
        rule = feature["toFhir"]
        if rule["type"] == "birthYearFromAge":
            age = int(raw)
            patient["birthDate"] = str(rule["referenceYear"] - age)
        elif rule["type"] == "patientGender":
            if raw not in rule["map"]:
                raise MappingError(f"{feature['column']}={raw!r} is not a valid value")
            patient["gender"] = rule["map"][raw]
        else:  # pragma: no cover - guards spec typos
            raise MappingError(f"unsupported Patient transform {rule['type']!r}")
    return patient


def _observation_skeleton(feature: dict[str, Any], patient_id: str, spec: dict[str, Any]) -> dict[str, Any]:
    fhir = feature["fhir"]
    conv = spec["bundleConventions"]
    return {
        "resourceType": "Observation",
        "id": f"{patient_id.lower()}-{fhir['resourceIdSuffix']}",
        "status": conv["observationStatus"],
        "category": [_codes(_coding(OBSERVATION_CATEGORY_SYSTEM, fhir["category"], _category_display(fhir["category"])))],
        "code": {
            "coding": [_coding(fhir["code"]["system"], fhir["code"]["code"], fhir["code"]["display"])],
            "text": fhir["codeText"],
        },
        "subject": _reference(patient_id, spec),
        "effectiveDateTime": conv["effectiveDateTime"],
    }


_CATEGORY_DISPLAY = {
    "vital-signs": "Vital Signs",
    "laboratory": "Laboratory",
    "procedure": "Procedure",
    "survey": "Survey",
    "exam": "Exam",
}


def _category_display(code: str) -> str:
    return _CATEGORY_DISPLAY.get(code, code)


def build_observation(row: dict[str, str], patient_id: str, feature: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    fhir = feature["fhir"]
    rule = feature["toFhir"]
    raw = row[feature["column"]].strip()
    obs = _observation_skeleton(feature, patient_id, spec)

    if rule["type"] == "codeMap":
        if raw not in rule["map"]:
            raise MappingError(f"{feature['column']}={raw!r} is not a valid value")
        mapped = rule["map"][raw]
        obs["valueCodeableConcept"] = {
            "coding": [_coding(mapped["system"], mapped["code"], mapped["display"])],
            "text": mapped.get("text", mapped["display"]),
        }
        if feature["id"] == "restingEcg":
            obs["method"] = {"text": "Resting 12-lead ECG"}

    elif rule["type"] == "quantity":
        sentinel = rule.get("sentinel")
        if sentinel and float(raw) == float(sentinel["value"]):
            if not sentinel.get("treatAsMissing", True):
                raise MappingError(f"sentinel for {feature['column']} must map to a value")
            obs["dataAbsentReason"] = _codes(_coding(DATA_ABSENT_REASON_SYSTEM, "unknown", "Unknown"))
        else:
            value = float(raw)
            scale = float(rule.get("scale", 1))
            obs["valueQuantity"] = _quantity(feature, _num(value * scale))

    elif rule["type"] == "thresholdQuantity":
        is_true = raw == "1"
        obs["valueQuantity"] = _quantity(feature, _num(rule["threshold"]))
        obs["valueQuantity"]["comparator"] = rule["trueComparator"] if is_true else rule["falseComparator"]
        interpretation = rule["trueInterpretation"] if is_true else rule["falseInterpretation"]
        obs["interpretation"] = [
            _codes(
                _coding(
                    rule["interpretationSystem"],
                    interpretation,
                    "High" if interpretation == "H" else "Normal",
                )
            )
        ]
    elif rule["type"] == "boolean":
        if raw not in rule["map"]:
            raise MappingError(f"{feature['column']}={raw!r} is not a valid value")
        obs["valueBoolean"] = rule["map"][raw]
    else:  # pragma: no cover - guards spec typos
        raise MappingError(f"unsupported Observation transform {rule['type']!r}")
    return obs


def _quantity(feature: dict[str, Any], value: int | float) -> dict[str, Any]:
    unit = feature["fhir"]["unit"]
    return {
        "value": value,
        "unit": unit["display"],
        "system": unit["system"],
        "code": unit["code"],
    }


def build_condition(row: dict[str, str], patient_id: str, spec: dict[str, Any]) -> dict[str, Any] | None:  # noqa: E501
    label = spec["label"]

    if label["column"] not in row:
        return None

    raw_label = row.get(label["column"])
    # A form-generated Bundle has no known label; absence means "no Condition".
    if raw_label is None or str(raw_label).strip() == "":
        return None
    present = int(raw_label) == int(label["toFhir"]["presentWhen"])
    if not present:
        return None
    fhir = label["fhir"]
    return {
        "resourceType": "Condition",
        "id": f"{patient_id.lower()}-{fhir['resourceIdSuffix']}",
        "clinicalStatus": _codes(
            _coding("http://terminology.hl7.org/CodeSystem/condition-clinical", fhir["clinicalStatus"], "Active")
        ),
        "verificationStatus": _codes(
            _coding(
                "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                fhir["verificationStatus"],
                "Confirmed",
            )
        ),
        "category": [
            _codes(
                _coding(
                    "http://terminology.hl7.org/CodeSystem/condition-category",
                    fhir["category"],
                    "Problem List Item",
                )
            )
        ],
        "code": {"coding": [_coding(fhir["code"]["system"], fhir["code"]["code"], fhir["code"]["display"])]},
        "subject": _reference(patient_id, spec),
        "recordedDate": spec["bundleConventions"]["effectiveDateTime"],
    }


def build_bundle(row: dict[str, str], patient_id: str, spec: dict[str, Any], bundle_id: str | None = None) -> dict[str, Any]:
    patient = build_patient(row, patient_id, spec)
    entries = [{"fullUrl": _patient_url(patient_id, spec), "resource": patient}]
    for feature in features(spec):
        if feature["fhir"]["resource"] != "Observation":
            continue
        obs = build_observation(row, patient_id, feature, spec)
        entries.append(
            {
                "fullUrl": f"{spec['canonicalBase']}/Observation/{obs['id']}",
                "resource": obs,
            }
        )
    condition = build_condition(row, patient_id, spec)
    if condition:
        entries.append(
            {
                "fullUrl": f"{spec['canonicalBase']}/Condition/{condition['id']}",
                "resource": condition,
            }
        )
    return {
        "resourceType": "Bundle",
        "id": bundle_id or patient_id.lower(),
        "identifier": {"system": "https://vita.example.org/fhir/sid/bundle", "value": patient_id},
        "type": spec["bundleConventions"]["type"],
        "timestamp": spec["bundleConventions"]["effectiveDateTime"],
        "entry": entries,
    }


# --------------------------------------------------------------------------- #
# FHIR -> ML feature vector
# --------------------------------------------------------------------------- #
def _find_patient(bundle: dict[str, Any]) -> dict[str, Any]:
    for entry in bundle.get("entry", []):
        if entry["resource"]["resourceType"] == "Patient":
            return entry["resource"]
    raise MappingError("Bundle contains no Patient resource")


def _index_observations(bundle: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    index: dict[tuple[str, str], dict[str, Any]] = {}
    for entry in bundle.get("entry", []):
        resource = entry["resource"]
        if resource["resourceType"] != "Observation":
            continue
        for coding in resource.get("code", {}).get("coding", []):
            index[(coding["system"], coding["code"])] = resource
    return index


def _age_from_birth_date(birth_date: str, reference: str) -> int | None:
    if not birth_date:
        return None
    reference_date = _dt.date.fromisoformat(reference[:10])
    if len(birth_date) == 4:  # year precision
        return reference_date.year - int(birth_date)
    born = _dt.date.fromisoformat(birth_date)
    return reference_date.year - born.year - ((reference_date.month, reference_date.day) < (born.month, born.day))


def _reverse_lookup(rule: dict[str, Any], coding: dict[str, str]) -> str | None:
    for source_value, target in rule["map"].items():
        if target["system"] == coding.get("system") and target["code"] == coding.get("code"):
            return source_value
    return None


def extract_features(bundle: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Return {column: value}, with None for values absent from the Bundle."""
    patient = _find_patient(bundle)
    observations = _index_observations(bundle)
    conv = spec["bundleConventions"]
    result: dict[str, Any] = {}

    for feature in features(spec):
        rule = feature["fromFhir"]
        column = feature["column"]
        fhir = feature["fhir"]

        if fhir["resource"] == "Patient":
            if rule["type"] == "ageFromBirthDate":
                result[column] = _age_from_birth_date(patient.get("birthDate", ""), conv["referenceDate"])
            elif rule["type"] == "patientGenderReverse":
                result[column] = rule["map"].get(patient.get("gender", ""))
            else:  # pragma: no cover
                raise MappingError(f"unsupported Patient extract {rule['type']!r}")
            continue

        obs = observations.get((fhir["code"]["system"], fhir["code"]["code"]))
        if obs is None:
            result[column] = None
            continue
        if "dataAbsentReason" in obs:
            result[column] = None
            continue

        if rule["type"] == "quantityValue":
            quantity = obs.get("valueQuantity", {})
            if "value" not in quantity:
                result[column] = None
            else:
                value = float(quantity["value"]) * float(rule.get("scale", 1))
                result[column] = round(value, rule.get("round", 2))
                if result[column] == int(result[column]):
                    result[column] = int(result[column])
        elif rule["type"] == "comparatorBoolean":
            comparator = obs.get("valueQuantity", {}).get("comparator")

            if comparator not in (">", "<="):
                raise ValueError("Invalid FastingBS comparator. Expected '>' or '<='.")

            result[column] = 1 if comparator == rule["trueComparator"] else 0

        elif rule["type"] == "booleanReverse":
            value = obs.get("valueBoolean")
            result[column] = rule["map"].get(str(value).lower()) if value is not None else None

        elif rule["type"] == "codeMapReverse":
            coding = (obs.get("valueCodeableConcept", {}).get("coding") or [{}])[0]
            result[column] = _reverse_lookup(feature["toFhir"], coding)

        else:
            raise MappingError(f"unsupported Observation extract {rule['type']!r}")
    return result


def extract_label(bundle: dict[str, Any], spec: dict[str, Any]) -> int:
    label = spec["label"]
    target = (label["fhir"]["code"]["system"], label["fhir"]["code"]["code"])

    for entry in bundle.get("entry", []):
        resource = entry["resource"]

        if resource["resourceType"] != "Condition":
            continue
        if any((c["system"], c["code"]) == target for c in resource.get("code", {}).get("coding", [])):

            return int(label["fromFhir"]["presentWhen"])
    return 0


# --------------------------------------------------------------------------- #
# Structural validation
# --------------------------------------------------------------------------- #
def validate_bundle(bundle: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    """Check the Bundle against the mapping's structural and range rules."""
    problems: list[str] = []
    conv = spec["bundleConventions"]
    patient = _find_patient(bundle)
    patient_url = _patient_url(patient["id"], spec)

    if bundle.get("type") != conv["type"]:
        problems.append(f"Bundle.type is {bundle.get('type')!r}, expected {conv['type']!r}")
    if not patient.get("gender"):
        problems.append("Patient.gender is missing")
    if not patient.get("birthDate"):
        problems.append("Patient.birthDate is missing")

    seen_ids: set[str] = set()
    for entry in bundle.get("entry", []):
        resource = entry["resource"]
        rid = resource.get("id", "")
        if rid in seen_ids:
            problems.append(f"duplicate resource id {rid!r}")
        seen_ids.add(rid)
        if not entry.get("fullUrl", "").endswith(f"/{resource['resourceType']}/{rid}"):
            problems.append(f"fullUrl does not match resource id for {rid!r}")

    observations = _index_observations(bundle)
    for feature in features(spec):
        if feature["fhir"]["resource"] != "Observation":
            continue
        fhir = feature["fhir"]
        key = (fhir["code"]["system"], fhir["code"]["code"])
        obs = observations.get(key)
        label = feature["column"]
        if obs is None:
            problems.append(f"{label}: Observation {fhir['code']['code']} is missing")
            continue
        if obs.get("status") != conv["observationStatus"]:
            problems.append(f"{label}: status is {obs.get('status')!r}")
        if not obs.get("category"):
            problems.append(f"{label}: category is missing")
        if obs.get("effectiveDateTime") != conv["effectiveDateTime"]:
            problems.append(f"{label}: unexpected effectiveDateTime {obs.get('effectiveDateTime')!r}")
        if obs.get("subject", {}).get("reference") != patient_url:
            problems.append(f"{label}: subject does not reference {patient_url}")
        coding = (obs.get("code", {}).get("coding") or [{}])[0]
        if not coding.get("display"):
            problems.append(f"{label}: code display is missing")
        quantity = obs.get("valueQuantity")
        if quantity is not None:
            unit = fhir.get("unit") or {}
            if quantity.get("system") != "http://unitsofmeasure.org":
                problems.append(f"{label}: unit system is not UCUM")
            if unit and quantity.get("code") != unit["code"]:
                problems.append(f"{label}: unit code {quantity.get('code')!r} != {unit['code']!r}")
            limits = feature.get("validation", {})
            if "min" in limits and "value" in quantity:
                # Convert back to the source unit (e.g. Oldpeak mV -> mm) before
                # applying the range rule, which is expressed in source units.
                value = float(quantity["value"]) * float(feature["fromFhir"].get("scale", 1))
                if not (limits["min"] <= value <= limits["max"]):
                    problems.append(f"{label}: value {value} outside {limits['min']}..{limits['max']}")
    return problems


def compare_expected(extracted: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Compare extracted features with the expected vector (None means missing)."""
    problems: list[str] = []
    for column, want in expected.items():
        got = extracted.get(column)
        if want is None:
            if got is not None:
                problems.append(f"{column}: expected missing, got {got!r}")
            continue
        if isinstance(want, float):
            if got is None or abs(float(got) - want) > 1e-6:
                problems.append(f"{column}: expected {want!r}, got {got!r}")
        elif got != want:
            problems.append(f"{column}: expected {want!r}, got {got!r}")
    return problems
