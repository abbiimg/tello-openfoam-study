"""Freeze metadata/helpers for one existing tiny positive control; no GPU."""
from pathlib import Path
import ast,hashlib,json,re,shlex,subprocess
W=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work')
P=W/'native_stdpar_install/nsys_2026_5_positive_control_proposal'
N=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar');NEW=Path('/opt/openfoam-workspace/gpu-feasibility/nsight-systems-2026.5.1')
nsys=NEW/'extracted/opt/nvidia/nsight-systems-cli/2026.5.1/bin/nsys';binary=N/'user/platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin/Test-nativeStdparFields';source=N/'field_algebra_gate/Test-nativeStdparFields.C';core=N/'source/OpenFOAM-v2606/platforms/linuxARM64Nvidia-gpuDPInt32Opt/lib/libOpenFOAM.so';case=Path('/opt/openfoam-workspace/cases/native_stdpar_gpu_pilots_20261102/field_algebra_gate')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def record(p):return {'path':str(p),'sha256':sha(p)}
def dump(p,d):p.write_text(json.dumps(d,indent=2)+'\n')
assert not (P/'protocol.json').exists();assert sha(nsys)=='dbe02661b00efbfb4c9c3cd3c2d8df6fecd6e80ac794305892e233e0d712a527';assert sha(binary)=='df5772176bdbe30ef5c596b883c844ff39bbd58195319b64eefdfdd284c1d4cb';assert sha(core)=='7d4befeac01a410631071f7edcb887de17a8b7937950d5a4ebc14058426bcbfb';assert sha(source)=='046dfc47664ff9b29544bfbb78d395ca9c745623d906b7af844c5c24d416a88b'
help_run=subprocess.run([str(nsys),'profile','--help'],capture_output=True,text=True);assert help_run.returncode==0;help_text=help_run.stdout+help_run.stderr
for flag in ['--discard-environment=','--capture-range-end=','--cuda-trace-scope=','--kill=','--wait=','--nvtx-capture=']:assert flag in help_text
ldd=subprocess.run(['/bin/bash','-c','. '+shlex.quote(str(N/'env.sh'))+'\nldd '+shlex.quote(str(binary))],capture_output=True,text=True);assert ldd.returncode==0 and 'not found' not in ldd.stdout
libraries=[]
for line in ldd.stdout.splitlines():
 match=re.search(r'(?:=>\s+)?(/\S+)\s+\(',line)
 if match:
  r=record(Path(match[1]).resolve())
  if r not in libraries:libraries.append(r)
assert record(core) in libraries
dump(P/'linked_libraries.json',{'files':libraries,'method':'ldd under matching private native env; no application main executed'})
cleanup=W/'gpu_actuator_port/execution/strict_runs/gpu_profile_proposal_v3/owned_cleanup.py';assert sha(cleanup)=='c50601d01b0513cfe94892578e2a00b4d2f3fba58b7c312cbeeb81b778b67203';(P/'owned_cleanup.py').write_bytes(cleanup.read_bytes())
prior=json.loads((N/'provenance/native_field_post_resume_gate.json').read_text())
p={'schema':'new-nsight-2026.5.1-existing-native-field-positive-control-v1','status':'SOURCE_ONLY_PENDING_ROOT_APPROVAL_NO_GPU_RUN','binary':record(binary),'source':record(source),'core_library':record(core),'nsys':record(nsys),'new_tool_installation_receipt':record(NEW/'installation_receipt.json'),'native_environment':record(N/'env.sh'),'library_identity':record(P/'linked_libraries.json'),'plain_failure_reconciliation':record(W/'gpu_actuator_port/execution/strict_runs/root_plain_gpu_failed_terminal_reconciliation.json'),'prior_positive_control':record(N/'provenance/native_field_post_resume_gate.json'),'case':str(case),'case_files':{str(x.relative_to(case)):sha(x) for x in case.rglob('*') if x.is_file()},'command':[str(binary),'-case',str(case)],'range':'NATIVE_STDPAR_FIELD_ALGEBRA','expected_arithmetic_result':prior['result'],'application_timeout_s':30,'cleanup_grace_s':5,'profiler_timeout_s':110,'export_timeout_s':60,'maximum_GPU_applications':1,'minimum_MemAvailable_GiB':20,'nice':15,'nsys_flags':['--trace=cuda,nvtx','--sample=none','--cpuctxsw=none','--capture-range=nvtx','--nvtx-capture=NATIVE_STDPAR_FIELD_ALGEBRA','--capture-range-end=stop','--kill=none','--cuda-trace-scope=process-tree','--wait=all','--discard-environment=true','--stats=false','--force-overwrite=false'],'profile_child_environment_only':{'NSYS_NVTX_PROFILER_REGISTER_ONLY':'0'},'evidence':str(NEW/'native_field_positive_control_20261102'),'help_verification':{'profile_help_sha256':hashlib.sha256(help_text.encode()).hexdigest(),'required_flags_supported':True,'no_GPU_or_app_launch':True},'scope':'Existing Field algebra and new profiler dependency verification only; no CFD, geometry, timestep, build, 2.4 adoption or timing','C29_large_transient_status':'FAILED_UNQUALIFIED in both profiled and plain2.3 attempts','GPU_action_authorized_by_this_preparation':False}
dump(P/'protocol.json',p)
for f in P.glob('*.py'):ast.parse(f.read_text(),filename=f.name)
m={'schema':'new-nsys-native-field-control-helper-freeze-v1','status':'SOURCE_ONLY_PENDING_ROOT_APPROVAL','files':{f.name:sha(f) for f in sorted(P.iterdir()) if f.is_file() and f.name!='helper_manifest.json'},'generator_sha256':sha(__file__),'source_probe_case_libraries_or_SDK_changed':False,'case_created_or_CFD_run':False,'GPU_run':False,'AST_parse_only_helpers_not_imported':True}
dump(P/'helper_manifest.json',m);print(json.dumps({'protocol_sha256':sha(P/'protocol.json'),'helper_manifest_sha256':sha(P/'helper_manifest.json'),'files':m['files']},indent=2))
