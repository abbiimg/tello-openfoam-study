"""Apply the preregistered identical-F14-phi fallback before any strict steps."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import shutil

WORK = Path(__file__).resolve().parent
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
ARCHIVE = Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/strict_initial_computed_archive_20261102')
assert os.geteuid() == 999 and not ARCHIVE.exists()
for p in (ARCHIVE, *ARCHIVE.parents, BASE, *BASE.parents): assert not p.is_symlink()
report_path = WORK/'strict_initial_runs/initial_field_comparison.json'
report = json.loads(report_path.read_text())
assert not report['startup_gate_passed'] and report['roles']['cpu']['all_values_exact']
assert report['roles']['gpu']['fields']['U']['all_internal_and_boundary_value_blocks_exact']
assert report['roles']['gpu']['fields']['P']['all_internal_and_boundary_value_blocks_exact']
assert not report['roles']['gpu']['fields']['Phi']['all_internal_and_boundary_value_blocks_exact']
assert json.loads((WORK/'strict_initial_runs/f14_execution.json').read_text())['initialization_completed']
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
canonical = BASE/'foundation14_control/0.6/phi'
canonical_sha = sha(canonical)
assert canonical_sha == 'f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c'
plan = json.loads((WORK.parent/'candidate/validation_recipe.json').read_text())
spec = importlib.util.spec_from_file_location('root_admission', WORK.parent/'candidate/admission_audit.py')
reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
ARCHIVE.mkdir()
roles = {}
for role in ('cpu', 'gpu'):
    case = BASE/('native_'+role)
    for rel, item in plan['unchanged_input_hashes'].items(): assert sha(case/rel) == item['sha256'], rel
    assert not (case/'0.6/phi').exists()
    archive = ARCHIVE/role; archive.mkdir()
    moved = {}
    for field in ('U', 'P', 'Phi'):
        source = case/'0.6'/('c29_initial'+field)
        assert sha(source) == report['roles'][role]['fields'][field]['candidate_sha256']
        target = archive/source.name
        assert target.resolve().is_relative_to(ARCHIVE) and not target.exists()
        os.rename(source, target)
        moved[str(source)] = {'archive': str(target), 'sha256': sha(target)}
    target = case/'0.6/phi'
    with canonical.open('rb') as src, target.open('xb') as dst: shutil.copyfileobj(src, dst, 1024*1024)
    assert sha(target) == canonical_sha
    control = case/'constant/c29PortControls'
    original = control.read_text()
    assert reader.setting(original, 'initialPhiPolicy') == 'computeFromPinnedU'
    assert reader.setting(original, 'allowFiveStepSourceExperiment') == 'false'
    (archive/'c29PortControls.before_shared').write_bytes(control.read_bytes())
    experiment = 'c29_strict_shared_initial_'+role+'_20261102_a'
    receipt = BASE/'receipts'/(experiment+'.foam')
    edits = {'initialPhiPolicy': 'sharedPinnedPhi',
        'experimentId': json.dumps(experiment), 'experimentReceiptFile': json.dumps(str(receipt))}
    updated = original
    for key, value in edits.items():
        pattern = r'(?m)^(\s*'+key+r'\s+)(?:"[^"\n]*"|[^;\n]+)\s*;'
        updated, count = re.subn(pattern, lambda m: m[1]+value+';', updated)
        assert count == 1, key
    control.write_text(updated)
    for rel, item in plan['unchanged_input_hashes'].items(): assert sha(case/rel) == item['sha256'], rel
    roles[role] = {'copied_phi_sha256': sha(target), 'moved_initial_audit_files': moved,
        'controls_before_sha256': hashlib.sha256(original.encode()).hexdigest(),
        'controls_after_sha256': sha(control), 'experiment_id': experiment,
        'new_receipt_json': str(receipt.with_suffix('.json'))}
assert sha(canonical) == canonical_sha
record = {'kind': 'Predeclared exact-startup fallback, not a relaxed equality threshold',
    'reason': 'GPU computed initial phi differs by at most3.1742559698354905e-19; U/p and CPU phi exact',
    'failed_computed_startup_report_sha256': sha(report_path),
    'canonical_F14_phi': str(canonical), 'canonical_phi_sha256': canonical_sha,
    'policy': 'Copy one identical F14 output into both native backends; F14 control already owns same bytes',
    'roles': roles, 'all_original_U_p_mesh_source_schemes_parameters_unchanged': True,
    'no_controller_or_timestep': True, 'exact_startup_gate_must_be_repeated': True}
output = WORK/'strict_initial_shared_fallback.json'
assert not output.exists()
output.write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({'canonical_phi_sha256': canonical_sha, 'roles': list(roles), 'archived_previous_audits': str(ARCHIVE)}, indent=2))
