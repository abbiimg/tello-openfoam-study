"""Private v2.2: actual F14 current-time-name API only; no algorithm change."""
from pathlib import Path
import hashlib,json,os,pwd,shutil,difflib
from datetime import datetime,timezone
PARENT=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation')
OLD=PARENT/'f14_phi_compat_v2_1_20261102'
NEW=PARENT/'f14_phi_compat_v2_2_20261102'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='openfoam'
assert not NEW.exists()
for p in (NEW,*NEW.parents):assert not p.is_symlink()
module=Path('/opt/openfoam14/applications/modules/incompressibleFluid/incompressibleFluid.C')
lines=module.read_text().splitlines();constructor='\n'.join(f'{i+1}: {lines[i]}' for i in range(88,105))
assert 'runTime.name()' in constructor
(NEW/'source/foundation14_phi/Make').mkdir(parents=True);(NEW/'bin').mkdir()
for name in ('C29ExperimentAdmission.H','foundation14_phi/c29FoundationInitialPhi.C','foundation14_phi/Make/files','foundation14_phi/Make/options'):
    shutil.copyfile(OLD/'source'/name,NEW/'source'/name)
p=NEW/'source/foundation14_phi/c29FoundationInitialPhi.C';original=p.read_text()
assert original.count('runTime.timeName()')==3
adapted=original.replace('runTime.timeName()','runTime.name()')
p.write_text(adapted,newline='\n')
patch=''.join(difflib.unified_diff(original.splitlines(True),adapted.splitlines(True),
    fromfile='private_v2_1/c29FoundationInitialPhi.C',tofile='private_v2_2/c29FoundationInitialPhi.C'))
(NEW/'compatibility_from_v2_1.patch').write_text(patch)
shutil.copyfile(OLD/'COPYING',NEW/'COPYING')
record=dict(kind='Private F14 utility v2.2 current-time getter API compatibility',
    prepared_utc=datetime.now(timezone.utc).isoformat(),previous_version=str(OLD),
    prior_build_log_sha256=sha(OLD/'build.log'),previous_source_sha256=sha(OLD/'source/foundation14_phi/c29FoundationInitialPhi.C'),
    private_source_sha256=sha(p),patch_sha256=sha(NEW/'compatibility_from_v2_1.patch'),
    reference_module_sha256=sha(module),actual_original_phi_constructor=constructor,
    source_and_Make_files={str(q.relative_to(NEW/'source')):{'sha256':sha(q)} for q in (NEW/'source').rglob('*') if q.is_file()},
    change='runTime.timeName() -> runTime.name(): actual F14 current-time-name API',
    interpolation_IO_semantics_receipt_fields_source_time_physics_changed=False,
    candidate_modified=False,utility_executed=False)
(NEW/'source_compatibility.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'prefix':str(NEW),'source_sha256':sha(p),'patch_sha256':sha(NEW/'compatibility_from_v2_1.patch'),'actual_constructor':constructor},indent=2))
