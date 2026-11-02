"""Run the single Root-approved strict native CPU five-step validation once.

Fixed case/binary/output, strict input binding and exact shared-startup gates.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import re
import subprocess
import time

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
PREFIX_BASE = Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation')
AUDITOR = WORK.parent/'candidate/audit_candidate.py'
COMBINED = WORK.parent/'managed_strict_combined_v2_3/combined_source_manifest.json'
OUTPUT = WORK/'strict_runs'
TAG = 'native_cpu_five'
CONFIG = {
    'f14': ('foundation14_control', 'f14_phi_compat_v2_2_20261102', 'c29FoundationInitialPhi',
        '161be52ffe49e0a5ec62093f4fc92a5a215f1976be141edc3965294fe8fc8888',
        '91a08df81f64d3d0296d22c11ad40a9b3d6b524a9bb9fb1124665abb2bb8b7d5'),
    'cpu': ('native_cpu', 'native_cpu_managed_strict_v2_3_20261102', 'c29ManagedHybridFoamStrict',
        '535cb85ecb08b34b6a6ff08a00d1afc1857b68f041d4e89df309e2dbb5c01e89',
        '3fadf986e56cde01723a7256853c039580923f970a4ba3121028916aa8d97d80'),
    'gpu': ('native_gpu', 'native_gpu_managed_strict_v2_3_20261102', 'c29ManagedHybridFoamStrict',
        '7056d5f5bcffb88119881752361f09d40459126af065fd37cdc45288c00d9185',
        'c3e61de12b03e5406d5c1155d932b2de5b27c7198dd99e29c1228ccd18deadff'),
}

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--role', choices=CONFIG, required=True)
role = ap.parse_args().role
assert role == 'cpu'
case_name, prefix_name, executable, binary_sha, identity_sha = CONFIG[role]
case, prefix = BASE/case_name, PREFIX_BASE/prefix_name
binary, identity = prefix/'bin'/executable, prefix/'library_identity.json'
backend = 'gpu' if role == 'gpu' else 'cpu'
phase = 'five_fixed_steps'
control_name = 'c29InitialPhiControls' if role == 'f14' else 'c29PortControls'
assert os.geteuid() == 999
expected_options = {'f14': 'linuxArm64GccDPInt32Opt', 'cpu': 'linuxARM64GccDPInt32Opt', 'gpu': 'linuxARM64Nvidia-gpuDPInt32Opt'}
assert os.environ['WM_OPTIONS'] == expected_options[role]
assert sha(binary) == binary_sha and sha(identity) == identity_sha
assert sha(COMBINED) == '7e4492d4d644e3b03211315f0a0c692db5b6652edb063cf2779a6ff1db9cbaf5'
if role != 'f14':
    for rel, expected in json.loads(COMBINED.read_text())['files'].items():
        assert sha(prefix/'source'/rel) == expected, rel
else:
    assert sha(prefix/'source/foundation14_phi/c29FoundationInitialPhi.C') == '2e461721d515bf1eb5a667c8580e9ce205439f96963492abffa204ccbbb301cb'
plan = json.loads((WORK.parent/'candidate/validation_recipe.json').read_text())
for rel, item in plan['unchanged_input_hashes'].items(): assert sha(case/rel) == item['sha256'], rel
assert sha(case/'0.6/phi') == 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'
OUTPUT.mkdir(exist_ok=True)

import sys
sys.path.insert(0, str(WORK/'strict_pressure_proposal'))
from strict_pressure_admission import validate_strict_audit
STRICT_AUDIT = WORK/'strict_runs/root_input_audit.json'
strict_input_binding = validate_strict_audit(STRICT_AUDIT, BASE, ['cpu'])
assert json.loads((WORK/'strict_initial_shared_runs/initial_field_comparison.json').read_text())['startup_gate_passed']

BINARY_FOR_IDENTITY, CASE_FOR_IDENTITY = binary, case
assert not any(p.is_dir() and re.fullmatch(r'[0-9.]+',p.name) and float(p.name) > .6 for p in case.iterdir())
assert not (OUTPUT/(TAG+'_execution.json')).exists()
spec = importlib.util.spec_from_file_location('root_admission_reader', AUDITOR.parent/'admission_audit.py')
reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
controls = (case/'constant'/control_name).read_text()
receipt = Path(reader.setting(controls, 'experimentReceiptFile')).with_suffix('.json')
assert receipt.parent == BASE/'receipts' and not receipt.exists()
before = {str(p.relative_to(case)): sha(p) for p in case.rglob('*') if p.is_file()}
subprocess.run(['python3', str(AUDITOR), '--case', str(case), '--private-root', str(BASE),
    '--backend', backend, '--phase', phase, '--binary', str(binary), '--library-identity', str(identity),
    '--shared-phi-sha256', 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c',
    '--write-launch-receipt', str(receipt)], check=True)
subprocess.run(['python3', str(AUDITOR), '--verify-launch-receipt', str(receipt)], check=True)
launch = json.loads(receipt.read_text())
expected_argv = [str(binary), '-case', str(case)]
assert launch['manual_argv'] == expected_argv
record = {'kind': 'Actual five fixed steps, managed-ownership strict-pressure native CPU, functional validation only',
    'role': role, 'backend': backend, 'started_utc': utc(), 'case': str(case),
    'binary': str(binary), 'binary_sha256': binary_sha, 'library_identity_sha256': identity_sha,
    'combined_source_manifest_sha256': sha(COMBINED) if role != 'f14' else None,
    'launch_receipt': str(receipt), 'launch_receipt_sha256': sha(receipt),
    'manual_argv': expected_argv, 'case_before': before}
(OUTPUT/(TAG+'_prelaunch.json')).write_text(json.dumps(record, indent=2)+'\n')
with (OUTPUT/(TAG+'_stdout.log')).open('x') as output:
    child = subprocess.Popen(['nice', '-n', '15', *expected_argv], stdout=output, stderr=subprocess.STDOUT, start_new_session=True, cwd=case)
    record['actual_child_pid'] = child.pid
    record['actual_birth_tick'] = (Path('/proc')/str(child.pid)/'stat').read_text().split(') ', 1)[1].split()[19]
    start = time.monotonic(); seen = set()
    while child.poll() is None:
        try:

            proc = Path('/proc')/str(child.pid)
            if (proc/'exe').resolve() == BINARY_FOR_IDENTITY.resolve():
                uid_line = next(x for x in (proc/'status').read_text().splitlines() if x.startswith('Uid:'))
                record['actual_child_identity'] = {'pid':child.pid,
                    'uid':int(uid_line.split()[1]), 'cwd':str((proc/'cwd').resolve()),
                    'exe':str((proc/'exe').resolve()),
                    'cmdline':(proc/'cmdline').read_bytes().decode().strip('\0').split('\0'),
                    'birth_tick':record['actual_birth_tick']}
            for line in (Path('/proc')/str(child.pid)/'maps').read_text().splitlines():
                parts = line.split(maxsplit=5)
                if len(parts) == 6 and parts[5].startswith('/') and '.so' in parts[5]:
                    path = Path(parts[5].removesuffix(' (deleted)')).resolve()
                    if path.is_file(): seen.add(str(path))
        except FileNotFoundError: pass
        if time.monotonic()-start > 600:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=15)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            record['timeout'] = True
            break
        time.sleep(.02)
    record['actual_child_returncode'] = child.wait()
record['loaded_libraries_observed'] = [{'path': p, 'sha256': sha(p)} for p in sorted(seen)]
observed = {item['path']: item['sha256'] for item in record['loaded_libraries_observed']}
declared = json.loads(identity.read_text())['files']
record['declared_libraries_actually_observed_unchanged'] = all(observed.get(item['path']) == item['sha256'] for item in declared)
after = {str(p.relative_to(case)): sha(p) for p in case.rglob('*') if p.is_file()}
record['original_inputs_unchanged'] = all(after.get(p) == h for p, h in before.items())
record['added_files'] = sorted(set(after)-set(before))

text = (OUTPUT/(TAG+'_stdout.log')).read_text()
record['source_calls_observed'] = len(re.findall(r'^C29_SOURCE_AUDIT ',text,re.M))
record['controller_updates_observed'] = len(re.findall(r'^TILT ',text,re.M))
record['time_values'] = [float(x) for x in re.findall(r'^Time = ([0-9.eE+-]+)',text,re.M)]
record['timesteps_observed'] = len(record['time_values'])
record['End_marker'] = bool(re.search(r'^End\s*$',text,re.M))

identity_observed = record.get('actual_child_identity', {})
record['actual_identity_passed'] = (identity_observed.get('uid') == 999
    and identity_observed.get('cwd') == str(CASE_FOR_IDENTITY.resolve())
    and identity_observed.get('exe') == str(BINARY_FOR_IDENTITY.resolve())
    and identity_observed.get('cmdline') == [str(BINARY_FOR_IDENTITY), '-case', str(CASE_FOR_IDENTITY)])
record['strict_protocol_input_audit'] = strict_input_binding

record['completed_utc'] = utc()
record['numerical_acceptance'] = 'Separate frozen-threshold mechanical analysis required'
record['five_step_process_completed'] = (record['actual_child_returncode'] == 0
    and record['original_inputs_unchanged'] and record['declared_libraries_actually_observed_unchanged']
    and record['source_calls_observed'] == record['controller_updates_observed'] == record['timesteps_observed'] == 5
    and record['time_values'] == [.6001,.6002,.6003,.6004,.6005]
    and record['End_marker'] and record['actual_identity_passed'])
(OUTPUT/(TAG+'_execution.json')).write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:record[k] for k in ('role','actual_child_returncode','original_inputs_unchanged',
    'declared_libraries_actually_observed_unchanged','actual_identity_passed','five_step_process_completed')},indent=2))
assert record['five_step_process_completed']
