"""Export the JSON mapping to review-friendly CSVs.

Produces two generated files (never edit them by hand):

* `mappings/vita-feature-mapping.csv`  - one row per clinical feature
* `mappings/vita-terminology.csv`      - one row per code, with a browsable link
                                         and the provenance from the verification
                                         report

    python scripts/export_mapping_csv.py
"""

from __future__ import annotations

import csv
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from verify_terminology import SYSTEM_NAME, api_url, lookup_url  # noqa: E402
from vita_mapping import features, load_spec  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_FEATURES = ROOT / "mappings" / "vita-feature-mapping.csv"
OUT_TERMINOLOGY = ROOT / "mappings" / "vita-terminology.csv"
REPORT = ROOT / "mappings" / "terminology-verification.json"

FEATURE_COLUMNS = [
    "order",
    "dataset_column",
    "fhir_resource",
    "fhir_element",
    "value_type",
    "unit_ucum",
    "category",
    "code_system_name",
    "code_system_uri",
    "code",
    "code_display",
    "code_lookup_url",
    "code_lookup_api_url",
    "terminology_verified",
    "transform",
    "extract",
    "validation",
    "required",
]


def format_version(version: str) -> str:
    """SNOMED versions are URIs (…/version/20250201); render them as 2025-02-01."""
    if version.startswith("http"):
        tail = version.rstrip("/").split("/")[-1]
        if len(tail) == 8 and tail.isdigit():
            return f"{tail[:4]}-{tail[4:6]}-{tail[6:]}"
    return version


def provenance(report: dict) -> dict[tuple[str, str], dict]:
    return {(entry["system"], entry["code"]): entry for entry in report["entries"]}


def main() -> int:
    spec = load_spec()
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    verified = provenance(report)

    rows = []
    for feature in features(spec):
        fhir = feature["fhir"]
        code = fhir.get("code") or {}
        unit = fhir.get("unit") or {}
        validation = feature.get("validation", {})
        rules = []
        if "allowed" in validation:
            rules.append("allowed=" + "|".join(str(v) for v in validation["allowed"]))
        if "min" in validation:
            rules.append(f"range={validation['min']}..{validation['max']} {validation.get('unit', '')}".strip())

        system, value_code = code.get("system", ""), code.get("code", "")
        proof = verified.get((system, value_code))
        if not system:
            system_name, lookup, api, verified_text = "FHIR native", "", "", ""
        elif "vita.example.org" in system:
            system_name = "VITA local CodeSystem"
            lookup = f"fhir/terminology/CodeSystem-{system.rstrip('/').split('/')[-1]}.json"
            api = ""
            verified_text = "local (project CodeSystem)"
        else:
            system_name = SYSTEM_NAME.get(system, system)
            lookup = lookup_url(system, value_code)
            api = api_url(system, value_code)
            verified_text = (
                f"tx.fhir.org · {system_name} {format_version(proof['version'])}" if proof and proof["verified"] else "NOT VERIFIED"
            )

        rows.append(
            {
                "order": feature["order"],
                "dataset_column": feature["column"],
                "fhir_resource": fhir["resource"],
                "fhir_element": fhir["element"],
                "value_type": fhir["valueType"],
                "unit_ucum": unit.get("code", ""),
                "category": fhir.get("category", ""),
                "code_system_name": system_name,
                "code_system_uri": system,
                "code": value_code,
                "code_display": code.get("display", "— (FHIR native)"),
                "code_lookup_url": lookup,
                "code_lookup_api_url": api,
                "terminology_verified": verified_text,
                "transform": feature["toFhir"]["type"],
                "extract": feature["fromFhir"]["type"],
                "validation": "; ".join(rules),
                "required": str(feature["required"]).lower(),
            }
        )

    label = spec["label"]
    proof = verified.get((label["fhir"]["code"]["system"], label["fhir"]["code"]["code"]))
    rows.append(
        {
            "order": "label",
            "dataset_column": label["column"],
            "fhir_resource": label["fhir"]["resource"],
            "fhir_element": "Condition.code",
            "value_type": "Condition",
            "unit_ucum": "",
            "category": label["fhir"]["category"],
            "code_system_name": SYSTEM_NAME.get(label["fhir"]["code"]["system"], ""),
            "code_system_uri": label["fhir"]["code"]["system"],
            "code": label["fhir"]["code"]["code"],
            "code_display": label["fhir"]["code"]["display"],
            "code_lookup_url": lookup_url(label["fhir"]["code"]["system"], label["fhir"]["code"]["code"]),
            "code_lookup_api_url": api_url(label["fhir"]["code"]["system"], label["fhir"]["code"]["code"]),
            "terminology_verified": f"tx.fhir.org · SNOMED CT {format_version(proof['version'])}" if proof else "NOT VERIFIED",
            "transform": label["toFhir"]["type"],
            "extract": label["fromFhir"]["type"],
            "validation": "allowed=0|1",
            "required": "true",
        }
    )

    OUT_FEATURES.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_FEATURES, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FEATURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT_FEATURES.relative_to(ROOT)} ({len(rows)} rows)")

    terminology_rows = []
    for entry in report["entries"]:
        link = entry["lookupUrl"]
        if not link and "vita.example.org" in entry["system"]:
            link = f"fhir/terminology/CodeSystem-{entry['system'].rstrip('/').split('/')[-1]}.json"
        terminology_rows.append(
            {
                "system_name": entry["systemName"],
                "system_uri": entry["system"],
                "code": entry["code"],
                "display": entry.get("serverDisplay") or entry["expectedDisplay"],
                "used_by": "; ".join(entry["usedBy"]),
                "version": entry.get("version", ""),
                "lookup_url": link,
                "api_url": entry.get("apiUrl", ""),
                "verified": "yes" if entry["verified"] else "no",
            }
        )
    with open(OUT_TERMINOLOGY, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "system_name",
                "system_uri",
                "code",
                "display",
                "used_by",
                "version",
                "lookup_url",
                "api_url",
                "verified",
            ],
        )
        writer.writeheader()
        writer.writerows(terminology_rows)
    print(f"wrote {OUT_TERMINOLOGY.relative_to(ROOT)} ({len(terminology_rows)} codes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
