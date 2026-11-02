#!/usr/bin/env python3
"""Build the minimal native GPU stack after its compiler gate; run an isolated tutorial."""
import csv,hashlib,io,json,math,os,pathlib,re,shlex,shutil,signal,subprocess,time
from datetime import datetime,timezone

P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
R=P/"source/OpenFOAM-v2606"
T=P/"source/ThirdParty-v2606"
SDK=P/"nvhpc/Linux_aarch64/26.9"
CMAKE=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/pressure-offload/tools/cmake-3.31.7-linux-aarch64/bin/cmake")
UMP=T/"platforms/linuxARM64Nvidia-gpu/umpire-2025.03.0"
PLATFORM=R/"platforms/linuxARM64Nvidia-gpuDPInt32Opt"
STATE=P/"build_progress.json"
WORK=pathlib.Path("/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/native_stdpar_install")
JOURNAL=P/"provenance/minimal_build_journal.json"
RECORDS=json.loads(JOURNAL.read_text()) if JOURNAL.exists() else []
def utc():return datetime.now(timezone.utc).isoformat()
def build_jobs():return min(4,max(1,int(json.loads((WORK/"build_budget.json").read_text())["max_jobs"])))
def write(path,data):
 tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2)+"\n");os.replace(tmp,path)
def status(stage,**extra):
 d={"stage":stage,"updated_utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),"max_build_jobs":build_jobs(),**extra};write(STATE,d);print(json.dumps(d),flush=True)
def available_kb():
 return int(next(line.split()[1] for line in pathlib.Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemAvailable:")))
def command(name,args,cwd=None,timeout=21600):
 jobs=build_jobs()
 args=[str(a).replace("@JOBS@",str(jobs)) for a in args]
 while available_kb()<20*1024*1024:
  status("waiting_for_20GiB_available_memory",next_stage=name,available_kb=available_kb());time.sleep(10)
 shell=". "+shlex.quote(str(P/"env.sh"))+"; export WM_NCOMPPROCS="+str(jobs)+"; exec "+shlex.join([str(a) for a in args])
 log=P/"logs"/(name+".log")
 status(name,command=args,log=str(log),available_kb=available_kb())
 started=time.monotonic()
 with log.open("w") as out:
  child=subprocess.Popen(["bash","--noprofile","--norc","-c",shell],cwd=cwd,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  try:
   while child.poll() is None:
    if time.monotonic()-started>timeout:raise RuntimeError("Stage timeout")
    if available_kb()<4*1024*1024:raise RuntimeError("Resource gate: available RAM below4GiB; terminating only this owned build group")
    time.sleep(2)
  except BaseException:
   if child.poll() is None:
    os.killpg(child.pid,signal.SIGTERM)
    try:child.wait(timeout=15)
    except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait()
   raise
 record={"stage":name,"command":args,"return_code":child.returncode,"elapsed_s":time.monotonic()-started,"completed_utc":utc(),"log":str(log)}
 RECORDS.append(record);write(P/"provenance/minimal_build_journal.json",RECORDS)
 if child.returncode:raise RuntimeError(name+" exited "+str(child.returncode)+"; see "+str(log))
 return log
def require(paths):
 absent=[str(p) for p in paths if not p.is_file() or p.stat().st_size==0]
 if absent:raise RuntimeError("Expected stage outputs missing: "+repr(absent))
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 status("waiting_for_managed_stdpar_device_execution_gate")
 while not (P/"provenance/stdpar_device_marker_gate.json").exists():
  if (P/"install_progress.json").exists() and json.loads((P/"install_progress.json").read_text()).get("stage")=="failed":raise RuntimeError("SDK/compiler gate failed")
  if (P/"marker_progress.json").exists() and json.loads((P/"marker_progress.json").read_text()).get("stage")=="failed":raise RuntimeError("Device execution marker failed")
  time.sleep(5)
 gate=json.loads((P/"provenance/stdpar_compiler_gate.json").read_text())
 if not gate["result"]["exact_element_check"]:raise RuntimeError("Compiler arithmetic gate did not pass")
 source=P/"source/umpire-2025.03.0"
 build=P/"build/umpire-2025.03.0-cuda133"
 config=[str(CMAKE),"-Ucamp_DIR","-Ufmt_DIR","-S",str(source),"-B",str(build),
 "-DCMAKE_BUILD_TYPE=Release","-DCMAKE_INSTALL_PREFIX="+str(UMP),
 "-DCMAKE_INSTALL_LIBDIR="+str(UMP/"lib"),"-DCMAKE_POSITION_INDEPENDENT_CODE=ON",
 "-DCMAKE_C_COMPILER=/usr/bin/gcc","-DCMAKE_CXX_COMPILER=/usr/bin/g++",
 "-DCMAKE_CUDA_COMPILER="+str(SDK/"cuda/13.3/bin/nvcc"),"-DCUDA_TOOLKIT_ROOT_DIR="+str(SDK/"cuda/13.3"),"-DCMAKE_CUDA_HOST_COMPILER=/usr/bin/g++",
 "-DCMAKE_CUDA_ARCHITECTURES=121","-DBLT_CXX_STD=c++17",
 "-DENABLE_CUDA=ON","-DUMPIRE_ENABLE_CUDA=ON","-DBUILD_SHARED_LIBS=OFF",
 "-DENABLE_MPI=OFF","-DENABLE_OPENMP=OFF","-DENABLE_TESTS=OFF","-DCAMP_ENABLE_TESTS=OFF",
 "-DENABLE_EXAMPLES=OFF","-DENABLE_BENCHMARKS=OFF","-DENABLE_FORTRAN=OFF",
 "-DENABLE_DOCS=OFF","-DENABLE_DOXYGEN=OFF","-DENABLE_ASTYLE=OFF",
 "-DUMPIRE_ENABLE_NUMA=OFF","-DUMPIRE_ENABLE_TOOLS=OFF"]
 command("umpire_configure",config)
 command("umpire_build",[str(CMAKE),"--build",str(build),"--parallel","@JOBS@"])
 command("umpire_install",[str(CMAKE),"--install",str(build)])
 require([UMP/"include/umpire/Umpire.hpp",UMP/"lib/libumpire.a",UMP/"lib/libcamp.a"])
 cache=(build/"CMakeCache.txt").read_text()
 if "ENABLE_CUDA:BOOL=ON" not in cache or "UMPIRE_ENABLE_CUDA:BOOL=ON" not in cache:raise RuntimeError("Umpire CUDA options not enabled in actual cache")
 command("wmake_tools",[str(R/"wmake/src/Allmake"),"-j@JOBS@"],cwd=R)
 command("openfoam_base",[str(R/"src/Allwmake-base"),"-j@JOBS@"],cwd=R)
 lib=PLATFORM/"lib"
 require([lib/"libOpenFOAM.so",lib/"libmeshTools.so",lib/"libfileFormats.so",lib/"libsurfMesh.so",lib/"libOSspecific.o",lib/"dummy/libPstream.so"])
 command("native_std_execution_build",["wmake","-j@JOBS@",str(R/"applications/test/std_execution")],cwd=R)
 for name,path in [("finiteVolume","src/finiteVolume"),("blockMesh_library","src/mesh/blockMesh"),("extrudeModel","src/mesh/extrudeModel"),("dynamicMesh","src/dynamicMesh")]:
  command(name+"_build",["wmake","-j@JOBS@","libso",str(R/path)],cwd=R)
 command("blockMesh_application_build",["wmake","-j@JOBS@",str(R/"applications/utilities/mesh/generation/blockMesh")],cwd=R)
 command("icoFoam_build",["wmake","-j@JOBS@",str(R/"applications/solvers/incompressible/icoFoam")],cwd=R)
 require([PLATFORM/"bin/blockMesh",PLATFORM/"bin/icoFoam"])
 case=pathlib.Path("/opt/openfoam-workspace/cases/native_stdpar_gpu_pilots_20261102/cavity_native_gpu")
 source_case=R/"tutorials/incompressible/icoFoam/cavity/cavity"
 if case.exists():raise RuntimeError("Refusing to overlay an existing tutorial case")
 case.parent.mkdir(parents=True,exist_ok=True)
 shutil.copytree(source_case,case)
 allrun=case/"Allrun"
 allrun.write_text("#!/bin/bash\nset -eo pipefail\ncd -- \"$(dirname -- \"$0\")\"\n. "+shlex.quote(str(P/"env.sh"))+"\n"+shlex.quote(str(PLATFORM/"bin/blockMesh"))+" > log.blockMesh 2>&1\n"+shlex.quote(str(PLATFORM/"bin/icoFoam"))+" > log.icoFoam 2>&1\n")
 allrun.chmod(0o755)
 command("cavity_blockMesh",[str(PLATFORM/"bin/blockMesh"),"-case",str(case)],timeout=300)
 user_bin=P/"user/platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin"
 # The upstream application is a long timing benchmark, not a bounded
 # correctness test. Its reference-captured stack object also elicited
 # NVHPC's no_device_stack warning under the selected managed mode.
 # Keep its compiled source/binary, but do not run it as an acceptance gate.
 benchmark_source=R/"applications/test/std_execution/Test-std_execution.C"
 benchmark={"source":str(benchmark_source),"source_sha256":hashlib.sha256(benchmark_source.read_bytes()).hexdigest(),"binary":str(user_bin/"Test-std_execution"),"compiled":True,"executed":False,"reason":"Upstream timing benchmark: ten million cells with1000 sequential and1000 parallel interpolation repeats; compiler reports reference-captured local N likely unsafe on device in managed mode. No runtime failure is claimed.","replacement_correctness_gate":str(P/"provenance/native_field_arithmetic_gate.json"),"replacement_gpu_execution_gate":str(P/"provenance/native_field_gpu_api_gate.json")}
 write(P/"provenance/native_std_execution_benchmark_review.json",benchmark)
 solver_log=command("cavity_icoFoam",[str(PLATFORM/"bin/icoFoam"),"-case",str(case)],timeout=600)
 text=solver_log.read_text()
 times=[float(v) for v in re.findall(r"^Time = ([0-9.eE+-]+)",text,re.M)]
 local=[float(v) for v in re.findall(r"time step continuity errors\s*:\s*sum local =\s*([0-9.eE+-]+)",text)]
 if not times or abs(times[-1]-.5)>1e-10 or "\nEnd\n" not in text:raise RuntimeError("Tutorial did not reach standard endTime0.5 with End")
 if not local or max(local)>1e-5:raise RuntimeError("Tutorial continuity smoke gate failed")
 final=case/"0.5"
 for field in ["U","p"]:
  fieldtext=(final/field).read_text()
  if re.search(r"\b(?:nan|inf)\b",fieldtext,re.I):raise RuntimeError("Non-finite final "+field)
 if "memory pool : managed" not in text:raise RuntimeError("Actual application did not enable managed memory pool")
 trace=gate.get("trace",{})
 kernel_trace={"attempted":False,"verified":False}
 if trace.get("nsys") and "error" not in trace:
  kernel_trace["attempted"]=True
  try:
   nsys=trace["nsys"]
   profile=P/"smoke/cavity_icoFoam_cuda_trace"
   command("cavity_icoFoam_cuda_trace",[nsys,"profile","--trace=cuda","--sample=none","--cpuctxsw=none","--stats=true","--force-overwrite=true","-o",str(profile),str(PLATFORM/"bin/icoFoam"),"-case",str(case)],timeout=600)
   stats=command("cavity_cuda_kernel_stats",[nsys,"stats","--report","cuda_gpu_kern_sum","--format","csv",str(profile)+".nsys-rep"],timeout=180)
   kernel_trace.update(stats_log=str(stats),report=str(profile)+".nsys-rep",note="Inspect actual CSV kernel rows before claiming execution proof")
  except Exception as e:kernel_trace["error"]=str(e)
 evidence={"kind":"Actual minimal native GPU OpenFOAM installation/tutorial smoke; not the rotor study","completed_utc":utc(),"openfoam_pin":"b239fea6e48922730477e218c44e8b6a8ab17ade","thirdparty_pin":"b70425b2611c23f26f24bdb97a5e6b48b99ffe0d","api_info":(R/"META-INFO/api-info").read_text(),"compiler_flags":"-stdpar=gpu -gpu=cc121,mem:managed -DFOAM_OFFLOAD","umpire_prefix":str(UMP),"umpire_library_sha256":hashlib.sha256((UMP/"lib/libumpire.a").read_bytes()).hexdigest(),"openfoam_library_sha256":hashlib.sha256((lib/"libOpenFOAM.so").read_bytes()).hexdigest(),"icoFoam_sha256":hashlib.sha256((PLATFORM/"bin/icoFoam").read_bytes()).hexdigest(),"tutorial_case":str(case),"tutorial_cell_count_expected":400,"tutorial_final_time":times[-1],"tutorial_peak_local_continuity":max(local),"managed_pool_log_verified":True,"kernel_trace":kernel_trace,"no_actuator_port":True,"no_production_backend_change":True,"speedup_measured":False,"journal":str(P/"provenance/minimal_build_journal.json")}
 write(P/"provenance/native_openfoam_tutorial_gate.json",evidence)
 status("minimal_native_openfoam_tutorial_gate_passed",evidence=str(P/"provenance/native_openfoam_tutorial_gate.json"),kernel_trace=kernel_trace)
if __name__=="__main__":
 try:main()
 except Exception as e:status("failed",error=str(e));raise
