#!/usr/bin/env python3
"""Annotate only the task-private icoFoam time loop for process-attributed CUDA API audit."""
import difflib,hashlib,json,pathlib
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
R=P/"source/OpenFOAM-v2606"
REL="applications/solvers/incompressible/icoFoam/icoFoam.C"
def main():
 source=R/REL;marker=P/"provenance/ico_time_loop_annotation.json"
 if marker.exists():
  d=json.loads(marker.read_text())
  if hashlib.sha256(source.read_bytes()).hexdigest()!=d["annotated_sha256"]:raise RuntimeError("Annotated source contents changed")
  print(json.dumps(d));return
 old=source.read_text()
 anchors=['#include "pisoControl.H"','    while (runTime.loop())','    Info<< "End\\n" << endl;']
 if any(old.count(a)!=1 for a in anchors):raise RuntimeError("Pinned icoFoam annotation anchors must be unique")
 new=old.replace(anchors[0],anchors[0]+"\n#include <nvtx3/nvToolsExt.h>")
 new=new.replace(anchors[1],'    // Backend audit annotation; does not change solver arithmetic.\n    nvtxRangePushA("NATIVE_STDPAR_CFD_TIME_LOOPS");\n\n'+anchors[1])
 new=new.replace(anchors[2],"    nvtxRangePop();\n\n"+anchors[2])
 source.write_text(new)
 patch="".join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile="a/"+REL,tofile="b/"+REL))
 patch_path=P/"provenance/ico_time_loop_annotation.patch";patch_path.write_text(patch)
 d={"kind":"NVTX annotation only for isolating CUDA launch API events in actual CFD time loops","completed_utc":datetime.now(timezone.utc).isoformat(),"openfoam_pin":"b239fea6e48922730477e218c44e8b6a8ab17ade","path":REL,"original_sha256":hashlib.sha256(old.encode()).hexdigest(),"annotated_sha256":hashlib.sha256(new.encode()).hexdigest(),"patch":str(patch_path),"patch_sha256":hashlib.sha256(patch.encode()).hexdigest(),"range":"NATIVE_STDPAR_CFD_TIME_LOOPS","scope":"Starts after mesh/field initialization and ends after the last runTime.loop iteration; no equations, solver controls or case inputs changed.","header":"NVTX3 from pinned private NVHPC26.9 CUDA13.3 SDK","production_change":False}
 marker.write_text(json.dumps(d,indent=2)+"\n")
 print(json.dumps(d),flush=True)
if __name__=="__main__":main()
