#!/usr/bin/env python3
"""Install the private, narrowly filtered NVHPC26.9 linkstub GCC trampoline."""
import hashlib,json,pathlib,shutil
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
WORK=pathlib.Path(__file__).resolve().parent
def main():
 source=WORK/"stub_gcc_wrapper.py"
 target=P/"tools/stub-gcc-wrapper/gcc"
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(source,target);target.chmod(0o755)
 record={"installed_utc":datetime.now(timezone.utc).isoformat(),"wrapper":str(target),"sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"scope":"Only command environments sourcing the private native stdpar env; SDK and system compiler files unchanged","purpose":"Change GCC-fpic to-fPIC only for the matching NVHPC26.9 include_acc/linkstub.c registration object"}
 (P/"provenance/stub_pic_wrapper_install.json").write_text(json.dumps(record,indent=2)+"\n")
 print(json.dumps(record))
if __name__=="__main__":main()
