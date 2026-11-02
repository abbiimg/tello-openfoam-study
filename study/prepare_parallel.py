"""Install the supplied two-rank runner in newly generated, unstarted cases.

Generate a fresh case root first. Previously started cases are never changed.
Run this script on Linux; OpenFOAM runs should use a non-root account.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--owner', help='Optional owner:group for newly prepared cases; requires root')
    args = parser.parse_args()
    root, here = Path(args.root).resolve(), Path(__file__).resolve().parent
    runner = (here/'Allrun.template').read_text().replace('\r\n', '\n')
    decomposition = (here/'decomposeParDict.template').read_text().replace('\r\n', '\n')
    runner_hash = hashlib.sha256(runner.encode()).hexdigest()
    cases = sorted(c for c in root.glob('*_n*') if c.is_dir() and (c/'geometry.json').exists())
    prepared, unchanged = [], []
    for case in cases:
        assert case.resolve().is_relative_to(root)
        path = case/'geometry.json'
        geometry = json.loads(path.read_text())
        execution = geometry.get('execution', {})
        if execution.get('runner_sha256') == runner_hash:
            assert hashlib.sha256((case/'Allrun').read_bytes()).hexdigest() == runner_hash
            unchanged.append(case.name)
            continue
        if (case/'log.foamRun').exists() or (case/'processor0').exists():
            raise ValueError(f'Refusing to modify started case: {case.name}')
        (case/'Allrun').write_text(runner)
        (case/'Allrun').chmod(0o755)
        (case/'system/decomposeParDict').write_text(decomposition)
        geometry['execution'] = dict(mpi_ranks=2, threads_per_rank=1,
            decomposition='hierarchical (2 1 1)', start='cold uniform rest', runner_sha256=runner_hash)
        path.write_text(json.dumps(geometry, indent=2)+'\n')
        if args.owner:
            if os.geteuid() != 0:
                raise PermissionError('--owner requires root')
            subprocess.run(['chown', '-R', args.owner, str(case)], check=True)
        prepared.append(case.name)
    print(json.dumps(dict(prepared=prepared, unchanged_count=len(unchanged), runner_sha256=runner_hash), indent=2))

if __name__ == '__main__':
    main()
