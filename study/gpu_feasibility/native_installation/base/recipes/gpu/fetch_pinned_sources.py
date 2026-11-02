#!/usr/bin/env python3
"""Fetch immutable official source archives and their provenance into one private prefix."""
import hashlib
import json
import os
import pathlib
import tarfile
import time
import urllib.request
from datetime import datetime, timezone

PREFIX=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
OPENFOAM_SHA="b239fea6e48922730477e218c44e8b6a8ab17ade"
THIRDPARTY_SHA="b70425b2611c23f26f24bdb97a5e6b48b99ffe0d"
ITEMS=[
 ("OpenFOAM-v2606","https://gitlab.com/api/v4/projects/openfoam%2Fcore%2Fopenfoam/repository/archive.tar.gz?sha="+OPENFOAM_SHA,OPENFOAM_SHA),
 ("ThirdParty-v2606","https://gitlab.com/api/v4/projects/openfoam%2Fcore%2FThirdParty-common/repository/archive.tar.gz?sha="+THIRDPARTY_SHA,THIRDPARTY_SHA),
 ("umpire-2025.03.0","https://github.com/LLNL/Umpire/releases/download/v2025.03.0/umpire-2025.03.0.tar.gz","v2025.03.0")
]
def utc():return datetime.now(timezone.utc).isoformat()
def write(path,data):path.write_text(json.dumps(data,indent=2)+"\n")
def main():
 os.nice(15)
 records=[]
 for name,url,pin in ITEMS:
  archive=PREFIX/"downloads"/(name+"-"+pin+".tar.gz")
  start=time.monotonic()
  if not archive.exists():
   part=archive.with_suffix(".part")
   with urllib.request.urlopen(url,timeout=90) as r,part.open("wb") as f:
    while b:=r.read(4*1024*1024):f.write(b)
   os.replace(part,archive)
  digest=hashlib.sha256()
  with archive.open("rb") as f:
   while b:=f.read(8*1024*1024):digest.update(b)
  destination=PREFIX/"source"/name
  marker=destination/".native_stdpar_source_pin"
  if not marker.exists():
   with tarfile.open(archive,"r:gz") as tf:
    members=tf.getmembers()
    roots={pathlib.PurePosixPath(m.name).parts[0] for m in members if m.name and m.name!="."}
    if len(roots)!=1:raise RuntimeError("Expected one source archive root: "+str(roots))
    original=PREFIX/"source"/next(iter(roots))
    if original.exists() or destination.exists():raise RuntimeError("Refusing to overlay existing unmarked source "+str(destination))
    tf.extractall(PREFIX/"source",filter="data")
   original.rename(destination)
   marker.write_text(pin+"\n")
  elif marker.read_text().strip()!=pin:raise RuntimeError("Source marker pin mismatch")
  records.append({"name":name,"pin":pin,"source_url":url,"archive":str(archive),"archive_bytes":archive.stat().st_size,"archive_sha256":digest.hexdigest(),"source_directory":str(destination),"elapsed_s":time.monotonic()-start})
  write(PREFIX/"provenance/source_archives.json",{"updated_utc":utc(),"sources":records})
  print(json.dumps(records[-1]),flush=True)
 print(json.dumps({"stage":"source_downloads_complete","updated_utc":utc(),"source_count":len(records)}),flush=True)
if __name__=="__main__":main()
