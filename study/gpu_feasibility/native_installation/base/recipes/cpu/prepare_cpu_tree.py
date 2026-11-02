#!/usr/bin/env python3
"""Make a pristine, checksum-verified same-pin CPU tree without touching GPU sources."""
import hashlib,json,os,pathlib,shutil,subprocess,tarfile
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-cpu-control")
G=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
PINS={"OpenFOAM-v2606":("b239fea6e48922730477e218c44e8b6a8ab17ade","f99f550f3944c3de0b4d7959fed4bd0ccb438d38eff6bbcfa731409528b64c0c"),"ThirdParty-v2606":("b70425b2611c23f26f24bdb97a5e6b48b99ffe0d","1a71c738a5bba2639f2b17e17b426f44ca75c549da6cadef1fe8fa590c5c3e03")}
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 for name in ["downloads","source","logs","provenance","tmp","runtime","runtime/jobControl","runtime-config","user","runs"]:(P/name).mkdir(parents=True,exist_ok=True)
 upstream=json.loads((G/"provenance/source_archives.json").read_text())["sources"];records=[]
 for name,(pin,expected) in PINS.items():
  original=next(x for x in upstream if x["name"]==name)
  if original["pin"]!=pin or original["archive_sha256"]!=expected:raise RuntimeError("Source provenance mismatch")
  src=pathlib.Path(original["archive"])
  if sha(src)!=expected:raise RuntimeError("Existing immutable source archive checksum mismatch")
  archive=P/"downloads"/src.name
  if not archive.exists():shutil.copyfile(src,archive)
  if sha(archive)!=expected:raise RuntimeError("Private archive checksum mismatch")
  dest=P/"source"/name;marker=dest/".native_cpu_source_pin"
  if not marker.exists():
   if dest.exists():raise RuntimeError("Refusing to overlay unmarked source")
   with tarfile.open(archive,"r:gz") as tf:
    members=tf.getmembers();roots={pathlib.PurePosixPath(x.name).parts[0] for x in members if x.name and x.name!="."}
    if len(roots)!=1:raise RuntimeError("Unexpected archive roots")
    original_root=P/"source"/next(iter(roots))
    if original_root.exists():raise RuntimeError("Refusing to overlay extracted source root")
    tf.extractall(P/"source",filter="data")
   original_root.rename(dest);marker.write_text(pin+"\n")
  elif marker.read_text().strip()!=pin:raise RuntimeError("CPU source pin mismatch")
  records.append({"name":name,"pin":pin,"source_url":original["source_url"],"archive":str(archive),"archive_bytes":archive.stat().st_size,"archive_sha256":expected,"source_directory":str(dest),"separate_pristine_extraction":True})
 bison=json.loads((G/"provenance/bison.json").read_text());deb_src=pathlib.Path(bison["archive"]);deb=P/"downloads"/deb_src.name
 if sha(deb_src)!=bison["sha256"]:raise RuntimeError("Bison archive checksum mismatch")
 if not deb.exists():shutil.copyfile(deb_src,deb)
 if sha(deb)!=bison["sha256"]:raise RuntimeError("CPU Bison archive checksum mismatch")
 bison_root=P/"tools/bison";bison_root.mkdir(parents=True,exist_ok=True)
 subprocess.run(["dpkg-deb","-x",str(deb),str(bison_root)],check=True)
 r=P/"source/OpenFOAM-v2606"
 env=f"""# Private same-pin CPU control; source only for this build/run command.
export PATH='{P}/tools/bison/usr/bin:/usr/bin:/bin'
export LD_LIBRARY_PATH=''
unset CPATH CPLUS_INCLUDE_PATH C_INCLUDE_PATH LIBRARY_PATH NVCOMPILERS NVARCH CUDA_HOME CUDA_PATH CUDA_ROOT NVHPC_CUDA_HOME FOAM_MEMORY_POOL
export BISON_PKGDATADIR='{P}/tools/bison/usr/share/bison'
export TMPDIR='{P}/tmp'
export XDG_CONFIG_HOME='{P}/runtime-config'
export FOAM_CONFIG_MODE=o
. '{r}/etc/bashrc' WM_COMPILER=Gcc WM_COMPILER_TYPE=system WM_MPLIB=none WM_PRECISION_OPTION=DP WM_LABEL_SIZE=32 WM_COMPILE_OPTION=Opt
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
unset FOAM_MEMORY_POOL
export WM_PROJECT_USER_DIR='{P}/user'
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR='{P}/runtime/jobControl'
export FOAM_RUN='{P}/runs'
export PATH="$FOAM_USER_APPBIN:$PATH"
"""
 (P/"env.sh").write_text(env)
 evidence={"prepared_utc":datetime.now(timezone.utc).isoformat(),"sources":records,"compiler":"system GCC/G++13.3.0","settings":{"WM_COMPILER":"Gcc","WM_COMPILER_TYPE":"system","WM_MPLIB":"none","WM_PRECISION_OPTION":"DP","WM_LABEL_SIZE":32,"WM_COMPILE_OPTION":"Opt","OMP_NUM_THREADS":1},"environment":str(P/"env.sh"),"environment_sha256":sha(P/"env.sh"),"bison_archive":str(deb),"bison_sha256":bison["sha256"],"source_edits":[],"no_shared_generated_files":True,"no_cuda_or_foam_offload_flags":True,"no_global_changes":True}
 (P/"provenance/source_and_environment.json").write_text(json.dumps(evidence,indent=2)+"\n")
 print(json.dumps(evidence,indent=2))
if __name__=="__main__":main()
