"""Prepare one exact-input fresh clone for the unprofiled same-binary test.

No solver/tool/receipt issuance; phase dictionary edits use the MCP parser.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,shutil
WORK=Path(__file__).resolve().parent
OUT=WORK/'strict_runs'
SOURCE=Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102/native_gpu')
ROOT=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102')
DEST=ROOT/'plain_unprofiled_v2_3'
RECEIPT=SOURCE.parent/'receipts/c29_strict_shared_five_gpu_20261102_a.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,obj):
    with p.open('x') as f:json.dump(obj,f,indent=2);f.write('\n')
parser=argparse.ArgumentParser();parser.add_argument('--mode',choices=['clone','finalize'],required=True)
mode=parser.parse_args().mode
assert os.geteuid()==999 and sha(RECEIPT)=='074540859b1dbb757122f06fed2b152158773da93138091b598fb3fbdb5f6d68'
assert sha(OUT/'root_gpu_v2_3_failed_terminal_reconciliation.json')=='7e0b9c049c3ee9d743afe41ee636df9c0cba735a6c178438fafbef94b3bad270'
for path in (SOURCE,ROOT,*SOURCE.parents,*ROOT.parents):assert not path.is_symlink()
original=json.loads(RECEIPT.read_text());inputs=original['inputs']
assert {'0.6/U','0.6/p','0.6/phi','constant/c29PortControls','system/fvSolution'}<=set(inputs)
for rel,record in inputs.items():
    assert '..' not in Path(rel).parts and not Path(rel).is_absolute()
    p=SOURCE/rel;assert str(p)==record['path'] and sha(p)==record['sha256'],rel
if mode=='clone':
    assert not DEST.exists()
    DEST.mkdir();(ROOT/'receipts').mkdir(exist_ok=True)
    for rel,record in inputs.items():
        target=DEST/rel;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(SOURCE/rel,target)
        assert sha(target)==record['sha256'],rel
    write(OUT/'plain_gpu_clone_original_inputs.json',{'source_case':str(SOURCE),'case':str(DEST),
        'source_receipt_sha256':sha(RECEIPT),'copied_original_inputs':inputs,
        'source_or_solver_launched':False})
    print(json.dumps({'fresh_case':str(DEST),'exact_copied_input_files':len(inputs),'solver_launched':False}))
else:
    original_record=OUT/'plain_gpu_clone_original_inputs.json'
    assert original_record.is_file()
    after={str(p.relative_to(DEST)):sha(p) for p in DEST.rglob('*') if p.is_file()}
    assert set(after)==set(inputs)
    changes=[rel for rel,value in after.items() if value!=inputs[rel]['sha256']]
    assert changes==['constant/c29PortControls'],changes
    assert sha(DEST/'0.6/phi')=='f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'
    controls=(DEST/'constant/c29PortControls').read_text()
    assert 'c29_plain_unprofiled_2_3_20261102_a' in controls and 'sharedPinnedPhi' in controls
    result={'schema':'root-same2.3-fresh-unprofiled-clone-preparation-v1',
        'prepared_utc':datetime.now(timezone.utc).isoformat(),'case':str(DEST),'source_case':str(SOURCE),
        'source_receipt':{'path':str(RECEIPT),'sha256':sha(RECEIPT)},
        'original_copy_record':{'path':str(original_record),'sha256':sha(original_record)},
        'copied_original_file_count':len(inputs),'current_case_hashes':after,
        'changed_files':['constant/c29PortControls'],
        'change':'Only fresh diagnostic experiment ID and receipt pathname, edited/read through foamDictionary',
        'physical_inputs_mesh_U_p_phi_schemes_strict_solver_criteria_unchanged':True,
        'advanced_fields_or_controller_state_copied':False,'original_case_bytes_unchanged':True,
        'solver_or_debugger_or_profiler_launched':False}
    path=OUT/'plain_gpu_fresh_clone_preparation.json';write(path,result)
    print(json.dumps({'preparation':str(path),'sha256':sha(path),'solver_launched':False},indent=2))
