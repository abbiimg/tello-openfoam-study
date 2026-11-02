"""Future single-shot functional profile. Requires separate root approval/receipt."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time
from profile_common import *
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);parser.add_argument('--execute-approved-receipt',action='store_true');args=parser.parse_args()
 require(args.execute_approved_receipt,'SOURCE-ONLY proposal: explicit approved execution flag required')
 protocol,approval,receipt=load(args.approval,args.receipt)
 require(os.geteuid()==999 and os.environ.get('WM_OPTIONS')=='linuxARM64Nvidia-gpuDPInt32Opt','Source the exact reviewed native GPU env first')
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
 require(available>=20*1024**2,'Less than 20 GiB memory reserve; no launch')
 admission=original_admission(protocol);admission.source_audit();admission.verify_receipt(args.receipt)
 evidence=Path(protocol['evidence']);require(not evidence.exists() and not Path(protocol['stdout_log']).exists(),'Refuse prior evidence/log collision');evidence.mkdir()
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 command=[protocol['nsys']['path'],'profile',*protocol['nsys_flags'],'-o',str(evidence/'first_complete_step'),'/usr/bin/python3','-B',str(HERE/'run_actual_gpu_child.py'),'--approval',str(args.approval),'--receipt',str(args.receipt)]
 env=dict(os.environ);env['NSYS_NVTX_PROFILER_REGISTER_ONLY']='0'
 preflight={'started_utc':utc(),'protocol_sha256':sha(HERE/'protocol.json'),'receipt_sha256':sha(args.receipt),'foam_companion_sha256':sha(args.receipt.with_suffix('.foam')),'approval_sha256':sha(args.approval),'receipt_verified_before_profiler_injection':True,'command':command,'nice':os.getpriority(os.PRIO_PROCESS,0),'MemAvailable_kib':available,'speedup_measured':False};save(evidence/'outer_prelaunch.json',preflight)
 timed_out=False;child_cleanup=[]
 with (evidence/'profiler.log').open('xb') as output:
  process=subprocess.Popen(command,env=env,cwd=protocol['case'],stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:profiler_code=process.wait(timeout=protocol['profiler_timeout_s'])
  except subprocess.TimeoutExpired:
   timed_out=True;start_file=evidence/'actual_solver_start.json'
   if start_file.exists():
    identity=json.loads(start_file.read_text())['actual_child'];pid=identity['pid']
    try:
     pidfd=os.pidfd_open(pid);live=proc_identity(pid)
     require(all(live[k]==identity[k] for k in ['pid','uid','birth_start_ticks','cwd','exe']),'Refuse timeout signal to changed child identity')
     signal.pidfd_send_signal(pidfd,signal.SIGTERM);child_cleanup.append('SIGTERM to verified actual solver via pidfd')
     deadline=time.monotonic()+protocol['cleanup_grace_s']
     while time.monotonic()<deadline and (Path('/proc')/str(pid)).exists():time.sleep(.2)
     if (Path('/proc')/str(pid)).exists():signal.pidfd_send_signal(pidfd,signal.SIGKILL);child_cleanup.append('SIGKILL to same pidfd after grace')
     os.close(pidfd)
    except ProcessLookupError:pass
   try:profiler_code=process.wait(timeout=protocol['profiler_cleanup_timeout_s'])
   except subprocess.TimeoutExpired:
    # Actual solver was already handled separately; preserve profiler failure.
    process.terminate()
    try:profiler_code=process.wait(timeout=30)
    except subprocess.TimeoutExpired:process.kill();profiler_code=process.wait()
 profiler={'completed_utc':utc(),'return_code':profiler_code,'timed_out':timed_out,'verified_child_cleanup':child_cleanup,'actual_solver_exit_is_separate':True,'command':command};save(evidence/'profiler_exit.json',profiler)
 require(not timed_out and profiler_code==0,'Profiler failed/timed out; preserve true child receipt and partial trace')
 report=evidence/'first_complete_step.nsys-rep';require(report.is_file(),'No profile report')
 export=[protocol['nsys']['path'],'export','--type=sqlite','--force-overwrite=false','--output',str(evidence/'first_complete_step.sqlite'),str(report)]
 with (evidence/'export.log').open('xb') as output:r=subprocess.run(export,stdout=output,stderr=subprocess.STDOUT,timeout=protocol['export_timeout_s'])
 save(evidence/'export_exit.json',{'command':export,'return_code':r.returncode,'completed_utc':utc()});require(r.returncode==0,'Trace export failed; do not repeat CFD')
 from validate_gpu_profile import validate
 result=validate(args.approval,args.receipt);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
