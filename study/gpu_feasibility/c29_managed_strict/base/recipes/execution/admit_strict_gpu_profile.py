"""Issue one fresh Root-approved GPU five-step receipt; does not launch a solver."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess
WORK = Path(__file__).resolve().parent
OUT = WORK/'strict_runs'
PROPOSAL = OUT/'gpu_profile_proposal_v3'
BASE = Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
PREFIX = Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102')
RECEIPT = BASE/'receipts/c29_strict_shared_five_gpu_20261102_a.json'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p): return json.loads(p.read_text())
def binding(p): return {'path':str(p),'sha256':sha(p)}
assert os.geteuid() == 999 and os.environ['WM_OPTIONS'] == 'linuxARM64Nvidia-gpuDPInt32Opt'
assert sha(PROPOSAL/'protocol.json') == 'ef302349a02d6fc507773e9a7ec70d8c7176db51fbf3046f424e7e8381148cf0'
assert sha(PROPOSAL/'helper_manifest.json') == '467b014b9fefe74ac76f26e7efe7bb0206994792cbe7e32d85c362dbbca1c5cb'
for name,pin in load(PROPOSAL/'helper_manifest.json')['files'].items(): assert sha(PROPOSAL/name) == pin
review_path = OUT/'root_gpu_profile_static_review.json'
review = load(review_path)
assert review['decision'] == 'APPROVED_FOR_ONE_GPU_FIVE_STEP_FUNCTIONAL_PROFILE'
assert review['helper_manifest_sha256'] == sha(PROPOSAL/'helper_manifest.json')
independent = review['independent_review']
assert sha(Path(independent['path'])) == independent['sha256']
external = OUT/'root_f14_to_cpu_external_gate.json'
assert sha(external) == '9d1a7729b4368eba60bb7f298836c5f1866dde3dd6e9ab31e4221359edd9cfa2'
assert load(external)['root_asserted_pass'] is True
startup = WORK/'strict_initial_shared_runs/initial_field_comparison.json'
assert load(startup)['startup_gate_passed'] is True
assert not RECEIPT.exists() and not (OUT/'root_gpu_profile_approval.json').exists()
command = ['python3',str(WORK.parent/'candidate/audit_candidate.py'),
    '--case',str(BASE/'native_gpu'),'--private-root',str(BASE),'--backend','gpu',
    '--phase','five_fixed_steps','--binary',str(PREFIX/'bin/c29ManagedHybridFoamStrict'),
    '--library-identity',str(PREFIX/'library_identity.json'),
    '--shared-phi-sha256','f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c',
    '--write-launch-receipt',str(RECEIPT)]
subprocess.run(command,check=True)
subprocess.run(['python3',str(WORK.parent/'candidate/audit_candidate.py'),'--verify-launch-receipt',str(RECEIPT)],check=True)
approval = {'decision':'APPROVED_FOR_ONE_GPU_FIVE_STEP_FUNCTIONAL_PROFILE',
    'approved_utc':datetime.now(timezone.utc).isoformat(),
    'protocol_sha256':sha(PROPOSAL/'protocol.json'),
    'helper_manifest_sha256':sha(PROPOSAL/'helper_manifest.json'),
    'launch_receipt':binding(RECEIPT),
    'exact_shared_startup_gate':{**binding(startup),'root_asserted_pass':True},
    'f14_to_cpu_strict_numerical_gate':{**binding(external),'root_asserted_pass':True},
    'static_review':binding(review_path),
    'scope':'One bounded five-step functional profile only. Separate unchanged d600 numerical analysis and Root external review remain mandatory. No performance or production adoption is approved.'}
path = OUT/'root_gpu_profile_approval.json'
with path.open('x') as stream: json.dump(approval,stream,indent=2);stream.write('\n')
print(json.dumps({'approval':str(path),'approval_sha256':sha(path),'receipt_sha256':sha(RECEIPT),
    'solver_launched':False},indent=2))
