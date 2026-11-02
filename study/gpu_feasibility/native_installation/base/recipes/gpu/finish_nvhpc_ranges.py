#!/usr/bin/env python3
"""Finish the owned SDK download using four HTTP ranges; verify complete archive."""
import hashlib,json,os,pathlib,threading,time,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
NAME="nvhpc_2026_269_Linux_aarch64_cuda_13.3.tar.gz"
URL="https://developer.download.nvidia.com/hpc-sdk/26.9/"+NAME
SUMURL="https://developer.download.nvidia.com/hpc-sdk/26.9/md5sum.txt"
TOTAL=6904150881
def utc():return datetime.now(timezone.utc).isoformat()
def write(data):
 t=P/"download_progress.json.tmp";t.write_text(json.dumps(data,indent=2)+"\n");os.replace(t,P/"download_progress.json")
def main():
 os.nice(15)
 archive=P/"downloads"/NAME
 base=archive.with_suffix(archive.suffix+".part")
 start=time.monotonic()
 initial=base.stat().st_size
 manifest=P/"provenance/download_ranges.json"
 if manifest.exists():
  state=json.loads(manifest.read_text())
  if initial!=state["initial_prefix_bytes"]:raise RuntimeError("Initial prefix changed")
  ranges=state["ranges"]
 else:
  remaining=TOTAL-initial
  ranges=[]
  for i in range(4):
   a=initial+remaining*i//4;b=initial+remaining*(i+1)//4-1
   ranges.append({"index":i,"start":a,"end":b,"path":str(P/"downloads"/(NAME+".range"+str(i)))})
  manifest.write_text(json.dumps({"initial_prefix_bytes":initial,"total_bytes":TOTAL,"ranges":ranges},indent=2)+"\n")
 lock=threading.Lock()
 counts={r["index"]:pathlib.Path(r["path"]).stat().st_size if pathlib.Path(r["path"]).exists() else 0 for r in ranges}
 def download(r):
  target=pathlib.Path(r["path"]);expected=r["end"]-r["start"]+1
  for attempt in range(4):
   offset=target.stat().st_size if target.exists() else 0
   if offset==expected:return
   if offset>expected:raise RuntimeError("Oversized range")
   try:
    req=urllib.request.Request(URL,headers={"Range":"bytes="+str(r["start"]+offset)+"-"+str(r["end"])})
    with urllib.request.urlopen(req,timeout=90) as remote,target.open("ab") as f:
     if remote.status!=206:raise RuntimeError("Range response must be 206")
     expected_header="bytes "+str(r["start"]+offset)+"-"+str(r["end"])+"/"+str(TOTAL)
     if remote.headers.get("Content-Range")!=expected_header:raise RuntimeError("Wrong Content-Range "+str(remote.headers.get("Content-Range")))
     while chunk:=remote.read(4*1024*1024):
      f.write(chunk);offset+=len(chunk)
      with lock:counts[r["index"]]=offset
    if offset!=expected:raise RuntimeError("Incomplete range")
    return
   except Exception:
    if attempt==3:raise
    time.sleep(2)
 with ThreadPoolExecutor(max_workers=4) as executor:
  jobs=[executor.submit(download,r) for r in ranges]
  while not all(j.done() for j in jobs):
   with lock:done=initial+sum(counts.values())
   write({"stage":"downloading_four_ranges","updated_utc":utc(),"url":URL,"downloaded_bytes":done,"total_bytes":TOTAL,"elapsed_s":time.monotonic()-start,"preserved_prefix_bytes":initial,"nice":os.getpriority(os.PRIO_PROCESS,0)})
   time.sleep(5)
  for job in jobs:job.result()
 merged=P/"downloads"/(NAME+".complete")
 sha,md5,count=hashlib.sha256(),hashlib.md5(),0
 write({"stage":"merging_verifying","updated_utc":utc(),"downloaded_bytes":TOTAL,"total_bytes":TOTAL,"nice":os.getpriority(os.PRIO_PROCESS,0)})
 with merged.open("wb") as out:
  for chunkfile in [base]+[pathlib.Path(r["path"]) for r in ranges]:
   with chunkfile.open("rb") as f:
    while b:=f.read(8*1024*1024):
     out.write(b);sha.update(b);md5.update(b);count+=len(b)
 checksum_bytes=(P/"provenance/nvidia-official-md5sum.txt").read_bytes()
 expected=[x.split()[0].lower() for x in checksum_bytes.decode().splitlines() if x.split() and x.split()[-1].lstrip("*").split("/")[-1]==NAME]
 if count!=TOTAL or len(expected)!=1 or md5.hexdigest()!=expected[0]:raise RuntimeError("Full archive verification failed")
 os.replace(merged,archive)
 result={"stage":"download_verified","completed_utc":utc(),"url":URL,"archive":str(archive),"bytes":count,"sha256":sha.hexdigest(),"md5":md5.hexdigest(),"official_md5":expected[0],"official_md5_url":SUMURL,"official_checksum_document_sha256":hashlib.sha256(checksum_bytes).hexdigest(),"elapsed_s_four_range_resume":time.monotonic()-start,"preserved_prefix_bytes":initial,"nice":os.getpriority(os.PRIO_PROCESS,0),"no_driver_or_system_package_changes":True}
 (P/"provenance/nvhpc_archive.json").write_text(json.dumps(result,indent=2)+"\n");write(result)
 print(json.dumps(result),flush=True)
if __name__=="__main__":main()
