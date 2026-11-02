"""Root's read-only reconciliation of the strict F14-to-nativeCPU experiment.

Writes a distinct bounded external gate. No GPU launch/receipt or case edits.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, importlib.util, json
import numpy as np
WORK = Path(__file__).resolve().parent
OUT = WORK/'strict_runs'
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def load(path): return json.loads(path.read_text())
def bind(path): return {'path':str(path),'sha256':sha(path)}
report_path = OUT/'f14_to_cpu_analysis.json'
assert sha(report_path) == '9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e'
report = load(report_path)
comparison = report['comparisons']['f14-to-cpu']
assert comparison['mechanical_passed'] and not comparison['failed_checks']
assert all(x['pass'] for x in comparison['checks'])
assert report['pressure_protocol'] == 'strict-pressure-v1'
assert report['thresholds']['sha256'] == 'd6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b'
spec = importlib.util.spec_from_file_location('strict_admission', WORK/'strict_pressure_proposal/strict_pressure_admission.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
audit = module.validate_strict_audit(OUT/'root_input_audit.json',BASE,['f14','cpu','gpu'])
startup = WORK/'strict_initial_shared_runs/initial_field_comparison.json'
assert load(startup)['startup_gate_passed']
receipts = {}
for role, dirname, name in [('f14','foundation14_control','f14_control_five_execution.json'),('cpu','native_cpu','native_cpu_five_execution.json')]:
    path = OUT/name; record = load(path); case = BASE/dirname
    assert record['actual_child_returncode'] == 0 and record['actual_identity_passed']
    assert record['time_values'] == [.6001,.6002,.6003,.6004,.6005] and record['End_marker']
    assert sha(Path(record['binary'])) == record['binary_sha256']
    assert record['strict_protocol_input_audit']['sha256'] == audit['sha256']
    for rel, value in record['case_before'].items(): assert sha(case/rel) == value, (role,rel)
    for library in record['loaded_libraries_observed']:
        assert sha(Path(library['path'])) == library['sha256'], library['path']
    if role == 'f14':
        assert record['original_inputs_and_cached_library_unchanged']
        assert record['expected_cached_actuator_library_actually_loaded'] and record['no_actuator_recompile_observed']
        assert record['TILT_samples'] == 5
    else:
        assert record['five_step_process_completed'] and record['original_inputs_unchanged']
        assert record['declared_libraries_actually_observed_unchanged']
        assert record['source_calls_observed'] == record['controller_updates_observed'] == 5
    receipts[role] = bind(path)
shared_runs = {}
for role in ['cpu','gpu']:
    path = WORK/'strict_initial_shared_runs'/(role+'_execution.json')
    assert load(path)['initialization_completed']
    shared_runs[role] = bind(path)
result = {'schema':'root-c29-strict-f14-to-nativecpu-external-gate-v1',
    'root_asserted_pass':True, 'reviewed_utc':datetime.now(timezone.utc).isoformat(),
    'numerical_report':bind(report_path),'strict_input_binding':audit,
    'actual_five_step_receipts':receipts,'exact_shared_startup_gate':bind(startup),
    'actual_shared_initial_receipts':shared_runs,
    'passed_mechanical_checks':len(comparison['checks']),
    'numpy_version_for_analysis_and_reconciliation':np.__version__,
    'scope':'Only the new shared-phi strict-pressure managed2.3 F14-to-nativeCPU five-fixed-step validation. GPU transient qualification, performance, production default and study optimum are not decided by this gate.',
    'preserved_failures':'Original computed-GPU startup phi exactness failed by 3.1742559698354905e-19; preregistered common-phi fallback used. Original legacy relTol.05 five-step continuity failures remain unwaived.'}
target = OUT/'root_f14_to_cpu_external_gate.json'
with target.open('x') as stream: json.dump(result,stream,indent=2);stream.write('\n')
print(json.dumps({'path':str(target),'sha256':sha(target),'root_asserted_pass':True,
    'passed_mechanical_checks':result['passed_mechanical_checks']},indent=2))
