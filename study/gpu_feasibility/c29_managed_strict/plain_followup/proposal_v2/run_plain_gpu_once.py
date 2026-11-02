"""Future direct-child owner; every post-Popen path cleans up and records status."""
from pathlib import Path
import argparse,json,os,re,signal,subprocess,sys,time,traceback
from plain_common import *
from owned_cleanup import stop_and_reap
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--execute-approved-diagnostic',action='store_true');args=parser.parse_args()
 require(args.execute_approved_diagnostic,'SOURCE-ONLY: explicit Root execution flag required')
 protocol,approval,receipt=load(args.approval,args.receipt)
 evidence=Path(protocol['evidence']);require(not evidence.exists() and not Path(protocol['stdout_log']).exists(),'Refuse previous diagnostic evidence/log');evidence.mkdir()
 require(Path(protocol['stdout_log']).parent==evidence,'Keep diagnostic stdout with its fresh evidence')
 require(os.geteuid()==999 and os.environ.get('WM_OPTIONS')=='linuxARM64Nvidia-gpuDPInt32Opt','Wrong UID/native GPU environment')
 overlay={}
 admission=original_admission(protocol);admission.source_audit();admission.verify_receipt(args.receipt);same_bound_receipt_files(admission,receipt)
 save(evidence/'plain_prelaunch.json',{'receipt_sha256':sha(args.receipt),'approval_sha256':sha(args.approval),'protocol_sha256':sha(HERE/'protocol.json'),'no_profiler_or_tool_injection':True,'environment_unchanged':True})
 require(0<=time.time()-receipt['created_epoch']<=receipt['max_age_s'],'Receipt expired before launch')
 case=Path(protocol['case']);log=Path(protocol['stdout_log']);start_file=evidence/'actual_solver_start.json';exit_file=evidence/'actual_solver_exit.json'
 require(not log.exists() and not start_file.exists() and not exit_file.exists(),'Refuse prior child evidence')
 before=case_hashes(case);os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 start={'started_utc':utc(),'wrapper_pid':os.getpid(),'receipt_sha256':sha(args.receipt),'approval_sha256':sha(args.approval),'protocol_sha256':sha(HERE/'protocol.json'),'binary_sha256':sha(protocol['binary']['path']),'source_tree_sha256':protocol['source_tree_sha256'],'case_before':before,'manual_argv':receipt['manual_argv'],'no_profiler_or_tool_injection':True,'loader_overlay':overlay,'environment':{k:os.environ.get(k) for k in ['WM_OPTIONS','FOAM_MEMORY_POOL','LD_PRELOAD','LD_LIBRARY_PATH','OMP_NUM_THREADS']}}
 cancelled=False;timed_out=False;pidfd=None;seen=set();errors=[];cleanup=None
 def request_stop(signum,frame):
  nonlocal cancelled
  cancelled=True
 signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
 save(evidence/'actual_wrapper_start.json',{'identity':proc_identity(os.getpid()),'receipt_sha256':sha(args.receipt),'started_utc':utc()})
 require(not cancelled,'Cancelled before launch')
 with log.open('xb') as stream:
  begin=time.monotonic()
  child=subprocess.Popen(receipt['manual_argv'],cwd=case,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   start['actual_child']={'pid':child.pid,'identity_complete':False}
   save(evidence/'actual_solver_spawn.json',start) # Atomic ASAP; cleanup covers failure.
   pidfd=os.pidfd_open(child.pid);identity=proc_identity(child.pid);start['actual_child']=identity;save(start_file,start)
   require(identity['uid']==999 and identity['cwd']==str(case) and identity['exe']==protocol['binary']['path'] and identity['nice']>=15,'Actual child identity mismatch')
   while child.poll() is None:
    try:
     for line in (Path('/proc')/str(child.pid)/'maps').read_text().splitlines():
      parts=line.split(maxsplit=5)
      if len(parts)==6 and parts[5].startswith('/') and '.so' in parts[5]:
       path=Path(parts[5].removesuffix(' (deleted)')).resolve()
       if path.is_file():seen.add(str(path))
    except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    if cancelled:break
    if time.monotonic()-begin>protocol['solver_timeout_s']:timed_out=True;break
    time.sleep(.02)
  except BaseException:errors.append({'stage':'post_Popen_identity_monitor','traceback':traceback.format_exc()})
  finally:
   cleanup=stop_and_reap(child,protocol['cleanup_grace_s'],pidfd)
   if pidfd is not None:
    try:os.close(pidfd)
    except OSError:errors.append({'stage':'pidfd_close','traceback':traceback.format_exc()})
   result={**start,'completed_utc':utc(),**cleanup,'timed_out':timed_out,'cancelled':cancelled,'wrapper_errors':errors,'postprocessing_complete':False,'wrapper_status_is_separate':True,'scientific_acceptance':'Separate frozen strict d600 analysis required','speedup_measured':False}
   try:save(exit_file,result) # Before log-close, hashing, parsing or case scan.
   except BaseException:errors.append({'stage':'initial_exit_receipt_save','traceback':traceback.format_exc()});print('ACTUAL_SOLVER_CHILD_FALLBACK '+json.dumps(result),file=sys.stderr,flush=True)
 try:
  after=case_hashes(case);expected={x['path']:x['sha256'] for x in json.loads(Path(protocol['library_identity']['path']).read_text())['files']}
  observed={path:sha(path) for path in sorted(seen)};text=log.read_text()
  result['saved_output_field_sha256']={name:pin for name,pin in after.items() if name.split('/')[0] in ['0.6001','0.6002','0.6003','0.6004','0.6005'] and name.split('/')[-1] in ['U','p','phi']}
  result['tool_libraries_observed']=[path for path in seen if 'Nsight' in path or 'libcupti' in path]
  result.update(binary_sha256_after=sha(protocol['binary']['path']),log=str(log),log_sha256=sha(log),loaded_libraries_observed=[{'path':path,'sha256':pin} for path,pin in observed.items()],declared_libraries_actually_observed_unchanged=all(observed.get(path)==pin for path,pin in expected.items()),original_case_files_unchanged=all(after.get(path)==pin for path,pin in before.items()),added_case_files=sorted(set(after)-set(before)),time_values=[float(x) for x in re.findall(r'^Time = ([0-9.eE+-]+)',text,re.M)],source_calls=len(re.findall(r'^C29_SOURCE_AUDIT ',text,re.M)),controller_updates=len(re.findall(r'^TILT ',text,re.M)),End_marker=bool(re.search(r'^End\s*$',text,re.M)),nonfinite_log_token=bool(re.search(r'\b(?:nan|[-+]?inf(?:inity)?)\b',text,re.I)),postprocessing_complete=True)
 except BaseException:errors.append({'stage':'post_wait_evidence_processing','traceback':traceback.format_exc()})
 finally:
  result['wrapper_errors']=errors
  result['plain_process_gate_passed']=bool(cleanup['return_code']==0 and cleanup['actual_child_waited'] and not errors and not cleanup['cleanup_errors'] and not timed_out and not cancelled and result['postprocessing_complete'] and result.get('declared_libraries_actually_observed_unchanged') and result.get('original_case_files_unchanged') and result.get('source_calls')==result.get('controller_updates')==len(result.get('time_values',[]))==5 and result.get('End_marker') and not result.get('nonfinite_log_token') and len(result.get('saved_output_field_sha256',{}))==15 and not result.get('tool_libraries_observed'))
  try:save(exit_file,result)
  except BaseException:
   result['plain_process_gate_passed']=False
   errors.append({'stage':'final_exit_receipt_save','traceback':traceback.format_exc()});print('ACTUAL_SOLVER_CHILD_FALLBACK '+json.dumps(result),file=sys.stderr,flush=True)
  save(evidence/'actual_wrapper_exit.json',{'completed_utc':utc(),'actual_child_launched':True,'actual_child_waited':cleanup['actual_child_waited'],'true_child_return_code':cleanup['return_code'],'wrapper_errors':errors,'cleanup_errors':cleanup['cleanup_errors'],'postprocessing_complete':result['postprocessing_complete']})
 print('ACTUAL_SOLVER_CHILD_EXIT '+str(cleanup['return_code']),flush=True)
 if errors or cleanup['cleanup_errors'] or not cleanup['actual_child_waited'] or not result.get('plain_process_gate_passed'):return 1
 rc=cleanup['return_code'];return rc if rc>=0 else 128-rc
if __name__=='__main__':
 try:sys.exit(main())
 except BaseException as error:
  if not isinstance(error,SystemExit):
   try:
    protocol=json.loads((HERE/'protocol.json').read_text());e=Path(protocol['evidence'])
    if e.is_dir() and not (e/'actual_wrapper_exit.json').exists():save(e/'actual_wrapper_exit.json',{'completed_utc':utc(),'actual_child_launched':(e/'actual_solver_spawn.json').exists(),'wrapper_errors':[{'stage':'wrapper_exit','traceback':traceback.format_exc()}]})
   except BaseException:pass
  raise
