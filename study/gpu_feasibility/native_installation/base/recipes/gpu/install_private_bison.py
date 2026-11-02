#!/usr/bin/env python3
"""Extract the missing Bison binary privately; do not install a system package."""
import hashlib,json,os,pathlib,subprocess,urllib.request
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
VERSION="2:3.8.2+dfsg-1ubuntu0.24.04.1"
def main():
 os.nice(15)
 r=subprocess.run(["apt-cache","show","bison="+VERSION],capture_output=True,text=True,check=True)
 fields={}
 for line in r.stdout.splitlines():
  if ":" in line and not line.startswith(" "):
   k,v=line.split(":",1);fields[k]=v.strip()
 assert fields["Architecture"]=="arm64"
 url="https://ports.ubuntu.com/ubuntu-ports/"+fields["Filename"]
 archive=P/"downloads"/pathlib.Path(fields["Filename"]).name
 if not archive.exists():
  with urllib.request.urlopen(url,timeout=60) as remote:archive.write_bytes(remote.read())
 sha=hashlib.sha256(archive.read_bytes()).hexdigest()
 if sha!=fields["SHA256"]:raise RuntimeError("APT metadata SHA256 mismatch")
 dest=P/"tools/bison"
 dest.mkdir(parents=True,exist_ok=True)
 subprocess.run(["dpkg-deb","-x",str(archive),str(dest)],check=True)
 result=subprocess.run([str(dest/"usr/bin/bison"),"--version"],capture_output=True,text=True,check=True)
 evidence={"observed_at_utc":datetime.now(timezone.utc).isoformat(),"name":"bison","version":VERSION,"source_url":url,"archive":str(archive),"bytes":archive.stat().st_size,"sha256":sha,"expected_sha256":fields["SHA256"],"prefix":str(dest),"method":"dpkg-deb -x only; no dpkg/apt installation or maintainer scripts","version_output":result.stdout.strip(),"runtime_data_environment":{"BISON_PKGDATADIR":str(dest/"usr/share/bison")}}
 (P/"provenance/bison.json").write_text(json.dumps(evidence,indent=2)+"\n")
 print(json.dumps(evidence),flush=True)
if __name__=="__main__":main()
