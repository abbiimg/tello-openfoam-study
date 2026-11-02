#!/usr/bin/env python3
"""Resume only the two private native workers, detached from transient tool pipes."""
import datetime,fcntl,json,os,pathlib,subprocess,time
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path(__file__).resolve().parent
SPECS=[("main","build_minimal_native_stack.py","build_progress.json"),("profile","profile_native_cfd_loop.py","native_cfd_profile_progress.json")]
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def matches(pid,script):
 try:
  args=(pathlib.Path("/proc")/str(pid)/"cmdline").read_bytes().split(b"\0")
  return str(script).encode() in args
 except OSError:return False
def main():
 runtime=P/"runtime";runtime.mkdir(exist_ok=True)
 with (runtime/"detached_launcher.lock").open("w") as lock:
  fcntl.flock(lock,fcntl.LOCK_EX)
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
  records=[]
  for name,filename,statefile in SPECS:
   script=WORK/filename;statepath=P/statefile
   old=json.loads(statepath.read_text()) if statepath.exists() else {}
   if old.get("pid") and matches(old["pid"],script):
    records.append({"worker":name,"pid":old["pid"],"action":"kept_already_running"});continue
   if old:(P/"provenance"/(name+"_stale_state_"+stamp+".json")).write_text(json.dumps(old,indent=2)+"\n")
   log=P/"logs"/("detached_"+name+"_"+stamp+".log")
   args=["/usr/bin/python3",str(script)]
   with log.open("ab",buffering=0) as stream:
    child=subprocess.Popen(args,cwd=WORK,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,close_fds=True,start_new_session=True)
   time.sleep(1)
   if not matches(child.pid,script):raise RuntimeError("Detached worker did not survive startup: "+name+"; inspect "+str(log))
   records.append({"worker":name,"pid":child.pid,"action":"launched_detached","argv":args,"log":str(log),"session_id":os.getsid(child.pid),"process_group":os.getpgid(child.pid),"nice":os.getpriority(os.PRIO_PROCESS,child.pid)})
  data={"launched_utc":utc(),"method":"Python Popen start_new_session, stdin DEVNULL, separate file stdout/stderr, close_fds; no dependency on an interactive tool exec session","records":records,"prior_worker_loss":"Previous PIDs and tool sessions were absent; exact cause not proven. Completed objects are retained and journal entries are preserved on resume.","budget_file":str(WORK/"build_budget.json")}
  target=P/"provenance"/("detached_workers_"+stamp+".json");target.write_text(json.dumps(data,indent=2)+"\n")
  (P/"detached_workers.json").write_text(json.dumps(data,indent=2)+"\n")
  print(json.dumps(data,indent=2))
if __name__=="__main__":main()
