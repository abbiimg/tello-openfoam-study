#!/usr/bin/env python3
"""GCC trampoline limited to NVHPC's generated CUDA registration object."""
import hashlib,json,os,pathlib,shutil,sys,time
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
args=sys.argv[1:]
source=P/"nvhpc/Linux_aarch64/26.9/compilers/include_acc/linkstub.c"
output=args[args.index("-o")+1] if "-o" in args and args.index("-o")+1<len(args) else ""
changed=("-c" in args and str(source) in args and pathlib.Path(output).name.startswith("pgcudareg") and "-fpic" in args)
forward=["-fPIC" if changed and a=="-fpic" else a for a in args]
record={"time_ns":time.time_ns(),"pid":os.getpid(),"original_args":args,"forwarded_args":forward,"changed_only_generated_registration_pic":changed}
if changed:
 record["linkstub_source_sha256"]=hashlib.sha256(source.read_bytes()).hexdigest()
 for a in args:
  if a.startswith("-DREGFILE="):
   reg=pathlib.Path(a.split("=",1)[1].strip(chr(34)))
   if reg.is_file() and reg.stat().st_size<10000000:
    out=P/"provenance/stub_compilations";out.mkdir(exist_ok=True)
    saved=out/(str(os.getpid())+"_"+reg.name);shutil.copyfile(reg,saved)
    record.update(registration_source=str(saved),registration_source_sha256=hashlib.sha256(saved.read_bytes()).hexdigest())
with (P/"logs/stub_gcc_wrapper.jsonl").open("a") as f:f.write(json.dumps(record)+"\n")
os.execv("/usr/bin/gcc",["/usr/bin/gcc",*forward])
