#!/usr/bin/env python3
"""Corroborate the completed device marker with the SDK's versioned Nsight Systems."""
import csv,io,json,os,pathlib,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
SDK=P/"nvhpc/Linux_aarch64/26.9"
def main():
 os.nice(15)
 nsys=SDK/"profilers/13.3/Nsight_Systems/bin/nsys"
 env=dict(os.environ);env.update({"LD_LIBRARY_PATH":"/usr/lib/wsl/lib:"+env.get("LD_LIBRARY_PATH",""),"TMPDIR":str(P/"tmp"),"XDG_CONFIG_HOME":str(P/"runtime-config"),"CUDA_CACHE_PATH":str(P/"runtime-config/CudaCache")})
 output=P/"smoke/stdpar_device_marker_cuda_trace"
 records=[]
 result={"kind":"Additional process-attributed CUDA kernel trace for the already-passed stdpar marker; not CFD or a timing benchmark","attempted":True,"nsys":str(nsys),"gpu_kernel_execution_proof":"unverified"}
 for name,args in [
 ("nsys_version",[str(nsys),"--version"]),
 ("device_marker_cuda_profile",[str(nsys),"profile","--trace=cuda","--sample=none","--cpuctxsw=none","--stats=true","--force-overwrite=true","-o",str(output),str(P/"smoke/stdpar_device_marker"),"324508639"]),
 ("device_marker_cuda_kernel_stats",[str(nsys),"stats","--force-export=true","--report","cuda_gpu_kern_sum","--format","csv",str(output)+".nsys-rep"])]:
  log=P/"logs"/(name+".log");start=time.monotonic()
  with log.open("w") as f:r=subprocess.run(args,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  records.append({"name":name,"command":args,"return_code":r.returncode,"elapsed_s":time.monotonic()-start,"log":str(log)})
  if r.returncode:result["error"]=name+" exited"+str(r.returncode);break
 if len(records)==3 and all(x["return_code"]==0 for x in records):
  text=(P/"logs/device_marker_cuda_kernel_stats.log").read_text()
  lines=text.splitlines();header=next((i for i,line in enumerate(lines) if "Instances" in line and "Name" in line),None)
  if header is not None:
   rows=list(csv.DictReader(io.StringIO("\n".join(lines[header:]))))
   counts=[]
   for row in rows:
    try:counts.append(int(row.get("Instances","").replace(",","")))
    except ValueError:pass
   if sum(counts)>0:
    result.update(gpu_kernel_execution_proof="Nsight CUDA kernel summary contains executed kernels",kernel_instances=sum(counts),kernel_rows=rows)
 result.update(completed_utc=datetime.now(timezone.utc).isoformat(),records=records,report=str(output)+".nsys-rep")
 (P/"provenance/stdpar_device_marker_cuda_trace.json").write_text(json.dumps(result,indent=2)+"\n")
 # Preserve that the ordinary heap gate and the profiled marker are distinct.
 gate_path=P/"provenance/stdpar_compiler_gate.json"
 gate=json.loads(gate_path.read_text())
 gate["trace"]={k:v for k,v in result.items() if k in ["attempted","nsys","gpu_kernel_execution_proof","kernel_instances","error","report"]}
 gate["trace"]["test"]="separate device-only stdpar marker"
 gate_path.write_text(json.dumps(gate,indent=2)+"\n")
 print(json.dumps(result),flush=True)
if __name__=="__main__":main()
