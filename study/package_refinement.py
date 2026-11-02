"""Finalize approved Tello cases, verify complete ZIP CRCs and build setup ZIP.

Run only at final handoff with --approved-cases pointing to a frozen JSON list
of case names (or {"cases": [names]}). The list must match every actual case
directory; no fixed count or live execution manifest can finalize the study.
"""
from pathlib import Path
import argparse
import json
import zipfile
from archive_completed import (EXPECTED_SOURCE_SHA256, actual_cases, add_case, archive_lock,
                               atomic_json, case_files, read_index, recover_pending_index,
                               retry_sharing, validate_case, verify_archive)


def main(args):
    root, out = Path(args.root), Path(args.out)
    approval_path = Path(args.approved_cases).resolve()
    approved = json.loads(approval_path.read_text())
    approved = approved['cases'] if isinstance(approved, dict) else approved
    if (not isinstance(approved, list) or not approved or
            any(not isinstance(name, str) or Path(name).name != name for name in approved) or
            len(approved) != len(set(approved))):
        raise ValueError('Approved case list must contain unique plain case names')
    cases = actual_cases(root)
    if set(approved) != {case.name for case in cases}:
        raise ValueError('Frozen approved case list differs from actual case directories')
    if approval_path.parent != out.resolve():
        raise ValueError('Keep the frozen approved case list in the deliverable folder')
    with archive_lock(out, session=True):
        with archive_lock(out):
            recover_pending_index(root, out)
        checks = {case.name: validate_case(case) for case in cases}
        if {v['source_sha256'] for v in checks.values()} != {EXPECTED_SOURCE_SHA256}:
            raise ValueError('Source-model mismatch across approved cases')
        for case in cases:
            fresh, _ = add_case(case, out)
            if fresh:
                print(json.dumps(dict(event='archived_final', case=case.name)), flush=True)
        with archive_lock(out):
            if {case.name for case in actual_cases(root)} != set(approved):
                raise ValueError('Actual case set changed during final packaging')
            checked = verify_archive(root, out, full_crc=True)
            if set(checked) != set(approved):
                raise ValueError('Archive index differs from frozen approved case list')
            index = read_index(out)
        atomic_json(out / 'validation.json', checked)
        compact = out / 'setup_results.zip'
        temporary = out / '.setup_results.zip.updated'
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as z:
            for path in sorted(out.rglob('*')):
                if not path.is_file() or path.suffix in ('.gz', '.zip', '.pyc'):
                    continue
                relative = path.relative_to(out)
                if any(p.startswith('.') or p == '__pycache__' for p in relative.parts):
                    continue
                z.write(path, (Path('study') / relative).as_posix())
            for case in cases:
                for path in case_files(case, checked[case.name]):
                    rel = path.relative_to(case)
                    parts = rel.parts
                    include = (parts[0] in ('0', checked[case.name]['initial_time'], 'system') or
                               (parts[0] == 'constant' and len(parts) == 2) or
                               (len(parts) == 1 and (path.name in (
                                   'Allrun', 'geometry.json', 'run_status.json', 'case.foam',
                                   'initialization.json', 'prepare_mapped.py') or path.suffix == '.json'
                                   or path.name.startswith('log.'))))
                    if include:
                        z.write(path, (Path('cases') / case.name / rel).as_posix())
        with zipfile.ZipFile(temporary) as z:
            bad = z.testzip()
            if bad is not None:
                raise ValueError(f'Compact archive CRC error: {bad}')
        retry_sharing(lambda: temporary.replace(compact), compact, 'publish_verified_setup_zip')
        print(json.dumps(dict(validated_cases=len(checked),
                              zip_members=sum(len(v['snapshot']['files']) for v in index['cases'].values()),
                              cases_zip_bytes=(out / 'cases.zip').stat().st_size,
                              setup_results_zip_bytes=compact.stat().st_size,
                              source_sha256=EXPECTED_SOURCE_SHA256, archives_crc_ok=True)), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--out', default=str(Path(__file__).parent))
    parser.add_argument('--approved-cases', required=True)
    main(parser.parse_args())
