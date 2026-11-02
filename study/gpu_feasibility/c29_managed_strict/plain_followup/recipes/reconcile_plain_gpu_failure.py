"""Reconcile the actual same2.3 no-tool failure without changing either case."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
WORK=Path(__file__).resolve().parent
EVIDENCE=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102/plain_unprofiled_diagnostic_v1_20261102')
CASE=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102/plain_unprofiled_v2_3')
ORIGINAL=Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102/native_gpu')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def bind(p):return {'path':str(p),'sha256':sha(p)}
path=EVIDENCE/'actual_solver_exit.json';actual=json.loads(path.read_text())
assert actual['actual_child_waited'] is True and actual['return_code']==-11
assert actual['wrapper_errors']==[] and actual['cleanup_errors']==[] and actual['postprocessing_complete']
assert actual['original_case_files_unchanged'] and actual['declared_libraries_actually_observed_unchanged']
assert actual['source_calls']==actual['controller_updates']==0 and actual['time_values']==[.6001] and not actual['End_marker']
assert actual['no_profiler_or_tool_injection'] and not actual['environment']['LD_PRELOAD']
assert not any('Nsight' in x['path'] or 'ToolsInjection' in x['path'] for x in actual['loaded_libraries_observed'])
assert actual['binary_sha256']==actual['binary_sha256_after']=='7056d5f5bcffb88119881752361f09d40459126af065fd37cdc45288c00d9185'
for rel,value in actual['case_before'].items():assert sha(CASE/rel)==value,rel
for x in actual['loaded_libraries_observed']:assert sha(Path(x['path']))==x['sha256']
expected=['0.6/c29_initialP','0.6/c29_initialPhi','0.6/c29_initialU']
assert actual['added_case_files']==expected
startup={}
for rel in expected:
    assert sha(CASE/rel)==sha(ORIGINAL/rel),rel
    startup[rel]=sha(CASE/rel)
identity=actual['actual_child'];proc=Path('/proc')/str(identity['pid'])
if proc.exists():assert int((proc/'stat').read_text().rsplit(') ',1)[1].split()[19])!=identity['birth_start_ticks']
log=Path(actual['log']);text=log.read_text()
assert 'Foam::sigSegv::sigHandler' in text and 'Courant Number mean:' not in text
result={'schema':'root-c29-plain-same2.3-failed-terminal-reconciliation-v1',
    'reconciled_utc':datetime.now(timezone.utc).isoformat(),'actual_child':identity,
    'actual_child_waited':True,'actual_child_return_code':-11,'wrapper_return_code':1,
    'wrapper_errors':[],'cleanup_errors':[],'original_owned_child_no_longer_alive':True,
    'no_profiler_observer_or_debugger_injection':True,
    'binary_unchanged':'7056d5f5bcffb88119881752361f09d40459126af065fd37cdc45288c00d9185',
    'initial_audit_fields_exact_same_bytes_as_qualified_shared_startup':startup,
    'entered_time_headers_s':[.6001],'completed_timesteps':0,'source_calls':0,'controller_updates':0,'End_marker':False,
    'input_and_actual_loaded_library_bytes_rechecked_unchanged':True,
    'added_case_files':expected,'actual_exit_receipt':bind(path),'stdout':bind(log),
    'root_approval':bind(WORK/'strict_runs/root_plain_gpu_approval.json'),
    'fresh_clone_preparation':bind(WORK/'strict_runs/plain_gpu_fresh_clone_preparation.json'),
    'interpretation':'The first-step failure reproduces without Nsight/tool injection. Profiling is not required to reproduce it; exact host instruction/device-kernel cause remains unproven.',
    'qualification':'Native full-size GPU transient remains UNQUALIFIED. No GPU rotor lift, accepted full-step CUDA proof, CPU/GPU transient parity or speed measurement.',
    'decision':'No causally unsupported2.4 build or timing. Preserve source-only proposal. Complete dependency verification, evidence curation and delivery with this explicit limitation.'}
target=WORK/'strict_runs/root_plain_gpu_failed_terminal_reconciliation.json'
with target.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({'path':str(target),'sha256':sha(target),'actual_child_return_code':-11},indent=2))
