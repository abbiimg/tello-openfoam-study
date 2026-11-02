"""Use the second authorized slot for one short core-backend build, not a benchmark."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,shutil,signal,subprocess,time,uuid
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');WORK=Path(__file__).resolve().parent
R=BASE/'source';USER=BASE/'user/platforms/linuxARM64NvidiaDPInt32Opt/bin';BUDGET=WORK/'build_budget.json'
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/pool_executor_marker')
def atomic(path,data):
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def restore(claim):
    b=json.loads(BUDGET.read_text())
    if b.get('extra_probe_claim')==claim:
        b.update(max_jobs=2,extra_probe_claim=None,extra_probe_reserved_jobs=0);atomic(BUDGET,b)
os.nice(15);assert os.getuid()==999
state=json.loads((BASE/'build_progress.json').read_text());assert state['stage']=='base_libraries' and state['max_build_jobs']==1
assert (R/'platforms/linuxARM64NvidiaDPInt32Opt/lib/libOpenFOAM.so').is_file()
assert int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))>=22*1024**2
b=json.loads(BUDGET.read_text());assert b['max_jobs']==2
claim=uuid.uuid4().hex;b.update(max_jobs=1,extra_probe_claim=claim,extra_probe_reserved_jobs=1,
    reason='Completed core target boundary permits main1 plus one core-executor proof job; restore main2 only after proof terminal; totalSPUMA<=2')
atomic(BUDGET,b)
try:
    probe=BASE/'smoke/spumaPoolDevice';assert not probe.exists();(probe/'Make').mkdir(parents=True)
    shutil.copyfile(WORK/'spuma_pool_device_marker.C',probe/'spuma_pool_device_marker.C')
    (probe/'Make/files').write_text('spuma_pool_device_marker.C\n\nEXE = $(FOAM_USER_APPBIN)/Test-spumaPoolDevice\n')
    (probe/'Make/options').write_text('EXE_INC = -I$(LIB_SRC)/OpenFOAM/lnInclude\n\nEXE_LIBS = -lcudart\n')
    log=BASE/'logs/core_executor_marker_build.log';assert not log.exists()
    command='. '+shlex.quote(str(BASE/'env.sh'))+'; export WM_NCOMPPROCS=1; exec wmake -j1 '+shlex.quote(str(probe))
    clean={k:v for k,v in os.environ.items() if not k.startswith(('FOAM','WM_','MPI_','OPAL_'))}
    with log.open('x') as output:
        child=subprocess.Popen(['bash','--noprofile','--norc','-c',command],cwd=BASE,env=clean,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
        start=time.monotonic()
        try:
            while child.poll() is None:
                if time.monotonic()-start>600:raise RuntimeError('Proof compiler timeout')
                if int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))<20*1024**2:raise RuntimeError('20GiB reserve')
                time.sleep(1)
        except BaseException:
            if child.poll() is None:os.killpg(child.pid,signal.SIGTERM);child.wait(timeout=15)
            raise
    assert child.returncode==0,'Core marker build failed; inspect '+str(log)
    assert (USER/'Test-spumaPoolDevice').is_file() and not CASE.exists()
    CASE.mkdir(parents=True)
    (CASE/'system').mkdir()
    (CASE/'system/controlDict').write_text('FoamFile { version 2.0; format ascii; class dictionary; object controlDict; }\napplication Test-spumaPoolDevice;\nstartFrom startTime; startTime 0; stopAt endTime; endTime 0; deltaT 1; writeControl timeStep; writeInterval 1;\n')
    allrun='#!/bin/bash\ncd -- "$(dirname -- "$0")" || exit\n. '+shlex.quote(str(BASE/'env.sh'))+' || exit\nexec /opt/codex-tools/openfoam-mcp-venv/bin/python '+shlex.quote(str(WORK/'run_core_executor_gate.py'))+' '+shlex.quote(str(CASE))+' '+claim+'\n'
    (CASE/'Allrun').write_text(allrun);(CASE/'Allrun').chmod(0o755)
    record=dict(kind='Actual SPUMA core pool and CUDA-executor gate only',prepared_utc=datetime.now(timezone.utc).isoformat(),case=str(CASE),extra_probe_claim=claim,
        main_pipeline_jobs=1,extra_probe_jobs=1,SPUMA_total_max=2,SDK_reused_readonly=True,compiler_returncode=0,compiler_log=str(log),
        source_sha256=hashlib.sha256((probe/'spuma_pool_device_marker.C').read_bytes()).hexdigest(),binary=str(USER/'Test-spumaPoolDevice'),
        no_solver_tutorial_yet=True,no_speed_benchmark=True,no_actuator_port=True,started=False)
    (CASE/'purpose.json').write_text(json.dumps(record,indent=2)+'\n');(WORK/'core_executor_preparation.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)
except BaseException:restore(claim);raise
