#!/usr/bin/env python3
"""Isolated SDK extraction/install and a managed stdpar compiler/runtime gate."""
import hashlib,json,os,pathlib,shutil,subprocess,tarfile,time
from datetime import datetime,timezone

P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path("/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/native_stdpar_install")
NAME="nvhpc_2026_269_Linux_aarch64_cuda_13.3"
SDK=P/"nvhpc/Linux_aarch64/26.9"
STATE=P/"install_progress.json"
def utc():return datetime.now(timezone.utc).isoformat()
def state(stage,**extra):
 data={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),"max_build_jobs":1,**extra}
 temp=STATE.with_suffix(".tmp");temp.write_text(json.dumps(data,indent=2)+"\n");os.replace(temp,STATE)
 print(json.dumps(data),flush=True)
def command(name,args,env,cwd=None,timeout=3600):
 start=time.monotonic()
 log=P/"logs"/(name+".log")
 state(name,command=args,log=str(log))
 with log.open("w") as out:
  p=subprocess.run(args,env=env,cwd=cwd,stdout=out,stderr=subprocess.STDOUT,timeout=timeout)
 record={"stage":name,"command":args,"return_code":p.returncode,"elapsed_s":time.monotonic()-start,"log":str(log),"completed_utc":utc()}
 (P/"provenance"/(name+".json")).write_text(json.dumps(record,indent=2)+"\n")
 if p.returncode:raise RuntimeError(name+" exited "+str(p.returncode)+"; see "+str(log))
 return record
def main():
 os.nice(15)
 state("waiting_for_verified_sdk_download")
 while True:
  marker=P/"provenance/nvhpc_archive.json"
  if marker.exists():
   record=json.loads(marker.read_text())
   if record.get("stage")=="download_verified":break
  time.sleep(5)
 archive=pathlib.Path(record["archive"])
 if archive.parent != P/"downloads" or archive.stat().st_size != record["bytes"]:
  raise RuntimeError("Archive provenance/containment mismatch")
 staging=P/"source"/NAME
 if not (staging/".verified_extraction_complete").exists():
  if staging.exists():raise RuntimeError("Refusing to overlay unmarked SDK staging directory")
  state("extracting_verified_sdk",archive=str(archive),archive_sha256=record["sha256"])
  started=time.monotonic()
  with tarfile.open(archive,"r:gz") as tf:
   members=tf.getmembers()
   roots={pathlib.PurePosixPath(m.name).parts[0] for m in members if m.name and m.name!="."}
   if roots!={NAME}:raise RuntimeError("Unexpected SDK archive roots: "+repr(roots))
   tf.extractall(P/"source",members=members,filter="data")
  (staging/".verified_extraction_complete").write_text(record["sha256"]+"\n")
  extraction={"completed_utc":utc(),"elapsed_s":time.monotonic()-started,"archive_sha256":record["sha256"],"member_count":len(members),"extraction_root":str(staging),"data_filter_used":True}
  (P/"provenance/sdk_extraction.json").write_text(json.dumps(extraction,indent=2)+"\n")
 env=dict(os.environ)
 env.update({"TMPDIR":str(P/"tmp"),"XDG_CONFIG_HOME":str(P/"runtime-config"),"CUDA_CACHE_PATH":str(P/"runtime-config/CudaCache"),"NVHPC_SILENT":"true","NVHPC_INSTALL_DIR":str(P/"nvhpc"),"NVHPC_INSTALL_TYPE":"single","NVHPC_DEFAULT_CUDA":"13.3","OMP_NUM_THREADS":"1"})
 if not (SDK/"compilers/bin/nvc++").exists():
  installer=staging/"install"
  command("nvhpc_silent_install",["/bin/bash",str(installer)],env,cwd=staging)
 # The26.9 installer still forwards NVHPC_STDPAR_CUDACC to a removed
 # makelocalrc option. Set the GPU architecture in explicit compiler flags,
 # and generate local GNU/CUDA configuration without that deprecated option.
 command("nvhpc_localrc",[str(SDK/"compilers/bin/makelocalrc"),"-x",str(SDK/"compilers/bin"),"-cuda","13.3"],env,timeout=60)
 env["PATH"]=str(SDK/"compilers/bin")+":"+str(SDK/"cuda/bin")+":"+env["PATH"]
 env["LD_LIBRARY_PATH"]="/usr/lib/wsl/lib:"+env.get("LD_LIBRARY_PATH","")
 command("nvcxx_version",[str(SDK/"compilers/bin/nvc++"),"--version"],env,timeout=60)
 command("nvaccelinfo",[str(SDK/"compilers/bin/nvaccelinfo")],env,timeout=60)
 smoke=P/"smoke"
 smoke.mkdir(exist_ok=True)
 source=smoke/"stdpar_smoke.cpp"
 shutil.copyfile(WORK/"stdpar_smoke.cpp",source)
 flags=["-std=c++17","-stdpar=gpu","-gpu=cc121,mem:managed","-Minfo=all","-O2"]
 command("stdpar_smoke_compile",[str(SDK/"compilers/bin/nvc++"),*flags,str(source),"-o",str(smoke/"stdpar_smoke")],env,timeout=600)
 runtime=command("stdpar_smoke_run",[str(smoke/"stdpar_smoke")],env,timeout=180)
 lines=(P/"logs/stdpar_smoke_run.log").read_text().splitlines()
 result=json.loads(next(line for line in reversed(lines) if line.startswith("{")))
 if not result["exact_element_check"] or result["pointer_memory_type"]!=3 or result["cuda_synchronize_status"]!=0 or result["cuda_last_error"]!=0:
  raise RuntimeError("Managed stdpar arithmetic/runtime gate failed")
 nsys_candidates=list(SDK.glob("profilers/**/bin/nsys"))+list(SDK.glob("profilers/**/target-linux-sbsa-armv8/nsys"))
 nsys=list(dict.fromkeys(p for p in nsys_candidates if p.is_file() and os.access(p,os.X_OK)))
 trace={"attempted":False,"gpu_kernel_execution_proof":"pending","note":"Exact arithmetic, managed pointer type and successful CUDA synchronization are verified separately; do not label an untraced image as profiler proof."}
 if nsys:
  trace["attempted"]=True;trace["nsys"]=str(nsys[0])
  try:
   run=command("stdpar_smoke_cuda_trace",[str(nsys[0]),"profile","--trace=cuda","--sample=none","--cpuctxsw=none","--stats=true","--force-overwrite=true","-o",str(smoke/"stdpar_smoke_cuda_trace"),str(smoke/"stdpar_smoke")],env,timeout=300)
   trace["command_record"]=run
   trace["gpu_kernel_execution_proof"]="inspect trace log/kernel summary"
  except Exception as e:trace["error"]=str(e)
 evidence={"kind":"Actual private managed stdpar compiler/runtime installation gate; not CFD","completed_utc":utc(),"sdk":str(SDK),"nvhpc_version":"26.9","compiler_flags":flags,"source_sha256":hashlib.sha256(source.read_bytes()).hexdigest(),"binary_sha256":hashlib.sha256((smoke/"stdpar_smoke").read_bytes()).hexdigest(),"runtime":runtime,"result":result,"trace":trace,"no_production_backend_change":True}
 (P/"provenance/stdpar_compiler_gate.json").write_text(json.dumps(evidence,indent=2)+"\n")
 state("stdpar_compiler_runtime_gate_passed",gate=str(P/"provenance/stdpar_compiler_gate.json"),trace=trace)
if __name__=="__main__":
 try:main()
 except Exception as e:
  state("failed",error=str(e))
  raise
