"""Prepare/preregister a DISTINCT five-step strict fixture; do not launch."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,shutil

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
PLATFORM=SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt'
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/cavity_gpu_fixedpool_strict_v2')
assert os.getuid()==999 and not CASE.exists()
build=json.loads((BASE/'provenance/ico_first_step_build.json').read_text())
assert build['returncode']==0 and build['core_and_finiteVolume_hashes_unchanged']
observer=BASE/'smoke/libspuma_cuda_observer.so';assert observer.is_file()
shutil.copytree(SOURCE/'tutorials/incompressible/icoFoam/cavity/cavity',CASE)
stock={str(p.relative_to(CASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in CASE.rglob('*') if p.is_file()}
fv=CASE/'system/fvSolution';text=fv.read_text()
for old,new in [('preconditioner  DIC;','preconditioner  aDIC;'),('smoother        symGaussSeidel;','smoother        twoStageSymGaussSeidel;'),('relTol          0.05;','relTol          0;')]:
    assert text.count(old)==1; text=text.replace(old,new)
fv.write_text(text)
control=CASE/'system/controlDict';text=control.read_text()
for old,new in [('endTime         0.5;','endTime         0.025;'),('writeInterval   20;','writeInterval   1;'),('writePrecision  6;','writePrecision  17;')]:
    assert text.count(old)==1;text=text.replace(old,new)
control.write_text(text)
core=json.loads((BASE/'provenance/core_executor_gate.json').read_text())
assert hashlib.sha256((PLATFORM/'lib/libOpenFOAM.so').read_bytes()).hexdigest()==core['libOpenFOAM_sha256']
shutil.copy2(Path(core['case'])/'log.poolDeviceMarker',CASE/'log.poolDeviceMarker')
shutil.copy2(BASE/'provenance/core_executor_gate.json',CASE/'core_executor_gate.json')
artifacts={'icoFoam':str(PLATFORM/'bin/icoFoam'),'libOpenFOAM.so':str(PLATFORM/'lib/libOpenFOAM.so'),
           'libfiniteVolume.so':str(PLATFORM/'lib/libfiniteVolume.so'),'observer.so':str(observer),'environment':str(BASE/'env.sh')}
recorder='''from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
files=ARTIFACTS
result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'phase':sys.argv[1],
        'files':{name:{'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for name,p in files.items()}}
Path('runtime_artifacts_'+sys.argv[1]+'.json').write_text(json.dumps(result,indent=2)+'\\n')
'''.replace('ARTIFACTS',repr(artifacts))
(CASE/'record_runtime_artifacts.py').write_text(recorder)
wrapper='''from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
binary=BINARY
observer=OBSERVER
existing=os.environ.get('LD_PRELOAD','')
env=dict(os.environ,LD_PRELOAD=observer+(':'+existing if existing else ''))
started=datetime.now(timezone.utc).isoformat()
child=subprocess.Popen([binary,'-pool','fixedSizeMemoryPool','-poolSize','1'],env=env)
identity={'pid':child.pid,'uid':os.getuid(),'cwd':str(Path.cwd()),'binary':binary,
          'birth_tick':int((Path('/proc')/str(child.pid)/'stat').read_text().rsplit(')',1)[1].split()[19]),'started_utc':started}
Path('icoFoam_child_identity.json').write_text(json.dumps(identity,indent=2)+'\\n')
timed_out=False
try: rc=child.wait(timeout=600)
except subprocess.TimeoutExpired:
    timed_out=True;child.terminate()
    try:rc=child.wait(timeout=30)
    except subprocess.TimeoutExpired:child.kill();rc=child.wait()
receipt={'kind':'Actual strict-v2 child exit after cleanup, separate from profiler/Allrun',
         'started_utc':started,'returned_utc':datetime.now(timezone.utc).isoformat(),'returncode':rc,
         'timed_out':timed_out,'child_identity':identity,'binary':binary,
         'binary_sha256_after_return':hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
temp=Path('icoFoam_exit_receipt.json.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\\n');temp.replace('icoFoam_exit_receipt.json')
sys.exit(rc if rc>=0 else 128-rc)
'''.replace('BINARY',repr(str(PLATFORM/'bin/icoFoam'))).replace('OBSERVER',repr(str(observer)))
(CASE/'run_profiled_ico.py').write_text(wrapper)
nsys=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys')
q=shlex.quote
allrun=f'''#!/bin/bash
set -o pipefail
cd -- "$(dirname -- "$0")" || exit
test ! -e .strict-v2-started || exit 73
. {q(str(BASE/'env.sh'))} || exit
test "$have_cuda" = true || exit
test "$have_umpire" = false || exit
export NSYS_NVTX_PROFILER_REGISTER_ONLY=0
set -e
touch .strict-v2-started
/usr/bin/python3 record_runtime_artifacts.py start
/usr/bin/nice -n 15 {q(str(PLATFORM/'bin/blockMesh'))} -pool fixedSizeMemoryPool -poolSize 1 > log.blockMesh 2>&1
/usr/bin/ldd {q(str(PLATFORM/'bin/icoFoam'))} > runtime_libraries.txt
/usr/bin/timeout 900 /usr/bin/nice -n 15 {q(str(nsys))} profile --trace=cuda,nvtx --capture-range=nvtx --nvtx-capture=SPUMA_CFD_FIRST_COMPLETE_STEP --capture-range-end=stop --kill=none --cuda-trace-scope=process-tree --wait=all --sample=none --cpuctxsw=none --stats=false --force-overwrite=false -o {q(str(CASE/'cavity_first_step_trace'))} /usr/bin/python3 run_profiled_ico.py > log.icoFoam 2>&1
/usr/bin/python3 -c 'import json; from pathlib import Path; r=json.loads(Path("icoFoam_exit_receipt.json").read_text()); assert r["returncode"]==0 and not r["timed_out"]'
/usr/bin/python3 record_runtime_artifacts.py complete
'''
(CASE/'Allrun').write_text(allrun);(CASE/'Allrun').chmod(0o755)
criterion=dict(all_corrector_local_continuity_max=1e-5,comparison='<=',all_pressure_final_residual_max=1.05e-6,
    all_U_final_residual_max=1.05e-5,max_pressure_iterations_exclusive=1000,
    all_five_written_U_p_phi_finite=True,independent_final_saved_flux_continuity_max_exclusive=1e-5,
    verify_all_closed_wall_fluxes_abs_max_exclusive=1e-12,U_norm_max_exclusive=2,Ux_max_min_exclusive=.1,
    Ux_min_max_exclusive=-.01,p_abs_max_exclusive=10,p_range_min_exclusive=.001,p_reference_abs_max_exclusive=1e-5,
    actual_icoFoam_and_Allrun_returncodes=0,actual_child_timeout_forbidden=True,
    source_binary_core_FV_observer_env_hashes_unchanged=True,
    first_complete_step_CUDA_API_launch_success_required=True,same_globalTid_filter_required=True,
    failed_launch_and_sync_API_calls_allowed=0,device_context_sync_after_last_launch_required=True,
    no_unique_kernel_activity_or_speed_claim=True)
record=dict(kind='PREREGISTERED distinct SPUMA strict-v2 functional fixture; not a replacement pass for failed original',
    preregistered_utc=datetime.now(timezone.utc).isoformat(),case=str(CASE),solver_started=False,
    source_pin=build['annotation']['source_pin'],source_annotation=build['annotation'],source_build=build,
    mesh_cells=400,delta_t_s=.005,end_s=.025,steps=5,writeInterval=1,writePrecision=17,
    p=dict(solver='PCG',preconditioner='aDIC',tolerance=1e-6,relTol=0),pFinal=dict(inherits='p',relTol=0),
    U=dict(solver='smoothSolver',smoother='twoStageSymGaussSeidel',tolerance=1e-5,relTol=0),
    physical_initial_and_boundary_inputs_from_fresh_stock=True,stock_source_input_hashes=stock,
    pool='fixedSizeMemoryPool',pool_size_GiB=1,criteria=criterion,
    profiling=dict(range='SPUMA_CFD_FIRST_COMPLETE_STEP',capture_range_end='stop',kill='none',scope='process-tree',wait='all',
                   first_complete_step_only=True,remaining_four_steps_not_collected=True,API_not_unique_kernel_counts=True,
                   NSYS_NVTX_PROFILER_REGISTER_ONLY=0,unregistered_string_capture_documentation='https://docs.nvidia.com/nsight-systems/UserGuide/'),
    original_failed_attempt=str(BASE/'provenance/original_attempt/original_attempt_diagnostic.json'),
    no_posthoc_threshold_relaxation=True,no_actuator_port_or_CPU_study_change=True,no_performance_inference=True,
    input_hashes={str(p.relative_to(CASE)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(CASE.rglob('*')) if p.is_file()})
(CASE/'protocol_strict_v2.json').write_text(json.dumps(record,indent=2)+'\n')
(BASE/'provenance/protocol_strict_v2.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'protocol_strict_v2.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
