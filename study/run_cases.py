"""Run fresh supplied cold or mapped cases on Linux using their frozen runner.

Use a fresh generated/prepared root, not an archived completed case directory.
The original execution manifest records the actual connector-managed runs.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import argparse
import hashlib
import json
import re
import subprocess
import threading
import time


def ranks_and_runner(case, geometry):
    """Read current or legacy rank metadata and require a matching dictionary."""
    candidates = {}
    for label, metadata in (('execution', geometry.get('execution', {})),
                            ('numerics', geometry.get('numerics', {}))):
        if metadata.get('mpi_ranks') is not None:
            candidates[label] = metadata['mpi_ranks']
    init = (json.loads((case/'initialization.json').read_text())
            if (case/'initialization.json').is_file() else {})
    if init.get('mpi_ranks') is not None:
        candidates['initialization'] = init['mpi_ranks']
    text = (case/'system/decomposeParDict').read_text()
    text = re.sub(r'/\*[\s\S]*?\*/|//[^\n]*', '', text)
    counts = re.findall(r'\bnumberOfSubdomains\s+(\d+)\s*;', text)
    if len(counts) != 1:
        raise ValueError(f'Expected one explicit numberOfSubdomains in {case.name}')
    ranks = int(counts[0])
    if ranks not in (1, 2) or any(value != ranks for value in candidates.values()):
        raise ValueError(f'Rank metadata/dictionary mismatch in {case.name}: {candidates}, dictionary={ranks}')
    runner = case/'Allrun'
    if not runner.is_file():
        raise ValueError(f'Prepared runner missing: {case.name}')
    expected = geometry.get('execution', {}).get('runner_sha256')
    recorded = init.get('target_inputs_after_preparation', {}).get('Allrun', {}).get('sha256')
    actual = hashlib.sha256(runner.read_bytes()).hexdigest()
    if any(value != actual for value in (expected, recorded) if value is not None):
        raise ValueError(f'Frozen runner hash differs in {case.name}')
    return ranks, list(candidates) or ['decomposeParDict_legacy']


def atomic(path, value):
    temporary = path.with_name(path.name+'.updated')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', required=True)
    p.add_argument('--jobs', type=int, default=8, help='Concurrent cases; rank count comes from each case metadata')
    p.add_argument('--validate-only', action='store_true',
                   help='Check fresh cases, ranks and frozen runner hashes; write nothing and launch nothing')
    p.add_argument('cases', nargs='*', help='Case names; default all newly generated cases')
    a = p.parse_args()
    if a.jobs < 1:
        raise ValueError('--jobs must be positive')
    root = Path(a.root).resolve()
    names = a.cases or sorted(c.name for c in root.glob('*_n*') if c.is_dir())
    if not names:
        raise ValueError('No cases found')
    if len(names) != len(set(names)):
        raise ValueError('Duplicate case names would launch the same case more than once')
    records = []
    for name in names:
        case = (root/name).resolve()
        if case.parent != root:
            raise ValueError('Case names must refer directly to the given root')
        geometry = json.loads((case/'geometry.json').read_text())
        ranks, rank_sources = ranks_and_runner(case, geometry)
        if (any((case/path).exists() for path in
                ('run_status.json', 'log.foamRun', 'log.launch', '.warm-solver-started'))
                or any(case.glob('processor*'))):
            raise ValueError(f'Refusing previously started case: {name}')
        records.append(dict(case=name, state='queued', mpi_ranks=ranks,
                            rank_metadata_sources=rank_sources))
    manifest = root/'local_run_manifest.json'
    if a.validate_only:
        print(json.dumps(dict(validated=True, no_solver_launched=True,
                              no_files_written=True, cases=records), indent=2))
        return
    if manifest.exists():
        raise ValueError('Existing local_run_manifest.json; use a fresh run root')
    lock = threading.Lock()
    def save():
        atomic(manifest, dict(total_planned=len(records), cases=records))
    save()
    def run(record):
        case = root/record['case']
        with lock:
            record['state'] = 'running'
            save()
        started = time.monotonic()
        error = None
        try:
            with (case/'log.launch').open('x') as log:
                result = subprocess.run(['bash', str(case/'Allrun')], stdout=log, stderr=subprocess.STDOUT)
            code = result.returncode
        except Exception as exc:
            code, error = 1, f'{type(exc).__name__}: {exc}'
        status = dict(case=case.name, state='succeeded' if code == 0 else 'failed',
            returncode=code, elapsed_s=time.monotonic()-started, mpi_ranks=record['mpi_ranks'])
        if error:
            status['launch_error'] = error
        atomic(case/'run_status.json', status)
        with lock:
            record.update(status)
            save()
        print(json.dumps(status), flush=True)
        return code
    with ThreadPoolExecutor(max_workers=a.jobs) as executor:
        return_codes = list(executor.map(run, records))
    raise SystemExit(1 if any(return_codes) else 0)

if __name__ == '__main__':
    main()
