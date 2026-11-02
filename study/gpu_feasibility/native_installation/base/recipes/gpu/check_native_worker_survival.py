#!/usr/bin/env python3
"""One-shot liveness/cgroup evidence, suitable for a delayed transient service."""
import datetime,json,os,pathlib
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path(__file__).resolve().parent
rows=[]
managed=json.loads((P/"systemd_workers.json").read_text()) if (P/"systemd_workers.json").exists() else {}
for name,statefile,script in [("main","build_progress.json","build_minimal_native_stack.py"),("profile","native_cfd_profile_progress.json","profile_native_cfd_loop.py")]:
 state=json.loads((P/statefile).read_text());pid=state["pid"];q=pathlib.Path("/proc")/str(pid)
 row={"worker":name,"pid":pid,"stage":state["stage"],"alive":q.exists()}
 if q.exists():
  row.update(cmdline=[x.decode() for x in (q/"cmdline").read_bytes().split(b"\0") if x],nice=os.getpriority(os.PRIO_PROCESS,pid),cgroup=(q/"cgroup").read_text().strip(),uid=q.stat().st_uid)
  row["cmdline_matches"]=str(WORK/script) in row["cmdline"]
  row["expected_unit"]=managed.get(name+"_unit")
  row["in_expected_systemd_unit"]=bool(row["expected_unit"] and row["expected_unit"] in row["cgroup"])
 rows.append(row)
data={"checked_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"method":"Independent one-shot process check after the launching tool command exited; no solver or compiler launched","checker_pid":os.getpid(),"workers":rows,"all_alive_and_matching":all(x["alive"] and x.get("cmdline_matches",False) for x in rows),"all_in_expected_systemd_units":all(x.get("in_expected_systemd_unit",False) for x in rows)}
stamp=datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
for filename in ["post_return_survival_"+stamp+".json","post_return_survival_latest.json"]:
 (P/"provenance"/filename).write_text(json.dumps(data,indent=2)+"\n")
print(json.dumps(data,indent=2))
