#!/usr/bin/env python3
"""Prove stdpar GPU execution with device-only output after the ordinary compiler gate."""
import hashlib,json,os,pathlib,shutil,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path("/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/native_stdpar_install")
SDK=P/"nvhpc/Linux_aarch64/26.9"
def utc():return datetime.now(timezone.utc).isoformat()
def state(stage,**extra):
 d={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),**extra}
 (P/"marker_progress.json").write_text(json.dumps(d,indent=2)+"\n");print(json.dumps(d),flush=True)
def main():
 os.nice(15);state("waiting_for_ordinary_managed_stdpar_gate")
 while not (P/"provenance/stdpar_compiler_gate.json").exists():
  if (P/"install_progress.json").exists() and json.loads((P/"install_progress.json").read_text()).get("stage")=="failed":raise RuntimeError("SDK/compiler gate failed")
  time.sleep(5)
 env=dict(os.environ)
 env.update({"PATH":str(SDK/"compilers/bin")+":"+env["PATH"],"LD_LIBRARY_PATH":"/usr/lib/wsl/lib:"+env.get("LD_LIBRARY_PATH",""),"TMPDIR":str(P/"tmp"),"XDG_CONFIG_HOME":str(P/"runtime-config"),"CUDA_CACHE_PATH":str(P/"runtime-config/CudaCache"),"OMP_NUM_THREADS":"1"})
 source=P/"smoke/stdpar_device_marker.cpp";binary=source.with_suffix("")
 shutil.copyfile(WORK/source.name,source)
 flags=["-std=c++17","-stdpar=gpu","-gpu=cc121,mem:managed","-Minfo=all","-O2"]
 records=[]
 for name,args in [("device_marker_compile",[str(SDK/"compilers/bin/nvc++"),*flags,str(source),"-o",str(binary)]),("device_marker_run",[str(binary),"324508639"])]:
  state(name,command=args);start=time.monotonic();log=P/"logs"/(name+".log")
  with log.open("w") as f:r=subprocess.run(args,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300)
  records.append({"name":name,"command":args,"return_code":r.returncode,"elapsed_s":time.monotonic()-start,"log":str(log)})
  if r.returncode:raise RuntimeError(name+" exited "+str(r.returncode)+"; "+str(log))
 result=json.loads(next(x for x in (P/"logs/device_marker_run.log").read_text().splitlines() if x.startswith("{")))
 if not result["passed"] or result["output_memory_type"]!=2 or not result["output_host_pointer_is_null"] or not result["output_device_pointer_valid"] or result["mismatches"]:raise RuntimeError("Device-only execution marker failed")
 evidence={"kind":"Actual GPU execution proof for managed-mode nvc++ stdpar; not CFD","completed_utc":utc(),"compiler_flags":flags,"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"records":records,"result":result,"device_execution_proof":"Managed heap input indices, runtime seed and cudaMalloc DEVICE output captured by value; hostPointer null verified; every copied-back nonuniform unsigned result matched after successful CUDA synchronization.","no_cpu_fallback_control_run":True,"reference":"https://forums.developer.nvidia.com/t/implicit-data-copy-to-device-for-allocated-arrays-using-compilation-option-stdpar-gpu/253279"}
 (P/"provenance/stdpar_device_marker_gate.json").write_text(json.dumps(evidence,indent=2)+"\n")
 state("device_execution_marker_passed",evidence=str(P/"provenance/stdpar_device_marker_gate.json"))
if __name__=="__main__":
 try:main()
 except Exception as e:state("failed",error=str(e));raise
