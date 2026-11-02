"""Correct the flag-token collector gate on ALREADY LINKED files; no rebuild."""
from pathlib import Path
import json,shlex,subprocess
import build_combined_managed_strict as worker
w=worker.WORK;p=worker.BASE/'native_cpu_managed_strict_v2_3_20261102'
progress=json.loads((w/'build_progress.json').read_text())
assert progress['status']=='failed_preserve_evidence'
assert progress['backends']['cpu']['exit_code']==0 and progress['backends']['gpu']['exit_code']==0
archive=w/'attempt_b_cpu_collector_substring_failure';archive.mkdir()
(archive/'build_progress.json').write_bytes((w/'build_progress.json').read_bytes())
private_archive=p/'attempt_b_cpu_collector_substring_failure';private_archive.mkdir()
for n in ['runtime_dependency_audit.log','library_identity.json','elf_dynamic.log','elf_header.log']:(private_archive/n).write_bytes((p/n).read_bytes())
cpu_binary=p/'bin/c29ManagedHybridFoamStrict';cpu_sha=worker.sha(cpu_binary)
gpu=worker.BASE/'native_gpu_managed_strict_v2_3_20261102'
gpu_identity_sha=worker.sha(gpu/'linked_identity.json');gpu_binary_sha=worker.sha(gpu/'bin/c29ManagedHybridFoamStrict')
manifest=json.loads((w/'combined_source_manifest.json').read_text())
method=json.loads((p/'method_identity.json').read_text());child=json.loads((p/'actual_child.json').read_text())
result=worker.collect('cpu',p,method,manifest,child)
assert worker.sha(cpu_binary)==cpu_sha and worker.sha(gpu/'bin/c29ManagedHybridFoamStrict')==gpu_binary_sha
assert worker.sha(gpu/'linked_identity.json')==gpu_identity_sha
gpu_record=json.loads((gpu/'linked_identity.json').read_text())
gpu_commands=gpu_record['actual_compile_and_link_commands']
gpu_compile=next(x for x in gpu_commands if ' -c ' in x)
gpu_tokens=shlex.split(gpu_compile)
gpu_offload=[x for x in gpu_tokens if x=='-DFOAM_OFFLOAD' or x.startswith(('-stdpar=','-gpu='))]
assert '-DC29_USE_CUDA=1' in gpu_tokens and all(x in gpu_offload for x in ['-DFOAM_OFFLOAD','-stdpar=gpu','-gpu=cc121,mem:managed'])
note={'schema':'c29-linked-artifact-collector-recovery-v1','created_utc':worker.now(),'cause':'String-substring flag screen matched native-stdpar in verified NVTX INCLUDE PATH; actual compile tokens and CPU linked libraries contain no CUDA/offload backend','source_or_flags_modified':False,'rebuild':False,'application_executed':False,'case_mutated':False,'original_failed_collector_preserved':str(archive),'cpu_actual_compile_tokens':result['actual_compile_tokens'],'cpu_actual_offload_flag_tokens':result['actual_offload_flag_tokens'],'gpu_actual_compile_tokens':gpu_tokens,'gpu_actual_offload_flag_tokens':gpu_offload,'cpu_binary_sha256':cpu_sha,'gpu_binary_sha256':gpu_binary_sha,'gpu_completed_identity_unmodified_sha256':gpu_identity_sha,'collector_fixed_source_sha256':worker.sha(worker.__file__),'recovery_script_sha256':worker.sha(__file__)}
worker.dump(w/'collector_recovery.json',note)
progress['backends']['cpu'].update(status='linked_no_runtime',binary_sha256=cpu_sha,linked_identity_sha256=worker.sha(p/'linked_identity.json'),collector_recovery_sha256=worker.sha(w/'collector_recovery.json'))
progress['backends']['cpu'].pop('error',None);progress['backends']['cpu'].pop('traceback',None)
progress.update(status='complete_linked_no_runtime',collection_recovered_utc=worker.now(),collector_recovery_sha256=worker.sha(w/'collector_recovery.json'))
worker.dump(w/'build_progress.json',progress)
print(json.dumps({'status':progress['status'],'CPU_binary_sha256':cpu_sha,'GPU_binary_sha256':gpu_binary_sha,'source_tree_sha256':manifest['source_tree_sha256'],'CPU_offload_tokens':result['actual_offload_flag_tokens'],'GPU_offload_tokens':gpu_offload,'runtime':False,'rebuild':False},indent=2))
