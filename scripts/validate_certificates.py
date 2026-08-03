#!/usr/bin/env python3
"""Stdlib-only validator for every committed `certificates/h*.json`. [SOUND]

Checks each certificate for the shared schema-family fields (see
docs/release-checklist.md), the fixed core-claim values, valid gate
soundness/result vocabulary, an aggregate PASS, and that every source
file hash the certificate claims still matches that file's CURRENT
content - detecting silent drift between code and the last-emitted
certificate. A certificate is not required to list every file currently
under `horizon/`: certificates are frozen at generation time, so an
older certificate legitimately predates newer modules. What must never
happen is a hash the certificate DOES claim failing to match reality.

Exits non-zero with a precise, itemized message on any failure.
"""
import glob
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# NOTE: `seeds` is deliberately NOT in this mandatory set. H2-H5 record a
# `seeds` list; H1 predates that convention and, under this project's
# additive-only discipline (existing files are edited only for README
# Roadmap lines or .gitignore appends - see docs/release-checklist.md),
# `scripts/run_h1.py` is not retrofitted to add one. This is a recorded
# asymmetry, not silently ignored: see docs/release-checklist.md.
MANDATORY_FIELDS = {
    "certificate_version": str,
    "benchmark_id": str,
    "program": str,
    "claim_class": str,
    "execution_tier": str,
    "promotion_allowed": bool,
    "empirical_claim": str,
    "adversary_model": str,
    "heuristic_warnings": list,
    "unit_convention": dict,
    "gates": list,
    "aggregate": str,
    "source_hashes": dict,
    "python_version": str,
}
VALID_SOUNDNESS_TAGS = {"SOUND", "HEURISTIC"}
VALID_GATE_RESULTS = {"PASS", "FAIL", "EXPECTED_ATTACK_SUCCESS"}


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def validate_certificate(path):
    errors = []
    with open(path) as f:
        cert = json.load(f)

    for field, typ in MANDATORY_FIELDS.items():
        if field not in cert:
            errors.append(f"missing mandatory field '{field}'")
        elif not isinstance(cert[field], typ):
            errors.append(f"field '{field}' has type "
                          f"{type(cert[field]).__name__}, expected {typ.__name__}")

    if cert.get("claim_class") != "ENGINEERING_REFERENCE":
        errors.append("claim_class must be 'ENGINEERING_REFERENCE', got "
                      f"{cert.get('claim_class')!r}")
    if cert.get("execution_tier") != "BENCHMARK":
        errors.append(f"execution_tier must be 'BENCHMARK', got {cert.get('execution_tier')!r}")
    if cert.get("promotion_allowed") is not False:
        errors.append(f"promotion_allowed must be false, got {cert.get('promotion_allowed')!r}")
    if cert.get("empirical_claim") != "NONE":
        errors.append(f"empirical_claim must be 'NONE', got {cert.get('empirical_claim')!r}")
    if cert.get("aggregate") != "PASS":
        errors.append(f"aggregate must be 'PASS', got {cert.get('aggregate')!r}")

    for gate in cert.get("gates", []):
        gid = gate.get("gate")
        tag = gate.get("soundness_tag")
        if tag not in VALID_SOUNDNESS_TAGS:
            errors.append(f"gate {gid!r} has invalid soundness_tag {tag!r}")
        result = gate.get("result")
        if result not in VALID_GATE_RESULTS:
            errors.append(f"gate {gid!r} has invalid result {result!r}")

    for rel_path, claimed_hash in cert.get("source_hashes", {}).items():
        abs_path = os.path.join(ROOT, rel_path)
        if not os.path.isfile(abs_path):
            errors.append(f"source_hashes references missing file '{rel_path}'")
            continue
        actual_hash = sha256_file(abs_path)
        if actual_hash != claimed_hash:
            errors.append(f"'{rel_path}' has drifted from its certified hash "
                          f"(certificate: {claimed_hash}, actual: {actual_hash})")

    return errors


def main():
    cert_paths = sorted(glob.glob(os.path.join(ROOT, "certificates", "h*_certificate.json")))
    if not cert_paths:
        print("no certificates found under certificates/", file=sys.stderr)
        return 1

    all_ok = True
    for path in cert_paths:
        rel = os.path.relpath(path, ROOT)
        errors = validate_certificate(path)
        if errors:
            all_ok = False
            print(f"{rel}: FAIL")
            for e in errors:
                print(f"  - {e}")
        else:
            print(f"{rel}: OK")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
