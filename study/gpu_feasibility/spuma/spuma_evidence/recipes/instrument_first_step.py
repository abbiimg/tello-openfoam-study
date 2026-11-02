"""Add only a complete first-step capture range after preserving attempt1."""
from pathlib import Path
from datetime import datetime,timezone
import difflib,hashlib,json,os,subprocess

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
REL='applications/solvers/incompressible/icoFoam/icoFoam.C';path=SOURCE/REL
assert os.getuid()==999
assert json.loads((BASE/'provenance/original_attempt/original_attempt_diagnostic.json').read_text())['actual_icoFoam_returncode']==-15
old=path.read_text();prior=json.loads((BASE/'provenance/ico_time_loop_annotation.json').read_text())
assert hashlib.sha256(old.encode()).hexdigest()==prior['annotated_sha256']
assert not (BASE/'provenance/ico_first_step_annotation.json').exists()
anchors=['    while (runTime.loop())\n    {','        runTime.printExecutionTime(Info);']
assert all(old.count(a)==1 for a in anchors)
new=old.replace(anchors[0],'    bool spumaAuditFirstStep = true;\n\n'+anchors[0]+'\n        if (spumaAuditFirstStep)\n        {\n            nvtxRangePushA("SPUMA_CFD_FIRST_COMPLETE_STEP");\n        }')
new=new.replace(anchors[1],anchors[1]+'\n\n        if (spumaAuditFirstStep)\n        {\n            nvtxRangePop();\n            spumaAuditFirstStep = false;\n        }')
upstream=subprocess.check_output(['git','-C',str(SOURCE),'show','HEAD:'+REL],text=True)
patch=''.join(difflib.unified_diff(upstream.splitlines(keepends=True),new.splitlines(keepends=True),fromfile='a/'+REL,tofile='b/'+REL))
target=BASE/'patches/ico_first_step_annotation.patch';assert not target.exists();target.write_text(patch);path.write_text(new)
record=dict(kind='Annotation-only complete first-step NVTX capture; existing full-loop annotation retained',
    recorded_utc=datetime.now(timezone.utc).isoformat(),source_pin=prior['source_pin'],path=REL,
    upstream_sha256=hashlib.sha256(upstream.encode()).hexdigest(),previous_annotated_sha256=hashlib.sha256(old.encode()).hexdigest(),
    annotated_sha256=hashlib.sha256(new.encode()).hexdigest(),patch=str(target),patch_sha256=hashlib.sha256(patch.encode()).hexdigest(),
    range_name='SPUMA_CFD_FIRST_COMPLETE_STEP',
    scope='One first runTime.loop body after entering time0.005 through all PISO corrections, write and execution log; no source arithmetic or numerical setting changed',
    old_binary_and_source_preserved=str(BASE/'provenance/original_attempt'),core_or_FV_rebuild=False,no_production_change=True)
(BASE/'provenance/ico_first_step_annotation.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'ico_first_step_annotation.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
