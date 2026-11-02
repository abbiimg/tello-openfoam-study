#!/usr/bin/env python3
"""Run a small independent native Field algebra gate after the core library links."""
import hashlib,json,os,pathlib,shlex,shutil,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path("/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/native_stdpar_install")
R=P/"source/OpenFOAM-v2606";LIB=R/"platforms/linuxARM64Nvidia-gpuDPInt32Opt/lib/libOpenFOAM.so"
BUDGET=WORK/"build_budget.json";STATE=P/"early_field_gate_progress.json"
OWNER_REASON="Temporary native base3 plus one independent Field gate compiler; total native4."
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 t=path.with_suffix(path.suffix+".tmp");t.write_text(json.dumps(data,indent=2)+"\n");os.replace(t,path)
def status(stage,**extra):
 d={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),**extra};save(STATE,d);print(json.dumps(d),flush=True)
def command(name,args,timeout=600):
 while int(next(x.split()[1] for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))<20*1024*1024:
  status("waiting_for_20GiB_memory_reserve");time.sleep(10)
 log=P/"logs"/(name+".log");shell=". "+shlex.quote(str(P/"env.sh"))+"; export WM_NCOMPPROCS=1; exec "+shlex.join([str(a) for a in args])
 status(name,command=args,log=str(log))
 with log.open("w") as f:r=subprocess.run(["bash","--noprofile","--norc","-c",shell],stdout=f,stderr=subprocess.STDOUT,timeout=timeout)
 if r.returncode:raise RuntimeError(name+" failed"+str(r.returncode)+"; "+str(log))
 return log
def main():
 os.nice(15);status("waiting_for_native_core_library")
 last=None;stable=0
 while True:
  build=json.loads((P/"build_progress.json").read_text())
  if build.get("stage")=="failed":raise RuntimeError("Main native build failed")
  if LIB.exists():
   now=(LIB.stat().st_size,LIB.stat().st_mtime_ns)
   stable=stable+1 if now==last else 0;last=now
   if stable>=3 and now[0]>100000:break
  time.sleep(3)
 budget=json.loads(BUDGET.read_text());original=dict(budget)
 if budget["max_jobs"]<4:
  status("waiting_for_spare_native_compile_slot",budget=budget["max_jobs"])
  while json.loads(BUDGET.read_text())["max_jobs"]<4:time.sleep(5)
  budget=json.loads(BUDGET.read_text());original=dict(budget)
 borrowed=bool(budget.get("early_field_probe_borrowed_spuma_slot",False))
 if not borrowed:
  budget.update(max_jobs=3,reason=OWNER_REASON);save(BUDGET,budget)
 try:
  # A3job currently-running base remains unchanged; future stages also see3
  # while this single compiler owns the fourth native slot.
  while True:
   build=json.loads((P/"build_progress.json").read_text())
   if build.get("stage")=="failed":raise RuntimeError("Main native build failed")
   if borrowed or build.get("max_build_jobs",0)<=3 or build.get("stage","").endswith("passed"):break
   status("waiting_for_active_four_job_stage_to_finish");time.sleep(5)
  app=P/"field_algebra_gate";(app/"Make").mkdir(parents=True,exist_ok=True)
  shutil.copyfile(WORK/"Test-nativeStdparFields.C",app/"Test-nativeStdparFields.C")
  (app/"Make/files").write_text("Test-nativeStdparFields.C\n\nEXE = $(FOAM_USER_APPBIN)/Test-nativeStdparFields\n")
  (app/"Make/options").write_text("EXE_INC =\n\nEXE_LIBS =\n")
  command("native_field_gate_compile",["wmake","-j1",str(app)])
 finally:
  current=json.loads(BUDGET.read_text())
  if borrowed and current.get("early_field_probe_borrowed_spuma_slot"):
   current["early_field_probe_borrowed_spuma_slot"]=False;save(BUDGET,current)
  elif current.get("reason")==OWNER_REASON:save(BUDGET,original)
 case=pathlib.Path("/opt/openfoam-workspace/cases/native_stdpar_gpu_pilots_20261102/field_algebra_gate")
 if not case.exists():
  case.parent.mkdir(parents=True,exist_ok=True)
  shutil.copytree(R/"tutorials/incompressible/icoFoam/cavity/cavity",case)
 binary=P/"user/platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin/Test-nativeStdparFields"
 nsys=P/"nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys"
 output=P/"smoke/native_field_algebra_cuda_trace"
 log=command("native_field_gate_profile",[str(nsys),"profile","--trace=cuda,nvtx","--sample=none","--cpuctxsw=none","--stats=false","--force-overwrite=true","-o",str(output),str(binary),"-case",str(case)])
 text=log.read_text();result=json.loads(next(x for x in text.splitlines() if x.startswith('{"kind":"native Foam')))
 if not result["passed"] or result["mismatches"] or result["pointer_memory_type"]!=3:raise RuntimeError("Native Field arithmetic verification failed")
 if "memory pool : managed" not in text:raise RuntimeError("Native managed pool not enabled")
 d={"kind":"Actual native Foam Field arithmetic/Umpire integration smoke; not CFD or speed result","completed_utc":utc(),"binary":str(binary),"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"core_library_sha256":hashlib.sha256(LIB.read_bytes()).hexdigest(),"source":str(app/"Test-nativeStdparFields.C"),"source_sha256":hashlib.sha256((app/"Test-nativeStdparFields.C").read_bytes()).hexdigest(),"result":result,"managed_pool_log_verified":True,"trace_report":str(output)+".nsys-rep","trace_range":"NATIVE_STDPAR_FIELD_ALGEBRA","log":str(log),"launch_api_audit_pending":True,"no_production_change":True}
 save(P/"provenance/native_field_arithmetic_gate.json",d)
 status("native_field_arithmetic_gate_passed",evidence=str(P/"provenance/native_field_arithmetic_gate.json"))
if __name__=="__main__":
 try:main()
 except Exception as e:status("failed",error=str(e));raise
