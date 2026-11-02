"""Prepare exactly one bounded serial copy of the completed direct benchmark.

Only the fresh fine_serial case is written. No OpenFOAM meshing, mapping,
solver, decomposition or reconstruction utility is launched. foamDictionary
is used read-only to compare effective numerical settings. The completed
fine_direct source and all production cases are left unchanged.
"""
from pathlib import Path
import argparse
import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import time


SOURCE_NAME = 'fine_direct_n8_e19.2923_d1000_az0000'
TARGET_NAME = 'fine_serial_n8_e19.2923_d1000_az0000'
MESH_FILES = ('points', 'faces', 'owner', 'neighbour', 'boundary')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path,
                        default=Path('/opt/openfoam-workspace/cases/tello_solver_probe'))
    parser.add_argument('--owner', default='openfoam:openfoam')
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location('mapped_preparation', here / 'prepare_mapped.py')
    mapped = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mapped)
    root = args.root.resolve(strict=True)
    source = (root / SOURCE_NAME).resolve(strict=True)
    target = root / TARGET_NAME
    assert source.parent == root and target.resolve().parent == root
    if target.exists():
        raise FileExistsError(f'Refusing an existing serial benchmark: {target}')
    if args.owner and os.geteuid() != 0:
        raise PermissionError('--owner requires root')
    source_log = (source / 'log.foamRun').read_text(errors='replace')
    if not re.search(r'^End\s*$', source_log, re.M) or re.search(r'FOAM FATAL|MPI_ABORT', source_log):
        raise ValueError('Direct source benchmark must have completed cleanly')
    source_initialization = mapped.verify(source)
    original_geometry = json.loads((source / 'geometry.json').read_text())
    if (original_geometry['study_role'] != 'sensitivity' or original_geometry['mesh_cells'] != 922576
            or original_geometry['source_sha256'] != mapped.SOURCE_SHA):
        raise ValueError('Unexpected source benchmark identity')
    source_configuration, source_signature, source_switches = mapped.solver_configuration(source)
    if (source_configuration['decomposition']['numberOfSubdomains'] != ['2'] or
            source_switches != dict(p=True, pFinal=True)):
        raise ValueError('Source must be the direct-coarsest two-rank benchmark')
    expected_control = dict(startFrom='startTime', startTime='.6', endTime='.62',
                            stopAt='endTime', writeInterval='.01')
    for key, expected in expected_control.items():
        actual = mapped.dictionary_value(source, 'system/controlDict', key)
        if key in ('startTime', 'endTime', 'writeInterval'):
            if float(actual) != float(expected):
                raise ValueError(f'Unexpected source {key}')
        elif actual != expected:
            raise ValueError(f'Unexpected source {key}')
    if (source / '0.6/phi').exists():
        raise ValueError('Source initial phi must be absent')
    source_input_paths = ['geometry.json', 'initialization.json', 'Allrun', 'prepare_mapped.py',
                          'case.foam', 'log.blockMesh', 'log.checkMesh', 'log.mapFields', 'log.foamRun']
    for folder in ('0', '0.6', 'constant', 'system'):
        for path in sorted((source / folder).rglob('*')):
            if path.is_symlink():
                raise ValueError(f'Refusing symlinked input: {path}')
            if path.is_file():
                source_input_paths.append(str(path.relative_to(source)))
    source_input_paths = sorted(set(source_input_paths))
    source_before = {p: mapped.record(source / p) for p in source_input_paths}
    target.mkdir()
    for folder in ('0', '0.6', 'constant', 'system'):
        shutil.copytree(source / folder, target / folder)
    for name in ('geometry.json', 'Allrun', 'prepare_mapped.py', 'case.foam',
                 'log.blockMesh', 'log.checkMesh', 'log.mapFields'):
        shutil.copy2(source / name, target / name)
    input_paths = [p for p in source_input_paths if p not in
                   ('initialization.json', 'log.foamRun', 'case.foam')
                   and not p.startswith(('0.6/', 'constant/polyMesh/', 'log.'))]
    before_inputs = {p: mapped.record(target / p) for p in input_paths}
    # Only the serial execution dictionary and runner change among executable
    # inputs. Geometry additions below describe that execution and provenance.
    (target / 'system/decomposeParDict').write_text('''FoamFile
{
    format ascii;
    class dictionary;
    object decomposeParDict;
}
numberOfSubdomains 1;
method hierarchical;
hierarchicalCoeffs
{
    n (1 1 1);
    order xyz;
}
''')
    shutil.copyfile(here / 'Allrun_warm_serial.template', target / 'Allrun')
    (target / 'Allrun').chmod(0o755)
    configuration, signature, switches = mapped.solver_configuration(target)
    if (configuration['decomposition']['numberOfSubdomains'] != ['1'] or
            switches != dict(p=True, pFinal=True)):
        raise ValueError('Serial configuration identity is inconsistent')
    source_method = copy.deepcopy(source_configuration)
    serial_method = copy.deepcopy(configuration)
    source_method.pop('decomposition')
    serial_method.pop('decomposition')
    if source_method != serial_method:
        raise ValueError('A numerical setting other than decomposition changed')
    geometry = copy.deepcopy(original_geometry)
    geometry['benchmark_variant'] = 'Serial, one rank; exact direct-coarsest benchmark mesh, mapped initial fields, physical and numerical settings retained'
    geometry['numerics'] = dict(geometry.get('numerics', {}), mpi_ranks=1)
    source_case = Path(source_initialization['source_case'])
    source_reference = dict(case_name=source_case.name,
        archive_member_prefix=f'cases/{source_case.name}/', source_time_directory='0.6',
        historical_study_root_name=source_case.parent.name,
        original_source_time_fields_in_archive='not guaranteed; hashes identify the original fields',
        initialized_target_rerun_requires_live_source=False)
    geometry.update(initialization_method='mapped_coarse_fields', initialization_family='mapped',
        initialization_start_time_s=.6, initialization_source_time_s=.6,
        initialization_source_case=source_case.name,
        initialization_source_case_absolute_historical=str(source_case),
        initialization_source_case_reference=source_reference,
        initialization_controller_state_policy=mapped.CONTROLLER_POLICY,
        solver_configuration=configuration, solver_configuration_sha256=signature,
        pressure_direct_solve_coarsest=switches,
        execution=dict(mpi_ranks=1, execution_mode='serial', threads_per_rank=1,
            decomposition='none performed; declared hierarchy (1 1 1)',
            start='identical mapped U,p at 0.6 s; static actuator controller reinitialized',
            runner_sha256=mapped.digest(target / 'Allrun'),
            helper_sha256=mapped.digest(target / 'prepare_mapped.py')))
    (target / 'geometry.json').write_text(json.dumps(geometry, indent=2) + '\n')
    for key in mapped.INVARIANT_KEYS:
        if original_geometry[key] != geometry[key]:
            raise ValueError(f'Physical/operating geometry changed: {key}')
    target_mesh = {str(p.relative_to(target)): mapped.record(p)
                   for p in sorted((target / 'constant/polyMesh').rglob('*')) if p.is_file()}
    mapped_fields = {f'0.6/{f}': mapped.record(target / '0.6' / f) for f in ('U', 'p')}
    for path, details in {**target_mesh, **mapped_fields}.items():
        if details['sha256'] != source_before[path]['sha256']:
            raise ValueError(f'Mesh/initial field changed while copying: {path}')
    mapped_counts = {f: mapped.field_cells(target / '0.6' / f) for f in ('U', 'p')}
    if set(mapped_counts.values()) != {922576}:
        raise ValueError('Unexpected mapped initial field sizes')
    after_inputs = {p: mapped.record(target / p) for p in input_paths}
    changed_inputs = [p for p in input_paths if before_inputs[p]['sha256'] != after_inputs[p]['sha256']]
    if set(changed_inputs) != {'geometry.json', 'Allrun', 'system/decomposeParDict'}:
        raise ValueError(f'Unexpected executable/input differences: {changed_inputs}')
    source_after = {p: mapped.record(source / p) for p in source_input_paths}
    if source_before != source_after:
        raise RuntimeError('Completed source benchmark changed during clone preparation')
    audit = dict(role='One bounded serial performance sensitivity; not a new production variant',
        prepared_unix_s=time.time(), parent_case=source.name,
        parent_case_absolute_historical=str(source), serial_case=target.name,
        interval_s=[.6, .62], write_interval_s=.01, mpi_ranks=1,
        serial_no_decomposition_or_reconstruction=True,
        mesh_and_mapped_initial_fields_byte_identical=True,
        helper_byte_identical_to_parent=True,
        physical_and_operating_metadata_unchanged=True,
        effective_numerical_method_unchanged_except_decomposition=True,
        effective_pressure_direct_solve_coarsest=switches,
        parent_solver_configuration=source_configuration,
        parent_solver_configuration_sha256=source_signature,
        solver_configuration=configuration, solver_configuration_sha256=signature,
        changed_inputs=changed_inputs,
        parent_input_records=source_before, parent_input_records_after=source_after,
        parent_files_unchanged=True,
        copied_preparation_logs='Historical upstream mesh/mapping logs, copied unchanged; no new mesh or mapping was performed',
        excluded_parent_outputs=['processor*', 'dynamicCode', '0.61', '0.62',
                                 'log.foamRun', 'log.decomposePar', 'log.reconstructPar',
                                 '.warm-solver-started'])
    (target / 'solver_variant_audit.json').write_text(json.dumps(audit, indent=2) + '\n')
    manifest = copy.deepcopy(source_initialization)
    manifest.update(case=str(target), case_logical=target.name,
        prepared_unix_s=time.time(), status='mapped_ready_no_solver_run',
        preparation_method='clone_verified_immutable_mesh_and_mapped_initial_fields',
        initialization_method='mapped_coarse_fields', initialization_family='mapped',
        initialization_start_time_s=.6, initialization_source_time_s=.6,
        initialization_source_case=source_case.name,
        source_case_logical=source_case.name,
        source_case_absolute_historical=str(source_case), source_case_reference=source_reference,
        target_start_time_s=.6, target_end_time_s=.62,
        target_averaging_start_s=.61, target_averaging_stop_s=.62,
        run_control_provenance={k: [mapped.dictionary_value(target, 'system/controlDict', k)]
            for k in ('startFrom', 'startTime', 'stopAt', 'endTime', 'writeControl', 'writeInterval')},
        actual_target_cells=922576, mapped_field_cells=mapped_counts,
        target_inputs_before_preparation=before_inputs,
        target_inputs_after_preparation={p: mapped.record(target / p)
            for p in input_paths + ['solver_variant_audit.json']},
        target_mesh=target_mesh, mapped_fields=mapped_fields,
        preparation_logs={p: mapped.record(target / p)
            for p in ('log.blockMesh', 'log.checkMesh', 'log.mapFields')},
        frozen_helper_sha256=mapped.digest(target / 'prepare_mapped.py'),
        solver_configuration=configuration, solver_configuration_sha256=signature,
        pressure_direct_solve_coarsest=switches, mpi_ranks=1, execution_mode='serial',
        benchmark_derivation=dict(parent_case=source.name,
            parent_case_absolute_historical=str(source),
            parent_initialization_sha256=source_before['initialization.json']['sha256'],
            parent_derivation=source_initialization.get('benchmark_derivation'),
            audit_path='solver_variant_audit.json', audit_sha256=mapped.digest(target / 'solver_variant_audit.json')),
        controller_state_policy=mapped.CONTROLLER_POLICY,
        study_role='sensitivity', role='One bounded serial mapped/reinitialized performance benchmark; not primary validation; no solver launched by preparation.',
        reconstruction_policy='None: serial foamRun writes directly; mapped 0.6 inputs remain frozen',
        initialized_rerun_policy='Use target immutable mesh and mapped 0.6/U,p with the frozen helper and serial Allrun. No source remapping, decomposition or reconstruction required.')
    (target / 'initialization.json').write_text(json.dumps(manifest, indent=2) + '\n')
    # Use the exact copied helper for the runner's actual pre/post contract.
    subprocess.run(['python3', str(target / 'prepare_mapped.py'), '--case', str(target),
                    '--verify-only'], check=True)
    if args.owner:
        subprocess.run(['chown', '-R', args.owner, str(target)], check=True)
    print(json.dumps(dict(ready_case=str(target), mpi_ranks=1,
        no_solver_launched=True, source_unchanged=True,
        parent_solver_signature=source_signature, serial_solver_signature=signature,
        changed_inputs=changed_inputs), indent=2))


if __name__ == '__main__':
    main()
