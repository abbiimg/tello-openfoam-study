"""Prepare reviewed source combination and two isolated build clones; no run."""
from pathlib import Path
from datetime import datetime,timezone
import difflib,hashlib,json,os,pwd
BASE=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port')
OWN=BASE/'ownership_candidate_v2_3_source_only_b'
STRICT=BASE/'execution/strict_pressure_proposal'
OUT=BASE/'managed_strict_combined_v2_3'
PARENT=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation')
PINS={'ownership_proposal_manifest.json':'689b261f3a91f280719ba575d48b4b56187cc442cf032728dd8f80ba63088203','ownership_only.patch':'85439b77952af6e249af54bf3576c5517fb570a1e4d0324e5617585fe193dcb9'}
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def dump(path,obj):Path(path).write_text(json.dumps(obj,indent=2)+'\n')
def checked_directory(path):
 for parent in (path,*path.parents):
  if parent.is_symlink():raise RuntimeError('Symlink in new owned prefix')
 if path.exists():raise RuntimeError('Refusing existing destination '+str(path))
def content_copy(source,destination):
 destination.mkdir(parents=True)
 for p in source.rglob('*'):
  if p.is_symlink():raise RuntimeError('Unexpected source symlink '+str(p))
  if p.is_file():
   q=destination/p.relative_to(source);q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes())
def main():
 assert pwd.getpwuid(os.geteuid()).pw_name=='openfoam'
 for name,pin in PINS.items():assert sha(OWN/name)==pin
 review_path=BASE/'ownership_candidate_v2_3_independent_review.json'
 review=json.loads(review_path.read_text())
 assert review['verdict']=='ACCEPTABLE_FOR_CONTROLLED_COMPILATION_AND_FULL_SIZE_INITIAL_ONLY_GATE' and not review['blocking_findings']
 own_manifest=json.loads((OWN/'ownership_proposal_manifest.json').read_text())
 for name,pin in own_manifest['files'].items():assert sha(OWN/name)==pin
 assert sha(STRICT/'C29Restrictions.H')=='217b76d552ed28e9c5bd37b010cd036ce87717a79aef8a745716e66d26b93164'
 checked_directory(OUT)
 for backend in ['cpu','gpu']:checked_directory(PARENT/f'native_{backend}_managed_strict_v2_3_20261102')
 OUT.mkdir();source=OUT/'source';content_copy(OWN,source)
 (source/'C29Restrictions.H').write_bytes((STRICT/'C29Restrictions.H').read_bytes())
 original=(OWN/'Make/files').read_text()
 old='EXE = $(C29_APPBIN)/c29NativeHybridFoam'
 assert original.count(old)==1
 (source/'Make/files').write_text(original.replace(old,'EXE = $(C29_APPBIN)/c29ManagedHybridFoamStrict'))
 original_files={str(p.relative_to(OWN)):sha(p) for p in OWN.rglob('*') if p.is_file()}
 files={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
 changes=[name for name,pin in original_files.items() if files[name]!=pin]
 assert sorted(changes)==['C29Restrictions.H','Make/files']
 patch=''.join(''.join(difflib.unified_diff((OWN/name).read_text().splitlines(keepends=True),(source/name).read_text().splitlines(keepends=True),fromfile='reviewed_ownership_b/'+name,tofile='managed_strict_v2_3/'+name)) for name in sorted(changes))
 (OUT/'limited_combination.patch').write_text(patch)
 tree_sha=hashlib.sha256(''.join(name+'\0'+pin+'\n' for name,pin in sorted(files.items())).encode()).hexdigest()
 manifest={'schema':'c29-managed-strict-combined-source-v2.3','created_utc':datetime.now(timezone.utc).isoformat(),'status':'APPROVED_COMBINATION_FOR_CONTROLLED_COMPILATION_ONLY_NO_RUNTIME','method':'c29-native-managed-hybrid-strict-pressure-v2.3','source_pin':'b239fea6e48922730477e218c44e8b6a8ab17ade','source_directory':str(source),'source_tree_hash_algorithm':'SHA256(sorted UTF8 relative-name + NUL + file-SHA256 + newline)','source_tree_sha256':tree_sha,'files':files,'source_changes_from_reviewed_ownership_b':changes,'ownership_manifest_sha256':sha(OWN/'ownership_proposal_manifest.json'),'ownership_patch_sha256':sha(OWN/'ownership_only.patch'),'independent_review':{'path':str(review_path),'sha256':sha(review_path),'verdict':review['verdict']},'strict_restrictions_sha256':sha(source/'C29Restrictions.H'),'strict_protocol_sha256':sha(STRICT/'strict_pressure_protocol.json'),'root_strict_authorization_sha256':sha(STRICT/'root_authorization.json'),'limited_combination_patch_sha256':sha(OUT/'limited_combination.patch'),'verbatim_body_sha256':sha(source/'C29_body_verbatim.inc'),'verbatim_includes_sha256':sha(source/'C29_includes_verbatim.inc'),'validation_thresholds_sha256':sha(source/'validation_thresholds.json'),'copied_historical_candidate_manifests_and_source_only_notes_are_reference_only':True,'application_runtime_authorized':False,'case_mutations_authorized':False,'compiler_jobs_total_max':2,'compiler_jobs_per_backend_max':1,'nice':15,'minimum_MemAvailable_GiB':20,'generator_sha256':sha(__file__)}
 dump(OUT/'combined_source_manifest.json',manifest)
 methods={}
 for backend in ['cpu','gpu']:
  prefix=PARENT/f'native_{backend}_managed_strict_v2_3_20261102';prefix.mkdir();(prefix/'bin').mkdir();content_copy(source,prefix/'source')
  for name,pin in files.items():assert sha(prefix/'source'/name)==pin
  env=Path('/opt/openfoam-workspace/gpu-feasibility')/('native-cpu-control' if backend=='cpu' else 'native-stdpar')/'env.sh'
  old_identity=PARENT/f'native_{backend}_compat_v2_2_20261102/library_identity.json'
  identity=json.loads(old_identity.read_text())
  for record in identity['files']:assert sha(record['path'])==record['sha256']
  method={'schema':'c29-private-managed-strict-build-method-v2.3','method':manifest['method'],'backend':backend,'prefix':str(prefix),'binary_name':'c29ManagedHybridFoamStrict','source_tree_sha256':tree_sha,'source_files':files,'combined_source_manifest':{'path':str(OUT/'combined_source_manifest.json'),'sha256':sha(OUT/'combined_source_manifest.json')},'environment':{'path':str(env),'sha256':sha(env)},'native_source_pin':manifest['source_pin'],'C29_USE_CUDA':int(backend=='gpu'),'C29_USE_NVTX':1,'prior_library_identity':{'path':str(old_identity),'sha256':sha(old_identity)},'prior_libraries_all_unchanged_before_build':True,'compiler_jobs_max':1,'nice':15,'compiler_jobs_both_backends_max':2,'runtime_authorized':False,'no_case_created_or_modified':True,'original_versions_preserved':True}
  dump(prefix/'method_identity.json',method);dump(OUT/f'{backend}_method_identity.json',method);methods[backend]={'prefix':str(prefix),'method_identity_sha256':sha(prefix/'method_identity.json')}
 summary={'source_tree_sha256':tree_sha,'combined_source_manifest_sha256':sha(OUT/'combined_source_manifest.json'),'limited_patch_sha256':sha(OUT/'limited_combination.patch'),'changed_source_files':changes,'methods':methods,'compiled':False,'application_executed':False}
 dump(OUT/'preparation.json',summary);print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
