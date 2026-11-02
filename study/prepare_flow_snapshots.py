"""Copy completed fields into separate visualization cases; never run a solver.

Run on the OpenFOAM host. The provenance records byte hashes of the source
mesh, geometry and fields, and verifies that copying left them unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, required=True)
    p.add_argument('--target-root', type=Path, required=True)
    p.add_argument('--case', action='append', required=True)
    p.add_argument('--time', default='1.2')
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--owner', help='Optional native owner:group for the render service')
    a = p.parse_args()
    source_root, target_root = a.source_root.resolve(), a.target_root.resolve()
    if source_root == target_root or source_root in target_root.parents or target_root in source_root.parents:
        raise ValueError('Visualization and simulation roots must be separate')
    records = []
    for name in a.case:
        if Path(name).name != name or name in ('.', '..'):
            raise ValueError('Case must be a single directory name')
        source, target = source_root / name, target_root / name
        if '\nEnd\n' not in (source / 'log.foamRun').read_text():
            raise ValueError(f'{name}: solver has not finished normally')
        geometry = json.loads((source / 'geometry.json').read_text())
        if float(a.time) > geometry['averaging_stop_s'] + 1e-9:
            raise ValueError('Requested snapshot lies beyond the experiment')
        relative = [Path('geometry.json'), Path('system/controlDict')]
        relative += [x.relative_to(source) for x in sorted((source / 'constant/polyMesh').iterdir()) if x.is_file()]
        relative += [Path(a.time) / f for f in ('U', 'p')]
        before = {str(f): digest(source / f) for f in relative}
        if target.exists():
            if any(not (target / f).is_file() or digest(target / f) != h for f, h in before.items()):
                raise FileExistsError(f'{target}: existing visualization copy differs')
        else:
            for f in relative:
                (target / f).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source / f, target / f)
            (target / 'case.foam').touch()
            if a.owner:
                subprocess.run(['chown', '-R', a.owner, str(target)], check=True)
        copied = {str(f): digest(target / f) for f in relative}
        after = {str(f): digest(source / f) for f in relative}
        if before != copied or before != after:
            raise RuntimeError('Source/copy verification failed')
        records.append(dict(source_case=str(source), visualization_copy=str(target),
            snapshot_time_s=float(a.time), source_hashes=before, copied_hashes=copied,
            source_unchanged=True, layout=geometry.get('layout'), rotors=geometry['rotors'],
            nearest_spacing_m=geometry.get('nearest_spacing_m')))
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    a.manifest.write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(dict(manifest=str(a.manifest), copied_cases=len(records))))


if __name__ == '__main__':
    main()
