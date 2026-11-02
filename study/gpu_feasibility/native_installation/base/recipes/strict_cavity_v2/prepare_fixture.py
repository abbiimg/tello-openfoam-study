#!/usr/bin/env python3
"""Prepare the proposed common strict fixture only after root approves its protocol."""
import hashlib,json,pathlib,re,shutil
WORK=pathlib.Path(__file__).resolve().parent
def replace(text,key,value):
 pattern=r"(?m)^([ \t]*"+re.escape(key)+r"[ \t]+)[^;\n]+;"
 text,n=re.subn(pattern,lambda m:m[1]+str(value)+";",text)
 if n!=1:raise ValueError("Expected one control entry: "+key)
 return text
def main():
 protocol=json.loads((WORK/"protocol.json").read_text())
 approval=json.loads((WORK/"root_approval.json").read_text())
 if not approval.get("approved") or approval["protocol_sha256"]!=hashlib.sha256((WORK/"protocol.json").read_bytes()).hexdigest():raise RuntimeError("Root approval does not match frozen protocol")
 template=pathlib.Path(protocol["template"])
 actual={str(x.relative_to(template)):hashlib.sha256(x.read_bytes()).hexdigest() for x in template.rglob("*") if x.is_file()}
 if actual!=protocol["template_input_sha256"]:raise RuntimeError("Pinned template input hashes changed")
 root=pathlib.Path(protocol["proposed_case_root"]);fixture=root/"fixture"
 if fixture.exists():raise RuntimeError("Refusing to overlay existing fixture")
 shutil.copytree(template,fixture)
 fv=fixture/"system/fvSolution";text=fv.read_text()
 text,n=re.subn(r"relTol\s+0\.05\s*;","relTol          0;",text)
 if n!=1:raise ValueError("Expected one loose initial pressure relTol")
 fv.write_text(text)
 control=fixture/"system/controlDict";text=control.read_text()
 for key in ["startFrom","startTime","stopAt","endTime","deltaT","writeControl","writeInterval","writeFormat","writePrecision","writeCompression","timePrecision","runTimeModifiable"]:
  value=protocol["controls"][key]
  if isinstance(value,bool):value=str(value).lower()
  text=replace(text,key,value)
 control.write_text(text)
 manifest={str(x.relative_to(fixture)):hashlib.sha256(x.read_bytes()).hexdigest() for x in fixture.rglob("*") if x.is_file()}
 (root/"fixture_input_sha256.json").write_text(json.dumps(manifest,indent=2)+"\n")
 print(json.dumps({"fixture":str(fixture),"files":len(manifest),"solver_or_mesh_run":False}))
if __name__=="__main__":main()
