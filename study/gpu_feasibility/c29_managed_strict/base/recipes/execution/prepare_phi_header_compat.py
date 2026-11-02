"""Private v2.1 header-only F14 compatibility copy; preserve pinned v2."""
from pathlib import Path
import hashlib,json,os,pwd,shutil,difflib
from datetime import datetime,timezone
PROJECT=Path(__file__).resolve().parents[3]
CANDIDATE=PROJECT/'work/gpu_actuator_port/candidate'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/f14_phi_compat_v2_1_20261102')
PIN='562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='openfoam'
assert sha(CANDIDATE/'candidate_manifest.json')==PIN
manifest=json.loads((CANDIDATE/'candidate_manifest.json').read_text())
assert not PREFIX.exists()
for p in (PREFIX,*PREFIX.parents):assert not p.is_symlink()
headers=['argList.H','Time.H','fvMesh.H','volFields.H','surfaceFields.H','linear.H','IOdictionary.H']
header_records={}
for name in headers:
    choices=[Path('/opt/openfoam14/src/OpenFOAM/lnInclude')/name,Path('/opt/openfoam14/src/finiteVolume/lnInclude')/name]
    p=next(q for q in choices if q.is_file()).resolve()
    header_records[name]={'path':str(p),'sha256':sha(p)}
linear=Path(header_records['linear.H']['path']);lines=linear.read_text().splitlines()
contexts=[]
for i,line in enumerate(lines):
    if 'linearInterpolate' in line:contexts.append('\n'.join(f'{j+1}: {lines[j]}' for j in range(max(0,i-4),min(len(lines),i+15))))
assert contexts,'Actual linearInterpolate declarations must be present'
(PREFIX/'source/foundation14_phi/Make').mkdir(parents=True)
(PREFIX/'bin').mkdir()
for name in ('C29ExperimentAdmission.H','foundation14_phi/c29FoundationInitialPhi.C','foundation14_phi/Make/files','foundation14_phi/Make/options'):
    p=CANDIDATE/name;assert sha(p)==manifest['candidate_files'][name]['sha256']
    shutil.copyfile(p,PREFIX/'source'/name)
source=PREFIX/'source/foundation14_phi/c29FoundationInitialPhi.C'
original=source.read_text()
block='\n'.join('#include "'+name+'"' for name in headers)
assert original.count('#include "fvCFD.H"')==1
adapted=original.replace('#include "fvCFD.H"',block)
assert adapted.count('int main(')==1
adapted=adapted.replace('int main(','using namespace Foam;\nint main(')
assert adapted.replace(block,'#include "fvCFD.H"').replace('using namespace Foam;\nint main(','int main(')==original
source.write_text(adapted,newline='\n')
patch=''.join(difflib.unified_diff(original.splitlines(True),adapted.splitlines(True),
    fromfile='approved_v2/foundation14_phi/c29FoundationInitialPhi.C',tofile='private_v2_1/foundation14_phi/c29FoundationInitialPhi.C'))
(PREFIX/'compatibility.patch').write_text(patch)
shutil.copyfile(CANDIDATE/'COPYING',PREFIX/'COPYING')
record=dict(kind='Private F14 v2.1 header/namespace compatibility only',prepared_utc=datetime.now(timezone.utc).isoformat(),
    approved_candidate_manifest_sha256=PIN,approved_main_sha256=manifest['candidate_files']['foundation14_phi/c29FoundationInitialPhi.C']['sha256'],
    private_main_sha256=sha(source),compatibility_patch_sha256=sha(PREFIX/'compatibility.patch'),
    actual_header_records=header_records,linearInterpolate_declarations=contexts,
    changes=['Replace removed fvCFD.H umbrella with actual installed F14 headers','Explicit using namespace Foam'],
    source_and_Make_files={str(p.relative_to(PREFIX/'source')):{'sha256':sha(p)} for p in (PREFIX/'source').rglob('*') if p.is_file()},
    interpolation_IO_receipt_fields_source_time_physics_changed=False,
    candidate_modified=False,compiled=False,utility_executed=False)
(PREFIX/'source_compatibility.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'prefix':str(PREFIX),'source_sha256':sha(source),'patch_sha256':sha(PREFIX/'compatibility.patch'),'actual_declarations':contexts},indent=2))
