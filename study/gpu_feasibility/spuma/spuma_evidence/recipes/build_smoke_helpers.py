"""Build the functional-proof helpers only after the minimal stack is terminal."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,subprocess,time
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');WORK=Path(__file__).resolve().parent
SDK=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9');CUDA=SDK/'cuda/13.3'
def now():return datetime.now(timezone.utc).isoformat()
os.nice(15);assert os.getuid()==999
assert json.loads((BASE/'build_progress.json').read_text())['stage']=='minimal_binaries_built_runtime_not_yet_claimed'
assert int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))>=20*1024**2
assert (BASE/'smoke/spumaPoolDevice/Make/files').exists()
rows=[]
core_gate=json.loads((BASE/'provenance/core_executor_gate.json').read_text());assert core_gate['state']=='passed'
commands=[('cuda_observer_build',['/usr/bin/g++','-std=c++17','-shared','-fPIC','-O2','-I'+str(CUDA/'include'),str(BASE/'smoke/cuda_runtime_observer.cpp'),
        '-L'+str(CUDA/'lib64'),'-Wl,-rpath,'+str(CUDA/'lib64'),'-lcudart','-ldl','-o',str(BASE/'smoke/libspuma_cuda_observer.so')])]
for name,args in commands:
    log=BASE/'logs'/(name+'.log');assert not log.exists(),'Preserve previous helper build log'
    shell='. '+shlex.quote(str(BASE/'env.sh'))+'; export WM_NCOMPPROCS=2; exec '+shlex.join(args)
    clean={k:v for k,v in os.environ.items() if not k.startswith(('FOAM','WM_','MPI_','OPAL_'))}
    started=time.monotonic()
    with log.open('x') as output:result=subprocess.run(['bash','--noprofile','--norc','-c',shell],cwd=BASE,env=clean,stdout=output,stderr=subprocess.STDOUT,timeout=600)
    row=dict(stage=name,returncode=result.returncode,command=args,log=str(log),completed_utc=now(),elapsed_s=time.monotonic()-started,max_jobs=2,nice=15)
    rows.append(row);(BASE/'provenance/smoke_helper_build_journal.json').write_text(json.dumps(rows,indent=2)+'\n')
    assert result.returncode==0,name+' failed: '+str(log)
probe=BASE/'user/platforms/linuxARM64NvidiaDPInt32Opt/bin/Test-spumaPoolDevice';observer=BASE/'smoke/libspuma_cuda_observer.so'
assert probe.is_file() and observer.is_file()
record=dict(completed_utc=now(),build_only=True,runtime_not_started=True,records=rows,
    binaries={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [probe,observer]})
(WORK/'smoke_helper_build.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
