#!/usr/bin/env python3
"""Keep a transient service alive exactly while the adopted native worker lives."""
import json,os,pathlib,sys,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
pid=int(sys.argv[1]);expected=sys.argv[2]
def info():
 try:
  q=pathlib.Path("/proc")/str(pid)
  args=[x.decode() for x in (q/"cmdline").read_bytes().split(b"\0") if x]
  stat=(q/"stat").read_text();tail=stat[stat.rfind(")")+2:].split()
  if expected not in args or tail[0]=="Z":return None
  return {"start_ticks":int(tail[19]),"argv":args,"cgroup":(q/"cgroup").read_text().strip()}
 except OSError:return None
initial=info()
if initial is None:raise SystemExit("Expected native worker is not alive")
while True:
 current=info()
 if current is None or current["start_ticks"]!=initial["start_ticks"]:break
 record={"utc":datetime.now(timezone.utc).isoformat(),"supervisor_pid":os.getpid(),"worker_pid":pid,**current}
 path=P/"native_main_supervisor_progress.json";temp=path.with_suffix(".tmp")
 temp.write_text(json.dumps(record,indent=2)+"\n");os.replace(temp,path)
 time.sleep(10)
try:state=json.loads((P/"build_progress.json").read_text())
except (OSError,ValueError):state={}
success=state.get("stage")=="minimal_native_openfoam_tutorial_gate_passed"
print(json.dumps({"worker_finished":pid,"state":state,"success":success}),flush=True)
raise SystemExit(0 if success else 1)
