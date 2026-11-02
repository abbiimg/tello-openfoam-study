"""Run exactly the preregistered five-step original F14 control once."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import signal
import subprocess
import time

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
OUTPUT = WORK/'strict_runs'
OUTPUT.mkdir(exist_ok=True)
CASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102/foundation14_control')
BINARY = Path('/opt/openfoam14/platforms/linuxArm64GccDPInt32Opt/bin/foamRun')
LIBREL = 'dynamicCode/platforms/linuxArm64GccDPInt32Opt/lib/librotors_7ae57bb77feaae19c26ff305b44ebb5a6819f2ef.so'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()


import sys
sys.path.insert(0, str(WORK/'strict_pressure_proposal'))
from strict_pressure_admission import validate_strict_audit
STRICT_AUDIT = WORK/'strict_runs/root_input_audit.json'
strict_input_binding = validate_strict_audit(STRICT_AUDIT, BASE, ['f14'])
assert json.loads((WORK/'strict_initial_shared_runs/initial_field_comparison.json').read_text())['startup_gate_passed']

assert os.geteuid() == 999 and os.environ['WM_PROJECT_VERSION'] == '14'
assert json.loads((WORK/'strict_initial_shared_runs/initial_field_comparison.json').read_text())['startup_gate_passed']
assert not (OUTPUT/'f14_control_five_execution.json').exists()
assert not any(p.is_dir() and re.fullmatch(r'[0-9.]+', p.name) and float(p.name) > .6 for p in CASE.iterdir())
plan = json.loads((WORK.parent/'candidate/validation_recipe.json').read_text())
for rel, item in plan['unchanged_input_hashes'].items(): assert sha(CASE/rel) == item['sha256'], rel
assert sha(CASE/LIBREL) == '402b112e09f36444ac13d19a3a04f3aca24344a632eb7a258fd11fc3a33392ce'
assert sha(WORK.parent/'candidate/validation_thresholds.json') == 'd6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b'
assert sha(BINARY) == '3df39f3a5a3020c4dafee9d20063f9525a6556be874e9202aa5d122d0c9970da'
assert sha(CASE/'0.6/phi') == 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'
BINARY_FOR_IDENTITY, CASE_FOR_IDENTITY = BINARY, CASE
before = {str(p.relative_to(CASE)): sha(p) for p in CASE.rglob('*') if p.is_file()}
record = {'kind': 'Actual five-fixed-step original Foundation14 C29 control; not performance measurement',
    'started_utc': utc(), 'binary': str(BINARY), 'binary_sha256': sha(BINARY),
    'command': ['nice', '-n', '15', str(BINARY), '-case', str(CASE)],
    'case': str(CASE), 'case_before': before,
    'preregistered_thresholds_sha256': sha(WORK.parent/'candidate/validation_thresholds.json'),
    'controller': 'Fresh process, no priming or transferred controller history',
    'initial_phi': 'Read the predeclared byte-identical F14 starting phi, shared by all three backends',
    'expected_steps': 5, 'start_s': .6, 'end_s': .6005, 'fixed_dt_s': .0001}
(OUTPUT/'f14_control_five_prelaunch.json').write_text(json.dumps(record, indent=2)+'\n')
with (OUTPUT/'f14_control_five_stdout.log').open('x') as output:
    child = subprocess.Popen(record['command'], stdout=output, stderr=subprocess.STDOUT, start_new_session=True, cwd=CASE)
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
        if time.monotonic()-start > 300:
            os.killpg(child.pid, signal.SIGTERM)
            try: child.wait(timeout=15)
            except subprocess.TimeoutExpired: os.killpg(child.pid, signal.SIGKILL); child.wait()
            record['timeout'] = True
            break
        time.sleep(.03)
    record['actual_child_returncode'] = child.wait()
record['loaded_libraries_observed'] = [{'path': p, 'sha256': sha(p)} for p in sorted(seen)]
after = {str(p.relative_to(CASE)): sha(p) for p in CASE.rglob('*') if p.is_file()}
record['original_inputs_and_cached_library_unchanged'] = all(after.get(p) == h for p, h in before.items())
record['expected_cached_actuator_library_actually_loaded'] = str((CASE/LIBREL).resolve()) in seen
text = (OUTPUT/'f14_control_five_stdout.log').read_text()
record['no_actuator_recompile_observed'] = 'Creating new library' not in text and 'wmake libso' not in text
record['TILT_samples'] = len(re.findall(r'^TILT ', text, re.M))
record['time_values'] = [float(x) for x in re.findall(r'^Time = ([0-9.eE+-]+)', text, re.M)]
record['End_marker'] = bool(re.search(r'^End\s*$', text, re.M))

identity_observed = record.get('actual_child_identity', {})
record['actual_identity_passed'] = (identity_observed.get('uid') == 999
    and identity_observed.get('cwd') == str(CASE_FOR_IDENTITY.resolve())
    and identity_observed.get('exe') == str(BINARY_FOR_IDENTITY.resolve())
    and identity_observed.get('cmdline') == [str(BINARY_FOR_IDENTITY), '-case', str(CASE_FOR_IDENTITY)])
record['strict_protocol_input_audit'] = strict_input_binding

record['completed_utc'] = utc()
record['numerical_acceptance'] = 'Separate frozen-threshold analysis still required'
(OUTPUT/'f14_control_five_execution.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k: record[k] for k in ('actual_child_returncode', 'original_inputs_and_cached_library_unchanged',
    'expected_cached_actuator_library_actually_loaded', 'no_actuator_recompile_observed', 'TILT_samples', 'time_values', 'End_marker')}, indent=2))
assert record['actual_child_returncode'] == 0 and record['original_inputs_and_cached_library_unchanged']
assert record['expected_cached_actuator_library_actually_loaded'] and record['no_actuator_recompile_observed']

assert record['actual_identity_passed'] and record['TILT_samples'] == 5
assert record['time_values'] == [.6001,.6002,.6003,.6004,.6005] and record['End_marker']
