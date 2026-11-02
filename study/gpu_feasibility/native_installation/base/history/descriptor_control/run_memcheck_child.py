#!/usr/bin/env python3
"""Wait the exact unchanged C29 initial-only child and retain maps/true status."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess,time
WORK=Path(__file__).resolve().parent
BASE=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102')
CASE=BASE/'initial_memcheck';OUT=BASE/'memcheck_evidence'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_compat_v2_2_20261102')
BINARY=PREFIX/'bin/c29NativeHybridFoam';RECEIPT=BASE/'receipts/c29_native_gpu_initial_memcheck_20261102_a.json'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');os.replace(tmp,path)
def main():
 assert os.geteuid()==999 and os.environ['WM_OPTIONS']=='linuxARM64Nvidia-gpuDPInt32Opt'
 assert sha(BINARY)=='940336b28ca1f354398eaac971e5e86e4b401b323dec553cb7cdb5e0888da6a7'
 argv=json.loads(RECEIPT.read_text())['manual_argv'];assert argv==[str(BINARY),'-case',str(CASE),'-initialFieldsOnly']
 target=OUT/'actual_child_exit.json'
 if target.exists() or (OUT/'actual_child_stdout.log').exists():raise RuntimeError('Refusing to overwrite diagnostic child evidence')
 before={str(p.relative_to(CASE)):sha(p) for p in CASE.rglob('*') if p.is_file()}
 record={'started_utc':utc(),'argv':argv,'binary_sha256':sha(BINARY),'receipt_sha256':sha(RECEIPT),'case_before':before,'wrapper_pid':os.getpid(),'nice':os.getpriority(os.PRIO_PROCESS,0),'source_calls':0,'controller_updates':0,'PDE_timesteps':0}
 with (OUT/'actual_child_stdout.log').open('x') as output:
  child=subprocess.Popen(argv,cwd=CASE,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  pidfd=os.pidfd_open(child.pid);proc=Path('/proc')/str(child.pid);raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split()
  record['actual_child']={'pid':child.pid,'uid':proc.stat().st_uid,'birth_start_ticks':int(tail[19]),'cwd':os.readlink(proc/'cwd'),'exe':os.readlink(proc/'exe')}
  save(OUT/'actual_child_start.json',record);start=time.monotonic();seen=set();last_maps=''
  def forward(sig,frame):
   if child.poll() is None:
    try:signal.pidfd_send_signal(pidfd,sig)
    except ProcessLookupError:pass
  signal.signal(signal.SIGTERM,forward);signal.signal(signal.SIGINT,forward)
  while child.poll() is None:
   try:
    maps=(proc/'maps').read_text()
    if maps!=last_maps:(OUT/'actual_child_last_maps.txt').write_text(maps);last_maps=maps
    for line in maps.splitlines():
     parts=line.split(maxsplit=5)
     if len(parts)==6 and parts[5].startswith('/') and '.so' in parts[5]:
      p=Path(parts[5].removesuffix(' (deleted)')).resolve()
      if p.is_file():seen.add(str(p))
   except FileNotFoundError:pass
   if time.monotonic()-start>180:
    record['timeout180s']=True;forward(signal.SIGTERM,None)
    try:child.wait(timeout=15)
    except subprocess.TimeoutExpired:forward(signal.SIGKILL,None);child.wait(timeout=15)
    break
   time.sleep(.02)
  record['actual_child_return_code']=child.wait();os.close(pidfd)
 after={str(p.relative_to(CASE)):sha(p) for p in CASE.rglob('*') if p.is_file()}
 record.update(completed_utc=utc(),original_inputs_unchanged=all(after.get(p)==h for p,h in before.items()),added_files=sorted(set(after)-set(before)),loaded_libraries=[{'path':p,'sha256':sha(p)} for p in sorted(seen)],binary_sha256_after=sha(BINARY),actual_child_waited=True)
 save(target,record);print(json.dumps({'actual_child_return_code':record['actual_child_return_code'],'original_inputs_unchanged':record['original_inputs_unchanged'],'added_files':record['added_files']}),flush=True)
 return 0 if record['actual_child_return_code']==0 else 1
if __name__=='__main__':raise SystemExit(main())
