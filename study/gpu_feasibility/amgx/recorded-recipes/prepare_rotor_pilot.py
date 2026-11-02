"""Prepare two fresh five-step C29 compatibility pilots; never launches CFD.

Run as openfoam with Foundation14 sourced. Frozen sources are read only.
"""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import shutil
import stat
import subprocess
import zipfile

out = Path(__file__).resolve().parent
project = out.parents[1]
seed = project/'outputs/tello_refinement/gpu_feasibility/benchmark_reproduction'
base = Path('/opt/openfoam-workspace/cases/amgx_gpu_pilots_20261102')
frozen = Path('/opt/openfoam-workspace/gpu-feasibility/pressure-offload/benchmarks_20261101/cpu_serial')
amgx = Path('/opt/openfoam-workspace/gpu-feasibility/amgx-cuda')
assert os.environ.get('WM_PROJECT_VERSION') == '14'
assert os.geteuid() != 0

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def record(path):
    return dict(sha256=sha(path), size_bytes=path.stat().st_size)

package = json.loads((seed/'reproduction_manifest.json').read_text())
variant = package['variants']['cpu_serial']
original = seed/'overrides/cpu_serial/benchmark_manifest.json'
assert sha(original) == variant['benchmark_manifest_sha256']
benchmark = json.loads(original.read_text())
assert sha(seed/'shared_seed.zip') == package['shared_seed_archive']['sha256']
expected = json.loads((out/'setup_status.json').read_text())
for item in expected['artifacts'].values():
    assert sha(Path(item['path'])) == item['sha256'], item['path']
assert sha(out/'AmgXPressure.C') == json.loads((out/'adapter_build.json').read_text())['source_sha256']
assert not subprocess.check_output(['git','-C',str(amgx/'AMGX'),'status','--porcelain'], text=True).strip()

dynamic = frozen/'dynamicCode'
dynamic_records = {str(p.relative_to(dynamic)):record(p) for p in dynamic.rglob('*') if p.is_file()}
assert 'rotors/Make/SHA1Digest' in dynamic_records
assert (dynamic/'rotors/Make/SHA1Digest').read_text().strip() == '_7ae57bb77feaae19c26ff305b44ebb5a6819f2ef'
librel = 'platforms/linuxArm64GccDPInt32Opt/lib/librotors_7ae57bb77feaae19c26ff305b44ebb5a6819f2ef.so'
assert librel in dynamic_records
assert sha(frozen/'constant/fvModels') == benchmark['frozen_inputs']['constant/fvModels']['sha256']
source_before = {rel:record(frozen/rel) for rel in benchmark['frozen_inputs']}
assert source_before == benchmark['frozen_inputs']

def edit(case, file, entry, value):
    subprocess.run(['foamDictionary',str(case/file),'-entry',entry,'-set',value],
                   check=True, stdout=subprocess.DEVNULL)

cases = {}
for name in ('rotor-native', 'rotor-amgx'):
    case = base/name
    assert not case.exists(), 'Never overwrite an existing pilot: '+str(case)
    case.mkdir()
    with zipfile.ZipFile(seed/'shared_seed.zip') as archive:
        assert len(archive.namelist()) == len(set(archive.namelist()))
        assert set(archive.namelist()) == set(package['shared_seed_files'])
        for item in archive.infolist():
            relative = PurePosixPath(item.filename)
            assert not relative.is_absolute() and '..' not in relative.parts
            assert not stat.S_ISLNK(item.external_attr >> 16)
            target = case/relative
            assert target.resolve().is_relative_to(base)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(item) as source, target.open('xb') as dest:
                shutil.copyfileobj(source, dest, 1024*1024)
    for rel, rec in variant['override_files'].items():
        source = seed/'overrides/cpu_serial'/rel
        assert record(source) == rec
        assert not (case/rel).exists()
        (case/rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, case/rel)
    for rel, rec in benchmark['frozen_inputs'].items():
        assert record(case/rel) == rec, rel
    assert not (case/'0.6/phi').exists()
    # Exact generated code, digest, and compiled artifact copied from frozen CPU case.
    # No shared writable symlinks and no recompile are needed on this workstation.
    shutil.copytree(dynamic, case/'dynamicCode', copy_function=shutil.copyfile)
    for rel, rec in dynamic_records.items(): assert record(case/'dynamicCode'/rel) == rec
    for directory in ('runtime_cache/cuda', 'runtime_cache/tmp'):
        (case/directory).mkdir(parents=True)
    edit(case,'system/controlDict','endTime','0.60085')
    # This output-only function retains the original adjustableRunTime alignment.
    edit(case,'system/controlDict','functions', '''{
pilotFields { type writeObjects; libs ("libutilityFunctionObjects.so");
objects (U p phi); writeOption anyWrite;
writeControl timeStep; writeInterval 5; }
}''')
    gpu = name.endswith('amgx')
    if gpu:
        edit(case,'system/controlDict','libs',f'("{amgx}/install/lib/libAmgXPressure.so")')
        for field, reltol in (('p','.05'),('pFinal','0')):
            edit(case,'system/fvSolution','solvers/'+field,
                 '{ solver AmgXPressure; tolerance 1e-7; relTol '+reltol+'; maxIter 1000; minIter 0; }')
    env = (f'export LD_LIBRARY_PATH={amgx}/install/lib:{amgx}/cuda13/lib:/usr/lib/wsl/lib:$LD_LIBRARY_PATH\n'
           f'export LD_PRELOAD={amgx}/install/lib/libamgxLaunchAudit.so\n') if gpu else ''
    script = case/'AllrunPilot'
    script.write_text(f'''#!/bin/bash
set -e
cd "$(dirname "$0")"
source /opt/openfoam14/etc/bashrc
set -u -o pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 WM_NCOMPPROCS=1
export CUDA_CACHE_PATH="$PWD/runtime_cache/cuda"
export TMPDIR="$PWD/runtime_cache/tmp"
export XDG_CACHE_HOME="$PWD/runtime_cache"
{env}exec nice -n 15 timeout --signal=TERM --kill-after=15 900 foamRun
''')
    script.chmod(0o755)
    paths = [p for p in case.rglob('*') if p.is_file() and not p.is_relative_to(case/'runtime_cache')]
    cases[name] = dict(path=str(case), input_hashes={str(p.relative_to(case)):record(p) for p in paths},
                       backend='AmgXPressure' if gpu else 'GAMG', expected_steps=5)
assert source_before == {rel:record(frozen/rel) for rel in source_before}
report = dict(kind='Prepared actual C29 rotor compatibility pilots; no timing comparison',
              cases=cases, cells=922576, source_case=str(frozen),
              source_input_hashes=source_before, source_seed=str(seed/'shared_seed.zip'),
              source_seed_sha256=sha(seed/'shared_seed.zip'),
              actuator_generated_library=dict(path=str(dynamic/librel), **dynamic_records[librel]),
              actuator_dynamic_code_hashes=dynamic_records,
              libraries=expected['artifacts'], adapter_source_sha256=sha(out/'AmgXPressure.C'),
              start_time_s=.6, end_time_setting_s=.60085, expected_steps=5,
              unchanged_physics='C29 actuator geometry, power/loss map, source, mesh, U/p start, schemes, adaptive controls and velocity solves',
              changes=['short endTime','write-only fields function every five steps','AmgX case pressure backend and process-local runtime/audit'],
              no_phi_seed=True, no_controller_history_continuation_claim=True,
              solver_process_threads=1, solver_nice=15, max_compiler_jobs=1,
              performance_comparison=False, no_production_changes=True, prepared_only=True)
(out/'rotor_pilot_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
acceptance = dict(kind='Functional five-step rotor comparison criteria registered before launch',
                 start_time_s=.6, expected_steps=5, pressure_solves_per_step=2,
                 native_pressure_abs_tol=1e-7, p_first_rel_tol=.05, p_final_rel_tol=0,
                 max_volume_weighted_U_relative_L2=.002, max_volume_weighted_p_relative_L2=.002,
                 max_internal_face_phi_relative_L2=.002, max_mean_lift_relative_difference=.001,
                 max_mean_inferred_electrical_relative_difference=.001,
                 continuity='Report all corrector metrics; flag any deterioration over native plus 1e-12. Final corrector absolute local/global must remain <= 1e-7 for functional gate.',
                 means='Trapezoidal time-weighted mean over common first-through-last recorded actuator samples; controller reset is identical in both.',
                 actual_device='All nontrivial pressure solves must report positive intercepted successful CUDA launch calls plus checked synchronization and independently recomputed native residual.',
                 limits='Five steps prove bounded compatibility only; no steady performance, production adoption, full-field offload or scientific rotor validation.')
(out/'rotor_acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_input_hashes','actuator_dynamic_code_hashes','libraries')},indent=2))
