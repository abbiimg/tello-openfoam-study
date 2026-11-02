"""Exact all-value startup gate for the new managed strict source/binaries."""
from pathlib import Path
import hashlib
import importlib.util
import json

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
reader_path = WORK/'compare_initial_cpu.py'
assert hashlib.sha256(reader_path.read_bytes()).hexdigest() == '071202fdd5e9fa623f98701054e48ebea39d271be78171ce228a665b9292850c'
spec = importlib.util.spec_from_file_location('root_initial_field_reader', reader_path)
reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
report = {'kind': 'Exact full-size startup gate, managed-ownership strict-pressure variant',
    'source_tree_sha256': 'ad01489971b0b65d86eaf5f88fb51347ed9337bd1afeb570a6fc8c003c49f99b',
    'roles': {}, 'shared_phi_fallback_used': True}
for role in ('cpu', 'gpu'):
    execution = json.loads((WORK/'strict_initial_shared_runs'/(role+'_execution.json')).read_text())
    assert execution['initialization_completed']
    fields = {}
    for field, reference in [('U', BASE/'foundation14_control/0.6/U'),
                             ('P', BASE/'foundation14_control/0.6/p'),
                             ('Phi', BASE/'foundation14_control/0.6/phi')]:
        fields[field] = reader.compare(reference, BASE/('native_'+role)/'0.6'/('c29_initial'+field))
    report['roles'][role] = {'fields': fields,
        'all_values_exact': all(f['all_internal_and_boundary_value_blocks_exact'] for f in fields.values())}
report['startup_gate_passed'] = all(r['all_values_exact'] for r in report['roles'].values())
report['scope'] = 'Initial U/p/phi internal and every stored boundary value block only; no source/timestep/performance acceptance'
output = WORK/'strict_initial_shared_runs/initial_field_comparison.json'
assert not output.exists()
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({'startup_gate_passed': report['startup_gate_passed'], 'roles': {
    role: {field: {'exact': f['all_internal_and_boundary_value_blocks_exact'],
        'maximum_absolute_difference': max(b['maximum_absolute_difference'] for b in f['blocks'])}
        for field, f in row['fields'].items()} for role, row in report['roles'].items()}}, indent=2))

