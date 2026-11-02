"""Prepare one authorized isolated 400-cell case; do not launch it."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,shutil,subprocess
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');R=BASE/'source';WORK=Path(__file__).resolve().parent
PLATFORM=R/'platforms/linuxARM64NvidiaDPInt32Opt';USER=BASE/'user/platforms/linuxARM64NvidiaDPInt32Opt/bin'
CASE_ROOT=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102');CASE=CASE_ROOT/'cavity_gpu_fixedpool'
assert os.getuid()==999 and CASE_ROOT.resolve()==CASE_ROOT and not CASE_ROOT.is_symlink()
assert not CASE.exists() and not CASE.is_symlink()
assert json.loads((BASE/'build_progress.json').read_text())['stage']=='minimal_binaries_built_runtime_not_yet_claimed'
assert all((PLATFORM/'bin'/app).is_file() for app in ['blockMesh','icoFoam'])
probe=BASE/'smoke/spumaPoolDevice';assert probe.is_dir()
core_gate=json.loads((BASE/'provenance/core_executor_gate.json').read_text());assert core_gate['state']=='passed'
annotation=json.loads((BASE/'provenance/ico_time_loop_annotation.json').read_text())
assert hashlib.sha256((R/annotation['path']).read_bytes()).hexdigest()==annotation['annotated_sha256']
assert hashlib.sha256((PLATFORM/'lib/libOpenFOAM.so').read_bytes()).hexdigest()==core_gate['libOpenFOAM_sha256']
assert hashlib.sha256((USER/'Test-spumaPoolDevice').read_bytes()).hexdigest()==core_gate['binary_sha256']
shutil.copyfile(WORK/'cuda_runtime_observer.cpp',BASE/'smoke/cuda_runtime_observer.cpp')
CASE_ROOT.mkdir(parents=True,exist_ok=True);shutil.copytree(R/'tutorials/incompressible/icoFoam/cavity/cavity',CASE)
before={str(p.relative_to(CASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in CASE.rglob('*') if p.is_file()}
shutil.copyfile(Path(core_gate['case'])/'log.poolDeviceMarker',CASE/'log.poolDeviceMarker')
shutil.copyfile(BASE/'provenance/core_executor_gate.json',CASE/'core_executor_gate.json')
fv=CASE/'system/fvSolution';text=fv.read_text();assert text.count('preconditioner  DIC;')==text.count('smoother        symGaussSeidel;')==1
fv.write_text(text.replace('preconditioner  DIC;','preconditioner  aDIC;').replace('smoother        symGaussSeidel;','smoother        twoStageSymGaussSeidel;'))
control=CASE/'system/controlDict';text=control.read_text();assert text.count('writePrecision  6;')==1;control.write_text(text.replace('writePrecision  6;','writePrecision  12;'))
q=shlex.quote
artifacts={name:str(path) for name,path in {
    'icoFoam':PLATFORM/'bin/icoFoam',
    'libOpenFOAM.so':PLATFORM/'lib/libOpenFOAM.so',
    'observer.so':BASE/'smoke/libspuma_cuda_observer.so',
    'environment':BASE/'env.sh',
}.items()}
artifact_recorder='''from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
files=ARTIFACT_PATHS
record={'recorded_utc':datetime.now(timezone.utc).isoformat(),'phase':sys.argv[1],
        'files':{name:{'path':path,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                 for name,path in files.items()}}
Path('runtime_artifacts_'+sys.argv[1]+'.json').write_text(json.dumps(record,indent=2)+'\\n')
'''.replace('ARTIFACT_PATHS',repr(artifacts))
(CASE/'record_runtime_artifacts.py').write_text(artifact_recorder)
wrapper='''from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
binary=BINARY_PATH
observer=OBSERVER_PATH
inherited_preload=os.environ.get('LD_PRELOAD','')
env=dict(os.environ,LD_PRELOAD=observer+(':'+inherited_preload if inherited_preload else ''))
started=datetime.now(timezone.utc).isoformat()
result=subprocess.run([binary,'-pool','fixedSizeMemoryPool','-poolSize','1'],env=env)
receipt={'kind':'Actual child icoFoam exit observed after binary returned, distinct from profiler exit',
         'started_utc':started,'returned_utc':datetime.now(timezone.utc).isoformat(),
         'returncode':result.returncode,'binary':binary,
         'binary_sha256_after_return':hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
temp=Path('icoFoam_exit_receipt.json.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\\n')
temp.replace('icoFoam_exit_receipt.json')
sys.exit(result.returncode if result.returncode>=0 else 128-result.returncode)
'''.replace('BINARY_PATH',repr(str(PLATFORM/'bin/icoFoam'))).replace('OBSERVER_PATH',repr(str(BASE/'smoke/libspuma_cuda_observer.so')))
(CASE/'run_profiled_ico.py').write_text(wrapper)
nsys=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys')
assert nsys.is_file()
allrun=f'''#!/bin/bash
set -o pipefail
cd -- "$(dirname -- "$0")" || exit
test ! -e .spuma-smoke-started || exit 73
. {q(str(BASE/'env.sh'))} || exit
test "$WM_PROJECT_DIR" = {q(str(R))} || exit
test "$have_cuda" = true || exit
test "$have_umpire" = false || exit
set -e
touch .spuma-smoke-started
/usr/bin/python3 record_runtime_artifacts.py start
/usr/bin/nice -n 15 {q(str(PLATFORM/'bin/blockMesh'))} -pool fixedSizeMemoryPool -poolSize 1 > log.blockMesh 2>&1
/usr/bin/ldd {q(str(PLATFORM/'bin/icoFoam'))} > runtime_libraries.txt
/usr/bin/timeout 900 /usr/bin/nice -n 15 {q(str(nsys))} profile --trace=cuda,nvtx --cuda-trace-scope=process-tree --wait=all --sample=none --cpuctxsw=none --stats=false --force-overwrite=false -o {q(str(CASE/'cavity_icoFoam_time_loop_trace'))} /usr/bin/python3 run_profiled_ico.py > log.icoFoam 2>&1
/usr/bin/python3 record_runtime_artifacts.py complete
'''
(CASE/'Allrun').write_text(allrun);(CASE/'Allrun').chmod(0o755)
record=dict(kind='Isolated SPUMA GPU installation functional smoke, not rotor or performance study',prepared_utc=datetime.now(timezone.utc).isoformat(),
    case=str(CASE),source_pin='1ff2d45c002b7afb599b9dd8c4c6874666242349',mesh_cells=400,solver='icoFoam',end_s=.5,delta_t_s=.005,
    physical_case='standard closed 2D lid-driven cavity, source viscosity and boundaries unchanged',pool='fixedSizeMemoryPool',pool_size_GiB=1,
    source_case_input_hashes=before,adaptations=['p preconditioner DIC -> supported GPU aDIC','U smoother symGaussSeidel -> supported GPU twoStageSymGaussSeidel','write precision6 ->12, output only'],
    marker_log_reused_from=str(Path(core_gate['case'])/'log.poolDeviceMarker'),marker_repeated=False,
    time_loop_annotation=annotation,first_functional_run_profiled=True,performance_inference_forbidden=True,
    no_CPU_study_change=True,no_performance_benchmark=True,no_actuator_port=True,solver_started=False,
    binaries=[str(PLATFORM/'bin/blockMesh'),str(PLATFORM/'bin/icoFoam')],environment=str(BASE/'env.sh'),
    solver_nice_increment=15,OMP_NUM_THREADS=1,OPENBLAS_NUM_THREADS=1,
    probe_source_sha256=hashlib.sha256((probe/'spuma_pool_device_marker.C').read_bytes()).hexdigest(),
    observer_source_sha256=hashlib.sha256((BASE/'smoke/cuda_runtime_observer.cpp').read_bytes()).hexdigest(),
    Allrun_sha256=hashlib.sha256((CASE/'Allrun').read_bytes()).hexdigest())
(CASE/'purpose.json').write_text(json.dumps(record,indent=2)+'\n');(WORK/'smoke_case_preparation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
