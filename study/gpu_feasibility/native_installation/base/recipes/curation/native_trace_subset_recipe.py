#!/usr/bin/env python3
"""Copy only review-required CUDA launch/sync, one named NVTX and one process row."""
import hashlib,json,pathlib,re,sqlite3
from datetime import datetime,timezone
LAUNCH=["cudaLaunchKernel","cuLaunchKernel","cudaGraphLaunch","cuGraphLaunch","cudaLaunchCooperativeKernel","cuLaunchCooperativeKernel"]
SYNC=["cudaDeviceSynchronize","cudaStreamSynchronize","cuCtxSynchronize","cuStreamSynchronize"]
def digest(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def extract(source,report,destination,*,global_tid=None,range_name=None,expected_process_path=None):
 source=pathlib.Path(source);report=pathlib.Path(report);destination=pathlib.Path(destination)
 if destination.exists():raise RuntimeError("Refusing to overwrite a review subset")
 destination.parent.mkdir(parents=True,exist_ok=True)
 original_sha=digest(source);report_sha=digest(report)
 raw=sqlite3.connect("file:"+str(source)+"?mode=ro",uri=True);raw.row_factory=sqlite3.Row
 names=[x[0] for x in raw.execute("select name from sqlite_master where type='table'")]
 api_tables=[]
 for name in names:
  if not name.startswith("CUPTI_ACTIVITY_KIND_"):continue
  cols={x[1] for x in raw.execute('pragma table_info("'+name+'")')}
  if {"start","end","globalTid","nameId","returnValue"}.issubset(cols):api_tables.append(name)
 if global_tid is None:
  tids=set()
  for table in api_tables:
   for row in raw.execute('select a.globalTid,s.value from "'+table+'" a join StringIds s on a.nameId=s.id'):
    if any(x in row[1] for x in LAUNCH):tids.add(row[0])
  if len(tids)!=1:raise RuntimeError("Expected one actual launch thread for this marker")
  global_tid=tids.pop()
 pid=(global_tid//0x1000000)%0x1000000
 out=sqlite3.connect(destination);counts={};identifiers=set();launch=sync=failed=0
 def transfer(table,rows):
  schema=raw.execute("select sql from sqlite_master where type='table' and name=?",(table,)).fetchone()[0];out.execute(schema)
  if rows:
   columns=list(rows[0]);marks=",".join("?" for _ in columns)
   out.executemany('insert into "'+table+'" ('+",".join('"'+x+'"' for x in columns)+") values ("+marks+")",[tuple(r[x] for x in columns) for r in rows])
  counts[table]=len(rows)
 for table in sorted(api_tables):
  rows=[]
  query='select a.*,s.value as safe_name from "'+table+'" a join StringIds s on a.nameId=s.id where a.globalTid=? order by a.start,a.end,a.nameId'
  for row in raw.execute(query,(global_tid,)):
   is_launch=any(x in row["safe_name"] for x in LAUNCH);is_sync=any(x in row["safe_name"] for x in SYNC)
   if not (is_launch or is_sync):continue
   if not re.fullmatch(r"[A-Za-z0-9_]+",row["safe_name"]):raise RuntimeError("Unexpected API string")
   item=dict(row);item.pop("safe_name");rows.append(item);identifiers.add(row["nameId"])
   launch+=int(is_launch);sync+=int(is_sync);failed+=int(row["returnValue"]!=0)
  if rows:transfer(table,rows)
 ranges=[]
 if range_name is not None:
  ranges=[dict(x) for x in raw.execute("select * from NVTX_EVENTS where globalTid=? and (text=? or textId in(select id from StringIds where value=?)) and end is not null",(global_tid,range_name,range_name))]
  if len(ranges)!=1:raise RuntimeError("Expected one complete selected NVTX range")
  if any(ranges[0].get(x) is not None for x in ["jsonText","binaryData"]):raise RuntimeError("Unexpected NVTX payload")
  if ranges[0].get("text") not in (None,range_name):raise RuntimeError("Unexpected NVTX text")
  if ranges[0].get("textId") is not None:identifiers.add(ranges[0]["textId"])
 if "NVTX_EVENTS" in names:transfer("NVTX_EVENTS",ranges)
 processes=[dict(x) for x in raw.execute("select * from PROCESSES where pid=? and globalPid=?",(pid,global_tid-global_tid%0x1000000))]
 if len(processes)!=1:raise RuntimeError("Expected exactly one selected actual process row")
 process_name=processes[0]["name"]
 if expected_process_path is not None:
  expected_process_path=str(expected_process_path)
  if not expected_process_path.startswith("/opt/openfoam-workspace/gpu-feasibility/native-stdpar/") or not re.fullmatch(r"/[A-Za-z0-9_./-]+",expected_process_path) or ".." in pathlib.PurePosixPath(expected_process_path).parts:raise RuntimeError("Unexpected owned executable path")
  if process_name not in (expected_process_path,pathlib.Path(expected_process_path).name):raise RuntimeError("Actual process row differs from supplied exact owned executable path")
 elif not re.fullmatch(r"[A-Za-z0-9_.-]+",process_name):raise RuntimeError("Unexpected actual process row")
 transfer("PROCESSES",processes)
 strings=[dict(raw.execute("select * from StringIds where id=?",(i,)).fetchone()) for i in sorted(identifiers)]
 for row in strings:
  if not (row["value"]==range_name or (re.fullmatch(r"[A-Za-z0-9_]+",row["value"]) and any(x in row["value"] for x in LAUNCH+SYNC))):raise RuntimeError("Non-required StringIds value")
 transfer("StringIds",strings)
 info={"kind":"Lossless minimal subset for the named actual-thread CUDA review predicates","extracted_utc":datetime.now(timezone.utc).isoformat(),"source_private_sqlite":str(source),"source_sqlite_sha256":original_sha,"source_sqlite_bytes":source.stat().st_size,"source_private_report":str(report),"source_report_sha256":report_sha,"source_report_bytes":report.stat().st_size,"globalTid":global_tid,"decoded_pid":pid,"range_name":range_name,"row_counts":counts,"successful_launch_rows":launch-failed if failed else launch,"launch_rows":launch,"sync_rows":sync,"failed_launch_or_sync_rows":failed,"predicate":"All launch/sync rows for the actual solver globalTid across ALL retained trace timestamps, so post-window launch absence remains reviewable; exactly one named complete range when requested and one actual process row","StringIds_policy":"Only referenced safe API names and the selected static range name","process_policy":"Exact actual process row retained losslessly; basename or supplied exact owned executable path only","expected_process_path":expected_process_path,"environment_policy":"No environment tables or unreferenced StringIds queried/copied. Full originals are only hashed as bytes and remain private.","no_kernel_timeline_or_speed_claim":True,"originals_unchanged":True}
 out.execute("create table REVIEW_SUBSET_PROVENANCE (json TEXT NOT NULL)");out.execute("insert into REVIEW_SUBSET_PROVENANCE values (?)",(json.dumps(info),));out.commit()
 if out.execute("pragma integrity_check").fetchone()[0]!="ok":raise RuntimeError("Subset SQLite integrity failure")
 out.close();raw.close()
 if digest(source)!=original_sha or digest(report)!=report_sha:raise RuntimeError("Private original changed during extraction")
 info.update(review_subset=str(destination),review_subset_sha256=digest(destination),extraction_recipe_sha256=digest(__file__))
 destination.with_suffix(".json").write_text(json.dumps(info,indent=2)+"\n")
 return info
