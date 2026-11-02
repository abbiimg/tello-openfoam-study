"""Prepare the two fixed shared-phi initial-only reruns; no launch."""
from pathlib import Path
import ast
import json
work = Path(__file__).resolve().parent
fallback = json.loads((work/'strict_initial_shared_fallback.json').read_text())
source = (work/'launch_strict_initial_once.py').read_text()
source = source.replace("OUTPUT = WORK/'strict_initial_runs'", "OUTPUT = WORK/'strict_initial_shared_runs'")
source = source.replace("role = ap.parse_args().role", "role = ap.parse_args().role\nassert role in ('cpu', 'gpu')")
source = source.replace("assert not (case/'0.6/phi').exists()", "assert sha(case/'0.6/phi') == '"+fallback['canonical_phi_sha256']+"'")
needle="'--backend', backend, '--phase', phase, '--binary', str(binary), '--library-identity', str(identity),"
assert source.count(needle) == 1
source = source.replace(needle, needle+"\n    '--shared-phi-sha256', '"+fallback['canonical_phi_sha256']+"',")
source = source.replace("'kind': 'Actual strict-protocol initial-only experiment; no source/time stepping'", "'kind': 'Actual shared-pinned-phi strict initial-only experiment; no source/time stepping'")
ast.parse(source)
target = work/'launch_strict_shared_initial_once.py'
assert not target.exists()
target.write_text(source)
shell = (work/'launch_strict_initial_once.sh').read_text().replace('launch_strict_initial_once.py', 'launch_strict_shared_initial_once.py')
target = work/'launch_strict_shared_initial_once.sh'
assert not target.exists()
target.write_text(shell)
print('Prepared two fixed shared-phi startup reruns')
