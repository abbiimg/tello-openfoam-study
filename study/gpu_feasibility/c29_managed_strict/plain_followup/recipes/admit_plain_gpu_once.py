"""Issue the single unprofiled same2.3 diagnostic receipt and Root approval."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess
WORK=Path(__file__).resolve().parent;OUT=WORK/'strict_runs'
PROPOSAL=OUT/'plain_gpu_diagnostic_proposal_v2'
BASE=Path('/opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102')
CASE=BASE/'plain_unprofiled_v2_3'
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102')
RECEIPT=BASE/'receipts/c29_plain_unprofiled_2_3_20261102_a.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def binding(p):return {'path':str(p),'sha256':sha(p)}
assert os.geteuid()==999 and os.environ['WM_OPTIONS']=='linuxARM64Nvidia-gpuDPInt32Opt'
assert not os.environ.get('LD_PRELOAD') and not os.environ.get('CUDA_INJECTION64_PATH')
assert sha(PROPOSAL/'protocol.json')=='e6e58d9e37514f0dc3b3f76bfaaf6a839612faef2fde095f3c38ebf3d24c6395'
assert sha(PROPOSAL/'helper_manifest.json')=='ed3bd4f82fe29b361cae7a1da5fedbabfb3394e5021a55ae2ed0007dbad0ee8f'
for name,pin in load(PROPOSAL/'helper_manifest.json')['files'].items():assert sha(PROPOSAL/name)==pin
review=OUT/'plain_gpu_diagnostic_v2_independent_review.json'
assert sha(review)=='c37cdfceaed267e0e3eb49ea4d8ab3f21b35e06936f812b9e9041f6cf6125c5a'
assert load(review)['blocking_findings']==[]
external=OUT/'root_f14_to_cpu_external_gate.json'
assert sha(external)=='9d1a7729b4368eba60bb7f298836c5f1866dde3dd6e9ab31e4221359edd9cfa2' and load(external)['root_asserted_pass']
startup=WORK/'strict_initial_shared_runs/initial_field_comparison.json'
assert load(startup)['startup_gate_passed']
integrity=WORK.parents[1]/'c29_native_field_second_pass.json'
gate=load(integrity);assert gate['all31_exact'] and gate['source_unchanged'] and len(gate['observations'])==31
assert all(x['sha256']==x['source_sha256'] and x['independent_native_windows_second_pass'] for x in gate['observations'])
preparation=OUT/'plain_gpu_fresh_clone_preparation.json'
assert sha(preparation)=='f28f05447812b6c74e81ebbb0c8583b5d9de543b673430db214ecf3b05d908bd'
prepared=load(preparation)
for rel,value in prepared['current_case_hashes'].items():assert sha(CASE/rel)==value,rel
assert not RECEIPT.exists() and not (OUT/'root_plain_gpu_approval.json').exists()
auditor=WORK.parent/'candidate/audit_candidate.py'
subprocess.run(['python3',str(auditor),'--case',str(CASE),'--private-root',str(BASE),
    '--backend','gpu','--phase','five_fixed_steps','--binary',str(PREFIX/'bin/c29ManagedHybridFoamStrict'),
    '--library-identity',str(PREFIX/'library_identity.json'),
    '--shared-phi-sha256','f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c',
    '--write-launch-receipt',str(RECEIPT)],check=True)
subprocess.run(['python3',str(auditor),'--verify-launch-receipt',str(RECEIPT)],check=True)
approval={'decision':'APPROVED_FOR_ONE_UNPROFILED_GPU_DIAGNOSTIC_SAME_2_3',
    'approved_utc':datetime.now(timezone.utc).isoformat(),
    'protocol_sha256':sha(PROPOSAL/'protocol.json'),'helper_manifest_sha256':sha(PROPOSAL/'helper_manifest.json'),
    'launch_receipt':binding(RECEIPT),'fresh_clone_preparation':binding(preparation),
    'root_f14_cpu_external_gate':{**binding(external),'root_asserted_pass':True},
    'exact_shared_startup_gate':{**binding(startup),'root_asserted_pass':True},
    'native_windows_31_field_integrity_gate':{**binding(integrity),'root_asserted_pass':True},
    'independent_review':binding(review),
    'scope':'One same-binary 180s direct unprofiled functional diagnostic. No debugger, profiler, observer, source/build/tolerance change. Numerical/GPU execution/performance qualification remain separate.'}
path=OUT/'root_plain_gpu_approval.json'
with path.open('x') as f:json.dump(approval,f,indent=2);f.write('\n')
print(json.dumps({'approval':str(path),'sha256':sha(path),'solver_launched':False},indent=2))
