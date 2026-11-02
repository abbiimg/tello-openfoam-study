"""Prepare one exact approved utility source clone; never compile/run a utility."""
from pathlib import Path
import hashlib,json,os,pwd,shutil
from datetime import datetime,timezone
PROJECT=Path(__file__).resolve().parents[3]
CANDIDATE=PROJECT/'work/gpu_actuator_port/candidate'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/f14_phi_approved_v2_20261102')
PIN='562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='openfoam'
assert sha(CANDIDATE/'candidate_manifest.json')==PIN
manifest=json.loads((CANDIDATE/'candidate_manifest.json').read_text())
for p in (PREFIX,*PREFIX.parents):assert not p.is_symlink(),str(p)
assert not PREFIX.exists(),'Never overwrite an existing build clone'
PREFIX.mkdir(parents=True)
(PREFIX/'source/foundation14_phi/Make').mkdir(parents=True)
(PREFIX/'bin').mkdir()
records={}
for name in ('C29ExperimentAdmission.H','foundation14_phi/c29FoundationInitialPhi.C',
    'foundation14_phi/Make/files','foundation14_phi/Make/options'):
    source=CANDIDATE/name;target=PREFIX/'source'/name
    assert sha(source)==manifest['candidate_files'][name]['sha256']
    shutil.copyfile(source,target)
    assert sha(target)==sha(source)
    records[name]={'sha256':sha(target),'bytes':target.stat().st_size}
shutil.copyfile(CANDIDATE/'COPYING',PREFIX/'COPYING')
(PREFIX/'source_clone.json').write_text(json.dumps(dict(
    kind='Exact approved F14 utility source clone; no case/utility execution',
    candidate_manifest_sha256=PIN,source_files=records,compiler_slot_limit=1,nice=15,
    source_prepared_utc=datetime.now(timezone.utc).isoformat(),candidate_modified=False,
    no_case_created=True,no_solver_or_initializer=True),indent=2)+'\n')
print(json.dumps({'prefix':str(PREFIX),'source_files':records,'compiled':False},indent=2))
