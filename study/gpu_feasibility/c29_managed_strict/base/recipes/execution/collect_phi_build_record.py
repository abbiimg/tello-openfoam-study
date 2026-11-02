"""Read/record the single completed compile attempt; no utility execution."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,shutil
WORK=Path(__file__).resolve().parent
PROJECT=WORK.parents[2]
CANDIDATE=PROJECT/'work/gpu_actuator_port/candidate'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/f14_phi_approved_v2_20261102')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((CANDIDATE/'candidate_manifest.json').read_text())
assert sha(CANDIDATE/'candidate_manifest.json')=='562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7'
source=json.loads((PREFIX/'source_clone.json').read_text())
for name,record in source['source_files'].items():
    assert sha(PREFIX/'source'/name)==record['sha256']==manifest['candidate_files'][name]['sha256']
binary=PREFIX/'bin/c29FoundationInitialPhi'
assert not binary.exists()
shutil.copyfile(PREFIX/'build.log',WORK/'phi_utility_v2_build.log')
installed={}
libdir=Path('/opt/openfoam14/platforms/linuxArm64GccDPInt32Opt/lib')
for name in ('libfiniteVolume.so','libmeshTools.so','libOpenFOAM.so'):
    p=libdir/name
    if p.is_file():
        real=p.resolve();installed[name]={'path':str(real),'sha256':sha(real),'bytes':real.stat().st_size}
ast.parse((WORK/'prepare_native_c29_cases.py').read_text())
record=dict(kind='Authorized exact-v2 F14 phi utility COMPILE attempt, failed; not executed',
    recorded_utc=datetime.now(timezone.utc).isoformat(),prefix=str(PREFIX),
    candidate_manifest_sha256=sha(CANDIDATE/'candidate_manifest.json'),
    source_clone_sha256=sha(PREFIX/'source_clone.json'),source_files=source['source_files'],
    build_log_sha256=sha(PREFIX/'build.log'),build_exit_code=1,binary=None,
    compiler='g++13.3.0, Foundation14 linuxArm64GccDPInt32Opt, std=c++14, WM_DP/Int32',
    one_compiler_slot=True,nice=15,slot_released=True,
    failure='fvCFD.H is absent in Foundation14; umbrella-header API adapter needed in a separately preserved utility version/patch',
    installed_intended_libraries=installed,libraries_actually_linked=None,
    candidate_or_vendor_or_SDK_or_study_modified=False,no_cases=True,
    utility_or_solver_executed=False,restoration_script_executed=False,
    restorer_AST_parse=True,restorer_sha256=sha(WORK/'prepare_native_c29_cases.py'),
    plan_sha256=sha(WORK/'PLAN.md'),no_retry=True)
(WORK/'phi_utility_v2_build_record.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({key:record[key] for key in ('build_exit_code','failure','binary','slot_released',
    'candidate_manifest_sha256','restorer_AST_parse','restorer_sha256','utility_or_solver_executed')},indent=2))
