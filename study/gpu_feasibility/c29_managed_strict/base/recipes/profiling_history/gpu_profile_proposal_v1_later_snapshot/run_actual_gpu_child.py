"""Future profiled direct-child wrapper; source-only until root supplies approval."""
from pathlib import Path
import argparse,json,os,re,signal,subprocess,sys,time
from profile_common import *
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args()
 protocol,approval,receipt=load(args.approval,args.receipt)
 evidence=Path(protocol['evidence']);outer=json.loads((evidence/'outer_prelaunch.json').read_text())
 require(outer['receipt_sha256']==sha(args.receipt) and outer['protocol_sha256']==sha(HERE/'protocol.json'),'Outer preflight mismatch')
 require(outer['foam_companion_sha256']==sha(args.receipt.with_suffix('.foam')),'Receipt companion changed after outer verification')
 require(os.geteuid()==999 and os.environ.get('WM_OPTIONS')=='linuxARM64Nvidia-gpuDPInt32Opt','Wrong UID/native GPU environment')
 require(os.environ.get('NSYS_NVTX_PROFILER_REGISTER_ONLY')=='0','Unregistered capture names require REGISTER_ONLY=0')
 overlay=require_injection_overlay(receipt['environment'],os.environ,Path(protocol['nsys_root']).resolve())
 # Preserve the inherited injection LD_PRELOAD verbatim. No observer is added.
 admission=original_admission(protocol);admission.source_audit();same_bound_receipt_files(admission,receipt)
 require(0<=time.time()-receipt['created_epoch']<=receipt['max_age_s'],'Receipt expired before direct child launch')
 case=Path(protocol['case']);log=Path(protocol['stdout_log']);start_file=evidence/'actual_solver_start.json';exit_file=evidence/'actual_solver_exit.json'
 require(not log.exists() and not start_file.exists() and not exit_file.exists(),'Refuse to overwrite prior child evidence')
 before=case_hashes(case);os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 start={'started_utc':utc(),'wrapper_pid':os.getpid(),'receipt_sha256':sha(args.receipt),'approval_sha256':sha(args.approval),'protocol_sha256':sha(HERE/'protocol.json'),'binary_sha256':sha(protocol['binary']['path']),'source_tree_sha256':protocol['source_tree_sha256'],'case_before':before,'manual_argv':receipt['manual_argv'],'inherited_injection_preload_preserved':True,'loader_overlay':overlay,'environment':{k:os.environ.get(k) for k in ['WM_OPTIONS','FOAM_MEMORY_POOL','LD_PRELOAD','LD_LIBRARY_PATH','OMP_NUM_THREADS','NSYS_NVTX_PROFILER_REGISTER_ONLY']}}
 seen=set();timed_out=False;forced=False;cancelled=False
 with log.open('xb') as stream:
  child=subprocess.Popen(receipt['manual_argv'],cwd=case,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  pidfd=os.pidfd_open(child.pid);identity=proc_identity(child.pid)
  require(identity['uid']==999 and identity['cwd']==str(case) and identity['exe']==protocol['binary']['path'] and identity['nice']>=15,'Direct solver child identity mismatch')
  start['actual_child']=identity;save(start_file,start)
  term_at=None
  def forward(signum,frame):
   nonlocal cancelled,term_at
   cancelled=True
   if term_at is None:term_at=time.monotonic()
   if child.poll() is None:
    try:signal.pidfd_send_signal(pidfd,signum)
    except ProcessLookupError:pass
  signal.signal(signal.SIGTERM,forward);signal.signal(signal.SIGINT,forward)
  begin=time.monotonic()
  while child.poll() is None:
   try:
    for line in (Path('/proc')/str(child.pid)/'maps').read_text().splitlines():
     parts=line.split(maxsplit=5)
     if len(parts)==6 and parts[5].startswith('/') and '.so' in parts[5]:
      p=Path(parts[5].removesuffix(' (deleted)')).resolve()
      if p.is_file():seen.add(str(p))
   except (FileNotFoundError,ProcessLookupError,PermissionError):pass
   if not cancelled and (evidence/'outer_cancel_requested.json').exists():forward(signal.SIGTERM,None)
   if not timed_out and time.monotonic()-begin>protocol['solver_timeout_s']:
    timed_out=True;term_at=time.monotonic();signal.pidfd_send_signal(pidfd,signal.SIGTERM)
   if (timed_out or cancelled) and not forced and time.monotonic()-term_at>protocol['cleanup_grace_s']:
    forced=True;signal.pidfd_send_signal(pidfd,signal.SIGKILL)
   time.sleep(.02)
  returncode=child.wait();os.close(pidfd)
 after=case_hashes(case);expected={x['path']:x['sha256'] for x in json.loads(Path(protocol['library_identity']['path']).read_text())['files']}
 observed={p:sha(p) for p in sorted(seen)};text=log.read_text()
 result={**start,'completed_utc':utc(),'actual_child_waited':True,'return_code':returncode,'timed_out':timed_out,'cancelled':cancelled,'forced_kill':forced,'binary_sha256_after':sha(protocol['binary']['path']),'log':str(log),'log_sha256':sha(log),'loaded_libraries_observed':[{'path':p,'sha256':pin} for p,pin in observed.items()],'declared_libraries_actually_observed_unchanged':all(observed.get(p)==pin for p,pin in expected.items()),'original_case_files_unchanged':all(after.get(p)==pin for p,pin in before.items()),'added_case_files':sorted(set(after)-set(before)),'time_values':[float(x) for x in re.findall(r'^Time = ([0-9.eE+-]+)',text,re.M)],'source_calls':len(re.findall(r'^C29_SOURCE_AUDIT ',text,re.M)),'controller_updates':len(re.findall(r'^TILT ',text,re.M)),'End_marker':bool(re.search(r'^End\s*$',text,re.M)),'nonfinite_log_token':bool(re.search(r'\b(?:nan|[-+]?inf(?:inity)?)\b',text,re.I)),'profiler_status_is_separate':True,'scientific_acceptance':'Separate frozen strict d600 analyzer required; execution receipt is not numerical acceptance','speedup_measured':False}
 save(exit_file,result);print('ACTUAL_SOLVER_CHILD_EXIT '+str(returncode),flush=True)
 return returncode if returncode>=0 else 128-returncode
if __name__=='__main__':sys.exit(main())
