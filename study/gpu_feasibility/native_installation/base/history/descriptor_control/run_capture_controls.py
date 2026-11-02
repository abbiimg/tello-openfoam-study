from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess,time,re
WORK=Path(__file__).resolve().parent
BASE=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102')
CASE=BASE/'descriptor_control_case';OUT=BASE/'descriptor_control_evidence'
TEMPLATE=Path('/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/source/OpenFOAM-v2606/tutorials/incompressible/icoFoam/cavity/cavity')
BUILD=json.loads((WORK/'capture_control_build_b.json').read_text());BINARY=Path(BUILD['binary'])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
assert BUILD['return_code']==0 and sha(BINARY)==BUILD['binary_sha256']
large=json.loads((BASE/'memcheck_evidence/actual_child_exit.json').read_text())
if Path('/proc',str(large['actual_child']['pid'])).exists():raise RuntimeError('Previous owned GPU child must be terminal')
if CASE.exists() or OUT.exists():raise RuntimeError('Refusing existing diagnostic destinations')
shutil.copytree(TEMPLATE,CASE);OUT.mkdir()
before={str(p.relative_to(CASE)):sha(p) for p in CASE.rglob('*') if p.is_file()}
records=[]
for mode,n in [('raw',4096),('heap-ref',4096),('stack-ref',400),('stack-ref',4096)]:
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))/1024/1024
 if available<20:raise RuntimeError('Insufficient20GiB reserve')
 args=[str(BINARY),'-case',str(CASE),'-mode',mode,'-n',str(n)];log=OUT/(mode+'_'+str(n)+'.log')
 with log.open('x') as f:
  child=subprocess.Popen(args,stdout=f,stderr=subprocess.STDOUT,cwd=CASE)
  proc=Path('/proc')/str(child.pid);raw=(proc/'stat').read_text();tail=raw[raw.rfind(')')+2:].split();identity={'pid':child.pid,'uid':proc.stat().st_uid,'birth_start_ticks':int(tail[19])}
  try:rc=child.wait(timeout=30)
  except subprocess.TimeoutExpired:child.terminate();rc=child.wait(timeout=10)
 text=log.read_text();records.append({'mode':mode,'n':n,'argv':args,'actual_child':identity,'actual_child_return_code':rc,'log':str(log),'log_sha256':sha(log),'diagnostic_lines':[x for x in text.splitlines() if x.startswith('DIAG_')],'binary_sha256':sha(BINARY),'completed_utc':utc()})
 (OUT/'results.json').write_text(json.dumps(records,indent=2)+'\n')
 print(json.dumps(records[-1]),flush=True)
after={str(p.relative_to(CASE)):sha(p) for p in CASE.rglob('*') if p.is_file()}
summary={'completed_utc':utc(),'records':records,'inputs_unchanged':before==after,'case_inputs_sha256':before,'source_sha256':BUILD['source_sha256'],'binary_sha256':BUILD['binary_sha256'],'runner_sha256':sha(__file__),'no_C29_or_PDE_or_reset':True,'only_one_GPU_child_at_a_time':True}
(WORK/'descriptor_control_results.json').write_text(json.dumps(summary,indent=2)+'\n')
