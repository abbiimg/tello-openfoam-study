"""One approved new-profiler control, no compilation or CFD."""
from pathlib import Path
import argparse,json,os,signal,subprocess,time,traceback
from control_common import *
from owned_cleanup import stop_and_reap
def owner_state(e,marker):
 for n in ['actual_exit.json','wrapper_exit.json']:
  if (e/n).exists():
   d=json.loads((e/n).read_text())
   if d.get('actual_child_waited') or d.get('actual_child_launched') is False:return 'terminal_or_not_launched'
 if marker and not (e/'actual_wrapper_start.json').exists():return 'cancelled_before_wrapper_start'
 return 'unresolved'
def stop_owner(e,p,notes):
 marker=False
 try:save(e/'cancel.json',{'utc':utc()});marker=True
 except BaseException:notes.append(traceback.format_exc())
 for n in ['actual_start.json','actual_wrapper_start.json']:
  if not (e/n).exists():continue
  fd=None
  try:
   d=json.loads((e/n).read_text());old=d.get('actual_child',d.get('identity'));fd=os.pidfd_open(old['pid']);live=identity(old['pid'])
   require(all(old[k]==live[k] for k in ['pid','uid','birth_start_ticks','cwd','exe']),'Changed owned identity')
   require(live['uid']==999 and live['cwd']==p['case'],'Unrelated child')
   if n=='actual_start.json':require(live['exe']==p['binary']['path'],'Different probe')
   else:require(str(HERE/'control_child.py') in (Path('/proc')/str(old['pid'])/'cmdline').read_bytes().decode().split('\0'),'Different wrapper')
   signal.pidfd_send_signal(fd,signal.SIGTERM)
  except (ProcessLookupError,FileNotFoundError):pass
  except BaseException:notes.append(traceback.format_exc())
  finally:
   if fd is not None:os.close(fd)
 return marker
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--approval',type=Path,required=True);ap.add_argument('--execute-approved-control',action='store_true');args=ap.parse_args();require(args.execute_approved_control,'Source-only: explicit execution flag required');p,a=load(args.approval)
 require(not os.environ.get('LD_PRELOAD') and not any(os.environ.get(k) for k in ['CUDA_INJECTION64_PATH','NVTX_INJECTION64_PATH']),'No pre-existing observer/tool injection')
 e=Path(p['evidence']);require(not e.exists(),'Do not overwrite prior control attempt');e.mkdir();os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 command=[p['nsys']['path'],'profile',*p['nsys_flags'],'-o',str(e/'field_control'),'/usr/bin/python3','-B',str(HERE/'control_child.py'),'--approval',str(args.approval)]
 save(e/'prelaunch.json',{'utc':utc(),'command':command,'approval_sha256':sha(args.approval),'protocol_sha256':sha(HERE/'protocol.json'),'CPU_GPU_speed_test':False})
 env=dict(os.environ);env['NSYS_NVTX_PROFILER_REGISTER_ONLY']='0';cancelled=False;timed_out=False;errors=[];notes=[]
 def cancel(signum,frame):
  nonlocal cancelled
  cancelled=True
 signal.signal(signal.SIGTERM,cancel);signal.signal(signal.SIGINT,cancel)
 with (e/'profile.log').open('xb') as stream:
  proc=subprocess.Popen(command,env=env,cwd=p['case'],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   begin=time.monotonic()
   while proc.poll() is None:
    if cancelled:break
    if time.monotonic()-begin>p['profiler_timeout_s']:timed_out=True;break
    time.sleep(.1)
  except BaseException:errors.append(traceback.format_exc())
  finally:
   if cancelled or timed_out or errors or proc.poll() is None or proc.returncode!=0:
    marker=stop_owner(e,p,notes);state=owner_state(e,marker)
    while state=='unresolved':time.sleep(.1);state=owner_state(e,marker)
    if proc.poll() is None:notes.append(stop_and_reap(proc,p['cleanup_grace_s']))
   code=proc.wait();save(e/'profile_exit.json',{'return_code':code,'cancelled':cancelled,'timed_out':timed_out,'wrapper_errors':errors,'cleanup_notes':notes,'utc':utc()})
 require(code==0 and not cancelled and not timed_out and not errors,'Profile control failed; preserve evidence, no automatic repeat')
 export=[p['nsys']['path'],'export','--type=sqlite','--force-overwrite=false','--output',str(e/'field_control.sqlite'),str(e/'field_control.nsys-rep')]
 with (e/'export.log').open('xb') as stream:r=subprocess.run(export,stdout=stream,stderr=subprocess.STDOUT,timeout=60)
 save(e/'export_exit.json',{'return_code':r.returncode,'command':export});require(r.returncode==0,'Export failed; do not rerun control')
 from audit_control import audit
 print(json.dumps(audit(args.approval),indent=2))
if __name__=='__main__':main()
