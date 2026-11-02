import hashlib,json,math,os,pathlib,re
from datetime import datetime,timezone
WORK=pathlib.Path(__file__).resolve().parent
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def load_protocol():
 path=WORK/"protocol.json";approval=json.loads((WORK/"root_approval.json").read_text())
 if not approval.get("approved") or approval["protocol_sha256"]!=sha(path):raise RuntimeError("Protocol/approval hash mismatch")
 return json.loads(path.read_text())
def save(path,data):
 path=pathlib.Path(path);tmp=path.with_suffix(path.suffix+".tmp");tmp.write_text(json.dumps(data,indent=2)+"\n");os.replace(tmp,path)
def check_freeze(root):
 frozen=json.loads((pathlib.Path(root)/"validation_freeze.json").read_text())
 for name,digest in frozen["files"].items():
  if sha(name)!=digest:raise RuntimeError("Frozen code/input changed: "+name)
 return frozen
def field(path,n=400,vector=False):
 text=pathlib.Path(path).read_text()
 if re.search(r"\b(?:nan|[-+]?inf(?:inity)?)\b",text,re.I):raise ValueError("Nonfinite field token")
 if vector:
  m=re.search(r"internalField\s+nonuniform\s+List<vector>\s+(\d+)\s*\((.*?)\)\s*;",text,re.S)
  if m:
   if int(m[1])!=n:raise ValueError("Declared vector field count")
   data=[tuple(float(v) for v in x.split()) for x in re.findall(r"\(([^()]*)\)",m[2])]
  else:
   m=re.search(r"internalField\s+uniform\s*\(([^()]*)\)\s*;",text);data=[tuple(float(v) for v in m[1].split())]*n if m else []
  if any(len(x)!=3 for x in data):raise ValueError("Vector component count")
 else:
  m=re.search(r"internalField\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^()]*)\)\s*;",text,re.S)
  if m:
   if int(m[1])!=n:raise ValueError("Declared scalar field count")
   data=[float(v) for v in m[2].split()]
  else:
   m=re.search(r"internalField\s+uniform\s+([-+0-9.eE]+)\s*;",text);data=[float(m[1])]*n if m else []
 if len(data)!=n:raise ValueError("Internal field cell count")
 values=[v for x in data for v in x] if vector else data
 if not all(math.isfinite(v) for v in values):raise ValueError("Nonfinite numeric field")
 return data
