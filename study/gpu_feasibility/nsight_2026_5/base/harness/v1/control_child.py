"""Actual tiny Field-probe owner under Nsight; exact V3 cleanup module reused."""
from pathlib import Path
import argparse,json,os,signal,subprocess,sys,time,traceback
from control_common import *
from owned_cleanup import stop_and_reap
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--approval',type=Path,required=True);args=ap.parse_args();p,a=load(args.approval);e=Path(p['evidence'])
 require(e.is_dir() and (e/'prelaunch.json').is_file(),'Outer prelaunch required')
 require(os.environ.get('NSYS_NVTX_PROFILER_REGISTER_ONLY')=='0','Named range prerequisites missing')
 # The inherited Nsight injection preload is passed verbatim; no observer.
 before=case_hashes(p['case']);errors=[];pidfd=None;seen=set();cancelled=False;timed_out=False
 def stop(signum,frame):
  nonlocal cancelled
  cancelled=True
 signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 save(e/'actual_wrapper_start.json',{'identity':identity(os.getpid()),'started_utc':utc()})
 require(not (e/'cancel.json').exists() and not cancelled,'Cancelled before probe spawn')
 start={'started_utc':utc(),'binary_sha256':sha(p['binary']['path']),'source_sha256':sha(p['source']['path']),'core_sha256':sha(p['core_library']['path']),'approval_sha256':sha(args.approval),'case_before':before,'inherited_preload_preserved':os.environ.get('LD_PRELOAD'),'command':p['command']}
 with (e/'probe_stdout.log').open('xb') as output:
  begin=time.monotonic();child=subprocess.Popen(p['command'],cwd=p['case'],stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   start['actual_child']={'pid':child.pid,'identity_complete':False};save(e/'actual_spawn.json',start)
   pidfd=os.pidfd_open(child.pid);start['actual_child']=identity(child.pid);save(e/'actual_start.json',start)
   require(start['actual_child']['uid']==999 and start['actual_child']['cwd']==p['case'] and start['actual_child']['exe']==p['binary']['path'] and start['actual_child']['nice']>=15,'Wrong actual probe child')
   while child.poll() is None:
    try:
     for line in (Path('/proc')/str(child.pid)/'maps').read_text().splitlines():
      parts=line.split(maxsplit=5)
      if len(parts)==6 and parts[5].startswith('/') and '.so' in parts[5]:
       path=Path(parts[5].removesuffix(' (deleted)')).resolve()
       if path.is_file():seen.add(str(path))
    except (FileNotFoundError,ProcessLookupError,PermissionError):pass
    if (e/'cancel.json').exists():cancelled=True
    if cancelled:break
    if time.monotonic()-begin>p['application_timeout_s']:timed_out=True;break
    time.sleep(.01)
  except BaseException:errors.append(traceback.format_exc())
  finally:
   cleanup=stop_and_reap(child,p['cleanup_grace_s'],pidfd)
   if pidfd is not None:
    try:os.close(pidfd)
    except OSError:errors.append(traceback.format_exc())
   result={**start,**cleanup,'completed_utc':utc(),'cancelled':cancelled,'timed_out':timed_out,'wrapper_errors':errors,'postprocessing_complete':False}
   try:save(e/'actual_exit.json',result)
   except BaseException:errors.append(traceback.format_exc());print('ACTUAL_PROBE_FALLBACK '+json.dumps(result),file=sys.stderr,flush=True)
 try:
  text=(e/'probe_stdout.log').read_text();parsed=[json.loads(x) for x in text.splitlines() if x.startswith('{"kind":"native Foam Field')];require(len(parsed)==1,'One arithmetic JSON result required')
  observed={path:sha(path) for path in sorted(seen)};expected={x['path']:x['sha256'] for x in json.loads(Path(p['library_identity']['path']).read_text())['files']}
  result.update(arithmetic_result=parsed[0],loaded_libraries_observed=observed,declared_libraries_observed_unchanged=all(observed.get(path)==pin for path,pin in expected.items()),case_after=case_hashes(p['case']),binary_sha256_after=sha(p['binary']['path']),source_sha256_after=sha(p['source']['path']),core_sha256_after=sha(p['core_library']['path']),postprocessing_complete=True)
 except BaseException:errors.append(traceback.format_exc())
 finally:
  result['wrapper_errors']=errors
  try:save(e/'actual_exit.json',result)
  except BaseException:errors.append(traceback.format_exc());print('ACTUAL_PROBE_FALLBACK '+json.dumps(result),file=sys.stderr,flush=True)
  save(e/'wrapper_exit.json',{'actual_child_launched':True,'actual_child_waited':cleanup['actual_child_waited'],'true_child_returncode':cleanup['return_code'],'wrapper_errors':errors,'cleanup_errors':cleanup['cleanup_errors']})
 if errors or cleanup['cleanup_errors'] or not cleanup['actual_child_waited'] or cancelled or timed_out:return 1
 rc=cleanup['return_code'];return rc if rc>=0 else 128-rc
if __name__=='__main__':
 try:sys.exit(main())
 except BaseException as error:
  if not isinstance(error,SystemExit):
   try:
    p=json.loads((HERE/'protocol.json').read_text());e=Path(p['evidence'])
    if e.is_dir() and not (e/'wrapper_exit.json').exists():save(e/'wrapper_exit.json',{'actual_child_launched':(e/'actual_spawn.json').exists(),'wrapper_errors':[traceback.format_exc()]})
   except BaseException:pass
  raise
