#!/usr/bin/env python3
"""Configure only the task-owned immutable source checkout for N1X managed memory."""
import difflib,hashlib,json,os,pathlib
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
R=P/"source/OpenFOAM-v2606"
SHA="b239fea6e48922730477e218c44e8b6a8ab17ade"
def main():
 if (R/".native_stdpar_source_pin").read_text().strip()!=SHA:raise RuntimeError("Unexpected source pin")
 rule=R/"wmake/rules/linuxARM64Nvidia-gpu/c++"
 old=rule.read_text()
 before="-stdpar=gpu -gpu=cc90,mem:unified,managed -DFOAM_OFFLOAD"
 after="-stdpar=gpu -gpu=cc121,mem:managed -DFOAM_OFFLOAD"
 if before in old:
  if old.count(before)!=1:raise RuntimeError("Compiler rule match must be unique")
  new=old.replace(before,after)
  rule.write_text(new)
  patch="".join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile="a/wmake/rules/linuxARM64Nvidia-gpu/c++",tofile="b/wmake/rules/linuxARM64Nvidia-gpu/c++"))
  (P/"provenance/n1x_managed_compiler_rule.patch").write_text(patch)
 elif old.count(after)!=1:raise RuntimeError("Unrecognized compiler rule")
 for d in ["tmp","runs","runtime-config","runtime-config/CudaCache","runtime/jobControl","user","smoke","logs","build"]:
  (P/d).mkdir(parents=True,exist_ok=True)
 env=f"""# Task-private environment. Source only for the selected build/test command.
export NVCOMPILERS='{P}/nvhpc'
export NVARCH=Linux_aarch64
export PATH='{P}/tools/stub-gcc-wrapper:{P}/nvhpc/Linux_aarch64/26.9/compilers/bin:{P}/nvhpc/Linux_aarch64/26.9/cuda/bin:{P}/tools/bison/usr/bin:/opt/openfoam-workspace/gpu-feasibility/pressure-offload/tools/cmake-3.31.7-linux-aarch64/bin:'"$PATH"
export BISON_PKGDATADIR='{P}/tools/bison/usr/share/bison'
export LD_LIBRARY_PATH='/usr/lib/wsl/lib:'"$LD_LIBRARY_PATH"
export TMPDIR='{P}/tmp'
export XDG_CONFIG_HOME='{P}/runtime-config'
export CUDA_CACHE_PATH='{P}/runtime-config/CudaCache'
export FOAM_CONFIG_MODE=o
. '{R}/etc/bashrc' WM_COMPILER=Nvidia-gpu WM_MPLIB=none
export WM_NCOMPPROCS=4
export OMP_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
export WM_PROJECT_USER_DIR='{P}/user'
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR='{P}/runtime/jobControl'
export FOAM_RUN='{P}/runs'
export FOAM_MEMORY_POOL='managed; size=64; incr=64'
export PATH="$FOAM_USER_APPBIN:$PATH"
"""
 (P/"env.sh").write_text(env)
 record={"updated_utc":datetime.now(timezone.utc).isoformat(),"source_pin":SHA,"rule":str(rule),"rule_sha256":hashlib.sha256(rule.read_bytes()).hexdigest(),"compiler_device_flags":after,"environment":str(P/"env.sh"),"max_build_jobs":4,"minimum_available_memory_gib":20,"required_build_nice":15,"mpi":"none for this single-device smoke build","umpire_initial_pool_mb":64,"no_global_path_or_profile_change":True,"no_production_change":True}
 (P/"provenance/private_configuration.json").write_text(json.dumps(record,indent=2)+"\n")
 print(json.dumps(record),flush=True)
if __name__=="__main__":main()
