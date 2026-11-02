"""Mechanical source check only: deliberately does not compile or launch CFD."""
from pathlib import Path
import hashlib,json
ROOT=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/ownership_candidate_v2_3_source_only_b')
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
manifest=json.loads((ROOT/'ownership_proposal_manifest.json').read_text())
reference=Path(manifest['reference_source'])
reversals=json.loads((ROOT/'ownership_declaration_reversal_map.json').read_text())
texts={name:(ROOT/name).read_text() for name in sorted({x['file'] for x in reversals})}
for item in reversed(reversals):
 if texts[item['file']].count(item['after'])!=1:raise RuntimeError('Nonunique reverse declaration')
 texts[item['file']]=texts[item['file']].replace(item['after'],item['before'])
for name in ['c29NativeHybridFoam.C','C29Operators.H','C29HostSource.H']:
 texts[name]=texts[name].replace('#include "C29ManagedOwnership.H"\n','')
for line in [
 '            C29::managedMatrix(UEqn,"UEqn_existing_tmp_heap");\n',
 '                C29::managedMatrix(predictor(),"predictor_existing_tmp_heap");\n']:
 if texts['c29NativeHybridFoam.C'].count(line)!=1:raise RuntimeError('Missing main instrumentation line')
 texts['c29NativeHybridFoam.C']=texts['c29NativeHybridFoam.C'].replace(line,'')
for line in [
 '    C29::managedMatrix(result(),"momentum_result_existing_tmp_heap");\n',
 '    C29::managedGeometricField(result(),"Euler_result_existing_tmp_heap");\n']:
 if texts['C29Operators.H'].count(line)!=1:raise RuntimeError('Missing operator instrumentation line')
 texts['C29Operators.H']=texts['C29Operators.H'].replace(line,'')
texts['createC29Fields.H']=texts['createC29Fields.H'].replace('#include "createC29ManagedPhi.H"','#include "createPhi.H"')
checks={name:text==(Path(manifest['phi_initializer_preserved_from']) if name=='createC29ManagedPhi.H' else reference/name).read_text() for name,text in texts.items()}
if not all(checks.values()):raise RuntimeError('Ownership reverse changed numerical source: '+str(checks))
unchanged={name:sha(reference/name)==expected for name,expected in manifest['original_reference_files_sha256'].items()}
if not all(unchanged.values()):raise RuntimeError('Reference source changed')
result={'method':'Remove address-check instrumentation, substitute each exact original declaration from the recorded map, and compare complete source text byte-for-byte with native2.2 or pinned vendor createPhi.H. This is not a compilation or runtime test.','all_reversed_sources_exact':all(checks.values()),'source_matches':checks,'original_reference_unchanged':all(unchanged.values()),'declarations_reversed':len(reversals),'compiled':False,'CFD_run':False,'no_new_pressure_controls_or_tolerances':True,'patch_sha256':sha(ROOT/'ownership_only.patch'),'manifest_sha256':sha(ROOT/'ownership_proposal_manifest.json'),'checker_sha256':sha(__file__)}
(ROOT/'mechanical_source_check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
