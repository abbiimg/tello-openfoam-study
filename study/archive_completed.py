"""Archive immutable completed Tello-refinement cases without changing CFD files.

The watcher accepts coarse cases by default, or an explicit selected-case list
across all levels. It stays alive until an explicit stop file is created.
Processor directories are excluded: root mesh, actual initial/final fields,
inputs and logs are retained. Run in Linux/WSL.
"""
from pathlib import Path
from contextlib import contextmanager
import argparse
import errno
import fcntl
import hashlib
import json
import math
import os
import re
import time
import zipfile

EXPECTED_SOURCE_SHA256 = '29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
END = re.compile(r'^\s*(?:\[\d+\]\s*)?End\s*$', re.M)
FATAL = re.compile(r'FOAM FATAL|MPI_ABORT')
PREFIX = r'^\s*(?:\[\d+\]\s*)?'


class IncompleteCase(ValueError):
    """No immutable successful terminal case is available yet."""


class StaleArchive(ValueError):
    """Archive/index or archived source changed; never append silently."""


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def retry_sharing(operation, path, phase):
    """Wait out Windows readers denying rename, without losing a ZIP commit.

    Each sleep is bounded; the native watcher remains alive and logs retries.
    Other I/O failures (including disk-full/corruption) still fail explicitly.
    """
    attempts, last_report = 0, None
    while True:
        try:
            result = operation()
            if attempts:
                print(json.dumps(dict(event='publication_resumed', path=str(path),
                                      phase=phase, attempts=attempts)), flush=True)
            return result
        except OSError as exc:
            if exc.errno not in (errno.EACCES, errno.EPERM, errno.EBUSY) and getattr(exc, 'winerror', None) not in (32, 33):
                raise
            attempts += 1
            now = time.monotonic()
            if last_report is None or now - last_report >= 10:
                print(json.dumps(dict(event='publication_retry', path=str(path), phase=phase,
                                      attempts=attempts, error=str(exc))), flush=True)
                last_report = now
            time.sleep(min(1., .05 * 2 ** min(attempts, 5)))


def atomic_json(path, value):
    temporary = path.with_name(path.name + '.updated')
    payload = json.dumps(value, indent=2) + '\n'

    def write_pending():
        with temporary.open('w', encoding='utf-8') as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())

    retry_sharing(write_pending, temporary, 'write_pending_json')
    retry_sharing(lambda: temporary.replace(path), path, 'commit_pending_json')


@contextmanager
def archive_lock(out, session=False):
    """One archive mutation at a time; one watcher/final-packager session."""
    out.mkdir(parents=True, exist_ok=True)
    name = '.archive-session.lock' if session else '.cases-archive.lock'
    with (out / name).open('a') as stream:
        flags = fcntl.LOCK_EX | (fcntl.LOCK_NB if session else 0)
        try:
            fcntl.flock(stream.fileno(), flags)
        except BlockingIOError as exc:
            raise RuntimeError('Another archive watcher/final packager is active') from exc
        try:
            yield
        finally:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def actual_cases(root, coarse_only=False):
    """Select generated cases by metadata, excluding templates/processor trees."""
    result = []
    for case in sorted(root.iterdir()):
        if not case.is_dir() or case.name.startswith(('_', '.')):
            continue
        geometry = case / 'geometry.json'
        if not geometry.is_file():
            continue
        if coarse_only:
            try:
                if json.loads(geometry.read_text())['level'] != 'coarse':
                    continue
            except json.JSONDecodeError:
                continue  # A new case may still be being generated atomically.
        result.append(case)
    return result


def validate_initialization(case, geometry, initial_time):
    """Verify mapped initial fields and the immutable mapping provenance.

    Historical source records are checked against each other, rather than an
    absolute live source path, so delivered cases remain portable. Actual mapped
    fields and every recorded target input/mesh/log are checked byte for byte.
    """
    path = case / 'initialization.json'
    if not path.is_file():
        raise ValueError(f'{case.name}: nonzero start lacks initialization.json')
    initialization = json.loads(path.read_text())
    if (initialization.get('status') != 'mapped_ready_no_solver_run'
            or initialization.get('source_sha256') != EXPECTED_SOURCE_SHA256
            or initialization.get('source_unchanged') is not True
            or initialization.get('consistent_geometry') is not True
            or initialization.get('actual_source_and_target_fvModels_and_rotorParameters_byte_identical') is not True
            or initialization.get('mapping_method') != 'interpolate'):
        raise ValueError(f'{case.name}: invalid mapped initialization provenance')
    start = float(initial_time)
    source_time = initialization.get('source_time_directory')
    if (not math.isclose(start, .6, rel_tol=0, abs_tol=1e-12)
            or source_time != '0.6'
            or initialization.get('target_start_time_s') != start
            or not initialization.get('source_time_confirmed_by_mapFields')
            or any(float(t) != start for t in initialization['source_time_confirmed_by_mapFields'])):
        raise ValueError(f'{case.name}: inconsistent mapped source/target initial time')
    before = initialization.get('source_case_files_before', {})
    after = initialization.get('source_case_files_after', {})
    source_required = {'geometry.json', 'constant/fvModels', 'constant/rotorParameters',
                       '0.6/U', '0.6/p'} | {'constant/polyMesh/' + name for name in
                                              ('points', 'faces', 'owner', 'neighbour', 'boundary')}
    if not source_required <= set(before) or before != after:
        raise ValueError(f'{case.name}: source changed during mapping or provenance is incomplete')
    for relative, record in before.items():
        if (not re.fullmatch(r'[0-9a-f]{64}', record.get('sha256', ''))
                or not isinstance(record.get('size_bytes'), int) or record['size_bytes'] <= 0
                or not isinstance(record.get('mtime_ns'), int)):
            raise ValueError(f'{case.name}: malformed historical source record: {relative}')
    if before['constant/fvModels']['sha256'] != EXPECTED_SOURCE_SHA256:
        raise ValueError(f'{case.name}: mapped source-model hash is not approved')
    groups = {
        'target_inputs_after_preparation': {'geometry.json', 'constant/fvModels',
            'constant/rotorParameters', '0/U', '0/p', 'system/blockMeshDict',
            'system/controlDict', 'system/fvSchemes', 'system/fvSolution',
            'Allrun', 'prepare_mapped.py', 'system/decomposeParDict'},
        'target_mesh': {'constant/polyMesh/' + name for name in
                        ('points', 'faces', 'owner', 'neighbour', 'boundary')},
        'mapped_fields': {initial_time + '/U', initial_time + '/p'},
        'preparation_logs': {'log.blockMesh', 'log.checkMesh', 'log.mapFields'},
    }
    for group, required in groups.items():
        records = initialization.get(group, {})
        if not required <= set(records):
            raise ValueError(f'{case.name}: incomplete initialization group: {group}')
        for relative, record in records.items():
            rel = Path(relative)
            if rel.is_absolute() or '..' in rel.parts:
                raise ValueError(f'{case.name}: invalid provenance path: {relative}')
            target = case / rel
            if not target.is_file():
                raise ValueError(f'{case.name}: prepared target file absent: {relative}')
            stat = target.stat()
            if (digest(target) != record.get('sha256') or stat.st_size != record.get('size_bytes')
                    or stat.st_mtime_ns != record.get('mtime_ns')):
                raise ValueError(f'{case.name}: prepared input/initial field changed: {relative}')
    if digest(case / 'constant/rotorParameters') != before['constant/rotorParameters']['sha256']:
        raise ValueError(f'{case.name}: mapped source/target rotor parameters differ')
    if (case / initial_time / 'phi').exists():
        raise ValueError(f'{case.name}: mapped initial phi must be absent')
    mapping = (case / 'log.mapFields').read_text(errors='replace')
    selected = re.findall(r'Source time:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:s)?\s', mapping)
    if not selected or any(float(t) != start for t in selected) or not END.search(mapping) or FATAL.search(mapping):
        raise ValueError(f'{case.name}: mapFields did not finish at the exact source time')
    if initialization.get('actual_target_cells') != int(geometry['mesh_cells']):
        raise ValueError(f'{case.name}: mapped target mesh count differs from geometry')
    invariants = initialization.get('invariants', {})
    source_invariants = initialization.get('source_invariants', {})
    invariant_keys = {'rotors', 'battery_power_W', 'distance_cm', 'tilt_deg', 'radius_m',
                      'thickness_m', 'centers', 'normals', 'radials', 'source_sha256'}
    if not invariant_keys <= set(invariants) or set(invariants) != set(source_invariants):
        raise ValueError(f'{case.name}: geometry/operating invariants are incomplete')

    def same(a, b):
        if isinstance(a, (float, int)) and isinstance(b, (float, int)):
            return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)
        if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
            return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
        if isinstance(a, dict) and isinstance(b, dict):
            return a.keys() == b.keys() and all(same(a[k], b[k]) for k in a)
        return a == b

    if any(key not in geometry or not same(value, geometry[key])
           or not same(value, source_invariants[key]) for key, value in invariants.items()):
        raise ValueError(f'{case.name}: mapped source/target geometry or operating point differs')
    # Generalized production manifests additionally freeze numerical methods
    # and portable references. Legacy performance probes need no invented data.
    if 'solver_configuration' in initialization:
        configuration = initialization['solver_configuration']
        numerical_hash = hashlib.sha256(json.dumps(configuration, sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        if (numerical_hash != initialization.get('solver_configuration_sha256')
                or numerical_hash != geometry.get('solver_configuration_sha256')
                or configuration != geometry.get('solver_configuration')
                or initialization.get('pressure_direct_solve_coarsest') != geometry.get('pressure_direct_solve_coarsest')
                or initialization.get('frozen_helper_sha256') != digest(case / 'prepare_mapped.py')):
            raise ValueError(f'{case.name}: frozen helper/numerical-method provenance differs')
        source_name = initialization.get('source_case_logical')
        reference = initialization.get('source_case_reference', {})
        if (not source_name or Path(source_name).name != source_name
                or initialization.get('source_case_absolute_historical') != initialization.get('source_case')
                or Path(initialization['source_case']).name != source_name
                or reference.get('case_name') != source_name
                or reference.get('archive_member_prefix') != f'cases/{source_name}/'
                or reference.get('source_time_directory') != source_time
                or reference.get('initialized_target_rerun_requires_live_source') is not False
                or reference != geometry.get('initialization_source_case_reference')
                or geometry.get('initialization_source_case') != source_name
                or geometry.get('initialization_method') != 'mapped_coarse_fields'
                or geometry.get('initialization_start_time_s') != start
                or geometry.get('initialization_source_time_s') != start):
            raise ValueError(f'{case.name}: portable mapped-source reference is inconsistent')
        control_end = re.search(r'\bendTime\s+([^;\s]+)\s*;', (case / 'system/controlDict').read_text())
        if not control_end:
            raise ValueError(f'{case.name}: mapped control endTime is missing')
        declared = (float(initialization['target_end_time_s']),
                    float(initialization['target_averaging_start_s']),
                    float(initialization['target_averaging_stop_s']))
        actual = (float(control_end.group(1)), float(geometry['averaging_start_s']),
                  float(geometry['averaging_stop_s']))
        if not same(declared, actual) or not math.isclose(actual[0],
                float(geometry['configured_end_time_s']), rel_tol=0, abs_tol=1e-9):
            raise ValueError(f'{case.name}: mapped run/averaging-window provenance differs')
        if geometry.get('study_role') == 'validation' and any(
                not math.isclose(a, b, rel_tol=0, abs_tol=1e-9)
                for a, b in zip(actual, (1.2, .8, 1.2))):
            raise ValueError(f'{case.name}: mapped validation requires the approved 0.8-1.2 s window')
        physical_flag = initialization.get('actual_source_and_target_physicalProperties_and_momentumTransport_byte_identical')
        if physical_flag is not None:
            if physical_flag is not True:
                raise ValueError(f'{case.name}: mapped physical-property equality was not verified')
            for filename in ('physicalProperties', 'momentumTransport'):
                relative = 'constant/' + filename
                if relative not in before or digest(case / relative) != before[relative]['sha256']:
                    raise ValueError(f'{case.name}: mapped source/target physical properties differ')
        if initialization.get('mapped_field_cells') != dict(U=int(geometry['mesh_cells']), p=int(geometry['mesh_cells'])):
            raise ValueError(f'{case.name}: mapped-field cell-count provenance differs')
        source_cells = initialization.get('source_field_cells', {})
        if source_cells and (set(source_cells) != {'U', 'p'} or not isinstance(source_cells['U'], int) or source_cells['U'] <= 0 or source_cells['U'] != source_cells['p']):
            raise ValueError(f'{case.name}: incomplete source-field cell-count provenance')
    variant_path = case / 'solver_variant_audit.json'
    if variant_path.is_file():
        if 'solver_variant_audit.json' not in initialization['target_inputs_after_preparation']:
            raise ValueError(f'{case.name}: variant audit is not a frozen prepared input')
        audit = json.loads(variant_path.read_text())
        parent = audit.get('parent_input_records', {})
        if (not parent or parent != audit.get('parent_input_records_after')
                or audit.get('parent_files_unchanged') is not True
                or audit.get('serial_case') != case.name or audit.get('mpi_ranks') != 1
                or initialization.get('mpi_ranks') != 1
                or geometry.get('execution', {}).get('mpi_ranks') != 1
                or any(audit.get(flag) is not True for flag in (
                    'serial_no_decomposition_or_reconstruction',
                    'mesh_and_mapped_initial_fields_byte_identical',
                    'helper_byte_identical_to_parent',
                    'physical_and_operating_metadata_unchanged',
                    'effective_numerical_method_unchanged_except_decomposition'))):
            raise ValueError(f'{case.name}: serial-copy provenance audit is incomplete')
        unchanged = ['0.6/U', '0.6/p', 'prepare_mapped.py',
                     'constant/fvModels', 'constant/rotorParameters',
                     'constant/physicalProperties', 'constant/momentumTransport']
        unchanged += ['constant/polyMesh/' + name for name in ('points', 'faces', 'owner', 'neighbour', 'boundary')]
        for relative in unchanged:
            if relative not in parent or digest(case / relative) != parent[relative]['sha256']:
                raise ValueError(f'{case.name}: serial variant changed inherited input: {relative}')
        parent_configuration = audit['parent_solver_configuration']
        configuration = audit['solver_configuration']
        parent_hash = hashlib.sha256(json.dumps(parent_configuration, sort_keys=True,
            separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
        without_decomposition = lambda value: {k: v for k, v in value.items() if k != 'decomposition'}
        if (parent_hash != audit.get('parent_solver_configuration_sha256')
                or configuration != initialization.get('solver_configuration')
                or audit.get('solver_configuration_sha256') != initialization.get('solver_configuration_sha256')
                or without_decomposition(parent_configuration) != without_decomposition(configuration)):
            raise ValueError(f'{case.name}: serial audit numerical-method comparison differs')
    return dict(manifest_sha256=digest(path), initial_time_s=start,
                source_case=initialization['source_case'], source_time_directory=source_time,
                source_unchanged_during_mapping=True,
                source_fields_sha256={field: before['0.6/' + field]['sha256'] for field in ('U', 'p')},
                mapped_fields_sha256={field: initialization['mapped_fields'][initial_time + '/' + field]['sha256']
                                      for field in ('U', 'p')})


def validate_cold_initialization(case, geometry):
    """Check the explicit serial/direct cold sensitivity preparation record."""
    manifest = case / 'cold_preparation.json'
    preparation = json.loads(manifest.read_text())
    execution = geometry.get('execution', {})
    role = geometry.get('study_role')
    role_allowed = role == 'sensitivity' or (role == 'validation'
        and geometry.get('purpose') == preparation.get('purpose') == 'layout_comparison')
    if (preparation.get('case') != case.name
            or preparation.get('status') != 'prepared_no_solver_run'
            or preparation.get('initialization') != 'cold'
            or preparation.get('mpi_ranks') != 1
            or execution.get('mpi_ranks') != 1 or execution.get('execution_mode') != 'serial'
            or geometry.get('initialization_method') != 'cold_start'
            or geometry.get('initialization_family') != 'cold'
            or geometry.get('initialization_start_time_s') != 0
            or not role_allowed):
        raise ValueError(f'{case.name}: cold serial preparation provenance differs')
    configuration = geometry.get('solver_configuration')
    if not isinstance(configuration, dict):
        raise ValueError(f'{case.name}: cold serial numerical configuration is absent')
    signature = hashlib.sha256(json.dumps(configuration, sort_keys=True,
        separators=(',', ':'), ensure_ascii=True).encode()).hexdigest()
    runner_sha = digest(case / 'Allrun')
    direct = geometry.get('pressure_direct_solve_coarsest')
    edit = preparation.get('direct_coarsest_edit', {})
    if (signature != geometry.get('solver_configuration_sha256')
            or signature != preparation.get('solver_configuration_sha256')
            or runner_sha != execution.get('runner_sha256')
            or runner_sha != preparation.get('runner_sha256')
            or direct != dict(p=True, pFinal=True)
            or edit.get('requested') is not True or edit.get('effective_after') != direct
            or edit.get('all_other_solver_entries_unchanged') is not True
            or configuration.get('decomposition', {}).get('numberOfSubdomains') != ['1']):
        raise ValueError(f'{case.name}: cold serial runner/numerical signature differs')
    solvers = configuration.get('fvSolution', {}).get('solvers', {})
    if any(solvers.get(field, {}).get('directSolveCoarsest') != ['true'] for field in ('p', 'pFinal')):
        raise ValueError(f'{case.name}: cold serial direct-coarsest settings differ')
    velocity = re.search(r'\binternalField\s+uniform\s*\(([^)]*)\)\s*;', (case / '0/U').read_text())
    pressure = re.search(r'\binternalField\s+uniform\s+([^;\s]+)\s*;', (case / '0/p').read_text())
    values = [float(v) for v in velocity.group(1).split()] if velocity else []
    if len(values) != 3 or any(v != 0 for v in values) or not pressure or float(pressure.group(1)) != 0:
        raise ValueError(f'{case.name}: cold initial U,p are not uniform rest/zero')
    return dict(manifest_sha256=digest(manifest), numerical_method_sha256=signature,
                runner_sha256=runner_sha, initial_time_s=0,
                initial_fields_sha256={field: digest(case / '0' / field) for field in ('U', 'p')})


def validate_case(case):
    needed = ('geometry.json', 'run_status.json', 'log.foamRun', 'log.checkMesh',
              'constant/fvModels', 'system/controlDict')
    if not all((case / name).is_file() for name in needed):
        raise IncompleteCase(f'{case.name}: terminal status/reconstructed result pending')
    try:
        g = json.loads((case / 'geometry.json').read_text())
        status = json.loads((case / 'run_status.json').read_text())
    except json.JSONDecodeError as exc:
        raise IncompleteCase(f'{case.name}: metadata/status write pending') from exc
    if status.get('returncode') is None:
        raise IncompleteCase(f'{case.name}: terminal return code pending')
    if status['returncode'] != 0:
        raise ValueError(f'{case.name}: nonzero terminal return code')
    ranks = status.get('mpi_ranks')
    if (status.get('case') != case.name or status.get('state') != 'succeeded'
            or status.get('validated') is not True or ranks not in (1, 2)
            or g.get('execution', {}).get('mpi_ranks') != ranks):
        raise ValueError(f'{case.name}: inconsistent immutable terminal status')
    text = (case / 'log.foamRun').read_text(errors='replace')
    if not END.search(text):
        raise IncompleteCase(f'{case.name}: solver has not ended')
    if FATAL.search(text):
        raise ValueError(f'{case.name}: solver fatal error')
    if ranks == 2:
        if not (case / 'log.reconstructPar').is_file():
            raise IncompleteCase(f'{case.name}: reconstruction log pending')
        reconstructed = (case / 'log.reconstructPar').read_text(errors='replace')
        if not END.search(reconstructed):
            raise IncompleteCase(f'{case.name}: reconstruction has not ended')
        if FATAL.search(reconstructed):
            raise ValueError(f'{case.name}: reconstruction fatal error')
    elif g.get('execution', {}).get('execution_mode') != 'serial':
        raise ValueError(f'{case.name}: one-rank case must declare direct serial execution')
    if 'Mesh OK.' not in (case / 'log.checkMesh').read_text(errors='replace'):
        raise ValueError(f'{case.name}: mesh check did not pass')
    for name in ('points', 'faces', 'owner', 'neighbour', 'boundary'):
        if not (case / 'constant/polyMesh' / name).is_file():
            raise ValueError(f'{case.name}: reconstructed root mesh is missing {name}')
    control = (case / 'system/controlDict').read_text()
    start = re.search(r'\bstartTime\s+([^;\s]+)\s*;', control)
    start_from = re.search(r'\bstartFrom\s+([^;\s]+)\s*;', control)
    if not start or not start_from or start_from.group(1) != 'startTime':
        raise ValueError(f'{case.name}: an explicit startTime is required')
    start_value = float(start.group(1))
    if not math.isfinite(start_value) or start_value < 0:
        raise ValueError(f'{case.name}: invalid startTime')
    initial_candidates = [p.name for p in case.iterdir() if p.is_dir()
                          and re.fullmatch(r'[+\-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+\-]?\d+)?', p.name)
                          and math.isclose(float(p.name), start_value, rel_tol=0, abs_tol=1e-12)]
    if len(initial_candidates) != 1:
        raise ValueError(f'{case.name}: unique actual initial-time directory is missing')
    initial_time = initial_candidates[0]
    initialization = None
    cold_initialization = None
    if start_value != 0:
        if (case / 'cold_preparation.json').exists():
            raise ValueError(f'{case.name}: cold preparation conflicts with nonzero mapped start')
        initialization = validate_initialization(case, g, initial_time)
        mapped = json.loads((case / 'initialization.json').read_text())
        if mapped.get('mpi_ranks', 2) != ranks or (ranks == 1 and mapped.get('execution_mode') != 'serial'):
            raise ValueError(f'{case.name}: mapped execution rank/mode provenance differs')
    elif (case / 'initialization.json').exists():
        raise ValueError(f'{case.name}: mapping provenance conflicts with cold startTime 0')
    elif (case / 'cold_preparation.json').is_file():
        cold_initialization = validate_cold_initialization(case, g)
    elif ranks == 1 and g.get('initialization_method') == 'cold_start':
        raise ValueError(f'{case.name}: explicit cold serial preparation record is missing')
    rows, volumes = {}, {}
    for line in text.splitlines():
        match = re.match(PREFIX + r'TILT\s+(.+?)\s*$', line)
        if match:
            values = [float(v) for v in match.group(1).split()]
            if len(values) != 8 or not all(math.isfinite(v) for v in values):
                raise ValueError(f'{case.name}: malformed/nonfinite source diagnostic')
            t = values[0]
            if t in rows and any(not math.isclose(a, b, rel_tol=2e-6, abs_tol=1e-9)
                                 for a, b in zip(rows[t], values)):
                raise ValueError(f'{case.name}: conflicting MPI source diagnostics at {t:g}')
            rows[t] = values
        match = re.match(PREFIX + r'DISK_VOLUME\s+(\d+)\s+(\S+)', line)
        if match:
            rotor, volume = int(match.group(1)), float(match.group(2))
            if not math.isfinite(volume) or volume <= 0:
                raise ValueError(f'{case.name}: invalid actuator volume')
            if rotor in volumes and not math.isclose(volumes[rotor], volume, rel_tol=2e-6):
                raise ValueError(f'{case.name}: conflicting MPI actuator volumes')
            volumes[rotor] = volume
    if len(rows) < 3:
        raise ValueError(f'{case.name}: insufficient source history')
    end, first = max(rows), min(rows)
    avg_start, avg_stop = float(g['averaging_start_s']), float(g['averaging_stop_s'])
    if not (math.isfinite(avg_start) and math.isfinite(avg_stop) and 0 <= avg_start < avg_stop):
        raise ValueError(f'{case.name}: invalid averaging window')
    if avg_start < start_value - 1e-7:
        raise ValueError(f'{case.name}: averaging window precedes actual initialization')
    if first > avg_start + 1e-7 or end < avg_stop - 1e-7:
        raise IncompleteCase(f'{case.name}: source history does not cover averaging window')
    times = []
    for path in case.iterdir():
        if not path.is_dir():
            continue
        try:
            value = float(path.name)
        except ValueError:
            continue
        if math.isclose(value, end, rel_tol=0, abs_tol=1e-7):
            times.append(path.name)
    if len(times) != 1:
        raise IncompleteCase(f'{case.name}: unique reconstructed final time pending')
    final_time = times[0]
    for directory in (initial_time, final_time):
        if not all((case / directory / field).is_file() and (case / directory / field).stat().st_size > 0
                   for field in ('U', 'p')):
            raise IncompleteCase(f'{case.name}: initial/final root fields pending')
    radius, thickness = float(g['radius_m']), float(g['thickness_m'])
    if not (math.isfinite(radius) and math.isfinite(thickness) and radius > 0 and thickness > 0):
        raise ValueError(f'{case.name}: invalid geometry dimensions')
    expected = math.pi * radius * radius * thickness
    if 'geometric_volume_per_rotor_m3' in g and not math.isclose(
            float(g['geometric_volume_per_rotor_m3']), expected, rel_tol=1e-10):
        raise ValueError(f'{case.name}: geometric volume metadata disagrees with dimensions')
    if set(volumes) != set(range(int(g['rotors']))):
        raise ValueError(f'{case.name}: missing/unexpected actuator-volume diagnostics')
    error = max(abs(v / expected - 1) for v in volumes.values())
    if error >= .01:
        raise ValueError(f'{case.name}: actuator-volume error is not below 1%')
    continuity = re.findall(r'global\s*=\s*([^,\s]+)', text)
    if not continuity or not math.isfinite(float(continuity[-1])) or abs(float(continuity[-1])) >= 1e-6:
        raise ValueError(f'{case.name}: final continuity check failed')
    source_sha = digest(case / 'constant/fvModels')
    if source_sha != EXPECTED_SOURCE_SHA256 or g.get('source_sha256') != source_sha:
        raise ValueError(f'{case.name}: source hash differs from approved Tello model')
    if (g.get('quadrature_subcells_xy') != 16 or g.get('quadrature_subcells_per_cell') != 256):
        raise ValueError(f'{case.name}: unexpected source cubature')
    check = dict(rotors=int(g['rotors']), battery_budget_W=float(g['battery_power_W']),
                distance_cm=float(g['distance_cm']), tilt_deg=float(g['tilt_deg']), level=g['level'],
                radius_m=radius, thickness_m=thickness, initial_time=initial_time, final_time=final_time,
                end_s=end, averaging_start_s=avg_start, averaging_stop_s=avg_stop,
                solver_ended=True, reconstruction_ended=(ranks == 2), mesh_ok=True,
                last_global_continuity=float(continuity[-1]),
                actuator_volumes_m3=[volumes[i] for i in range(int(g['rotors']))],
                exact_geometric_volume_m3=expected, maximum_volume_error_percent=100 * error,
                source_sha256=source_sha, run_status=status)
    if initialization is not None:
        check['initialization'] = initialization
    if cold_initialization is not None:
        check['cold_initialization'] = cold_initialization
    if ranks == 1:
        check['root_fields_written_directly'] = True
    return check


def case_files(case, check):
    allowed = {'0', check['initial_time'], check['final_time'], 'constant', 'system',
               'Allrun', 'case.foam', 'geometry.json', 'run_status.json',
               'initialization.json', 'prepare_mapped.py', 'cold_preparation.json'}
    files = []
    for top in sorted(case.iterdir()):
        if top.name not in allowed and not (top.is_file() and top.name.startswith('log.')):
            continue
        if top.is_file():
            files.append(top)
        elif top.is_dir():
            files.extend(p for p in sorted(top.rglob('*')) if p.is_file())
    if (case / 'initialization.json').is_file():
        provenance = json.loads((case / 'initialization.json').read_text())
        for group in ('target_inputs_after_preparation', 'target_mesh', 'mapped_fields', 'preparation_logs'):
            for relative in provenance[group]:
                rel = Path(relative)
                if rel.is_absolute() or '..' in rel.parts:
                    raise ValueError(f'{case.name}: invalid referenced input path: {relative}')
                path = case / rel
                if not path.is_file():
                    raise ValueError(f'{case.name}: referenced input is missing: {relative}')
                files.append(path)
    return sorted(set(files))


def snapshot(case, files):
    records = {}
    for path in files:
        if path.is_symlink():
            raise ValueError(f'{case.name}: symlink archive inputs are unsupported: {path}')
        st = path.stat()
        row = {'size': st.st_size, 'mtime_ns': st.st_mtime_ns}
        if st.st_size < 1024 * 1024 or path.name.startswith('log.'):
            row['sha256'] = digest(path)
        records[path.relative_to(case).as_posix()] = row
    return dict(metadata_sha256=digest(case / 'geometry.json'), files=records)


def read_index(out):
    path, archive = out / 'archive_index.json', out / 'cases.zip'
    if not path.exists():
        if archive.exists():
            raise StaleArchive('cases.zip exists without a committed archive index')
        return dict(format_version=2, source_sha256=EXPECTED_SOURCE_SHA256, cases={})
    index = json.loads(path.read_text())
    if index.get('format_version') != 2 or index.get('source_sha256') != EXPECTED_SOURCE_SHA256:
        raise StaleArchive('Unexpected archive index format/source identity')
    if index['cases'] and not archive.is_file():
        raise StaleArchive('Archive index exists without cases.zip')
    return index


def verify_archive_members(z, index):
    expected = {f'cases/{case}/{rel}': row['size']
                for case, record in index['cases'].items()
                for rel, row in record['snapshot']['files'].items()}
    actual = {info.filename: info for info in z.infolist()}
    if len(actual) != len(z.infolist()) or set(expected) != set(actual):
        raise StaleArchive('ZIP member catalog differs from committed index or contains duplicates')
    for name, size in expected.items():
        if actual[name].file_size != size:
            raise StaleArchive(f'ZIP member size differs from index: {name}')
    for case, record in index['cases'].items():
        if set(record['member_crc32']) != set(record['snapshot']['files']):
            raise StaleArchive(f'Incomplete CRC index: {case}')
        for rel, crc in record['member_crc32'].items():
            if actual[f'cases/{case}/{rel}'].CRC != crc:
                raise StaleArchive(f'ZIP CRC catalog differs from index: {case}/{rel}')


def verify_cached(case, record):
    check = validate_case(case)
    if snapshot(case, case_files(case, check)) != record['snapshot'] or check != record['validation']:
        raise StaleArchive(f'{case.name}: archived source snapshot changed; preserve archive/index for diagnosis')
    return check


def verify_archive(root, out, full_crc=False):
    """Caller holds the archive lock; check all indexed cases and ZIP catalog."""
    index = read_index(out)
    checks = {name: verify_cached(root / name, record) for name, record in index['cases'].items()}
    if (out / 'cases.zip').exists():
        with zipfile.ZipFile(out / 'cases.zip') as z:
            verify_archive_members(z, index)
            if full_crc:
                bad = z.testzip()
                if bad is not None:
                    raise StaleArchive(f'Full case ZIP CRC error: {bad}')
    return checks


def recover_pending_index(root, out):
    """Caller holds archive lock. Recover only a complete verifiable commit.

    The pending index is flushed only after a closed/fsynced ZIP. Require all
    old records unchanged, at most one new case, current immutable snapshots,
    the exact ZIP catalog and full CRC before publishing that pending index.
    Partial/unverifiable journals are preserved for explicit diagnosis.
    """
    pending = out / 'archive_index.json.updated'
    if not pending.exists():
        return False
    try:
        candidate = json.loads(pending.read_text())
    except json.JSONDecodeError as exc:
        raise StaleArchive('Incomplete pending index preserved; audit before recovery') from exc
    if candidate.get('format_version') != 2 or candidate.get('source_sha256') != EXPECTED_SOURCE_SHA256 or not isinstance(candidate.get('cases'), dict):
        raise StaleArchive('Pending index identity is not valid for this study')
    if (out / 'archive_index.json').exists():
        committed = read_index(out)
    else:
        committed = dict(format_version=2, source_sha256=EXPECTED_SOURCE_SHA256, cases={})
    if (not set(committed['cases']) <= set(candidate['cases'])
            or len(set(candidate['cases']) - set(committed['cases'])) > 1
            or any(candidate['cases'][name] != record for name, record in committed['cases'].items())):
        raise StaleArchive('Pending index rewrites or skips committed records; preserved for audit')
    for name, record in candidate['cases'].items():
        if not isinstance(name, str) or name in ('', '.', '..') or Path(name).name != name or '\\' in name:
            raise StaleArchive('Pending index contains an invalid case name')
        verify_cached(root / name, record)
    with zipfile.ZipFile(out / 'cases.zip') as archive:
        verify_archive_members(archive, candidate)
        bad = archive.testzip()
        if bad is not None:
            raise StaleArchive(f'Pending archive CRC error: {bad}')
    retry_sharing(lambda: pending.replace(out / 'archive_index.json'),
                  out / 'archive_index.json', 'recover_verified_pending_index')
    recovered = dict(event='pending_index_recovered', indexed_cases=len(candidate['cases']),
                     added_cases=sorted(set(candidate['cases']) - set(committed['cases'])))
    print(json.dumps(recovered, sort_keys=True), flush=True)
    return True


def add_case(case, out):
    """Close/sync ZIP before committing one immutable case to the index."""
    with archive_lock(out):
        index = read_index(out)
        if set(index['cases']) - {c.name for c in actual_cases(case.parent)}:
            raise StaleArchive('Archive index contains a case missing from the actual root')
        if case.name in index['cases']:
            return False, verify_cached(case, index['cases'][case.name])
        check = validate_case(case)
        files = case_files(case, check)
        before = snapshot(case, files)
        with zipfile.ZipFile(out / 'cases.zip', 'a', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=3, allowZip64=True) as z:
            verify_archive_members(z, index)
            prefix = f'cases/{case.name}/'
            for path in files:
                z.write(path, prefix + path.relative_to(case).as_posix())
            crcs = {path.relative_to(case).as_posix(): z.getinfo(prefix + path.relative_to(case).as_posix()).CRC
                    for path in files}
        with (out / 'cases.zip').open('rb') as stream:
            os.fsync(stream.fileno())
        after = snapshot(case, case_files(case, check))
        if before != after or validate_case(case) != check:
            raise StaleArchive(f'{case.name}: changed during archiving; preserve archive/index for diagnosis')
        index['cases'][case.name] = dict(snapshot=after, validation=check, member_crc32=crcs)
        atomic_json(out / 'archive_index.json', index)
        return True, check


def watcher(args):
    root, out = Path(args.root), Path(args.out)
    last = None

    def report(value):
        line = json.dumps(value)
        print(line, flush=True)
        if args.progress_log:
            with Path(args.progress_log).open('a') as stream:
                stream.write(line + '\n')

    with archive_lock(out, session=True):
        with archive_lock(out):
            recover_pending_index(root, out)
            cached = verify_archive(root, out, full_crc=True)
        report(dict(event='startup_verified', indexed_cases=len(cached), crc_ok=True))
        while True:
            selected = None
            if args.selected_cases:
                selection = json.loads(Path(args.selected_cases).read_text())
                selection = selection['cases'] if isinstance(selection, dict) else selection
                if (not isinstance(selection, list) or not selection
                        or any(not isinstance(name, str) or Path(name).name != name for name in selection)
                        or len(selection) != len(set(selection))):
                    raise ValueError('Selected case list must contain unique plain case names')
                selected = set(selection)
                if set(read_index(out)['cases']) - selected:
                    raise StaleArchive('Selected scope omits an already archived case')
            cases = actual_cases(root, coarse_only=(selected is None))
            if selected is not None:
                cases = [case for case in cases if case.name in selected]
            missing = sorted(selected - {case.name for case in cases}) if selected is not None else []
            pending = []
            added = []
            for case in cases:
                try:
                    fresh, _ = add_case(case, out)
                    if fresh:
                        added.append(case.name)
                        report(dict(event='archived', case=case.name, bytes=(out / 'cases.zip').stat().st_size))
                except IncompleteCase:
                    pending.append(case.name)
            count = len(read_index(out)['cases'])
            summary = (len(cases), count, len(pending), tuple(missing))
            if added or summary != last:
                if selected is None:
                    report(dict(event='progress', coarse_found=len(cases), archived=count, pending=len(pending)))
                else:
                    report(dict(event='progress', selected_found=len(cases), selected_planned=len(selected),
                                archived=count, pending=len(pending), missing_selected_cases=missing))
                last = summary
            stop = bool(args.stop_file and Path(args.stop_file).exists())
            if not args.watch or stop:
                with archive_lock(out):
                    checks = verify_archive(root, out, full_crc=True)
                handoff = dict(event='handoff', indexed_cases=len(checks), crc_ok=True, stop_file=stop)
                handoff['pending_coarse' if selected is None else 'pending_selected_cases'] = pending
                if missing:
                    handoff['missing_selected_cases'] = missing
                report(handoff)
                return
            time.sleep(args.poll_seconds)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--out', default=str(Path(__file__).parent))
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--selected-cases', help='Explicit JSON case-name list across all levels; default is coarse only')
    parser.add_argument('--stop-file', help='Explicit handoff flag; required with --watch')
    parser.add_argument('--poll-seconds', type=float, default=30)
    parser.add_argument('--progress-log')
    args = parser.parse_args()
    if not 1 <= args.poll_seconds <= 45:
        parser.error('poll-seconds must be between 1 and 45')
    if args.watch and not args.stop_file:
        parser.error('--watch requires an explicit --stop-file handoff path')
    try:
        watcher(args)
    except Exception as exc:
        if args.progress_log:
            with Path(args.progress_log).open('a') as stream:
                stream.write(json.dumps(dict(event='error', error_type=type(exc).__name__, message=str(exc))) + '\n')
        raise
