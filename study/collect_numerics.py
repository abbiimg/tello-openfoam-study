"""Read-only canonical numerical audit; requires the OpenFOAM 14 environment.

python3 collect_numerics.py --root CASES --out numerical_configurations.json

Uses prepare_mapped.solver_configuration without invoking any preparation,
mesher, mapping utility or solver. No case or geometry file is changed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys
import subprocess

sys.dont_write_bytecode = True
AUDIT_SCHEMA = "tello-readonly-numerical-audit-v1"
NUMERICAL_SCHEMA = "openfoam-foundation14-numerical-method-v1"
INPUTS = ("geometry.json", "system/fvSolution", "system/fvSchemes",
          "system/controlDict", "system/decomposeParDict")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configuration_digest(configuration):
    return hashlib.sha256(json.dumps(configuration, sort_keys=True,
        separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def input_records(case):
    return {relative: dict(sha256=digest(case / relative),
                          size_bytes=(case / relative).stat().st_size) for relative in INPUTS}


def load_audit(path):
    if path is None:
        return None
    payload = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if payload.get("schema") != AUDIT_SCHEMA or not isinstance(payload.get("cases"), dict):
        raise ValueError("unrecognized numerical audit schema")
    return payload


def case_numerics(case, geometry, audit=None):
    """Attach signatures only after checking current inputs against the audit."""
    case = Path(case)
    declared = geometry.get("solver_configuration_sha256")
    row = dict(numerical_method_signature=None, numerical_audit_valid=False,
        numerical_audit_status="not_supplied", declared_numerical_method_signature=declared,
        numerical_method_label="Unknown numerical method (no verified audit)",
        numerical_rank_count=None, numerical_direct_coarsest_p=None,
        numerical_direct_coarsest_pFinal=None)
    if audit is None:
        return row
    entry = audit["cases"].get(case.name)
    if entry is None:
        row["numerical_audit_status"] = "case_not_in_audit"
        return row
    if entry.get("status") != "ok":
        row["numerical_audit_status"] = "audit_collection_failed: " + str(entry.get("reason", "unknown"))
        return row
    configuration, signature = entry.get("solver_configuration"), entry.get("solver_configuration_sha256")
    if not isinstance(configuration, dict) or configuration.get("schema") != NUMERICAL_SCHEMA:
        row["numerical_audit_status"] = "invalid_canonical_configuration_schema"
        return row
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-f]{64}", signature):
        row["numerical_audit_status"] = "invalid_signature"
        return row
    if configuration_digest(configuration) != signature:
        row["numerical_audit_status"] = "canonical_configuration_digest_mismatch"
        return row
    if set(entry.get("input_files", {})) != set(INPUTS):
        row["numerical_audit_status"] = "incomplete_input_hashes"
        return row
    try:
        current = input_records(case)
    except OSError as exc:
        row["numerical_audit_status"] = "input_unavailable: " + str(exc)
        return row
    changed = [name for name in INPUTS if current[name] != entry["input_files"][name]]
    if changed:
        row["numerical_audit_status"] = "input_hash_mismatch: " + ", ".join(changed)
        return row
    if declared is not None and declared != signature:
        row["numerical_audit_status"] = "geometry_signature_disagrees_with_current_audit"
        return row
    try:
        ranks = configuration["decomposition"]["numberOfSubdomains"]
        if not isinstance(ranks, list) or len(ranks) != 1 or not re.fullmatch(r"[1-9]\d*", str(ranks[0])):
            raise ValueError("invalid rank token")
        direct = {}
        for field in ("p", "pFinal"):
            settings = configuration["fvSolution"]["solvers"][field]
            switch = settings["directSolveCoarsest"]
            if settings["solver"] != ["GAMG"] or switch not in (["true"], ["false"]):
                raise ValueError("invalid effective pressure solver switch")
            direct[field] = switch == ["true"]
        if entry.get("effective_direct_coarsest") != direct:
            raise ValueError("sibling direct metadata disagrees with signed configuration")
    except (KeyError, TypeError, ValueError):
        row["numerical_audit_status"] = "invalid_rank_or_direct_metadata"
        return row
    row.update(numerical_method_signature=signature, numerical_audit_valid=True,
        numerical_audit_status="current_input_hashes_and_canonical_digest_verified",
        numerical_rank_count=int(ranks[0]) if len(ranks) == 1 else None,
        numerical_direct_coarsest_p=direct.get("p"),
        numerical_direct_coarsest_pFinal=direct.get("pFinal"))
    row['numerical_method_label'] = (f'{row["numerical_rank_count"]} rank(s), pressure direct-coarsest '
        f'{"on" if direct.get("p") else "off"} · {signature[:12]}')
    return row


def collect(root, out):
    # Importing this module for analysis never requires an OpenFOAM executable.
    from prepare_mapped import solver_configuration
    root, out = Path(root).resolve(), Path(out)
    cases = {}
    for gp in sorted(root.rglob("geometry.json")):
        geometry = json.loads(gp.read_text(encoding="utf-8-sig"))
        if not all(k in geometry for k in ("rotors", "battery_power_W", "tilt_deg")):
            continue
        case = gp.parent
        if case.name in cases:
            raise ValueError(f"duplicate case name in audit root: {case.name}")
        entry = dict(case=case.name, case_path=str(case))
        try:
            before = input_records(case)
            for relative in INPUTS[1:]:
                if re.search(r"#(?:include\w*|codeStream|calc|eval)\b",
                             (case / relative).read_text()):
                    raise ValueError(f"unhashed external/code directive in {relative}")
            configuration, signature, direct = solver_configuration(case)
            after = input_records(case)
            if before != after:
                raise ValueError("case inputs changed during read-only audit")
            entry.update(status="ok", input_files=after,
                solver_configuration=configuration, solver_configuration_sha256=signature,
                effective_direct_coarsest=direct,
                input_hashes_stable_during_collection=True)
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            entry.update(status="error", reason=str(exc))
        cases[case.name] = entry
    payload = dict(schema=AUDIT_SCHEMA, generated_utc=datetime.now(timezone.utc).isoformat(),
        case_root=str(root), cases=cases,
        collector_sha256=digest(Path(__file__)),
        canonicalizer_sha256=digest(Path(__file__).with_name("prepare_mapped.py")),
        interpretation="Canonical effective Foundation 14 numerical dictionaries; rank count comes from the case decomposition input, not independent inspection of the executing process",
        signature_excludes="Physical geometry, initial state, averaging/end times and output scheduling; those remain separate comparison requirements")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(cases=len(cases), audited=sum(e.get("status") == "ok" for e in cases.values()),
                          errors={n:e.get("reason") for n,e in cases.items() if e.get("status") != "ok"}, out=str(out)), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--out", default=str(Path(__file__).with_name("numerical_configurations.json")))
    args = parser.parse_args()
    collect(args.root, args.out)
