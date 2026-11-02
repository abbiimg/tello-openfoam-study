#!/usr/bin/env python3
"""Verify CUDA launch APIs within the native Foam Field algebra NVTX window."""
import hashlib,json,os,pathlib,shlex,sqlite3,subprocess
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
NSYS=P/"nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys"
OUT=P/"smoke/native_field_algebra_cuda_trace"
RANGE="NATIVE_STDPAR_FIELD_ALGEBRA"
def save(path,data):
 t=path.with_suffix(path.suffix+".tmp");t.write_text(json.dumps(data,indent=2)+"\n");os.replace(t,path)
def main():
 os.nice(15)
 args=[str(NSYS),"stats","--force-export=true","--report","cuda_api_sum","--format","csv",str(OUT)+".nsys-rep"]
 log=P/"logs/native_field_gate_trace_export.log"
 shell=". "+shlex.quote(str(P/"env.sh"))+"; exec "+shlex.join(args)
 with log.open("w") as stream:
  subprocess.run(["bash","--noprofile","--norc","-c",shell],stdout=stream,stderr=subprocess.STDOUT,timeout=300,check=True)
 db=pathlib.Path(str(OUT)+".sqlite")
 con=sqlite3.connect("file:"+str(db)+"?mode=ro",uri=True);con.row_factory=sqlite3.Row
 tables={row[0] for row in con.execute("select name from sqlite_master where type='table'")}
 cols={row[1] for row in con.execute("pragma table_info(NVTX_EVENTS)")}
 clauses=[];params=[]
 if "text" in cols:clauses.append("text=?");params.append(RANGE)
 if "textId" in cols:clauses.append("textId in (select id from StringIds where value=?)");params.append(RANGE)
 if not clauses:raise RuntimeError("NVTX range names unavailable")
 rows=[dict(r) for r in con.execute("select * from NVTX_EVENTS where ("+" or ".join(clauses)+") and end is not null",params)]
 if len(rows)!=1:raise RuntimeError("Expected exactly one complete Field algebra window")
 lo,hi=rows[0]["start"],rows[0]["end"]
 launches=[];sync=[];kernels={}
 for table in sorted(tables):
  if not table.startswith("CUPTI_ACTIVITY_KIND_"):continue
  columns={row[1] for row in con.execute('pragma table_info("'+table+'")')}
  if "KERNEL" in table:kernels[table]=con.execute('select count(*) from "'+table+'"').fetchone()[0]
  if not {"start","end","nameId","returnValue"}.issubset(columns):continue
  query='select s.value as name,a.returnValue as return_value,count(*) as calls from "'+table+'" a join StringIds s on a.nameId=s.id where a.start>=? and a.end<=? group by s.value,a.returnValue'
  for r in con.execute(query,(lo,hi)):
   item={"table":table,**dict(r)};name=item["name"]
   if any(n in name for n in ["cudaLaunchKernel","cuLaunchKernel","cudaGraphLaunch","cuGraphLaunch","cudaLaunchCooperativeKernel"]):launches.append(item)
   if any(n in name for n in ["cudaDeviceSynchronize","cudaStreamSynchronize","cuCtxSynchronize","cuStreamSynchronize"]):sync.append(item)
 con.close()
 success=sum(x["calls"] for x in launches if x["return_value"]==0)
 failed=sum(x["calls"] for x in launches if x["return_value"]!=0)
 failed_sync=sum(x["calls"] for x in sync if x["return_value"]!=0)
 if not success or failed or failed_sync:raise RuntimeError("Field algebra launch/synchronization audit failed")
 data={"kind":"Successful CUDA launch APIs within the actual native Foam Field algebra window; not CFD or a speed measurement","completed_utc":datetime.now(timezone.utc).isoformat(),"range_name":RANGE,"range_row":rows[0],"successful_launch_api_calls":success,"failed_launch_api_calls":failed,"failed_synchronization_api_calls":failed_sync,"launch_api_rows":launches,"synchronization_api_rows":sync,"kernel_activity_tables":kernels,"count_scope":"API calls, not distinct GPU kernels; runtime and driver calls may both be counted.","report":str(OUT)+".nsys-rep","report_sha256":hashlib.sha256(pathlib.Path(str(OUT)+".nsys-rep").read_bytes()).hexdigest(),"sqlite":str(db),"export_command":args,"export_log":str(log),"speedup_measured":False}
 evidence=P/"provenance/native_field_gpu_api_gate.json";save(evidence,data)
 gate_path=P/"provenance/native_field_arithmetic_gate.json";gate=json.loads(gate_path.read_text())
 gate.update(launch_api_audit_pending=False,cuda_api_audit=str(evidence),successful_launch_api_calls_in_field_algebra=success)
 save(gate_path,gate)
 print(json.dumps({"passed":True,"successful_launch_api_calls":success,"failed_launch_api_calls":failed,"failed_synchronization_api_calls":failed_sync,"kernel_activity_tables":kernels,"evidence":str(evidence)}))
if __name__=="__main__":main()
