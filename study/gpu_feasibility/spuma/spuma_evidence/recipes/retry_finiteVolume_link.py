"""Relink preserved finiteVolume objects once, prove unchanged, then resume."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, shlex, subprocess, time

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
assert os.getuid()==999
os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
assert int(next(s.split()[1] for s in Path('/proc/meminfo').read_text().splitlines() if s.startswith('MemAvailable:')))>=20*1024**2
progress=json.loads((BASE/'build_progress.json').read_text());assert progress['stage']=='failed_preserved'
assert not Path('/proc/'+str(progress['pid'])).exists(),'Do not overlap the prior build process'
assert json.loads((WORK/'build_budget.json').read_text())['max_jobs']==2
library=SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt/lib/libfiniteVolume.so'
assert not library.exists(),'Inspect any preserved partial link output before retry'
objects=SOURCE/'build/linuxARM64NvidiaDPInt32Opt/src/finiteVolume'

def inventory():
    return {str(p.relative_to(objects)):{'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'bytes':p.stat().st_size,'mtime_ns':p.stat().st_mtime_ns}
            for p in sorted(objects.rglob('*.o'))}

before=inventory();assert len(before)==432
manifest=BASE/'provenance/finiteVolume_preserved_objects.json';assert not manifest.exists()
manifest.write_text(json.dumps(before,indent=2)+'\n')
subprocess.run(['/opt/codex-tools/openfoam-mcp-venv/bin/python',str(WORK/'install_stub_pic_wrapper.py')],check=True)
log=BASE/'logs/finiteVolume_library_link_retry1.log';assert not log.exists()
command=['wmake','-j2','libso',str(SOURCE/'src/finiteVolume')]
shell='. '+shlex.quote(str(BASE/'env.sh'))+'; export WM_NCOMPPROCS=2; exec '+shlex.join(command)
started=time.monotonic()
with log.open('x') as out:
    result=subprocess.run(['bash','--noprofile','--norc','-c',shell],stdout=out,stderr=subprocess.STDOUT,timeout=600)
after=inventory();unchanged=(after==before)
record=dict(stage='finiteVolume_library',command=command,returncode=result.returncode,elapsed_s=time.monotonic()-started,
            completed_utc=datetime.now(timezone.utc).isoformat(),log=str(log),max_build_jobs=2,nice=15,
            retry_of=str(BASE/'logs/finiteVolume_library.log'),reason='Confirmed generated CUDA linkstub -fpic GOT limit; own narrowly filtered -fPIC trampoline',
            preserved_object_count=len(before),cached_objects_byte_and_mtime_unchanged=unchanged,
            preserved_inventory=str(manifest),preserved_inventory_sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
(BASE/'provenance/finiteVolume_link_retry.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'finiteVolume_link_retry.json').write_text(json.dumps(record,indent=2)+'\n')
assert result.returncode==0 and unchanged and library.is_file() and library.stat().st_size>0,'Preserve failed retry and inspect'
journal=BASE/'provenance/minimal_build_journal.json';rows=json.loads(journal.read_text());rows.append(record)
journal.write_text(json.dumps(rows,indent=2)+'\n');(WORK/'minimal_build_journal.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(record),flush=True)
os.execv('/opt/codex-tools/openfoam-mcp-venv/bin/python',['/opt/codex-tools/openfoam-mcp-venv/bin/python',str(WORK/'build_minimal_spuma.py')])
