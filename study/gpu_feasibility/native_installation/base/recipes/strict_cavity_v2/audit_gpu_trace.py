#!/usr/bin/env python3
"""Bind successful first-step CUDA execution and completion to the real solver PID."""
import argparse,json,pathlib,sqlite3
from strict_common import check_freeze,load_protocol,save,sha,utc
def audit(root,evidence):
 protocol=load_protocol();check_freeze(root);receipt=json.loads((evidence/"solver_exit.json").read_text());child=receipt["actual_child"];pid=child["pid"]
 frozen_binary=json.loads((root/"GPU_binary_pre_run.json").read_text())
 if receipt["binary_sha256"]!=frozen_binary["binary_sha256"] or receipt["binary_sha256"]!=receipt["binary_sha256_after"]:raise RuntimeError("GPU binary differs from pre-run freeze")
 if receipt["return_code"]!=0 or not receipt["actual_child_waited"]:raise RuntimeError("Actual GPU child did not finish successfully")
 if child["uid"]!=999 or pathlib.Path(child["cwd"]).resolve()!=pathlib.Path(receipt["case"]).resolve() or pathlib.Path(child["exe"]).resolve()!=pathlib.Path(receipt["binary"]).resolve():raise RuntimeError("Actual GPU solver UID/cwd/executable identity mismatch")
 combined=(evidence/"profile.log").read_text()+(evidence/"solver.log").read_text()
 start_message="Capture range started in the application.";end_message="Capture range ended in the application."
 if start_message not in combined or end_message not in combined:raise RuntimeError("Named capture start/end not observed")
 database=evidence/"strict_gpu_trace.sqlite";con=sqlite3.connect("file:"+str(database)+"?mode=ro",uri=True);con.row_factory=sqlite3.Row
 name=protocol["native_GPU_execution_proof"]["range"]
 ranges=[dict(x) for x in con.execute("select * from NVTX_EVENTS where (text=? or textId in(select id from StringIds where value=?)) and end is not null",(name,name))]
 if len(ranges)!=1:raise RuntimeError("Expected one complete first-step range")
 row=ranges[0];gtid=row["globalTid"];decoded_pid=(gtid//0x1000000)%0x1000000;decoded_tid=gtid%0x1000000
 if decoded_pid!=pid or decoded_tid!=pid or row["endGlobalTid"] not in (None,gtid):raise RuntimeError("NVTX globalTid does not bind the actual solver main thread")
 process=[dict(x) for x in con.execute("select * from PROCESSES where pid=? and globalPid=?",(pid,gtid-decoded_tid))]
 if len(process)!=1 or pathlib.Path(process[0]["name"]).name!=pathlib.Path(receipt["binary"]).name:raise RuntimeError("PROCESSES table does not bind actual solver binary")
 tables=[x[0] for x in con.execute("select name from sqlite_master where type='table'")];launch=[];sync=[];post_launch=[];kernel_tables={}
 for table in tables:
  if not table.startswith("CUPTI_ACTIVITY_KIND_"):continue
  cols={x[1] for x in con.execute('pragma table_info("'+table+'")')}
  if "KERNEL" in table:kernel_tables[table]=con.execute('select count(*) from "'+table+'"').fetchone()[0]
  if not {"globalTid","start","end","nameId","returnValue"}.issubset(cols):continue
  query='select a.start,a.end,a.globalTid,a.returnValue as return_value,s.value as name from "'+table+'" a join StringIds s on a.nameId=s.id where a.globalTid=? and a.start>=? and a.end<=?'
  for item in con.execute(query,(gtid,row["start"],row["end"])):
   item={"table":table,**dict(item)}
   if any(x in item["name"] for x in ["cudaLaunchKernel","cuLaunchKernel","cudaGraphLaunch","cuGraphLaunch","cudaLaunchCooperativeKernel","cuLaunchCooperativeKernel"]):launch.append(item)
   if any(x in item["name"] for x in ["cudaDeviceSynchronize","cuCtxSynchronize","cudaStreamSynchronize","cuStreamSynchronize"]):sync.append(item)
  query='select a.start,a.end,s.value as name from "'+table+'" a join StringIds s on a.nameId=s.id where a.globalTid=? and a.start>?'
  post_launch.extend(dict(x) for x in con.execute(query,(gtid,row["end"])) if any(n in x["name"] for n in ["LaunchKernel","GraphLaunch","LaunchCooperativeKernel"]))
 con.close()
 good=[x for x in launch if x["return_value"]==0];bad=[x for x in launch+sync if x["return_value"]!=0]
 if not good or bad:raise RuntimeError("Missing launches or failed launch/synchronization calls")
 last=max(x["end"] for x in good)
 completions=[x for x in sync if x["return_value"]==0 and any(n in x["name"] for n in ["cudaDeviceSynchronize","cuCtxSynchronize"]) and x["start"]>=last and x["end"]<=row["end"]]
 if not completions:raise RuntimeError("No successful same-thread device/context completion after last launch")
 if post_launch:raise RuntimeError("CUDA launches were still captured after the first-step range ended")
 result={"audited_utc":utc(),"passed":True,"actual_child":child,"actual_binary_sha256":receipt["binary_sha256"],"range":row,"process_table_row":process[0],"decoded_PID":decoded_pid,"decoded_TID":decoded_tid,"mapping_reference":"https://docs.nvidia.com/nsight-systems/AnalysisGuide/","successful_launch_api_calls":len(good),"failed_launch_or_sync_calls":len(bad),"last_launch_end_ns":last,"post_last_launch_completion":completions,"successful_sync_api_calls":len([x for x in sync if x["return_value"]==0]),"launch_rows":launch,"sync_rows":sync,"launches_captured_after_window":post_launch,"capture_start_message_observed":True,"capture_end_message_observed":True,"kernel_activity_tables":kernel_tables,"report_sha256":sha(evidence/"strict_gpu_trace.nsys-rep"),"count_scope":"API calls, not distinct GPU kernels; runtime and driver layers may both be counted","speedup_measured":False}
 save(evidence/"GPU_execution_gate.json",result);return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("root",type=pathlib.Path);p.add_argument("evidence",type=pathlib.Path);a=p.parse_args();r=audit(a.root,a.evidence);print(json.dumps({"passed":r["passed"],"successful_launch_api_calls":r["successful_launch_api_calls"]}))
