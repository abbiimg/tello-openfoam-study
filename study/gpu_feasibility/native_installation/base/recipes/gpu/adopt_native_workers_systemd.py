#!/usr/bin/env python3
"""Adopt the active private build without restarting compilers; service-own its idle watcher."""
import datetime,json,os,pathlib,signal,subprocess,sys,time
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path(__file__).resolve().parent
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def command(args):
 r=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if r.returncode:raise RuntimeError(str(args)+"\n"+r.stdout)
 return {"argv":args,"stdout":r.stdout.strip()}
def show(unit):
 text=command(["systemctl","show",unit,"--property=Id,ActiveState,SubState,MainPID,User,Nice,ControlGroup,CollectMode"])['stdout']
 return dict(x.split("=",1) for x in text.splitlines() if "=" in x)
def identity(pid,filename):
 q=pathlib.Path("/proc")/str(pid)
 if q.stat().st_uid!=999:raise RuntimeError("Unexpected worker owner")
 if str(WORK/filename).encode() not in (q/"cmdline").read_bytes().split(b"\0"):raise RuntimeError("Worker identity mismatch")
 return q
def tree(root):
 parent={}
 for q in pathlib.Path("/proc").iterdir():
  if not q.name.isdigit():continue
  try:
   s=(q/"stat").read_text();parent[int(q.name)]=int(s[s.rfind(")")+2:].split()[1])
  except (OSError,ValueError):pass
 ids={root}
 while True:
  old=len(ids);ids.update(pid for pid,ppid in parent.items() if ppid in ids)
  if len(ids)==old:return ids
def service(unit,script,args,log,delegate=False):
 extra=["--property=Delegate=yes"] if delegate else []
 return command(["systemd-run","--collect","--unit="+unit,"--uid=openfoam","--nice=15","--service-type=exec","--working-directory="+str(WORK),"--property=StandardInput=null","--property=StandardOutput=append:"+str(log),"--property=StandardError=append:"+str(log),*extra,"/usr/bin/python3",str(script),*args])
def main():
 if os.geteuid()!=0:raise RuntimeError("Task-scoped transient service creation requires root")
 stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
 state=json.loads((P/"build_progress.json").read_text());pid=state["pid"]
 identity(pid,"build_minimal_native_stack.py")
 managed=P/"systemd_workers.json"
 if managed.exists():
  previous=json.loads(managed.read_text())
  if previous.get("main_worker_pid")==pid and previous.get("main_unit") in (pathlib.Path("/proc")/str(pid)/"cgroup").read_text():
   current_profile=json.loads((P/"native_cfd_profile_progress.json").read_text())["pid"]
   identity(current_profile,"profile_native_cfd_loop.py")
   if previous.get("profile_unit") in (pathlib.Path("/proc")/str(current_profile)/"cgroup").read_text():
    print(json.dumps({"action":"kept_already_managed_workers","main_worker_pid":pid,"profile_worker_pid":current_profile,"main_unit":previous["main_unit"],"profile_unit":previous["profile_unit"]},indent=2));return
 mainunit="native-stdpar-main-"+stamp+".service"
 if len(sys.argv)>1:
  mainunit=sys.argv[1]
  if not (mainunit.startswith("native-stdpar-main-") and mainunit.endswith(".service")):raise RuntimeError("Unexpected existing private unit name")
  existing=show(mainunit)
  supervisor_args=(pathlib.Path("/proc")/existing["MainPID"]/"cmdline").read_bytes().split(b"\0")
  if existing["User"]!="openfoam" or str(WORK/"supervise_existing_native_worker.py").encode() not in supervisor_args or str(pid).encode() not in supervisor_args:raise RuntimeError("Existing private supervisor identity mismatch")
  # This systemd version requires Delegate at transient creation time.
  # Replace only a supervisor that has not adopted any build process yet.
  members={int(x) for x in (pathlib.Path("/sys/fs/cgroup")/existing["ControlGroup"].lstrip("/")/"cgroup.procs").read_text().split()}
  if members!={int(existing["MainPID"])}:raise RuntimeError("Refusing to replace a supervisor that already owns other processes")
  command(["systemctl","stop",mainunit])
  mainunit="native-stdpar-main-"+stamp+".service"
  launched=service(mainunit,WORK/"supervise_existing_native_worker.py",[str(pid),str(WORK/"build_minimal_native_stack.py")],P/"logs"/(mainunit+".log"),delegate=True)
 else:
  launched=service(mainunit,WORK/"supervise_existing_native_worker.py",[str(pid),str(WORK/"build_minimal_native_stack.py")],P/"logs"/(mainunit+".log"),delegate=True)
 attached=[]
 for attempt in range(4):
  target=show(mainunit)["ControlGroup"]
  for member in sorted(tree(pid)):
   q=pathlib.Path("/proc")/str(member)
   try:
    if q.stat().st_uid!=999:raise RuntimeError("Unexpected descendant owner")
    if target in (q/"cgroup").read_text():continue
    args=["busctl","--system","call","org.freedesktop.systemd1","/org/freedesktop/systemd1","org.freedesktop.systemd1.Manager","AttachProcessesToUnit","ssau",mainunit,"","1",str(member)]
    try:command(args);attached.append(member)
    except RuntimeError:
     if q.exists():raise
   except FileNotFoundError:pass
  if all(target in (pathlib.Path("/proc")/str(x)/"cgroup").read_text() for x in tree(pid) if (pathlib.Path("/proc")/str(x)).exists()):break
 else:raise RuntimeError("Could not adopt complete active worker tree")
 old=json.loads((P/"native_cfd_profile_progress.json").read_text());oldpid=old["pid"]
 q=identity(oldpid,"profile_native_cfd_loop.py")
 if old["stage"]!="waiting_for_native_tutorial_gate" or (q/"task"/str(oldpid)/"children").read_text().strip():raise RuntimeError("Refusing to replace an active profiling child")
 (P/"provenance"/("profile_pre_systemd_"+stamp+".json")).write_text(json.dumps(old,indent=2)+"\n")
 os.kill(oldpid,signal.SIGTERM)
 for _ in range(30):
  if not q.exists() or b"profile_native_cfd_loop.py" not in (q/"cmdline").read_bytes():break
  time.sleep(.1)
 profileunit="native-stdpar-profile-"+stamp+".service"
 profilelaunch=service(profileunit,WORK/"profile_native_cfd_loop.py",[],P/"logs"/(profileunit+".log"))
 time.sleep(1)
 info={"created_utc":utc(),"method":"Existing active build and its exact UID999 descendant tree adopted into a task-scoped transient supervisor service via systemd AttachProcessesToUnit; no compiler restarted. Idle profile watcher replaced by a direct transient service.","main_worker_pid":pid,"main_unit":mainunit,"main_launch":launched,"attached_pids":attached,"main_service":show(mainunit),"profile_unit":profileunit,"profile_launch":profilelaunch,"profile_service":show(profileunit),"method_reference":"https://www.freedesktop.org/software/systemd/man/latest/org.freedesktop.systemd1.html","no_global_configuration_change":True,"no_compiler_restart":True}
 (P/"systemd_workers.json").write_text(json.dumps(info,indent=2)+"\n")
 (P/"provenance"/("systemd_workers_"+stamp+".json")).write_text(json.dumps(info,indent=2)+"\n")
 print(json.dumps(info,indent=2))
if __name__=="__main__":main()
