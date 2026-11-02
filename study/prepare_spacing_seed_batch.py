"""Prepare the explicit 12-case spacing-seed input batch; never mesh or run CFD.

Load the Foundation 14 environment, then run as root only if --owner is used:
  python3 prepare_spacing_seed_batch.py --root NEW_ROOT \
      --manifest spacing_inputs.json --log spacing_inputs.log \
      --owner openfoam:openfoam

The destination must be absent or empty. This helper refuses overwrites and
uses the unchanged generic generator's guarded cleanup of its own fresh
staging directories. Only the 12 manifest-listed directories are candidates.
Neither this helper nor those candidates are added to the study archive scope.
After an interrupted batch, --resume permits only its same manifest/root and
revalidates existing deterministic candidates without rewriting their inputs.
"""
from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
import math
import os
from pathlib import Path
import pwd
import grp
import re
import sys

sys.dont_write_bytecode = True
import generate_design_case as design
from layout_geometry import geometry, physical_fingerprint
from prepare_mapped import solver_configuration
from archive_completed import atomic_json, validate_cold_initialization

SOURCE_SHA256 = '29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
NUMERICAL_SHA256 = 'be7fbf20fcedfaed74b459ac012046232b251d3767586d9d981b729523832eb8'
REFERENCE_POWER_W = 4.18 / (13 / 60)
HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def record(path):
    path = Path(path)
    return dict(sha256=digest(path), size_bytes=path.stat().st_size)


def specs():
    """Angles are signed; every spacing is nearest horizontal hub distance."""
    result = []
    for spacing in (0., 4., 10.):
        families = [(4, 'square_perimeter'), (8, 'square_perimeter')]
        if spacing != 0:
            families.append((8, 'circular_ring'))
        result.extend(dict(rotors=n, layout=layout, nearest_spacing_cm=spacing,
                           tilt_deg=0.) for n, layout in families)
    special = 100 * (2 * math.sqrt(2) * .08 * math.sin(math.pi / 8))
    result.extend(dict(rotors=8, layout='circular_ring', nearest_spacing_cm=s,
                       tilt_deg=0.) for s in (8., special))
    result.extend(dict(rotors=4, layout='square_perimeter', nearest_spacing_cm=10.,
                       tilt_deg=angle) for angle in (-10., 10.))
    assert len(result) == 12
    return result


def assert_close(actual, expected, name, tolerance=1e-12):
    if not math.isclose(float(actual), float(expected), rel_tol=0, abs_tol=tolerance):
        raise ValueError(f'{name}: {actual!r} differs from {expected!r}')


def expected_name(request):
    shape = geometry(request['rotors'], request['layout'],
                     request['nearest_spacing_cm']/100, request['tilt_deg'], .0762, .012)
    seed = dict(shape, battery_power_W=REFERENCE_POWER_W, source_sha256=SOURCE_SHA256,
        loss_model=dict(auxiliary_W=.5, esc_efficiency=.95, idle_W_per_motor=.1,
                        motor_conversion=.6, axial_fraction=.5))
    identity = dict(physical_design=physical_fingerprint(seed, include_operating=True),
        level='coarse', study_role='validation', end_s='1.2', average_start_s='0.8',
        initialization='cold serial; pressure direct-coarsest on')
    case_id = hashlib.sha256(json.dumps(identity, sort_keys=True,
                              separators=(',', ':')).encode()).hexdigest()
    theta = request['tilt_deg']
    sign = 'm' if theta < 0 else 'p' if theta > 0 else 'z'
    return (f'coarsespacingseed_{shape["layout"]}_n{request["rotors"]}_e{REFERENCE_POWER_W:g}_'
            f'd{round(shape["distance_cm"]*100):04d}_a{sign}{round(abs(theta)*100):04d}_{case_id[:12]}')


def own_generated_log(case, owner):
    # The unchanged generic generator creates this last log AFTER its chown.
    # Assign only that task-created file; all input contents remain unchanged.
    if owner:
        account, group = owner.split(':', 1)
        os.chown(case/'log.design_input_generation', pwd.getpwnam(account).pw_uid,
                 grp.getgrnam(group).gr_gid)


def verify(case, request, owner):
    g = json.loads((case / 'geometry.json').read_text())
    expected = geometry(request['rotors'], request['layout'],
                        request['nearest_spacing_cm'] / 100, request['tilt_deg'],
                        .0762, .012)
    for key in ('rotors', 'layout', 'centers', 'normals', 'radials',
                'physical_geometry_sha256', 'uniform_source_core_contains_forcing'):
        if g[key] != expected[key]:
            raise ValueError(f'{case.name}: incorrect geometry: {key}')
    if (g.get('input_mode') != 'nearest_spacing' or g.get('level') != 'coarse'
            or g.get('study_role') != 'validation' or g.get('tag') != 'spacingseed'
            or g.get('purpose') != 'layout_comparison'
            or g.get('initialization_family') != 'cold'
            or g.get('initialization_start_time_s') != 0
            or g.get('execution', {}).get('mpi_ranks') != 1
            or g['execution'].get('execution_mode') != 'serial'):
        raise ValueError(f'{case.name}: incorrect preparation protocol')
    for key, value in dict(diameter_m=.0762, radius_m=.0381, thickness_m=.012,
            half_thickness_m=.006, battery_power_W=REFERENCE_POWER_W,
            configured_end_time_s=1.2, averaging_start_s=.8, averaging_stop_s=1.2,
            averaging_duration_s=.4, nearest_spacing_m=expected['nearest_spacing_m'],
            tilt_deg=request['tilt_deg']).items():
        assert_close(g[key], value, key)
    if g['source_sha256'] != SOURCE_SHA256 or digest(case / 'constant/fvModels') != SOURCE_SHA256:
        raise ValueError(f'{case.name}: source hash differs')
    config, signature, direct = solver_configuration(case)
    if (signature != NUMERICAL_SHA256 or g['solver_configuration_sha256'] != signature
            or g['solver_configuration'] != config
            or direct != dict(p=True, pFinal=True)):
        raise ValueError(f'{case.name}: numerical protocol differs')
    validate_cold_initialization(case, g)
    for relative in ('constant/polyMesh', 'log.blockMesh', 'log.checkMesh',
            'log.foamRun', 'run_status.json', 'initialization.json',
            '.cold-solver-started'):
        if (case / relative).exists():
            raise ValueError(f'{case.name}: meshed/started output exists: {relative}')
    if list(case.glob('processor*')):
        raise ValueError(f'{case.name}: processor directory exists')
    for child in case.iterdir():
        if child.is_dir():
            try:
                numeric = float(child.name)
            except ValueError:
                continue
            if numeric != 0:
                raise ValueError(f'{case.name}: nonzero time directory exists')
    if owner:
        account, group = owner.split(':', 1)
        uid, gid = pwd.getpwnam(account).pw_uid, grp.getgrnam(group).gr_gid
        owned = [case] + list(case.rglob('*'))
        if any(path.stat().st_uid != uid or path.stat().st_gid != gid for path in owned):
            raise ValueError(f'{case.name}: ownership differs from {owner}')
    assert_close(g['geometric_volume_per_rotor_m3'], math.pi * .0381**2 * .012,
                 'geometric volume')
    bounds = g['forcing_bounds_xy_m'] + [g['forcing_z_extent_m']]
    limits = (.168, .168, .042)
    if not all(abs(v) <= limit + 1e-12 for pair, limit in zip(bounds, limits) for v in pair):
        raise ValueError(f'{case.name}: actual forcing is outside source core')
    # Read the actual generated dictionaries, rather than trusting geometry only.
    import subprocess
    def value(relative, entry):
        return subprocess.check_output(['foamDictionary', str(case / relative),
                    '-entry', entry, '-value', '-writePrecision', '17'], text=True).strip()
    for entry, expected_value in (('startFrom', 'startTime'), ('startTime', '0'),
                                  ('stopAt', 'endTime')):
        if value('system/controlDict', entry) != expected_value:
            raise ValueError(f'{case.name}: controlDict {entry} differs')
    assert_close(value('system/controlDict', 'endTime'), 1.2, 'controlDict endTime')
    if value('system/decomposeParDict', 'numberOfSubdomains') != '1':
        raise ValueError(f'{case.name}: decomposition input is not serial')
    for entry, expected_value in (('radius', .0381), ('halfThickness', .006),
                                  ('batteryPower', REFERENCE_POWER_W)):
        assert_close(value('constant/rotorParameters', entry), expected_value,
                     'rotorParameters ' + entry)
    for entry, vectors in (('centres', g['centers']), ('normals', g['normals']),
                            ('radials', g['radials'])):
        actual = [float(v) for v in re.findall(
            r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?',
            value('constant/rotorParameters', entry))]
        expected_values = [v for vector in vectors for v in vector]
        if len(actual) != len(expected_values):
            raise ValueError(f'{case.name}: rotorParameters {entry} count differs')
        for a, b in zip(actual, expected_values):
            assert_close(a, b, 'rotorParameters ' + entry)
    inputs = {str(p.relative_to(case)): record(p) for p in sorted(case.rglob('*')) if p.is_file()}
    return dict(case=case.name, path=str(case), requested=request,
        rotors=g['rotors'], layout=g['layout'], nearest_spacing_cm=100*g['nearest_spacing_m'],
        tilt_deg=g['tilt_deg'], projected_box_cm=[100*v for v in g['projected_footprint_xy_m']],
        forcing_bounds_m=bounds, uniform_core_contains_forcing=True,
        battery_power_W=g['battery_power_W'], numerical_signature=signature,
        source_sha256=SOURCE_SHA256, physical_design_sha256=g['design_physics_sha256'],
        geometry_sha256=digest(case / 'geometry.json'), inputs=inputs,
        checks=dict(geometry=True, actual_rotor_parameters=True, forcing_core_bounds=True,
                    cold_initial_fields=True, electrical_power=True, numerical_signature=True,
                    serial_direct_coarsest=True, zero_mesh_or_solver_outputs=True,
                    owner=owner, exact_time_protocol=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--owner')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    manifest, log = args.manifest.resolve(), args.log.resolve()
    if root == Path('/opt/openfoam-workspace/cases/tello_refinement'):
        raise ValueError('Refusing the actual study root')
    if args.root.is_symlink() or (root.exists() and not root.is_dir()):
        raise FileExistsError('Candidate root must be a plain directory')
    if not args.resume and root.exists() and any(root.iterdir()):
        raise FileExistsError('Candidate root must be absent or empty; no inputs overwritten')
    if not args.resume and (manifest.exists() or log.exists()):
        raise FileExistsError('Manifest and log must be fresh; refusing overwrite')
    if args.owner and os.geteuid() != 0:
        raise PermissionError('--owner requires root')
    log.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(parents=True, exist_ok=True)
    helpers = ('prepare_spacing_seed_batch.py', 'generate_design_case.py',
        'layout_geometry.py', 'generate_tello.py', 'base_generator.py',
        'prepare_serial_cold.py', 'prepare_mapped.py', 'Allrun_cold_serial.template',
        'decomposeParDict_serial.template', 'archive_completed.py')
    helper_records = {name: record(HERE / name) for name in helpers}
    previous = None
    if args.resume:
        previous = json.loads(manifest.read_text())
        if (previous.get('schema') != 'tello-spacing-seed-input-batch-v1'
                or previous.get('candidate_root') != str(root)
                or previous.get('source_sha256') != SOURCE_SHA256
                or previous.get('numerical_signature') != NUMERICAL_SHA256
                or previous.get('owner') != args.owner or not log.is_file()
                or previous.get('status') not in ('preparing_inputs_only', 'failed_existing_candidates_preserved', 'failed_preserved_no_cleanup')):
            raise ValueError('Resume requires this batch\'s same incomplete manifest/root/log/owner')
        for name in helpers:
            if name != Path(__file__).name and previous['helper_files'].get(name) != helper_records[name]:
                raise ValueError('A preparation dependency changed; refusing resume: '+name)
        allowed = {expected_name(request) for request in specs()}
        if any(path.name not in allowed or not path.is_dir() or path.is_symlink() for path in root.iterdir()):
            raise ValueError('Unexpected candidate-root entry; refusing resume')
    payload = dict(schema='tello-spacing-seed-input-batch-v1',
        generated_utc=datetime.now(timezone.utc).isoformat(), candidate_root=str(root),
        status='preparing_inputs_only', source_sha256=SOURCE_SHA256,
        numerical_signature=NUMERICAL_SHA256, requested_count=12,
        power_definition='4.18 / (13 / 60) W total battery input',
        battery_power_W=REFERENCE_POWER_W, diameter_m=.0762, thickness_m=.012,
        level='coarse', study_role='validation', tag='spacingseed',
        initialization='cold uniform rest, serial one rank, direct pressure coarsest solve',
        start_time_s=0., end_time_s=1.2, averaging_window_s=[.8, 1.2],
        owner=args.owner, no_mesh_utility_launched=True, no_solver_launched=True,
        not_added_to_study_or_archive_selection=True, helper_files=helper_records,
        reproduction=dict(helper='prepare_spacing_seed_batch.py', argv=[
            '--root', 'NEW_EMPTY_CANDIDATE_ROOT', '--manifest', 'NEW_MANIFEST.json',
            '--log', 'NEW_GENERATION.log'] + (['--owner', args.owner] if args.owner else []),
            requires='Foundation 14 foamDictionary environment; root only for --owner'),
        zero_spacing_equivalence=dict(representative='N8 square, flat, nearest spacing 0',
            omitted_design='N8 circle, flat, nearest spacing 0',
            explanation='Both have eight coincident equal cylinders and identical normals at zero tilt. '
              'The source uses radial directions only as an XY coordinate rotation when tiltSin=0; '
              'aa^2+bb^2=x^2+y^2, so the collapsed flat actuator model is physically equivalent. '
              'This is an overlapping-actuator limit, not feasible blade-resolved hardware.'),
        cases=[], private_staging_cleanup='Unchanged generic generator guard; only its own fresh staging directory', error=None)
    if previous:
        payload['prior_attempts'] = previous.get('prior_attempts', []) + [dict(
            status=previous['status'], error=previous.get('error'),
            generated_utc=previous.get('generated_utc'), helper_files=previous['helper_files'])]
    flat_square = geometry(8, 'square_perimeter', .08)
    special_spacing = 2 * math.sqrt(2) * .08 * math.sin(math.pi / 8)
    flat_circle = geometry(8, 'circular_ring', special_spacing)
    span = lambda g: max(math.dist(a, b) for a in g['centers'] for b in g['centers'])
    assert_close(span(flat_square), span(flat_circle), 'matched maximum hub span')
    if physical_fingerprint(geometry(8, 'square_perimeter', 0.)) != physical_fingerprint(geometry(8, 'circular_ring', 0.)):
        raise ValueError('Zero-spacing physical equivalence failed')
    payload['max_hub_span_match'] = dict(square_nearest_spacing_cm=8.,
        circular_nearest_spacing_cm=100*special_spacing,
        common_maximum_hub_center_distance_cm=100*span(flat_square),
        square_projected_box_cm=[100*v for v in flat_square['projected_footprint_xy_m']],
        circular_projected_box_cm=[100*v for v in flat_circle['projected_footprint_xy_m']],
        equal_bounding_box=False)
    atomic_json(manifest, payload)
    with log.open('a' if args.resume else 'x', encoding='utf-8', buffering=1) as stream:
        stream.write(json.dumps(dict(event='start', root=str(root), input_only=True))+'\n')
        try:
            for request in specs():
                command = argparse.Namespace(root=str(root), rotors=request['rotors'],
                    layout=request['layout'], nearest_spacing_cm=request['nearest_spacing_cm'],
                    projected_box_width_cm=None, tilt_deg=request['tilt_deg'],
                    diameter_m=.0762, thickness_m=.012, power_w=REFERENCE_POWER_W,
                    level='coarse', end_s=1.2, average_start_s=.8,
                    study_role='validation', tag='spacingseed', owner=args.owner)
                case = root / expected_name(request)
                if case.exists():
                    if not args.resume:
                        raise FileExistsError('Refusing existing candidate: '+str(case))
                    g = json.loads((case/'geometry.json').read_text())
                    if (g.get('input_generator_sha256') != helper_records['generate_design_case.py']['sha256']
                            or g.get('geometry_helper_sha256') != helper_records['layout_geometry.py']['sha256']):
                        raise ValueError('Existing candidate generator provenance differs')
                    stream.write(json.dumps(dict(event='resume_existing_no_input_rewrite',case=case.name))+'\n')
                else:
                    capture = io.StringIO()
                    with redirect_stdout(capture):
                        result = design.generate(command)
                    stream.write(capture.getvalue())
                    if Path(result['case']) != case:
                        raise ValueError('Generator returned an unexpected candidate path')
                own_generated_log(case, args.owner)
                row = verify(case, request, args.owner)
                payload['cases'].append(row)
                atomic_json(manifest, payload)
                stream.write(json.dumps(dict(event='verified', case=case.name,
                                             prepared=len(payload['cases'])))+'\n')
                print(json.dumps(dict(event='verified', case=case.name,
                                      prepared=len(payload['cases']))), flush=True)
            if len(payload['cases']) != 12 or len({row['physical_design_sha256'] for row in payload['cases']}) != 12:
                raise ValueError('Expected twelve unique rotor-count/geometry/operating designs')
            if helper_records != {name: record(HERE/name) for name in helpers}:
                raise ValueError('Preparation helper inputs changed during the batch')
            actual = sorted(p.name for p in root.iterdir() if p.is_dir() and (p/'geometry.json').is_file())
            if actual != sorted(row['case'] for row in payload['cases']):
                raise ValueError('Final candidate set does not match the explicit matrix')
            payload['status'] = 'prepared_verified_unrun_not_selected'
            payload['completed_utc'] = datetime.now(timezone.utc).isoformat()
            atomic_json(manifest, payload)
            stream.write(json.dumps(dict(event='complete', count=12, source_cases_unchanged=True))+'\n')
        except BaseException as exc:
            payload.update(status='failed_existing_candidates_preserved', error=repr(exc))
            atomic_json(manifest, payload)
            stream.write(json.dumps(dict(event='failed', error=repr(exc)))+'\n')
            raise
    print(json.dumps(dict(status=payload['status'], cases=12,
        manifest=str(manifest), log=str(log))), flush=True)


if __name__ == '__main__':
    main()
