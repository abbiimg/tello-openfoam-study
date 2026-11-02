"""Prepare or verify a fresh same-geometry, mapped/reinitialized warm start.

Requires Foundation OpenFOAM 14 utilities on PATH. This program builds/checks
the target mesh and runs mapFields; it NEVER launches foamRun or mpirun. The
source case is read-only. Existing mapped initial fields are never overwritten.
Use --verify-only to validate an already prepared case without writing it.

Supported default grids: coarse 248400, medium 481888, fine 922576 cells.
Generate validation targets with --study-role validation --end 1.2
--average-duration .4. Sensitivity/performance probes retain their explicitly
generated windows. All targets start from exact source time 0.6 s. The source
must be the same-geometry/model coarse case; only U and p are mapped.

--direct-coarsest is OPTIONAL and changes only the pressure GAMG
directSolveCoarsest switch, preserving pFinal's original $p inheritance.
--describe-numerics prints a read-only, canonical numerical-method signature.
--ranks selects serial (1) or two-rank (2) execution for newly prepared cases;
the default remains 2. Existing initialized cases and helpers are never edited.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import time
from decimal import Decimal, InvalidOperation

SOURCE_SHA = '29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
SOURCE_TIME = '0.6'
SUPPORTED_CELLS = dict(coarse=248400, medium=481888, fine=922576)
NUMERICAL_SCHEMA = 'openfoam-foundation14-numerical-method-v1'
CONTROL_NUMERICS = ('application', 'solver', 'deltaT', 'adjustTimeStep',
                    'maxCo', 'maxDeltaT')
CONTROLLER_POLICY = (
    'Only U and p are mapped. The unchanged actuator source reinitializes its '
    'static relaxed thrust to the target inferred from mapped velocity at the '
    'first nonzero-time update; controller history is not transferred. This '
    'is a mapped/reinitialized run, not a continuation of complete source state.')
INVARIANT_KEYS = (
    'rotors', 'battery_power_W', 'distance_cm', 'tilt_deg', 'diameter_m',
    'radius_m', 'thickness_m', 'half_thickness_m', 'centers', 'normals',
    'radials', 'domain_xy_m', 'domain_z_m', 'loss_model',
    'target_shaft_power_W', 'target_air_power_W', 'quadrature_subcells_xy',
    'quadrature_subcells_per_cell', 'source_sha256',
)


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def record(path):
    s = path.stat()
    return dict(sha256=digest(path), size_bytes=s.st_size, mtime_ns=s.st_mtime_ns)


def invariant_equal(a, b):
    # JSON input arithmetic may differ by a few ULPs after CLI conversion.
    # Actual fvModels and rotorParameters are additionally byte-identical.
    if isinstance(a, (float, int)) and isinstance(b, (float, int)):
        return math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-14)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(invariant_equal(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(invariant_equal(a[k], b[k]) for k in a)
    return a == b


class FoamDictionary:
    """Small strict parser for expanded numerical dictionaries, with spans.

    It is not used to interpret physics/source code. OpenFOAM itself expands
    macros first for signatures. Raw parsing is used only to insert a literal
    setting into the original p dictionary without expanding away $p.
    """
    pattern = re.compile(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{};()\[\]]|[^\s{};()\[\]"]+')

    def __init__(self, text):
        self.text = text
        self.tokens = [(m.group(), m.start(), m.end()) for m in self.pattern.finditer(text)
                       if not m.group().startswith(('//', '/*'))]
        self.index = 0
        self.spans = {}
        self.data = self.parse(())
        if self.index != len(self.tokens):
            raise ValueError('Trailing numerical dictionary tokens')

    def parse(self, path):
        result = {}
        while self.index < len(self.tokens):
            token, begin, end = self.tokens[self.index]
            if token == '}':
                break
            if token in ('{', ';', '(', ')', '[', ']'):
                raise ValueError(f'Unexpected dictionary keyword: {token}')
            self.index += 1
            key = token
            # Function-like keys such as div(phi,U) have no intervening space.
            while self.index < len(self.tokens):
                following, a, b = self.tokens[self.index]
                if a != end or following in ('{', '}', ';'):
                    break
                key += following
                end = b
                self.index += 1
            if key in result:
                raise ValueError(f'Duplicate dictionary keyword: {key}')
            if self.index >= len(self.tokens):
                raise ValueError(f'Missing value for {key}')
            current = self.tokens[self.index]
            location = path + (key,)
            if current[0] == '{':
                self.index += 1
                result[key] = self.parse(location)
                if self.index >= len(self.tokens) or self.tokens[self.index][0] != '}':
                    raise ValueError(f'Unclosed dictionary: {key}')
                self.spans[location] = (current[1], self.tokens[self.index][1], 'dictionary')
                self.index += 1
                if self.index < len(self.tokens) and self.tokens[self.index][0] == ';':
                    self.index += 1
            else:
                values = []
                value_begin = current[1]
                while self.index < len(self.tokens) and self.tokens[self.index][0] != ';':
                    value = self.tokens[self.index][0]
                    if value in ('{', '}'):
                        raise ValueError(f'Unterminated value for {key}')
                    values.append(value)
                    self.index += 1
                if self.index >= len(self.tokens):
                    raise ValueError(f'Unterminated value for {key}')
                self.spans[location] = (value_begin, self.tokens[self.index][1], 'value')
                result[key] = values
                self.index += 1
        return result


def canonical_tokens(value):
    if isinstance(value, dict):
        return {k: canonical_tokens(v) for k, v in sorted(value.items())}
    tokens = []
    for token in value:
        if token.startswith(('$', '#')):
            raise ValueError('Unexpanded macro/directive in numerical dictionary')
        if token.lower() in ('yes', 'true', 'on'):
            token = 'true'
        elif token.lower() in ('no', 'false', 'off'):
            token = 'false'
        else:
            try:
                numeric = Decimal(token)
                if numeric.is_finite():
                    token = str(numeric.normalize()) if numeric else '0'
            except InvalidOperation:
                pass
        tokens.append(token)
    return tokens


def expanded_dictionary(case, relative):
    text = subprocess.check_output(
        ['foamDictionary', relative, '-expand', '-writePrecision', '17'],
        cwd=case, text=True)
    parsed = FoamDictionary(text).data
    parsed.pop('FoamFile', None)
    if any(key.startswith(('$', '#')) for key in parsed):
        raise ValueError(f'Unexpanded numerical dictionary: {relative}')
    return canonical_tokens(parsed)


def effective_direct_settings(solution):
    solvers = solution.get('solvers', {})
    result = {}
    for field in ('p', 'pFinal'):
        settings = solvers.get(field)
        if not isinstance(settings, dict) or settings.get('solver') != ['GAMG']:
            raise ValueError(f'Expected explicit GAMG solver for {field}')
        # Installed Foundation 14 GAMGSolver.C initializes this switch false.
        value = settings.get('directSolveCoarsest', ['false'])
        if value not in (['false'], ['true']):
            raise ValueError(f'Invalid directSolveCoarsest for {field}: {value}')
        settings['directSolveCoarsest'] = value
        result[field] = value == ['true']
    return result


def configuration_digest(configuration):
    canonical = json.dumps(configuration, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def solver_configuration(case):
    solution = expanded_dictionary(case, 'system/fvSolution')
    direct = effective_direct_settings(solution)
    control = expanded_dictionary(case, 'system/controlDict')
    missing = set(CONTROL_NUMERICS) - control.keys()
    if missing:
        raise ValueError(f'Missing time-stepping controls: {missing}')
    configuration = dict(schema=NUMERICAL_SCHEMA,
        openfoam_family='Foundation', openfoam_major_version=14,
        fvSolution=solution,
        fvSchemes=expanded_dictionary(case, 'system/fvSchemes'),
        time_stepping={k: control[k] for k in CONTROL_NUMERICS},
        decomposition=expanded_dictionary(case, 'system/decomposeParDict'))
    return configuration, configuration_digest(configuration), direct


def enable_direct_coarsest(case):
    path = case / 'system/fvSolution'
    before = expanded_dictionary(case, 'system/fvSolution')
    effective_direct_settings(before)
    text = path.read_text()
    parsed = FoamDictionary(text)
    block = parsed.spans.get(('solvers', 'p'))
    if block is None or block[2] != 'dictionary':
        raise ValueError('Could not locate original pressure solver block')
    entry = parsed.spans.get(('solvers', 'p', 'directSolveCoarsest'))
    if entry is None:
        position = block[1]
        changed = text[:position] + '\n    directSolveCoarsest yes;\n' + text[position:]
    else:
        if entry[2] != 'value':
            raise ValueError('Pressure directSolveCoarsest must be a scalar switch')
        changed = text[:entry[0]] + 'yes' + text[entry[1]:]
    # Preserve literal $p inheritance and every other input character.
    path.write_text(changed)
    after = expanded_dictionary(case, 'system/fvSolution')
    effective = effective_direct_settings(after)
    if effective != dict(p=True, pFinal=True):
        raise ValueError('Both effective p and pFinal must inherit directSolveCoarsest=yes')
    for field in ('p', 'pFinal'):
        before['solvers'][field].pop('directSolveCoarsest')
        after['solvers'][field].pop('directSolveCoarsest')
    if before != after:
        raise ValueError('Optional direct-coarsest edit changed other solver settings')
    return dict(requested=True, edit='literal p-block insertion/replacement, preserving $p',
                effective_after=effective, all_other_solver_entries_unchanged=True)


def field_cells(path):
    with path.open() as stream:
        header = stream.read(65536)
    count = re.search(r'internalField\s+nonuniform\s+List<[^>]+>\s+(\d+)', header)
    if not count:
        raise ValueError(f'Expected a saved nonuniform ASCII field: {path}')
    return int(count[1])


def run(case, command, logname):
    log = case / logname
    if log.exists():
        raise FileExistsError(f'Refusing to replace preparation log: {log}')
    with log.open('x') as stream:
        result = subprocess.run(command, cwd=case, stdout=stream, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed ({result.returncode}); inspect {log}')
    return log.read_text(errors='replace')


def dictionary_value(case, file, entry):
    return subprocess.check_output(
        ['foamDictionary', file, '-entry', entry, '-value'], cwd=case,
        text=True).strip()


def write_dict_value(case, entry, value):
    subprocess.run(['foamDictionary', 'system/controlDict', '-entry', entry,
                    '-set', value], cwd=case, check=True, stdout=subprocess.DEVNULL)


def ensure_unstarted(case):
    forbidden = list(case.glob('processor*'))
    forbidden += [case / n for n in ('log.foamRun', '.warm-solver-started') if (case / n).exists()]
    if forbidden:
        raise ValueError(f'Refusing previously started/decomposed case: {forbidden}')
    numeric = []
    for path in case.iterdir():
        if not path.is_dir():
            continue
        try:
            value = float(path.name)
        except ValueError:
            continue
        if math.isfinite(value) and value != 0:
            numeric.append(path)
    if numeric:
        raise ValueError(f'Refusing pre-existing nonzero target times: {numeric}')


def verify(case):
    manifest = json.loads((case / 'initialization.json').read_text())
    if manifest.get('status') != 'mapped_ready_no_solver_run':
        raise ValueError('Initialization manifest is not complete')
    for group in ('target_inputs_after_preparation', 'target_mesh', 'mapped_fields'):
        for relative, expected in manifest[group].items():
            actual = digest(case / relative)
            if actual != expected['sha256']:
                raise ValueError(f'Prepared input/initial field changed: {relative}')
    if 'solver_configuration' in manifest:
        signature = configuration_digest(manifest['solver_configuration'])
        geometry = json.loads((case / 'geometry.json').read_text())
        if (signature != manifest.get('solver_configuration_sha256') or
                signature != geometry.get('solver_configuration_sha256') or
                manifest['solver_configuration'] != geometry.get('solver_configuration')):
            raise ValueError('Numerical-method signature/provenance is inconsistent')
        if manifest.get('frozen_helper_sha256') != digest(case / 'prepare_mapped.py'):
            raise ValueError('Frozen per-case preparation helper changed')
        ranks = manifest.get('mpi_ranks')
        if ranks is not None and (ranks not in (1, 2) or
                geometry.get('execution', {}).get('mpi_ranks') != ranks or
                manifest['solver_configuration']['decomposition']['numberOfSubdomains'] != [str(ranks)]):
            raise ValueError('Execution rank metadata/signature is inconsistent')
    if (case / SOURCE_TIME / 'phi').exists():
        raise ValueError('Mapped initial phi must be absent; solver reconstructs it')
    print(json.dumps(dict(case=str(case), initialization='verified',
                          initial_time_s=.6, source_fields_preserved=True)))
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--source', type=Path)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--verify-only', action='store_true')
    action.add_argument('--describe-numerics', action='store_true',
                        help='Print canonical effective numerical settings without writing the case')
    parser.add_argument('--direct-coarsest', action='store_true',
                        help='Opt in to pressure GAMG directSolveCoarsest=yes; default leaves it unchanged')
    parser.add_argument('--ranks', type=int, choices=(1, 2), default=2,
                        help='New-case execution ranks: 1 serial or 2 parallel (default 2)')
    parser.add_argument('--skip-runner-install', action='store_true')
    parser.add_argument('--owner', help='Optional target owner:group; requires root')
    a = parser.parse_args()
    case = a.case.resolve(strict=True)
    if a.direct_coarsest and (a.verify_only or a.describe_numerics):
        parser.error('--direct-coarsest is only valid when preparing a fresh case')
    if a.describe_numerics:
        config, signature, direct = solver_configuration(case)
        print(json.dumps(dict(solver_configuration=config,
                              solver_configuration_sha256=signature,
                              pressure_direct_solve_coarsest=direct), indent=2))
        return
    if a.verify_only:
        verify(case)
        return
    if a.source is None:
        parser.error('--source is required for preparation')
    source = a.source.resolve(strict=True)
    if source == case or source in case.parents or case in source.parents:
        raise ValueError('Source and target must be separate, non-nested cases')
    ensure_unstarted(case)
    if (case / 'initialization.json').exists():
        raise FileExistsError('Prepared initialization exists; use --verify-only')
    for utility in ('blockMesh', 'checkMesh', 'mapFields', 'foamDictionary'):
        if not shutil.which(utility):
            raise RuntimeError(f'{utility} unavailable; source OpenFOAM 14 environment')
    if a.owner and os.geteuid() != 0:
        raise PermissionError('--owner requires root')
    g = json.loads((case / 'geometry.json').read_text())
    sg = json.loads((source / 'geometry.json').read_text())
    invariants = {}
    for key in INVARIANT_KEYS:
        if not invariant_equal(g.get(key), sg.get(key)) or key not in g:
            raise ValueError(f'Geometry/operating invariant differs: {key}')
        invariants[key] = g[key]
    physical_files = ('fvModels', 'rotorParameters', 'physicalProperties', 'momentumTransport')
    for name in physical_files:
        if digest(case / 'constant' / name) != digest(source / 'constant' / name):
            raise ValueError(f'Source physics/parameters differ: {name}')
    if digest(source / 'constant/fvModels') != SOURCE_SHA or g['source_sha256'] != SOURCE_SHA:
        raise ValueError('Unexpected actuator source SHA256')
    expected_cells = SUPPORTED_CELLS.get(g.get('level'))
    if expected_cells is None or g['mesh_cells'] != expected_cells:
        raise ValueError('Target must declare a supported default coarse, medium or fine grid')
    if sg.get('level') != 'coarse' or sg.get('mesh_cells') != SUPPORTED_CELLS['coarse']:
        raise ValueError('Exact 0.6 source must be the same-geometry coarse grid')
    end = float(dictionary_value(case, 'system/controlDict', 'endTime'))
    if end <= .6:
        raise ValueError('Target endTime must exceed mapped source time')
    role = g.get('study_role')
    if role not in ('validation', 'sensitivity'):
        raise ValueError('Mapped targets must explicitly declare validation or sensitivity study_role')
    interval = (float(g['averaging_start_s']), float(g['averaging_stop_s']))
    if not (.6 <= interval[0] < interval[1] <= end + 1e-9):
        raise ValueError('Averaging window must follow mapped start and lie within target run')
    if not math.isclose(float(g['configured_end_time_s']), end, abs_tol=1e-9, rel_tol=0):
        raise ValueError('Geometry and control endTime differ')
    if role == 'validation' and not all(math.isclose(x, y, abs_tol=1e-9, rel_tol=0)
            for x, y in zip((end, *interval), (1.2, .8, 1.2))):
        raise ValueError('Mapped validation requires end 1.2 s and averaging 0.8-1.2 s')
    if (case / 'constant/polyMesh').exists():
        raise FileExistsError('Fresh preparation requires no existing target mesh')
    source_paths = ['geometry.json', '0.6/U', '0.6/p']
    source_paths += ['constant/' + name for name in physical_files]
    source_paths += ['constant/polyMesh/' + name for name in
                     ('points', 'faces', 'owner', 'neighbour', 'boundary')]
    # Exact directory required; never ask mapFields for latestTime.
    if not (source / SOURCE_TIME).is_dir():
        raise FileNotFoundError(f'Exact source time directory absent: {source / SOURCE_TIME}')
    source_field_cells = {f: field_cells(source / SOURCE_TIME / f) for f in ('U', 'p')}
    if any(n != sg['mesh_cells'] for n in source_field_cells.values()):
        raise ValueError('Saved source field sizes differ from the declared coarse mesh')
    source_before = {p: record(source / p) for p in source_paths}
    direct_change = (enable_direct_coarsest(case) if a.direct_coarsest else
                     dict(requested=False, edit='none; original setting retained'))
    # Freeze the helper/runner before any numerical/input snapshot or mapping.
    here = Path(__file__).resolve().parent
    helper_hash = digest(Path(__file__))
    if not a.skip_runner_install:
        runner_template = 'Allrun_warm_serial.template' if a.ranks == 1 else 'Allrun_warm.template'
        decomposition_template = 'decomposeParDict_serial.template' if a.ranks == 1 else 'decomposeParDict.template'
        shutil.copyfile(here / runner_template, case / 'Allrun')
        (case / 'Allrun').chmod(0o755)
        if here != case:
            shutil.copyfile(Path(__file__), case / 'prepare_mapped.py')
        shutil.copyfile(here / decomposition_template, case / 'system/decomposeParDict')
    if digest(case / 'prepare_mapped.py') != helper_hash:
        raise ValueError('Per-case helper must be a frozen copy of the executing version')
    if dictionary_value(case, 'system/decomposeParDict', 'numberOfSubdomains') != str(a.ranks):
        raise ValueError('Warm runner rank count differs from requested execution')
    write_dict_value(case, 'startFrom', 'startTime')
    write_dict_value(case, 'startTime', SOURCE_TIME)
    configuration, numerical_hash, direct = solver_configuration(case)
    direct_change['effective_after'] = direct
    source_reference = dict(case_name=source.name, archive_member_prefix=f'cases/{source.name}/',
                            source_time_directory=SOURCE_TIME,
                            historical_study_root_name=source.parent.name,
                            original_source_time_fields_in_archive='not guaranteed; hashes identify the original fields',
                            initialized_target_rerun_requires_live_source=False)
    g.update(initialization_method='mapped_coarse_fields', initialization_family='mapped',
        initialization_start_time_s=.6, initialization_source_time_s=.6,
        initialization_source_case=source.name,
        initialization_source_case_absolute_historical=str(source),
        initialization_source_case_reference=source_reference,
        initialization_controller_state_policy=CONTROLLER_POLICY,
        solver_configuration=configuration, solver_configuration_sha256=numerical_hash,
        pressure_direct_solve_coarsest=direct)
    execution = dict(g.get('execution', {}))
    execution.update(mpi_ranks=a.ranks, execution_mode='serial' if a.ranks == 1 else 'parallel',
        threads_per_rank=1,
        decomposition=('none performed; declared hierarchy (1 1 1)' if a.ranks == 1 else 'hierarchical (2 1 1)'),
        start='mapped U,p at 0.6 s; static actuator controller reinitialized',
        runner_sha256=digest(case / 'Allrun'), helper_sha256=helper_hash)
    g['execution'] = execution
    (case / 'geometry.json').write_text(json.dumps(g, indent=2) + '\n')
    input_paths = ['geometry.json', '0/U', '0/p', 'system/blockMeshDict',
                   'system/controlDict', 'system/fvSchemes', 'system/fvSolution',
                   'Allrun', 'prepare_mapped.py', 'system/decomposeParDict']
    input_paths += ['constant/' + name for name in physical_files]
    # The optional switch, start controls and provenance are already final here.
    initial_inputs = {p: record(case / p) for p in input_paths}
    meshlog = run(case, ['blockMesh'], 'log.blockMesh')
    checklog = run(case, ['checkMesh'], 'log.checkMesh')
    if 'Mesh OK.' not in checklog:
        raise RuntimeError('Target mesh did not report Mesh OK.')
    count = re.search(r'^\s*cells:\s*(\d+)\s*$', checklog, re.M)
    if count is None or int(count[1]) != g['mesh_cells']:
        raise RuntimeError('Actual target cell count differs from declared geometry mesh')
    actual_cells = int(count[1])
    seed = case / SOURCE_TIME
    seed.mkdir()
    for field in ('U', 'p'):
        shutil.copy2(case / '0' / field, seed / field)
    seeded = {f'0.6/{f}': record(seed / f) for f in ('U', 'p')}
    command = ['mapFields', str(source), '-sourceTime', SOURCE_TIME,
               '-consistent', '-mapMethod', 'interpolate']
    mapping_log = run(case, command, 'log.mapFields')
    # Foundation 14 prints the dimensional suffix as "Source time: 0.6s".
    selected = re.findall(r'Source time:\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(?:s)?\s', mapping_log)
    if not selected or any(float(t) != .6 for t in selected):
        raise RuntimeError('mapFields log did not confirm exact Source time: 0.6')
    if not re.search(r'^End\s*$', mapping_log, re.M) or 'FOAM FATAL' in mapping_log:
        raise RuntimeError('Mapping did not finish cleanly')
    if (seed / 'phi').exists():
        raise RuntimeError('Unexpected phi: preparation must map only U and p')
    mapped_field_cells = {f: field_cells(seed / f) for f in ('U', 'p')}
    if any(n != actual_cells for n in mapped_field_cells.values()):
        raise RuntimeError('Mapped target field sizes differ from the checked target mesh')
    source_after = {p: record(source / p) for p in source_paths}
    if source_before != source_after:
        raise RuntimeError('Source files changed during mapping')
    final_inputs = {p: record(case / p) for p in input_paths}
    if initial_inputs != final_inputs or digest(Path(__file__)) != helper_hash:
        raise RuntimeError('Frozen inputs or executing helper changed during preparation')
    control = expanded_dictionary(case, 'system/controlDict')
    run_provenance = {k: control[k] for k in
        ('startFrom', 'startTime', 'stopAt', 'endTime', 'writeControl', 'writeInterval',
         'writeFormat', 'writePrecision', 'writeCompression', 'timeFormat', 'timePrecision')
        if k in control}
    manifest = dict(
        status='mapped_ready_no_solver_run', prepared_unix_s=time.time(),
        case=str(case), source_case=str(source), source_time_directory='0.6',
        case_logical=case.name, source_case_logical=source.name,
        source_case_absolute_historical=str(source), source_case_reference=source_reference,
        initialization_method='mapped_coarse_fields', initialization_family='mapped',
        initialization_source_case=source.name, initialization_source_time_s=.6,
        initialization_start_time_s=.6,
        target_start_time_s=.6, source_time_confirmed_by_mapFields=selected,
        target_end_time_s=end, target_averaging_start_s=interval[0],
        target_averaging_stop_s=interval[1], run_control_provenance=run_provenance,
        mapping_method='interpolate', consistent_geometry=True,
        map_command=command, source_case_files_before=source_before,
        portable_map_command=['mapFields', '<EXTRACTED_ARCHIVE_ROOT>/cases/' + source.name,
                              '-sourceTime', SOURCE_TIME, '-consistent', '-mapMethod', 'interpolate'],
        portable_map_command_requirements='Remapping requires independently available original source 0.6/U,p and source mesh matching the recorded hashes. The source case archive prefix does not guarantee its intermediate 0.6 fields are stored.',
        initialized_rerun_policy='Prefer the archived target mesh, mapped 0.6/U,p, frozen inputs/helper/Allrun and initialization.json. verify-only and the initialized warm runner do not require a live source case or remapping.',
        source_case_files_after=source_after, source_unchanged=True,
        invariants=invariants, actual_target_cells=actual_cells,
        source_field_cells=source_field_cells, mapped_field_cells=mapped_field_cells,
        source_invariants={key: sg[key] for key in INVARIANT_KEYS},
        metadata_numeric_tolerance=dict(relative=1e-12, absolute=1e-14),
        actual_source_and_target_fvModels_and_rotorParameters_byte_identical=True,
        actual_source_and_target_physicalProperties_and_momentumTransport_byte_identical=True,
        target_inputs_before_preparation=initial_inputs,
        target_inputs_after_preparation=final_inputs,
        seeded_fields=seeded, mapped_fields={f'0.6/{f}': record(seed / f) for f in ('U', 'p')},
        target_mesh={'constant/polyMesh/' + p: record(case / 'constant/polyMesh' / p)
                     for p in ('points', 'faces', 'owner', 'neighbour', 'boundary')},
        preparation_logs={p: record(case / p) for p in ('log.blockMesh', 'log.checkMesh', 'log.mapFields')},
        source_sha256=SOURCE_SHA,
        frozen_helper_sha256=helper_hash,
        mpi_ranks=a.ranks, execution_mode='serial' if a.ranks == 1 else 'parallel',
        solver_configuration=configuration, solver_configuration_sha256=numerical_hash,
        pressure_direct_solve_coarsest=direct, optional_direct_coarsest=direct_change,
        numerical_signature_excludes=['startFrom', 'startTime', 'endTime', 'stopAt',
            'write/output controls', 'averaging windows', 'initialization regime'],
        phi_policy='Not copied or mapped: solver reconstructs phi from mapped U.',
        controller_state_policy=CONTROLLER_POLICY,
        study_role=role,
        role=('Mapped/reinitialized validation, averaging 0.8-1.2 s; no solver launched by preparation.'
              if role == 'validation' else
              'Mapped/reinitialized performance/initialization sensitivity probe; not primary validation; no solver launched by preparation.'),
        reconstruction_policy=('None: serial foamRun writes directly; mapped 0.6 inputs remain frozen'
            if a.ranks == 1 else 'reconstructPar -time 0.60000001: excludes mapped initial time 0.6'),
    )
    (case / 'initialization.json').write_text(json.dumps(manifest, indent=2) + '\n')
    verify(case)
    if a.owner:
        subprocess.run(['chown', '-R', a.owner, str(case)], check=True)


if __name__ == '__main__':
    main()
