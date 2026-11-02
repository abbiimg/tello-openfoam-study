"""Prepare fresh reproducible cases from the extracted delivered cases/ directory.

The default delivered mode preserves each case's actual initialization, frozen
runner and numerical settings. It copies only inputs, the initial fields and
the mesh (if supplied), never evolved fields or logs. Missing meshes are rebuilt
with blockMesh. Run on Linux with OpenFOAM 14 loaded, then use run_cases.py.

Parameter mode regenerates selected LEGACY square cold-start cases with
generate_tello.py. New planform/count pilots use delivered mode, or their
explicit generate_layout_pilots.py command; nearest spacing is not square d.
Mapped cases require delivered mode, or an explicit new same-geometry mapping
with prepare_mapped.py after running the coarse screening case to 0.6 s.
"""
from pathlib import Path
from pathlib import PurePosixPath
import argparse
import hashlib
import json
import math
import shlex
import shutil
import subprocess
import sys


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def relative_input(value):
    path = PurePosixPath(value)
    if path.is_absolute() or '..' in path.parts or '\\' in value or not path.parts:
        raise ValueError(f'Unsafe frozen input path: {value!r}')
    return Path(*path.parts)


def rebuild_missing_mesh(target):
    if (target/'constant/polyMesh/points').is_file():
        return False
    for command in ('blockMesh', 'checkMesh'):
        if not shutil.which(command):
            raise ValueError(f'{command} required to rebuild the omitted mesh; load OpenFOAM 14')
        with (target/f'log.{command}.reproduction').open('x') as log:
            subprocess.run([command, '-case', str(target)], check=True,
                           stdout=log, stderr=subprocess.STDOUT)
    if 'Mesh OK.' not in (target/'log.checkMesh.reproduction').read_text():
        raise ValueError('Reproduced mesh did not pass checkMesh')
    return True


def copy_case_marker(source, target):
    """Supply ParaView's marker while leaving the delivered source untouched."""
    if (source/'case.foam').is_file():
        shutil.copy2(source/'case.foam', target/'case.foam')
    else:
        (target/'case.foam').touch(exist_ok=False)


def copy_delivered(source, target, geometry):
    target.mkdir()
    for name in ('constant', 'system'):
        shutil.copytree(source/name, target/name)
    if (source/'0').is_dir():
        shutil.copytree(source/'0', target/'0')
    for name in ('geometry.json', 'Allrun', 'prepare_mapped.py', 'initialization.json', 'cold_preparation.json',
                 'solver_variant_audit.json'):
        if (source/name).is_file():
            shutil.copy2(source/name, target/name)
    if not (target/'Allrun').is_file():
        raise ValueError(f'Delivered runner missing: {source.name}')
    (target/'Allrun').chmod(0o755)
    manifest = (json.loads((source/'initialization.json').read_text())
                if (source/'initialization.json').is_file() else {})
    mapped = bool(manifest.get('mapped_fields')) or geometry.get('initialization_family') == 'mapped'
    if mapped:
        initial = str(manifest['source_time_directory'])
        initial_path = relative_input(initial)
        if len(initial_path.parts) != 1 or not math.isfinite(float(initial)) or float(initial) <= 0:
            raise ValueError('Mapped initial directory must be one positive numeric time')
        start = float(manifest['target_start_time_s'])
        if float(initial) != start or not math.isclose(start,
                float(geometry.get('initialization_start_time_s', start)), abs_tol=1e-9, rel_tol=0):
            raise ValueError('Mapped initial time differs from geometry metadata')
        (target/initial).mkdir()
        for field in ('U', 'p'):
            shutil.copy2(source/initial/field, target/initial/field)
        # A frozen helper may depend on additional input/audit files. Preserve
        # every recorded input, rather than a fixed list of root filenames.
        for name, record in manifest['target_inputs_after_preparation'].items():
            relative = relative_input(name)
            if relative.parts[0].startswith(('processor', 'log.')) or relative.parts[0] == 'dynamicCode':
                raise ValueError(f'Unexpected evolved/log file in frozen input group: {name}')
            try:
                numeric_time = float(relative.parts[0])
            except ValueError:
                numeric_time = None
            if numeric_time is not None and numeric_time not in (0, start):
                raise ValueError(f'Evolved time in frozen input group: {name}')
            original, fresh = source/relative, target/relative
            if not original.is_file():
                if name.startswith('constant/polyMesh/'):
                    continue  # Omitted setup mesh is reconstructed below.
                raise FileNotFoundError(f'Required frozen input absent: {original}')
            if digest(original) != record['sha256']:
                raise ValueError(f'Delivered frozen input changed: {name}')
            fresh.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, fresh)
    elif not (target/'0/U').is_file() or not (target/'0/p').is_file():
        raise ValueError(f'Cold initial U,p missing: {source.name}')
    (target/'Allrun').chmod(0o755)
    copy_case_marker(source, target)
    rebuilt = rebuild_missing_mesh(target)
    if mapped:
        for group in ('target_inputs_after_preparation', 'target_mesh', 'mapped_fields'):
            for name, record in manifest[group].items():
                if digest(target/relative_input(name)) != record['sha256']:
                    raise ValueError(f'Reproduced frozen input/mesh/initial field differs: {name}')
        subprocess.run([sys.executable, str(target/'prepare_mapped.py'),
                        '--case', str(target), '--verify-only'], check=True)
    return dict(case=source.name, initialization='mapped' if mapped else 'cold',
                mesh_rebuilt=rebuilt, copied_evolved_fields=False, copied_solver_logs=False,
                frozen_initialization_verified=mapped,
                cold_preparation_preserved=(target/'cold_preparation.json').is_file(),
                cold_preparation_sha256=(digest(target/'cold_preparation.json')
                    if (target/'cold_preparation.json').is_file() else None))


def require_legacy_parameter_cases(paths, root):
    """Reject changed distance/layout meanings BEFORE generating any files."""
    unsupported=[]
    for path in paths:
        g=json.loads(path.read_text())
        if (g.get('layout','square_perimeter')!='square_perimeter'
            or g.get('distance_parameter_definition')
            or g.get('purpose')=='layout_comparison'
            or (path.parent/'cold_preparation.json').is_file()):
            unsupported.append((path,g))
    if not unsupported:
        return
    source=paths[0].parent.parent
    delivered=[sys.executable,str(Path(__file__).resolve()),'--inputs',str(source),
               '--root',str(root),'--mode','delivered']+[path.parent.name for path in paths]
    message=('Parameter mode only accepts legacy square-half-side d inputs. '
        'These selected cases carry custom layout, nearest-spacing semantics or frozen serial cold preparation: '
        +', '.join(path.parent.name for path,_ in unsupported)+'. '
        'They must not be passed to generate_tello.py (whose distances are square d in 0–10 cm). '
        'Exact input-copy command: '+shlex.join(delivered)+'.')
    if all(g.get('purpose')=='layout_comparison' and g.get('experiment_stage') in
           ('layout_pilot','rotor_count_pilot') and g.get('level')=='coarse'
           and abs(float(g['tilt_deg']))<1e-10
           and math.isclose(float(g.get('comparison_footprint_width_m',0)),.2362,abs_tol=1e-10,rel_tol=0)
           and math.isclose(float(g.get('comparison_footprint_depth_m',0)),.2362,abs_tol=1e-10,rel_tol=0)
           for _,g in unsupported):
        stages={g['experiment_stage'] for _,g in unsupported}
        stage=('all' if len(stages)>1 else 'layout' if stages=={'layout_pilot'} else 'rotor_count')
        command=[sys.executable,str(Path(__file__).with_name('generate_layout_pilots.py').resolve()),
            '--root',str(root),'--journal',str(root.parent/(root.name+'_layout_preparation.json')),
            '--stage',stage]
        message+=' To regenerate the supplied matched flat 23.62 cm layout/count pilot family, run '+shlex.join(command)+'.'
    raise ValueError(message+' No cases were generated.')


def regenerate(path, root, generator):
    require_legacy_parameter_cases([path],root)
    g = json.loads(path.read_text())
    if (path.parent/'initialization.json').exists() or g.get('initialization_family') == 'mapped':
        raise ValueError(f'Use delivered mode for mapped case {path.parent.name}')
    command = [sys.executable, str(generator), '--root', str(root),
        '--rotors', str(g['rotors']), '--powers', str(g['battery_power_W']),
        '--distances', str(g['distance_cm']), '--angles', str(g['tilt_deg']),
        '--level', g['level'], '--diameter', str(g['diameter_m']),
        '--thickness', str(g['thickness_m']), '--domain-xy', str(g['domain_xy_m']),
        '--end', str(g.get('configured_end_time_s', g['averaging_stop_s'])),
        '--average-duration', str(g['averaging_stop_s']-g['averaging_start_s'])]
    if g.get('tag'):
        command += ['--tag', g['tag']]
    if g.get('study_role'):
        command += ['--study-role', g['study_role']]
    subprocess.run(command, check=True)
    fresh = root/path.parent.name/'geometry.json'
    if not fresh.is_file():
        raise ValueError(f'Case naming differs from delivered case: {path.parent.name}')
    result = json.loads(fresh.read_text())
    for key in ('rotors', 'battery_power_W', 'distance_cm', 'tilt_deg', 'diameter_m',
                'thickness_m', 'domain_xy_m', 'mesh_cells', 'averaging_start_s', 'averaging_stop_s'):
        if not math.isclose(float(g[key]), float(result[key]), rel_tol=1e-10, abs_tol=1e-10):
            raise ValueError(f'Regenerated parameter differs: {path.parent.name}/{key}')
    if result['source_sha256'] != g['source_sha256']:
        raise ValueError('Generated source version differs from delivered metadata')
    target = fresh.parent
    for name in ('fvModels', 'rotorParameters', 'physicalProperties', 'momentumTransport'):
        source_file, generated = path.parent/'constant'/name, target/'constant'/name
        if source_file.is_file() and digest(source_file) != digest(generated):
            raise ValueError(f'Generated physics/parameters differ: {path.parent.name}/{name}; use delivered mode')
    # Runtime extensions and recorded numerical controls are not all encoded
    # as generator options. Retain the supplied final controls and methods.
    for name in ('controlDict', 'fvSolution', 'fvSchemes'):
        original = path.parent/'system'/name
        if not original.is_file():
            raise FileNotFoundError(f'Recorded numerical input missing: {original}')
        shutil.copy2(original, target/'system'/name)
    return dict(case=path.parent.name, initialization='cold', mesh_rebuilt=False,
                copied_recorded_numerical_controls=True, generated_source_verified=True,
                copied_evolved_fields=False, copied_solver_logs=False)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', required=True, help='Extracted cases directory containing geometry.json files')
    p.add_argument('--root', required=True, help='Fresh output case root')
    p.add_argument('--mode', choices=('delivered', 'parameters'), default='delivered')
    p.add_argument('cases', nargs='*', help='Optional exact case names; default all delivered cases')
    a = p.parse_args()
    source, root = Path(a.inputs).resolve(), Path(a.root).resolve()
    if source == root or root.is_relative_to(source):
        raise ValueError('Use a separate fresh root, outside the delivered case directory')
    if root.exists() and any(root.iterdir()):
        raise ValueError('Output root must be empty or absent')
    geometries = sorted(source.glob('*/geometry.json'))
    if a.cases:
        requested = set(a.cases)
        geometries = [g for g in geometries if g.parent.name in requested]
        if requested != {g.parent.name for g in geometries}:
            raise ValueError('Requested case not found in delivered inputs')
    if not geometries:
        raise ValueError('No delivered case metadata found')
    if a.mode == 'parameters' and any((g.parent/'initialization.json').exists() or
            json.loads(g.read_text()).get('initialization_family') == 'mapped' for g in geometries):
        raise ValueError('Parameter mode requires explicitly selected cold cases; use delivered mode for mapped cases')
    if a.mode=='parameters':
        require_legacy_parameter_cases(geometries,root)
    root.mkdir(parents=True, exist_ok=True)
    generator = None
    if a.mode == 'parameters':
        # generate_tello writes study_metadata beside itself. A private tool
        # copy prevents parameter reproduction from modifying delivered files.
        tools = root/'_reproduction_tools'
        tools.mkdir()
        for name in ('generate_tello.py', 'base_generator.py'):
            shutil.copy2(Path(__file__).with_name(name), tools/name)
        generator = tools/'generate_tello.py'
    records = []
    for path in geometries:
        if a.mode == 'delivered':
            records.append(copy_delivered(path.parent, root/path.parent.name, json.loads(path.read_text())))
        else:
            records.append(regenerate(path, root, generator))
    (root/'reproduction_manifest.json').write_text(json.dumps(dict(mode=a.mode,
        no_solver_launched=True, cases=records), indent=2)+'\n')
    next_step = 'run_cases.py' if a.mode == 'delivered' else 'prepare_parallel.py, then run_cases.py'
    print(f'Prepared {len(geometries)} fresh cases in {a.mode} mode. Next: {next_step}.')

if __name__ == '__main__':
    main()
