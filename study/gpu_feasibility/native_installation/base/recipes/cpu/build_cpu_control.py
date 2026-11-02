#!/usr/bin/env python3
"""Build the isolated same-pin serial CPU libraries/apps and bounded cavity smoke."""
import hashlib,json,os,pathlib,re,shlex,shutil,signal,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-cpu-control")
R=P/"source/OpenFOAM-v2606";WORK=pathlib.Path(__file__).resolve().parent
STATE=P/"build_progress.json";JOURNAL=P/"provenance/build_journal.json"
RECORDS=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else []
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2)+"\n");os.replace(tmp,path)
def available():return int(next(x.split()[1] for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))/1024/1024
def budget():return json.loads((WORK/"build_budget.json").read_text())
def status(stage,**extra):
 data={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),"available_memory_GiB":round(available(),2),**extra};save(STATE,data);print(json.dumps(data),flush=True)
def command(stage,args,timeout=21600):
 while True:
  config=budget();spare=available()-config["minimum_available_memory_gib"]
  jobs=min(4,config["max_jobs"],int(spare/config["memory_allowance_per_new_cpu_job_gib"]))
  if jobs>=1:break
  status("waiting_for_memory_reserve",next_stage=stage);time.sleep(10)
 args=[str(x).replace("@JOBS@",str(jobs)) for x in args];log=P/"logs"/(stage+".log")
 shell=". "+shlex.quote(str(P/"env.sh"))+"; export WM_NCOMPPROCS="+str(jobs)+"; exec "+shlex.join(args)
 status(stage,max_build_jobs=jobs,command=args,log=str(log));start=time.monotonic()
 with log.open("w") as stream:
  child=subprocess.Popen(["bash","--noprofile","--norc","-c",shell],stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,cwd=R)
  try:
   while child.poll() is None:
    if time.monotonic()-start>timeout:raise RuntimeError("Owned CPU stage timeout")
    if available()<4:raise RuntimeError("Emergency RAM floor; stop only this owned CPU stage")
    time.sleep(2)
  except BaseException:
   if child.poll() is None:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   raise
 record={"stage":stage,"command":args,"jobs":jobs,"return_code":child.returncode,"elapsed_s":time.monotonic()-start,"completed_utc":utc(),"log":str(log)}
 RECORDS.append(record);save(JOURNAL,RECORDS)
 if child.returncode:raise RuntimeError(stage+" failed; "+str(log))
 return log
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 configlog=command("environment_audit",["bash","--noprofile","--norc","-c","printf '%s\\n' \"WM_OPTIONS=$WM_OPTIONS\" \"WM_COMPILER=$WM_COMPILER\" \"WM_MPLIB=$WM_MPLIB\" \"WM_PRECISION_OPTION=$WM_PRECISION_OPTION\" \"WM_LABEL_SIZE=$WM_LABEL_SIZE\" \"WM_PROJECT_DIR=$WM_PROJECT_DIR\" \"FOAM_APPBIN=$FOAM_APPBIN\" \"LD_LIBRARY_PATH=$LD_LIBRARY_PATH\"; command -v g++; g++ --version"],timeout=60)
 text=configlog.read_text()
 if "WM_OPTIONS=linuxARM64GccDPInt32Opt" not in text:raise RuntimeError("CPU precision/label/platform mismatch")
 if "WM_COMPILER=Gcc" not in text or "WM_MPLIB=none" not in text:raise RuntimeError("CPU compiler/MPI mismatch")
 command("wmake_tools",[str(R/"wmake/src/Allmake"),"-j@JOBS@"])
 command("openfoam_base",[str(R/"src/Allwmake-base"),"-j@JOBS@"])
 for stage,path in [("finiteVolume","src/finiteVolume"),("blockMesh_library","src/mesh/blockMesh"),("extrudeModel","src/mesh/extrudeModel"),("dynamicMesh","src/dynamicMesh")]:command(stage+"_build",["wmake","-j@JOBS@","libso",str(R/path)])
 command("blockMesh_application_build",["wmake","-j@JOBS@",str(R/"applications/utilities/mesh/generation/blockMesh")])
 command("icoFoam_build",["wmake","-j@JOBS@",str(R/"applications/solvers/incompressible/icoFoam")])
 platform=R/"platforms/linuxARM64GccDPInt32Opt";binary=platform/"bin/icoFoam"
 deps=command("runtime_dependency_audit",["ldd",str(binary)],timeout=60).read_text()
 if re.search(r"lib(?:cuda|cudart|nv|acc|umpire)",deps,re.I):raise RuntimeError("Unexpected GPU/Umpire runtime dependency in CPU binary")
 case=pathlib.Path("/opt/openfoam-workspace/cases/native_cpu_control_pilots_20261102/cavity_native_cpu")
 if case.exists():raise RuntimeError("Refusing to overlay an existing CPU pilot case")
 case.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(R/"tutorials/incompressible/icoFoam/cavity/cavity",case)
 command("cavity_blockMesh",[str(platform/"bin/blockMesh"),"-case",str(case)],timeout=300)
 log=command("cavity_icoFoam",[str(binary),"-case",str(case)],timeout=600);text=log.read_text()
 times=[float(x) for x in re.findall(r"^Time = ([0-9.eE+-]+)",text,re.M)];continuity=[float(x) for x in re.findall(r"time step continuity errors\s*:\s*sum local =\s*([0-9.eE+-]+)",text)]
 if not times or abs(times[-1]-.5)>1e-10 or "\nEnd\n" not in text or not continuity or max(continuity)>1e-5:raise RuntimeError("CPU cavity completion/continuity gate failed")
 for field in ["U","p"]:
  if re.search(r"\b(?:nan|inf)\b",(case/"0.5"/field).read_text(),re.I):raise RuntimeError("Nonfinite CPU cavity field")
 bad=[]
 for file in (P/"logs").glob("*_build.log"):
  for line in file.read_text(errors="replace").splitlines():
   if line.startswith(("g++ ","gcc ")) and any(flag in line for flag in ["FOAM_OFFLOAD","-stdpar=gpu","-gpu="]):bad.append(line)
 if bad:raise RuntimeError("Unexpected offload flag in actual CPU compiler command")
 evidence={"kind":"Actual same-pin OpenCFD CPU companion installation/cavity smoke, not C29 or a speed benchmark","completed_utc":utc(),"source_pin":"b239fea6e48922730477e218c44e8b6a8ab17ade","platform":"linuxARM64GccDPInt32Opt","compiler":"GCC13.3.0","mpi":"none","case":str(case),"final_time":times[-1],"peak_local_continuity":max(continuity),"binary_sha256":hashlib.sha256(binary.read_bytes()).hexdigest(),"core_library_sha256":hashlib.sha256((platform/"lib/libOpenFOAM.so").read_bytes()).hexdigest(),"no_gpu_runtime_dependencies":True,"no_offload_compiler_flags_observed":True,"no_C29_candidate_built_or_run":True,"speedup_measured":False,"journal":str(JOURNAL)}
 save(P/"provenance/native_cpu_cavity_gate.json",evidence);status("native_cpu_control_cavity_gate_passed",evidence=str(P/"provenance/native_cpu_cavity_gate.json"))
if __name__=="__main__":
 try:main()
 except Exception as error:status("failed",error=str(error));raise
