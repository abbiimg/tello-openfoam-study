#!/usr/bin/env python3
"""Audit successful CUDA launch APIs inside the annotated, isolated icoFoam CFD loop."""
import hashlib,json,os,pathlib,re,shlex,sqlite3,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
R=P/"source/OpenFOAM-v2606"
BINARY=R/"platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin/icoFoam"
CASE=pathlib.Path("/opt/openfoam-workspace/cases/native_stdpar_gpu_pilots_20261102/cavity_native_gpu")
NSYS=P/"nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys"
RANGE="NATIVE_STDPAR_CFD_TIME_LOOPS"
STATE=P/"native_cfd_profile_progress.json"
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2)+"\n");os.replace(tmp,path)
def status(stage,**extra):
 data={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),**extra};save(STATE,data);print(json.dumps(data),flush=True)
def run(name,args,timeout=900):
 log=P/"logs"/(name+".log")
 shell=". "+shlex.quote(str(P/"env.sh"))+"; exec "+shlex.join([str(x) for x in args])
 status(name,command=args,log=str(log))
 start=time.monotonic()
 with log.open("w") as f:r=subprocess.run(["bash","--noprofile","--norc","-c",shell],stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 if r.returncode:raise RuntimeError(name+" failed "+str(r.returncode)+"; "+str(log))
 return {"command":args,"return_code":r.returncode,"elapsed_s":time.monotonic()-start,"log":str(log)}
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)));status("waiting_for_native_tutorial_gate")
 while not (P/"provenance/native_openfoam_tutorial_gate.json").exists():
  if (P/"build_progress.json").exists() and json.loads((P/"build_progress.json").read_text()).get("stage")=="failed":raise RuntimeError("Native tutorial/build gate failed")
  time.sleep(5)
 while int(next(x.split()[1] for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))<20*1024*1024:
  status("waiting_for_20GiB_memory_reserve");time.sleep(10)
 output=P/"smoke/cavity_icoFoam_time_loop_trace"
 profile=run("cavity_cfd_loop_profile",[str(NSYS),"profile","--trace=cuda,nvtx","--sample=none","--cpuctxsw=none","--stats=false","--force-overwrite=true","-o",str(output),str(BINARY),"-case",str(CASE)])
 text=pathlib.Path(profile["log"]).read_text()
 times=[float(v) for v in re.findall(r"^Time = ([0-9.eE+-]+)",text,re.M)]
 continuity=[float(v) for v in re.findall(r"time step continuity errors\s*:\s*sum local =\s*([0-9.eE+-]+)",text)]
 if not times or abs(times[-1]-.5)>1e-10 or "\nEnd\n" not in text or not continuity or max(continuity)>1e-5:
  raise RuntimeError("Profiled CFD tutorial completion/continuity gate failed")
 exported=run("cavity_cfd_loop_export",[str(NSYS),"stats","--force-export=true","--report","cuda_api_sum","--format","csv",str(output)+".nsys-rep"],timeout=300)
 database=pathlib.Path(str(output)+".sqlite")
 con=sqlite3.connect("file:"+str(database)+"?mode=ro",uri=True);con.row_factory=sqlite3.Row
 tables={row[0] for row in con.execute("select name from sqlite_master where type='table'")}
 if "NVTX_EVENTS" not in tables:raise RuntimeError("No NVTX_EVENTS table; cannot isolate CFD loop")
 columns={row[1] for row in con.execute("pragma table_info(NVTX_EVENTS)")}
 clauses=[];params=[]
 if "text" in columns:clauses.append("text=?");params.append(RANGE)
 if "textId" in columns:clauses.append("textId in (select id from StringIds where value=?)");params.append(RANGE)
 if not clauses:raise RuntimeError("No supported NVTX name column")
 ranges=[dict(row) for row in con.execute("select * from NVTX_EVENTS where ("+" or ".join(clauses)+") and end is not null",params)]
 if len(ranges)!=1:raise RuntimeError("Expected one complete CFD loop NVTX range; found"+str(len(ranges)))
 start,end=ranges[0]["start"],ranges[0]["end"]
 counts=[];sync=[];kernel_activity={}
 for table in sorted(tables):
  if not table.startswith("CUPTI_ACTIVITY_KIND_"):continue
  cols={row[1] for row in con.execute('pragma table_info("'+table+'")')}
  if "KERNEL" in table:
   kernel_activity[table]=con.execute('select count(*) from "'+table+'"').fetchone()[0]
  if not {"start","end","nameId","returnValue"}.issubset(cols):continue
  query='select s.value as name,a.returnValue as return_value,count(*) as calls from "'+table+'" a join StringIds s on a.nameId=s.id where a.start>=? and a.end<=? group by s.value,a.returnValue'
  for row in con.execute(query,(start,end)):
   item={"table":table,**dict(row)}
   name=item["name"]
   if any(k in name for k in ["cudaLaunchKernel","cuLaunchKernel","cudaGraphLaunch","cuGraphLaunch","cudaLaunchCooperativeKernel"]):counts.append(item)
   if any(k in name for k in ["cudaDeviceSynchronize","cudaStreamSynchronize","cuCtxSynchronize","cuStreamSynchronize"]):sync.append(item)
 con.close()
 successful=sum(x["calls"] for x in counts if x["return_value"]==0)
 failed=sum(x["calls"] for x in counts if x["return_value"]!=0)
 bad_sync=sum(x["calls"] for x in sync if x["return_value"]!=0)
 if not successful or failed or bad_sync:raise RuntimeError("CFD loop launch/synchronization audit failed: "+repr((successful,failed,bad_sync)))
 d={"kind":"Actual CUDA launch API execution observed inside native icoFoam CFD time-loop; functionality gate, not speed measurement","completed_utc":utc(),"binary":str(BINARY),"binary_sha256":hashlib.sha256(BINARY.read_bytes()).hexdigest(),"case":str(CASE),"environment":str(P/"env.sh"),"range_name":RANGE,"range_start_ns":start,"range_end_ns":end,"range_row":ranges[0],"profile":profile,"export":exported,"report":str(output)+".nsys-rep","sqlite":str(database),"successful_launch_api_calls_in_cfd_loop":successful,"failed_launch_api_calls_in_cfd_loop":failed,"launch_api_rows":counts,"synchronization_api_rows":sync,"failed_synchronization_api_calls":bad_sync,"kernel_activity_tables":kernel_activity,"count_scope":"API call counts, not a count of distinct GPU kernels; runtime and driver layers may both be present.","tutorial_final_time":times[-1],"tutorial_peak_local_continuity":max(continuity),"solver_source_annotation":str(P/"provenance/ico_time_loop_annotation.json"),"production_switch":False,"speedup_measured":False}
 save(P/"provenance/native_cfd_time_loop_gpu_gate.json",d)
 status("native_cfd_time_loop_gpu_api_gate_passed",evidence=str(P/"provenance/native_cfd_time_loop_gpu_gate.json"),successful_launch_api_calls=successful)
if __name__=="__main__":
 try:main()
 except Exception as e:status("failed",error=str(e));raise
