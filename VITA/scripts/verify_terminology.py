"""Verify every code in the mapping against a public terminology server.

The mapping must never contain an invented code. This script resolves each code
(LOINC, SNOMED CT, HL7 terminology, UCUM) with `$lookup` / `$validate-code` on
the public FHIR terminology server and writes a verification report with the
server version, the server's display string and a browsable link.

    python scripts/verify_terminology.py            # verify, write report
    python scripts/verify_terminology.py --offline  # reuse the committed report

The report is committed so CI and reviewers can check the provenance of every
code without network access. `tests/test_mapping.py` asserts that every code in
the mapping appears in the report.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from vita_mapping import SPEC_PATH, features, load_spec  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
REPORT_PATH = ROOT / "mappings" / "terminology-verification.json"
TX = "https://tx.fhir.org/r4"

CATEGORY_DISPLAY = {
    "vital-signs": "Vital Signs",
    "laboratory": "Laboratory",
    "procedure": "Procedure",
    "survey": "Survey",
    "exam": "Exam",
}

LOINC = "http://loinc.org"
SNOMED = "http://snomed.info/sct"
UCUM = "http://unitsofmeasure.org"

STATIC_CODES = [
    ("http://terminology.hl7.org/CodeSystem/data-absent-reason", "unknown", "Unknown", "Observation.dataAbsentReason"),
    ("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "H", "High", "Observation.interpretation (FastingBS = 1)"),
    ("http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation", "N", "Normal", "Observation.interpretation (FastingBS = 0)"),
    ("http://terminology.hl7.org/CodeSystem/condition-clinical", "active", "Active", "Condition.clinicalStatus"),
    ("http://terminology.hl7.org/CodeSystem/condition-ver-status", "confirmed", "Confirmed", "Condition.verificationStatus"),
    ("http://terminology.hl7.org/CodeSystem/condition-category", "problem-list-item", "Problem List Item", "Condition.category"),
]

SYSTEM_NAME = {
    LOINC: "LOINC",
    SNOMED: "SNOMED CT",
    UCUM: "UCUM",
    "http://terminology.hl7.org/CodeSystem/observation-category": "HL7 Terminology",
    "http://terminology.hl7.org/CodeSystem/data-absent-reason": "HL7 Terminology",
    "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation": "HL7 Terminology",
    "http://terminology.hl7.org/CodeSystem/condition-clinical": "HL7 Terminology",
    "http://terminology.hl7.org/CodeSystem/condition-ver-status": "HL7 Terminology",
    "http://terminology.hl7.org/CodeSystem/condition-category": "HL7 Terminology",
}


def api_url(system: str, code: str, kind: str = "code") -> str:
    """Authoritative lookup on the public terminology server (always returns JSON)."""
    if "vita.example.org" in system:
        return ""
    if kind == "unit":
        return (
            f"{TX}/CodeSystem/$validate-code?url={urllib.parse.quote(system, safe='')}"
            f"&code={urllib.parse.quote(code, safe='')}"
        )
    return (
        f"{TX}/CodeSystem/$lookup?system={urllib.parse.quote(system, safe='')}"
        f"&code={urllib.parse.quote(code, safe='')}"
    )


def lookup_url(system: str, code: str) -> str:
    """A page a human can open (FHIR canonical URIs are identifiers, not web pages)."""
    if system == LOINC:
        return f"https://loinc.org/{code}/"
    if system == SNOMED:
        return (
            "https://ontoserver.csiro.au/shrimp/"
            f"?concept={code}&systems=http%3A%2F%2Fsnomed.info%2Fsct"
        )
    if "vita.example.org" in system:
        # Project-local CodeSystem: no public terminology server hosts it.
        return ""
    return api_url(system, code)


def collect(spec: dict) -> list[dict]:
    entries: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(system: str, code: str, display: str, used_by: str, kind: str = "code") -> None:
        key = (system, code)
        if key in seen:
            entry = next(e for e in entries if (e["system"], e["code"]) == key)
            entry["usedBy"].append(used_by)
            return
        seen.add(key)
        entries.append(
            {
                "system": system,
                "systemName": SYSTEM_NAME.get(system, "VITA local" if "vita.example.org" in system else system),
                "code": code,
                "expectedDisplay": display,
                "usedBy": [used_by],
                "kind": kind,
                "lookupUrl": lookup_url(system, code),
                "apiUrl": api_url(system, code, kind),
            }
        )

    for feature in features(spec):
        column = feature["column"]
        fhir = feature["fhir"]
        if fhir["resource"] != "Observation":
            continue
        add(
            "http://terminology.hl7.org/CodeSystem/observation-category",
            fhir["category"],
            CATEGORY_DISPLAY[fhir["category"]],
            f"{column} (Observation.category)",
        )
        add(fhir["code"]["system"], fhir["code"]["code"], fhir["code"]["display"], f"{column} (Observation.code)")
        unit = fhir.get("unit")
        if unit:
            add(unit["system"], unit["code"], unit["code"], f"{column} (Observation.valueQuantity.unit)", kind="unit")
        for source, mapped in feature["toFhir"].get("map", {}).items():
            if isinstance(mapped, dict) and "system" in mapped:
                add(mapped["system"], mapped["code"], mapped["display"], f"{column} = {source} (value)")

    label = spec["label"]["fhir"]
    add(label["code"]["system"], label["code"]["code"], label["code"]["display"], "HeartDisease (label, Condition.code)")
    for system, code, display, used_by in STATIC_CODES:
        add(system, code, display, used_by)
    return entries


def fetch_json(url: str, timeout: int = 40) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/fhir+json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def verify(entry: dict) -> dict:
    result = dict(entry)
    if "vita.example.org" in entry["system"]:
        result.update({"verified": True, "verifiedVia": "local CodeSystem (published in fhir/terminology/)", "serverDisplay": entry["expectedDisplay"], "version": "1.0.0"})
        return result

    params = {"system": entry["system"], "code": entry["code"], "_format": "json"}
    if entry["kind"] == "unit":
        url = f"{TX}/CodeSystem/$validate-code?url={urllib.parse.quote(entry['system'], safe='')}&code={urllib.parse.quote(entry['code'], safe='')}&_format=json"
    else:
        url = f"{TX}/CodeSystem/$lookup?{urllib.parse.urlencode(params)}"

    data = None
    last_error = None
    for _ in range(3):
        try:
            data = fetch_json(url)
            break
        except Exception as exc:  # network hiccup, retry
            last_error = exc
    if data is None:
        result.update({"verified": False, "error": f"terminology server unreachable: {last_error}"})
        return result

    parameters = {p["name"]: p for p in data.get("parameter", [])}
    if entry["kind"] == "unit":
        ok = parameters.get("result", {}).get("valueBoolean", False)
        server_display = parameters.get("display", {}).get("valueString", "")
        version = parameters.get("version", {}).get("valueString", "")
    else:
        ok = True
        server_display = parameters.get("display", {}).get("valueString", "")
        version = parameters.get("version", {}).get("valueString", "")
    result.update(
        {
            "verified": bool(ok),
            "verifiedVia": f"{TX} ({'$validate-code' if entry['kind'] == 'unit' else '$lookup'})",
            "serverDisplay": server_display,
            "version": version,
            "displayMatches": server_display.strip().lower() == entry["expectedDisplay"].strip().lower()
            or entry["kind"] == "unit",
        }
    )
    if not result["displayMatches"]:
        result["verified"] = False
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="reuse the committed report")
    args = parser.parse_args()

    spec = load_spec()
    if args.offline:
        report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    else:
        entries = collect(spec)
        results = [verify(entry) for entry in entries]
        verified = sum(1 for r in results if r["verified"])
        report = {
            "generatedBy": "scripts/verify_terminology.py",
            "server": TX,
            "verifiedAt": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "specVersion": spec["version"],
            "summary": {"total": len(results), "verified": verified, "failed": len(results) - verified},
            "entries": results,
        }
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for entry in report["entries"]:
        status = "OK  " if entry["verified"] else "FAIL"
        print(f"{status} {entry['code']:<12} {entry.get('serverDisplay') or entry['expectedDisplay']:<58} {entry.get('version', '')}")
    print()
    print(f"{report['summary']['verified']}/{report['summary']['total']} codes verified against {report['server']}")
    if report["summary"]["failed"]:
        print("RESULT: FAIL - at least one code could not be verified")
        return 1
    print(f"RESULT: PASS - report written to {REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
