"""Finalize explicitly selected completed Tello cases and verify ZIP CRCs.

Run only at final handoff with --approved-cases pointing to a frozen JSON list
of case names (or {"cases": [names]}). Unrun prepared inputs may remain in the
root; indexed or otherwise completed data must never be silently omitted.
"""
from pathlib import Path, PurePosixPath
import argparse
import json
import zipfile
from archive_completed import (EXPECTED_SOURCE_SHA256, IncompleteCase, actual_cases,
                               add_case, archive_lock, atomic_json, case_files,
                               digest, read_index, recover_pending_index,
                               retry_sharing, validate_case, verify_archive)


GPU_REPRODUCTION_ARCHIVES = frozenset((
    'gpu_feasibility/OGL_upstream_7c3ced4514fb.tar.gz',
    'gpu_feasibility/Ginkgo_upstream_13c917436066.tar.gz',
    'gpu_feasibility/benchmark_reproduction/shared_seed.zip',
))


def approved_selection(path, root, out):
    if path.is_symlink():
        raise ValueError('Frozen approved case list must not be a symlink')
    path = path.resolve()
    if path.parent != out:
        raise ValueError('Keep the frozen approved case list in the deliverable folder')
    approved = json.loads(path.read_text())
    if isinstance(approved, dict):
        if set(approved) != {'cases'}:
            raise ValueError('Approved object must contain only the cases list')
        approved = approved['cases']
    if (not isinstance(approved, list) or not approved or
            any(not isinstance(name, str) or name in ('', '.', '..') or
                Path(name).name != name or '\\' in name or ':' in name for name in approved) or
            len(approved) != len(set(approved))):
        raise ValueError('Approved case list must contain unique plain case names')
    discovered = actual_cases(root)
    by_name = {case.name: case for case in discovered}
    unknown = set(approved) - set(by_name)
    if unknown:
        raise ValueError('Approved case names are absent from the direct prepared root: ' +
                         ', '.join(sorted(unknown)))
    cases = [by_name[name] for name in sorted(approved)]
    if any(case.is_symlink() or case.resolve().parent != root for case in cases):
        raise ValueError('Approved case directories must be direct non-symlink children of the root')
    direct_geometry = {case / 'geometry.json' for case in discovered}
    nested = sorted(path.relative_to(root).as_posix() for path in root.rglob('geometry.json')
                    if path not in direct_geometry)
    return path, cases, dict(
        approval_file=str(path), approval_sha256=digest(path),
        selected_cases=sorted(approved), selected_case_count=len(approved),
        direct_prepared_cases=sorted(by_name), direct_prepared_case_count=len(by_name),
        excluded_direct_prepared_inputs=sorted(set(by_name) - set(approved)),
        nested_template_geometry_paths=nested,
        selection_policy='All normally completed experiments, including controls and unqualified measurements; unrun prepared inputs and nested templates are separate')


def require_index_subset(index, approved, label):
    omitted = set(index['cases']) - approved
    if omitted:
        raise ValueError(f'{label} contains completed case data omitted by approval: ' +
                         ', '.join(sorted(omitted)))


def require_excluded_incomplete(root, excluded):
    for name in excluded:
        try:
            validate_case(root / name)
        except IncompleteCase:
            continue
        raise ValueError('Completed case omitted by approval: ' + name)


def frozen_compact_inputs(case):
    """Retain verified portable frozen dependencies, while rebuilding the mesh."""
    manifest = case / 'initialization.json'
    if not manifest.is_file():
        return set()
    records = json.loads(manifest.read_text())['target_inputs_after_preparation']
    if not isinstance(records, dict):
        raise ValueError(f'{case.name}: frozen target inputs must be an object')
    resolved_case = case.resolve(strict=True)
    result = set()
    for name in records:
        if not isinstance(name, str):
            raise ValueError(f'{case.name}: frozen input paths must be strings')
        relative = PurePosixPath(name)
        if (relative.is_absolute() or not relative.parts or '..' in relative.parts or
                '\\' in name or ':' in relative.parts[0]):
            raise ValueError(f'{case.name}: unsafe frozen compact input: {name!r}')
        target = case
        for part in relative.parts:
            target = target / part
            if target.is_symlink():
                raise ValueError(f'{case.name}: frozen compact input must be non-symlink: {name!r}')
        try:
            target.resolve(strict=True).relative_to(resolved_case)
        except (OSError, ValueError) as exc:
            raise ValueError(f'{case.name}: frozen compact input is absent or outside its case: {name!r}') from exc
        if not target.is_file():
            raise ValueError(f'{case.name}: frozen compact input is not a file: {name!r}')
        if relative.parts[:2] != ('constant', 'polyMesh'):
            result.add(relative.as_posix())
    return result


def main(args):
    root, out = Path(args.root).resolve(), Path(args.out).resolve()
    approval_path, cases, scope = approved_selection(Path(args.approved_cases), root, out)
    approved = set(scope['selected_cases'])
    direct_names = set(scope['direct_prepared_cases'])
    if (out / 'gpu_feasibility/benchmark_evidence_manifest.json').is_file():
        missing = sorted(name for name in GPU_REPRODUCTION_ARCHIVES if not (out / name).is_file())
        if missing:
            raise ValueError('GPU reproduction dependencies are missing: ' + ', '.join(missing))
    with archive_lock(out, session=True):
        with archive_lock(out):
            pending = out / 'archive_index.json.updated'
            # The first closed ZIP commit may have only a pending index.
            # Preserve the existing recovery path rather than rejecting it as
            # an archive with no committed index before recovery can run.
            if (out / 'archive_index.json').exists() or not pending.exists():
                require_index_subset(read_index(out), approved, 'Archive index')
            if pending.exists():
                require_index_subset(json.loads(pending.read_text()), approved, 'Pending archive index')
            recover_pending_index(root, out)
            require_index_subset(read_index(out), approved, 'Recovered archive index')
        require_excluded_incomplete(root, scope['excluded_direct_prepared_inputs'])
        checks = {case.name: validate_case(case) for case in cases}
        if {v['source_sha256'] for v in checks.values()} != {EXPECTED_SOURCE_SHA256}:
            raise ValueError('Source-model mismatch across approved cases')
        compact_inputs = {case.name: frozen_compact_inputs(case) for case in cases}
        for case in cases:
            fresh, _ = add_case(case, out)
            if fresh:
                print(json.dumps(dict(event='archived_final', case=case.name)), flush=True)
        with archive_lock(out):
            if {case.name for case in actual_cases(root)} != direct_names:
                raise ValueError('Direct prepared case set changed during final packaging')
            require_excluded_incomplete(root, scope['excluded_direct_prepared_inputs'])
            checked = verify_archive(root, out, full_crc=True)
            if set(checked) != approved:
                raise ValueError('Archive index differs from frozen approved case list')
            index = read_index(out)
        if digest(approval_path) != scope['approval_sha256']:
            raise ValueError('Frozen approved case list changed during final packaging')
        atomic_json(out / 'validation.json', checked)
        atomic_json(out / 'packaging_scope.json', scope)
        compact = out / 'setup_results.zip'
        temporary = out / '.setup_results.zip.updated'
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as z:
            for path in sorted(out.rglob('*')):
                if not path.is_file() or path.suffix == '.pyc':
                    continue
                relative = path.relative_to(out)
                if path.suffix in ('.gz', '.zip') and relative.as_posix() not in GPU_REPRODUCTION_ARCHIVES:
                    continue
                if any(p.startswith('.') or p == '__pycache__' for p in relative.parts):
                    continue
                z.write(path, (Path('study') / relative).as_posix())
            for case in cases:
                for path in case_files(case, checked[case.name]):
                    rel = path.relative_to(case)
                    parts = rel.parts
                    include = (parts[0] in ('0', checked[case.name]['initial_time'], 'system') or
                               (parts[0] == 'constant' and len(parts) == 2) or
                               rel.as_posix() in compact_inputs[case.name] or
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
        if digest(approval_path) != scope['approval_sha256']:
            raise ValueError('Frozen approved case list changed during compact packaging')
        retry_sharing(lambda: temporary.replace(compact), compact, 'publish_verified_setup_zip')
        print(json.dumps(dict(validated_cases=len(checked),
                              excluded_direct_prepared_inputs=len(scope['excluded_direct_prepared_inputs']),
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
