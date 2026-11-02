#!/usr/bin/env python3
"""Retain and inspect only the failed native core link; never rebuild objects."""
import json,os,pathlib,shlex,subprocess,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
R=P/"source/OpenFOAM-v2606"
def main():
 os.nice(15)
 lines=(P/"logs/openfoam_base.log").read_text().splitlines()
 indices=[i for i,line in enumerate(lines) if line.startswith("nvc++ ") and " -shared " in line and "/src/OpenFOAM/" in line]
 if not indices:raise RuntimeError("No exact core shared link found")
 i=indices[-1];parts=[]
 while True:
  text=lines[i].rstrip();continued=text.endswith(chr(92))
  parts.append(text[:-1] if continued else text)
  if not continued:break
  i+=1
 args=shlex.split(" ".join(parts))
 (P/"provenance/core_failed_link_argv.json").write_text(json.dumps(args,indent=2)+"\n")
 if "-fPIC" not in args or "-shared" not in args or not args[-1].endswith("/libOpenFOAM.so"):raise RuntimeError("Unexpected link command")
 args.insert(1,"-v");args.insert(2,"-gpu=keep")
 log=P/"logs/core_verbose_relink.log"
 shell=". "+shlex.quote(str(P/"env.sh"))+"; exec "+shlex.join(args)
 start=time.monotonic()
 with log.open("w") as out:r=subprocess.run(["bash","--noprofile","--norc","-c",shell],cwd=R/"src/OpenFOAM",stdout=out,stderr=subprocess.STDOUT,timeout=600)
 d={"kind":"Link-only diagnostic; all628compiled objects preserved","completed_utc":datetime.now(timezone.utc).isoformat(),"return_code":r.returncode,"elapsed_s":time.monotonic()-start,"flags_added":["-v","-gpu=keep"],"has_fPIC":True,"log":str(log),"original_argv":str(P/"provenance/core_failed_link_argv.json")}
 (P/"provenance/core_verbose_relink.json").write_text(json.dumps(d,indent=2)+"\n")
 print(json.dumps(d),flush=True)
if __name__=="__main__":main()
