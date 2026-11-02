#!/usr/bin/env python3
"""Backport exactly two pinned upstream Umpire operation files for CUDA13 API compatibility."""
import difflib,hashlib,json,pathlib,shutil,urllib.request
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
ROOT=P/"source/umpire-2025.03.0"
PIN="03c43d88537e4932b9d6dac8591abcd8c25a61ae"
FILES=["src/umpire/op/CudaAdviseOperation.cpp","src/umpire/op/CudaMemPrefetchOperation.cpp"]
def main():
 marker=P/"provenance/umpire_cuda13_backport.json"
 if marker.exists():
  d=json.loads(marker.read_text())
  for row in d["files"]:
   if hashlib.sha256((ROOT/row["path"]).read_bytes()).hexdigest()!=row["patched_sha256"]:raise RuntimeError("Backport contents changed")
  print(json.dumps(d));return
 provenance=P/"provenance/umpire_cuda13_upstream"
 provenance.mkdir(exist_ok=True)
 patches=[];rows=[]
 for name in FILES:
  local=ROOT/name;old=local.read_bytes()
  url="https://raw.githubusercontent.com/LLNL/Umpire/"+PIN+"/"+name
  with urllib.request.urlopen(url,timeout=45) as r:new=r.read()
  if b"#if CUDART_VERSION >= 13000" not in new:raise RuntimeError("Pinned upstream lacks expected CUDA13 compatibility block")
  (provenance/(local.name+".original")).write_bytes(old)
  (provenance/(local.name+".upstream")).write_bytes(new)
  patches.extend(difflib.unified_diff(old.decode().splitlines(keepends=True),new.decode().splitlines(keepends=True),fromfile="a/"+name,tofile="b/"+name))
  local.write_bytes(new)
  rows.append({"path":name,"upstream_url":url,"upstream_commit":PIN,"original_sha256":hashlib.sha256(old).hexdigest(),"patched_sha256":hashlib.sha256(new).hexdigest()})
 patch=P/"provenance/umpire_cuda13_backport.patch";patch.write_text("".join(patches))
 d={"kind":"Exact two-file backport of official LLNL CUDA13 memory-API compatibility into pinned Umpire2025.03.0","completed_utc":datetime.now(timezone.utc).isoformat(),"base_archive_sha256":"3a75ac48f65fba52e1e02b434bcd918c93eede59a39455465c64d1fe8dd6632f","upstream_commit":PIN,"files":rows,"patch":str(patch),"patch_sha256":hashlib.sha256(patch.read_bytes()).hexdigest(),"reason":"CUDA13 cudaMemAdvise/cudaMemPrefetchAsync changed device arguments to cudaMemLocation; official OpenFOAM config still selects Umpire2025.03.0.","allocator_algorithm_changes":False,"production_changes":False}
 marker.write_text(json.dumps(d,indent=2)+"\n")
 if (P/"logs/umpire_build.log").exists():
  shutil.copyfile(P/"logs/umpire_build.log",P/"logs/umpire_build_before_cuda13_backport.log")
 print(json.dumps(d),flush=True)
if __name__=="__main__":main()
