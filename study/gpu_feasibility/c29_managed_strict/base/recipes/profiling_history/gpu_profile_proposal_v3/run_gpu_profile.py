"""Future single-shot profile with supervised failure cleanup; no receipt issuance."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time,traceback
from profile_common import *
from owned_cleanup import stop_and_reap
def request_case_owner_stop(evidence,protocol,notes):
 marker_published=False
 try:
  save(evidence/'outer_cancel_requested.json',{'requested_utc':utc(),'meaning':'Wrapper must stop/reap its own child'})
  marker_published=True
 except BaseException:notes.append({'cancel_marker_error':traceback.format_exc()})
 # Signal only birth/UID/cwd/exe-verified identities, never an arbitrary PID/group.
 for filename in ['actual_solver_start.json','actual_wrapper_start.json']:
  file=evidence/filename
  if not file.exists():continue
  pidfd=None
  try:
   data=json.loads(file.read_text());identity=data.get('actual_child',data.get('identity'));pid=identity['pid']
   pidfd=os.pidfd_open(pid);live=proc_identity(pid)
   require(all(live[k]==identity[k] for k in ['pid','uid','birth_start_ticks','cwd','exe']),'Changed timeout identity')
   require(live['uid']==999 and live['cwd']==protocol['case'],'Refuse unrelated identity')
   if filename=='actual_solver_start.json':require(live['exe']==protocol['binary']['path'],'Different solver')
   else:require(str(HERE/'run_actual_gpu_child.py') in (Path('/proc')/str(pid)/'cmdline').read_bytes().decode().split('\0'),'Different wrapper argv')
   signal.pidfd_send_signal(pidfd,signal.SIGTERM);notes.append({'signal':'SIGTERM','identity':identity})
  except (FileNotFoundError,ProcessLookupError):pass
  except BaseException:notes.append({'verified_signal_error':traceback.format_exc()})
  finally:
   if pidfd is not None:os.close(pidfd)
 return marker_published
def solver_terminal(evidence):
 for name in ['actual_solver_exit.json','actual_wrapper_exit.json']:
  file=evidence/name
  if not file.exists():continue
  data=json.loads(file.read_text())
  if data.get('actual_child_waited') is True or data.get('actual_child_launched') is False:return True
 return False
def owner_state(evidence,marker_published):
 if solver_terminal(evidence):return 'actual_child_terminal_or_not_launched'
 # Atomic wrapper-start publication MUST precede the wrapper's marker check
 # and possible solver Popen. If this marker is already published and there
 # is no start, a later wrapper cannot pass its pre-spawn marker check.
 if marker_published and not (evidence/'actual_wrapper_start.json').exists():return 'pre_wrapper_cancelled_safe'
 return 'unresolved'
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--execute-approved-receipt',action='store_true');args=parser.parse_args()
 require(args.execute_approved_receipt,'SOURCE-ONLY: explicit approved execution flag required')
 protocol,approval,receipt=load(args.approval,args.receipt)
 require(os.geteuid()==999 and os.environ.get('WM_OPTIONS')=='linuxARM64Nvidia-gpuDPInt32Opt','Source reviewed native GPU env first')
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')));require(available>=20*1024**2,'Memory reserve below 20 GiB')
 admission=original_admission(protocol);admission.source_audit();admission.verify_receipt(args.receipt)
 evidence=Path(protocol['evidence']);require(not evidence.exists() and not Path(protocol['stdout_log']).exists(),'Prior evidence/log collision');evidence.mkdir()
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 command=[protocol['nsys']['path'],'profile',*protocol['nsys_flags'],'-o',str(evidence/'first_complete_step'),'/usr/bin/python3','-B',str(HERE/'run_actual_gpu_child.py'),'--approval',str(args.approval),'--receipt',str(args.receipt)]
 env=dict(os.environ);env['NSYS_NVTX_PROFILER_REGISTER_ONLY']='0'
 save(evidence/'outer_prelaunch.json',{'started_utc':utc(),'protocol_sha256':sha(HERE/'protocol.json'),'receipt_sha256':sha(args.receipt),'foam_companion_sha256':sha(args.receipt.with_suffix('.foam')),'approval_sha256':sha(args.approval),'receipt_verified_before_profiler_injection':True,'command':command,'nice':os.getpriority(os.PRIO_PROCESS,0),'MemAvailable_kib':available,'speedup_measured':False})
 cancelled=False;timed_out=False;errors=[];cleanup_notes=[];process=None
 def request_stop(signum,frame):
  nonlocal cancelled
  cancelled=True
 signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)
 with (evidence/'profiler.log').open('xb') as output:
  process=subprocess.Popen(command,env=env,cwd=protocol['case'],stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   begin=time.monotonic()
   while process.poll() is None:
    if cancelled:break
    if time.monotonic()-begin>protocol['profiler_timeout_s']:timed_out=True;break
    time.sleep(.2)
  except BaseException:errors.append({'stage':'profile_monitor','traceback':traceback.format_exc()})
  finally:
   if cancelled or timed_out or errors or process.poll() is None or process.returncode!=0:
    marker_published=request_case_owner_stop(evidence,protocol,cleanup_notes)
    deadline=time.monotonic()+protocol['profiler_cleanup_timeout_s']
    state=owner_state(evidence,marker_published)
    while state=='unresolved':
     if time.monotonic()>=deadline:
      # Repeat only verified owner signaling. Actual-child reaping is required
      # even if the profiler has ALREADY failed; its exit proves no child exit.
      marker_published=request_case_owner_stop(evidence,protocol,cleanup_notes) or marker_published
      cleanup_notes.append({'waiting_for_owned_solver_reap':True});deadline=time.monotonic()+protocol['profiler_cleanup_timeout_s']
     time.sleep(.2);state=owner_state(evidence,marker_published)
    cleanup_notes.append({'owner_cleanup_state':state,'atomic_cancel_marker_published':marker_published})
    # Safe only after true child terminal evidence, or the pre-wrapper race
    # proof above. No arbitrary PID/group or GPU reset is used.
    if process.poll() is None:cleanup_notes.append({'profiler_cleanup':stop_and_reap(process,30)})
   profiler_code=process.wait()
   save(evidence/'profiler_exit.json',{'completed_utc':utc(),'return_code':profiler_code,'timed_out':timed_out,'cancelled':cancelled,'outer_wrapper_errors':errors,'verified_child_cleanup':cleanup_notes,'actual_solver_exit_is_separate':True,'command':command})
 require(not cancelled and not timed_out and not errors and profiler_code==0,'Profile failed/cancelled/timed out; evidence preserved, no rerun')
 report=evidence/'first_complete_step.nsys-rep';require(report.is_file(),'Missing profile report')
 export=[protocol['nsys']['path'],'export','--type=sqlite','--force-overwrite=false','--output',str(evidence/'first_complete_step.sqlite'),str(report)]
 with (evidence/'export.log').open('xb') as output:r=subprocess.run(export,stdout=output,stderr=subprocess.STDOUT,timeout=protocol['export_timeout_s'])
 save(evidence/'export_exit.json',{'command':export,'return_code':r.returncode,'completed_utc':utc()});require(r.returncode==0,'Export failed; do not rerun CFD')
 from validate_gpu_profile import validate
 print(json.dumps(validate(args.approval,args.receipt),indent=2))
if __name__=='__main__':main()
