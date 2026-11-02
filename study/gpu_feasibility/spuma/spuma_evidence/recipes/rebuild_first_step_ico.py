"""Recompile only the annotated icoFoam application, one nice15 job."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,subprocess,time

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
PLATFORM=SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt'
assert os.getuid()==999
os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
assert int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))>=20*1024**2
annotation=json.loads((BASE/'provenance/ico_first_step_annotation.json').read_text())
assert hashlib.sha256((SOURCE/annotation['path']).read_bytes()).hexdigest()==annotation['annotated_sha256']
libraries=[PLATFORM/'lib/libOpenFOAM.so',PLATFORM/'lib/libfiniteVolume.so']
before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries}
log=BASE/'logs/icoFoam_first_step_annotation_build.log';assert not log.exists()
command=['wmake','-j1',str(SOURCE/'applications/solvers/incompressible/icoFoam')]
shell='. '+shlex.quote(str(BASE/'env.sh'))+'; export WM_NCOMPPROCS=1; exec '+shlex.join(command)
started=time.monotonic()
with log.open('x') as out:r=subprocess.run(['bash','--noprofile','--norc','-c',shell],stdout=out,stderr=subprocess.STDOUT,timeout=600)
after={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in libraries}
record=dict(kind='Only icoFoam annotation rebuilt, no source arithmetic change',completed_utc=datetime.now(timezone.utc).isoformat(),
    command=command,returncode=r.returncode,elapsed_s=time.monotonic()-started,max_jobs=1,nice=15,log=str(log),
    core_and_finiteVolume_hashes_unchanged=before==after,library_hashes=after,annotation=annotation,
    binary=str(PLATFORM/'bin/icoFoam'),binary_sha256=hashlib.sha256((PLATFORM/'bin/icoFoam').read_bytes()).hexdigest())
(BASE/'provenance/ico_first_step_build.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'ico_first_step_build.json').write_text(json.dumps(record,indent=2)+'\n')
assert r.returncode==0 and before==after
print(json.dumps(record),flush=True)
