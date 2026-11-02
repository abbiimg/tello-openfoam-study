#!/usr/bin/env python3
"""Single authorized diagnostic launch; tool and actual C++ status stay separate."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,time
WORK=Path(__file__).resolve().parent
ROOTWORK=WORK.parents[2]/'gpu_actuator_port'
# Resolve explicitly on the shared workspace; no candidate source is edited.
AUDITOR=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/candidate/audit_candidate.py')
BASE=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102');CASE=BASE/'initial_memcheck';OUT=BASE/'memcheck_evidence'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_compat_v2_2_20261102');BINARY=PREFIX/'bin/c29NativeHybridFoam';IDENTITY=PREFIX/'library_identity.json';RECEIPT=BASE/'receipts/c29_native_gpu_initial_memcheck_20261102_a.json'
TOOL=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3/compute-sanitizer/compute-sanitizer')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))/1024/1024
 if available<20:raise RuntimeError('Insufficient20GiB memory reserve')
 if OUT.exists():raise RuntimeError('Refusing existing diagnostic evidence destination')
 OUT.mkdir()
 subprocess.run(['/usr/bin/python3',str(AUDITOR),'--case',str(CASE),'--private-root',str(BASE),'--backend','gpu','--phase','initial_fields_only','--binary',str(BINARY),'--library-identity',str(IDENTITY),'--write-launch-receipt',str(RECEIPT)],check=True)
 subprocess.run(['/usr/bin/python3',str(AUDITOR),'--verify-launch-receipt',str(RECEIPT)],check=True)
 args=[str(TOOL),'--tool','memcheck','--target-processes','all','--error-exitcode','86','--report-api-errors','all','--show-backtrace','yes','--print-limit','20','--destroy-on-device-error','context','--log-file',str(OUT/'compute_sanitizer.log'),'/usr/bin/python3',str(WORK/'run_memcheck_child.py')]
 record={'started_utc':utc(),'argv':args,'tool':str(TOOL),'tool_sha256':sha(TOOL),'binary_sha256':sha(BINARY),'receipt_sha256':sha(RECEIPT),'source_helpers_sha256':{p.name:sha(p) for p in [Path(__file__),WORK/'run_memcheck_child.py']},'max_owned_GPU_children':1,'nice':os.getpriority(os.PRIO_PROCESS,0),'available_GiB':available,'no_vendor_SDK_app_or_input_change':True,'actual_child_status_separate':True}
 (OUT/'prelaunch.json').write_text(json.dumps(record,indent=2)+'\n')
 with (OUT/'tool_stdout.log').open('x') as log:
  child=subprocess.Popen(args,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  record['sanitizer_pid']=child.pid
  try:record['sanitizer_return_code']=child.wait(timeout=215)
  except subprocess.TimeoutExpired:
   record['outer_timeout215s']=True;child.terminate()
   try:record['sanitizer_return_code']=child.wait(timeout=10)
   except subprocess.TimeoutExpired:child.kill();record['sanitizer_return_code']=child.wait(timeout=10)
 record['completed_utc']=utc();actual=OUT/'actual_child_exit.json'
 record['actual_child_receipt_present']=actual.exists()
 if actual.exists():record['actual_child_return_code']=json.loads(actual.read_text())['actual_child_return_code']
 (OUT/'tool_exit.json').write_text(json.dumps(record,indent=2)+'\n')
 print(json.dumps({k:record[k] for k in ['sanitizer_return_code','actual_child_receipt_present','actual_child_return_code'] if k in record},indent=2),flush=True)
if __name__=='__main__':main()
