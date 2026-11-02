"""Build only pinned SPUMA core/icoFoam/blockMesh privately, one nice15 job."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,signal,subprocess,time
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');R=BASE/'source';PLATFORM=R/'platforms/linuxARM64NvidiaDPInt32Opt'
WORK=Path(__file__).resolve().parent;BUDGET=WORK/'build_budget.json';RECORDS=[]
def jobs():
    value=int(json.loads(BUDGET.read_text())['max_jobs']);assert value in (1,2),'Only explicit root-authorized1or2 jobs'
    return value
def now():return datetime.now(timezone.utc).isoformat()
def atomic(path,data):
    temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n')
    for attempt in range(25):
        try:temp.replace(path);return
        except PermissionError:
            if attempt==24:raise
            time.sleep(.1)
def status(stage,**extra):
    data=dict(stage=stage,updated_utc=now(),pid=os.getpid(),nice=os.getpriority(os.PRIO_PROCESS,0),max_build_jobs=jobs(),**extra)
    atomic(BASE/'build_progress.json',data);atomic(WORK/'build_progress.json',data);print(json.dumps(data),flush=True)
def available():return int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))
def require(paths):
    absent=[str(p) for p in paths if not p.is_file() or not p.stat().st_size]
    assert not absent,'Missing outputs: '+repr(absent)
def stage(name,args,outputs,timeout=21600):
    if any(row.get('stage')==name and row.get('returncode')==0 for row in RECORDS):require(outputs);return
    count=jobs();args=[str(arg).replace('@JOBS@',str(count)) for arg in args]
    while available()<20*1024**2:status('waiting_for_20GiB_reserve',next_stage=name);time.sleep(10)
    log=BASE/'logs'/(name+'.log');assert not log.exists(),'Preserve existing failed log; choose a recorded retry suffix'
    clean={k:v for k,v in os.environ.items() if not k.startswith(('FOAM','WM_','MPI_','OPAL_'))}
    shell='. '+shlex.quote(str(BASE/'env.sh'))+'; export WM_NCOMPPROCS='+str(count)+'; exec '+shlex.join([str(a) for a in args])
    status(name,command=list(map(str,args)),log=str(log),available_kb=available())
    started=time.monotonic()
    with log.open('x') as out:
        child=subprocess.Popen(['bash','--noprofile','--norc','-c',shell],cwd=R,env=clean,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
        try:
            while child.poll() is None:
                if time.monotonic()-started>timeout:raise RuntimeError('Owned build stage exceeded6h bound')
                if available()<20*1024**2:raise RuntimeError('RAM gate below20GiB reserve; terminating only owned build group')
                time.sleep(2)
        except BaseException:
            if child.poll() is None:
                os.killpg(child.pid,signal.SIGTERM)
                try:child.wait(timeout=15)
                except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
            raise
    row=dict(stage=name,command=list(map(str,args)),returncode=child.returncode,elapsed_s=time.monotonic()-started,
        completed_utc=now(),log=str(log),max_build_jobs=count,nice=15)
    RECORDS.append(row);atomic(BASE/'provenance/minimal_build_journal.json',RECORDS);atomic(WORK/'minimal_build_journal.json',RECORDS)
    assert child.returncode==0,name+' failed; inspect '+str(log)
    require(outputs)
def main():
    current_nice=os.getpriority(os.PRIO_PROCESS,0)
    if current_nice<15:os.nice(15-current_nice)
    assert os.getuid()==999
    config=json.loads((BASE/'provenance/private_build_configuration.json').read_text());assert config['max_build_jobs'] in (1,2)
    assert hashlib.sha256((BASE/'env.sh').read_bytes()).hexdigest()==config['environment_sha256']
    journal=BASE/'provenance/minimal_build_journal.json'
    if journal.exists():RECORDS.extend(json.loads(journal.read_text()))
    status('starting_authorized_minimal_private_build',source_pin=config['source_pin'],fixed_pool=True,umpire=False)
    stage('wmake_tools',[R/'wmake/src/Allmake','-j@JOBS@'],[R/'platforms/tools/linuxARM64Nvidia/wmkdepend'])
    lib=PLATFORM/'lib'
    stage('base_libraries',[R/'src/Allwmake-base','-j@JOBS@'],[lib/'libOpenFOAM.so',lib/'libmeshTools.so',lib/'libfileFormats.so',lib/'libsurfMesh.so',lib/'libOSspecific.o',lib/'dummy/libPstream.so'])
    for name,path in [('finiteVolume','src/finiteVolume'),('blockMesh','src/mesh/blockMesh'),('extrudeModel','src/mesh/extrudeModel'),('dynamicMesh','src/dynamicMesh')]:
        stage(name+'_library',['wmake','-j@JOBS@','libso',R/path],[lib/('lib'+name+'.so')])
    stage('blockMesh_binary',['wmake','-j@JOBS@',R/'applications/utilities/mesh/generation/blockMesh'],[PLATFORM/'bin/blockMesh'])
    stage('icoFoam_binary',['wmake','-j@JOBS@',R/'applications/solvers/incompressible/icoFoam'],[PLATFORM/'bin/icoFoam'])
    status('minimal_binaries_built_runtime_not_yet_claimed',binaries=[str(PLATFORM/'bin/blockMesh'),str(PLATFORM/'bin/icoFoam')],
        gpu_runtime_or_solver_gate_passed=False,actuator_port=False,speed_benchmark=False)
if __name__=='__main__':
    try:main()
    except BaseException as error:status('failed_preserved',error=repr(error));raise
