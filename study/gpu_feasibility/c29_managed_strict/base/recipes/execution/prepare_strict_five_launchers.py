"""Create distinct one-shot strict-protocol launchers; never runs a solver."""
from pathlib import Path
import ast, hashlib, json
WORK = Path(__file__).resolve().parent
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def change(text, old, new):
    assert old in text, old
    return text.replace(old, new)
def save(name, text):
    target = WORK/name
    assert not target.exists()
    if name.endswith('.py'): ast.parse(text)
    with target.open('x', newline='\n') as stream: stream.write(text)
    return {'path':str(target),'sha256':sha(target)}
strict = '''
import sys
sys.path.insert(0, str(WORK/'strict_pressure_proposal'))
from strict_pressure_admission import validate_strict_audit
STRICT_AUDIT = WORK/'strict_runs/root_input_audit.json'
strict_input_binding = validate_strict_audit(STRICT_AUDIT, BASE, ROLES_TO_CHECK)
assert json.loads((WORK/'strict_initial_shared_runs/initial_field_comparison.json').read_text())['startup_gate_passed']
'''
identity_capture = '''
            proc = Path('/proc')/str(child.pid)
            if (proc/'exe').resolve() == BINARY_FOR_IDENTITY.resolve():
                uid_line = next(x for x in (proc/'status').read_text().splitlines() if x.startswith('Uid:'))
                record['actual_child_identity'] = {'pid':child.pid,
                    'uid':int(uid_line.split()[1]), 'cwd':str((proc/'cwd').resolve()),
                    'exe':str((proc/'exe').resolve()),
                    'cmdline':(proc/'cmdline').read_bytes().decode().strip('\\0').split('\\0'),
                    'birth_tick':record['actual_birth_tick']}
'''
checks = '''
identity_observed = record.get('actual_child_identity', {})
record['actual_identity_passed'] = (identity_observed.get('uid') == 999
    and identity_observed.get('cwd') == str(CASE_FOR_IDENTITY.resolve())
    and identity_observed.get('exe') == str(BINARY_FOR_IDENTITY.resolve())
    and identity_observed.get('cmdline') == [str(BINARY_FOR_IDENTITY), '-case', str(CASE_FOR_IDENTITY)])
record['strict_protocol_input_audit'] = strict_input_binding
'''
f14 = (WORK/'launch_f14_control_five_once.py').read_text()
f14 = change(f14, 'native_c29_validation_20261102/foundation14_control', 'native_c29_strict_pressure_20261102/foundation14_control')
f14 = change(f14, "WORK = Path(__file__).resolve().parent", "WORK = Path(__file__).resolve().parent\nBASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')\nOUTPUT = WORK/'strict_runs'\nOUTPUT.mkdir(exist_ok=True)")
f14 = change(f14, "assert os.geteuid() == 999", strict.replace('ROLES_TO_CHECK', "['f14']")+"\nassert os.geteuid() == 999")
f14 = change(f14, "(WORK/'initial_cpu_computed_phi_comparison.json')", "(WORK/'strict_initial_shared_runs/initial_field_comparison.json')")
f14 = change(f14, "(WORK/'f14_control_five_", "(OUTPUT/'f14_control_five_")
f14 = change(f14, "before = {", "assert sha(BINARY) == '3df39f3a5a3020c4dafee9d20063f9525a6556be874e9202aa5d122d0c9970da'\nassert sha(CASE/'0.6/phi') == 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'\nBINARY_FOR_IDENTITY, CASE_FOR_IDENTITY = BINARY, CASE\nbefore = {")
f14 = change(f14, 'Compute original constructor from pinned U; native CPU startup matched exactly', 'Read the predeclared byte-identical F14 starting phi, shared by all three backends')
f14 = change(f14, 'start_new_session=True)', 'start_new_session=True, cwd=CASE)')
f14 = change(f14, "        try:\n            for line", "        try:\n"+identity_capture+"            for line")
f14 = change(f14, "record['completed_utc'] = utc()", checks+"\nrecord['completed_utc'] = utc()")
f14 += "\nassert record['actual_identity_passed'] and record['TILT_samples'] == 5\nassert record['time_values'] == [.6001,.6002,.6003,.6004,.6005] and record['End_marker']\n"
cpu = (WORK/'launch_strict_shared_initial_once.py').read_text()
cpu = change(cpu, 'Fixed three-role strict-protocol initial-only experiments, selected by Root.\n\nNo arbitrary command, case, output or binary selection; no source/time loop.', 'Run the single Root-approved strict native CPU five-step validation once.\n\nFixed case/binary/output, strict input binding and exact shared-startup gates.')
cpu = change(cpu, "import signal", "import signal\nimport re")
cpu = change(cpu, "OUTPUT = WORK/'strict_initial_shared_runs'", "OUTPUT = WORK/'strict_runs'\nTAG = 'native_cpu_five'")
cpu = change(cpu, "assert role in ('cpu', 'gpu')", "assert role == 'cpu'")
cpu = change(cpu, "phase = 'foundation_initial_phi' if role == 'f14' else 'initial_fields_only'", "phase = 'five_fixed_steps'")
cpu = change(cpu, "OUTPUT.mkdir(exist_ok=True)", "OUTPUT.mkdir(exist_ok=True)\n"+strict.replace('ROLES_TO_CHECK', "['cpu']")+"\nBINARY_FOR_IDENTITY, CASE_FOR_IDENTITY = binary, case\nassert not any(p.is_dir() and re.fullmatch(r'[0-9.]+',p.name) and float(p.name) > .6 for p in case.iterdir())")
for suffix in ('execution.json','prelaunch.json','stdout.log'):
    cpu = change(cpu, "(role+'_"+suffix+"')", "(TAG+'_"+suffix+"')")
cpu = change(cpu, "expected_argv = [str(binary), '-case', str(case)] + ([] if role == 'f14' else ['-initialFieldsOnly'])", "expected_argv = [str(binary), '-case', str(case)]")
cpu = change(cpu, 'Actual shared-pinned-phi strict initial-only experiment; no source/time stepping', 'Actual five fixed steps, managed-ownership strict-pressure native CPU, functional validation only')
cpu = change(cpu, 'start_new_session=True)', 'start_new_session=True, cwd=case)')
cpu = change(cpu, "        try:\n            for line", "        try:\n"+identity_capture+"            for line")
cpu = change(cpu, 'start > 180:', 'start > 600:')
tail = cpu.index("expected_new = ['0.6/phi']")
cpu = cpu[:tail]+'''
text = (OUTPUT/(TAG+'_stdout.log')).read_text()
record['source_calls_observed'] = len(re.findall(r'^C29_SOURCE_AUDIT ',text,re.M))
record['controller_updates_observed'] = len(re.findall(r'^TILT ',text,re.M))
record['time_values'] = [float(x) for x in re.findall(r'^Time = ([0-9.eE+-]+)',text,re.M)]
record['timesteps_observed'] = len(record['time_values'])
record['End_marker'] = bool(re.search(r'^End\\s*$',text,re.M))
'''+checks+'''
record['completed_utc'] = utc()
record['numerical_acceptance'] = 'Separate frozen-threshold mechanical analysis required'
record['five_step_process_completed'] = (record['actual_child_returncode'] == 0
    and record['original_inputs_unchanged'] and record['declared_libraries_actually_observed_unchanged']
    and record['source_calls_observed'] == record['controller_updates_observed'] == record['timesteps_observed'] == 5
    and record['time_values'] == [.6001,.6002,.6003,.6004,.6005]
    and record['End_marker'] and record['actual_identity_passed'])
(OUTPUT/(TAG+'_execution.json')).write_text(json.dumps(record,indent=2)+'\\n')
print(json.dumps({k:record[k] for k in ('role','actual_child_returncode','original_inputs_unchanged',
    'declared_libraries_actually_observed_unchanged','actual_identity_passed','five_step_process_completed')},indent=2))
assert record['five_step_process_completed']
'''
entries = [save('launch_strict_f14_five_once.py',f14),save('launch_strict_cpu_five_once.py',cpu)]
for role, environment in [('f14','/opt/openfoam14/etc/bashrc'),('cpu','/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_cpu_managed_strict_v2_3_20261102/build_environment.sh')]:
    command = f"python3 {WORK.as_posix()}/launch_strict_{role}_five_once.py"+(' --role cpu' if role == 'cpu' else '')
    shell = f'#!/bin/bash\nsource {environment}\nset -euo pipefail\nexport OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1\nexec {command}\n'
    entries.append(save('launch_strict_'+role+'_five_once.sh',shell))
record = {'source_only':True,'case_or_receipt_mutated':False,'solver_launched':False,
    'original_F14_launcher_sha256':sha(WORK/'launch_f14_control_five_once.py'),
    'original_shared_initial_launcher_sha256':sha(WORK/'launch_strict_shared_initial_once.py'),
    'new_launchers':entries}
save('strict_five_launcher_preparation.json',json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
