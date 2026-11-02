"""Add only a named host annotation before the private icoFoam is compiled."""
from pathlib import Path
from datetime import datetime, timezone
import difflib, hashlib, json, os, subprocess

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma')
SOURCE=BASE/'source'
WORK=Path(__file__).resolve().parent
REL='applications/solvers/incompressible/icoFoam/icoFoam.C'
PIN='1ff2d45c002b7afb599b9dd8c4c6874666242349'
RANGE='SPUMA_CFD_TIME_LOOPS'
path=SOURCE/REL
marker=BASE/'provenance/ico_time_loop_annotation.json'
assert os.getuid()==999 and not marker.exists()
assert not (SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt/bin/icoFoam').exists()
assert subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()==PIN
old=path.read_text()
assert old==subprocess.check_output(['git','-C',str(SOURCE),'show','HEAD:'+REL],text=True)
anchors=['#include "pisoControl.H"','    while (runTime.loop())','    #include "poolMaxOccupancy.H"']
assert all(old.count(a)==1 for a in anchors)
new=old.replace(anchors[0],anchors[0]+'\n#include <nvtx3/nvToolsExt.h>')
new=new.replace(anchors[1],'    // Annotation only: isolate actual CFD-loop CUDA API events.\n    nvtxRangePushA("'+RANGE+'");\n\n'+anchors[1])
new=new.replace(anchors[2],'    nvtxRangePop();\n\n'+anchors[2])
patch=''.join(difflib.unified_diff(old.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/'+REL,tofile='b/'+REL))
patch_path=BASE/'patches/ico_time_loop_annotation.patch'
assert not patch_path.exists()
(BASE/'provenance/icoFoam.upstream.C').write_text(old)
patch_path.write_text(patch)
path.write_text(new)
record=dict(kind='Host NVTX annotation only for actual CFD-loop API coverage',
            recorded_utc=datetime.now(timezone.utc).isoformat(),source_pin=PIN,path=REL,
            original_sha256=hashlib.sha256(old.encode()).hexdigest(),annotated_sha256=hashlib.sha256(new.encode()).hexdigest(),
            patch=str(patch_path),patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),range_name=RANGE,
            scope='Push immediately before runTime.loop; pop immediately after loop and before final pool report. No equation, numerical control or case change.',
            header='NVTX3 from reused private NVHPC26.9/CUDA13.3 SDK',
            core_or_finiteVolume_rebuild_required=False,no_production_change=True)
marker.write_text(json.dumps(record,indent=2)+'\n')
(WORK/'ico_time_loop_annotation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
