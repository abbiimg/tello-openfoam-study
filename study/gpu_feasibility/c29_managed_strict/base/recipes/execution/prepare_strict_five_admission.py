"""Archive phase controls, or bind Root's authoritative strict dictionary audit.

Never edits a case or runs a solver. The MCP dictionary tool performs phase edits.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
OUT = WORK/'strict_runs'
ROLES = {'f14':'foundation14_control', 'cpu':'native_cpu', 'gpu':'native_gpu'}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write_new(p, obj):
    with p.open('x') as f: json.dump(obj, f, indent=2); f.write('\n')
mode = argparse.ArgumentParser()
mode.add_argument('--mode', choices=['archive','audit'], required=True)
args = mode.parse_args()
gate = WORK/'strict_initial_shared_runs/initial_field_comparison.json'
assert json.loads(gate.read_text())['startup_gate_passed']
OUT.mkdir(exist_ok=True)
if args.mode == 'archive':
    dest = OUT/'previous_controls'; dest.mkdir(exist_ok=False)
    records = {}
    for role, directory in ROLES.items():
        name = 'c29InitialPhiControls' if role == 'f14' else 'c29PortControls'
        source = BASE/directory/'constant'/name
        target = dest/(role+'_'+name)
        with target.open('xb') as f: f.write(source.read_bytes())
        records[role] = {'case_control':str(source), 'archive':str(target), 'sha256':sha(source)}
    write_new(OUT/'phase_archive.json', {'archived_utc':datetime.now(timezone.utc).isoformat(),
        'controls':records, 'source_or_solver_launched':False})
else:
    assert (OUT/'phase_archive.json').is_file()
    proof = OUT/'root_resolved_dictionary_queries.json'
    queries = json.loads(proof.read_text())
    assert len(queries) == 3
    for item in queries:
        assert item['role'] in ROLES and item['file'] == 'system/fvSolution'
        assert item['entry'] == 'solvers' and item['expand'] is True
        assert item['response'].get('isError') is not True
        assert item['response'].get('content')
    assert {x['role'] for x in queries} == set(ROLES)
    approval = WORK/'strict_pressure_proposal/root_authorization.json'
    assert sha(approval) == '8ea985fb7143d34fecfa2e6b7277b971466fbe9426a5013db98f4ebdfd259b56'
    expected = {'p':{'tolerance':1e-7,'relTol':0}, 'pFinal':{'tolerance':1e-7,'relTol':0},
        'U':{'tolerance':1e-7,'relTol':.05}, 'UFinal':{'tolerance':1e-7,'relTol':0}}
    audit = {'schema':'c29-strict-pressure-input-audit-v1',
        'protocol':'c29-native-five-fixed-steps-strict-pressure-v1',
        'protocol_sha256':'946e8c2a0e566cbfb5e494af2da1cf94ba3f3102567c8db36135fd1a758de8fd',
        'validation_thresholds_sha256':'d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b',
        'inputs_audited':True, 'audited_utc':datetime.now(timezone.utc).isoformat(),
        'root_authorization':{'path':str(approval),'sha256':sha(approval)},
        'authoritative_query_evidence':{'path':str(proof),'sha256':sha(proof)},
        'startup_gate':{'path':str(gate),'sha256':sha(gate)},
        'meaning':'Root inspected expanded foamDictionary results for all aliases; this binds input bytes, not runtime acceptance.',
        'cases':{}}
    for role, directory in ROLES.items():
        case = BASE/directory
        assert sha(case/'0.6/phi') == 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'
        fv = case/'system/fvSolution'
        rec = {'case':str(case),'fvSolution':{'path':str(fv),'sha256':sha(fv)},
            'audited_solver_criteria':expected}
        if role != 'f14':
            controls = case/'constant/c29PortControls'
            text = controls.read_text()
            assert 'sharedPinnedPhi' in text and 'c29_strict_shared_five_'+role+'_20261102_a' in text
            rec['c29PortControls'] = {'path':str(controls),'sha256':sha(controls)}
        audit['cases'][role] = rec
    target = OUT/'root_input_audit.json'
    write_new(target, audit)
    spec = importlib.util.spec_from_file_location('strict_pressure_admission', WORK/'strict_pressure_proposal/strict_pressure_admission.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    result = module.validate_strict_audit(target, BASE, list(ROLES))
    write_new(OUT/'root_input_audit_binding_check.json', result)
    print(json.dumps(result, indent=2))
