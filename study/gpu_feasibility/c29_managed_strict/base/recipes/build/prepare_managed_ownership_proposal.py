"""Source-only ownership adaptation from immutable native2.2; NEVER compile/run."""
from pathlib import Path
from datetime import datetime,timezone
import difflib,hashlib,json,re,shutil
WORK=Path(__file__).resolve().parent
SOURCE=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_compat_v2_2_20261102/source')
TARGET=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/ownership_candidate_v2_3_source_only_b')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def replace_once(text,before,after):
 if text.count(before)!=1:raise RuntimeError('Non-unique ownership match: '+before[:70])
 return text.replace(before,after)
inventory=[];reversals=[]
def own(text,typ,name,file,kind='geometric',reason='Reference-captured framework descriptor'):
 pattern=r'(?m)^([ \t]*)'+re.escape(typ)+r'\s+'+re.escape(name)+r'\s*\('
 matches=list(re.finditer(pattern,text))
 if len(matches)!=1:raise RuntimeError('Expected one declaration '+file+':'+name)
 match=matches[0];start=match.start();paren=text.index('(',match.start());depth=0;quote=None;escaped=False;end=None
 for i in range(paren,len(text)):
  c=text[i]
  if quote:
   if escaped:escaped=False
   elif c=='\\':escaped=True
   elif c==quote:quote=None
   continue
  if c in ['"',"'"]:quote=c
  elif c=='(':depth+=1
  elif c==')':
   depth-=1
   if depth==0:end=i+1;break
 if end is None or text[end:].lstrip()[0]!=';':raise RuntimeError('Constructor delimiter missing')
 semicolon=end+len(text[end:])-len(text[end:].lstrip())
 original=text[start:semicolon+1];indent=match[1];args=text[paren:end]
 owner=name+'Owner';checker='managedMatrix' if kind=='matrix' else 'managedGeometricField'
 replacement=(indent+'autoPtr<'+typ+'> '+owner+'\n'+indent+'(\n'+indent+'    new '+typ+args+'\n'+indent+');\n'+indent+typ+'& '+name+'='+owner+'();\n'+indent+'C29::'+checker+'('+name+',"'+name+'");')
 reversals.append({'file':file,'before':original,'after':replacement})
 inventory.append({'file':file,'name':name,'type':typ,'before':'automatic stack object','after':'managed new owned by autoPtr; stable original-name reference','same_constructor_argument_text':True,'same_lexical_scope_and_destruction_order':True,'reason':reason})
 return text[:start]+replacement+text[semicolon+1:]
def main():
 if TARGET.exists():raise RuntimeError('Refusing existing source-only proposal')
 originals={str(p.relative_to(SOURCE)):sha(p) for p in SOURCE.rglob('*') if p.is_file() and not any(x.startswith('linuxARM64') for x in p.parts) and p.suffix not in ['.o','.dep']}
 files={name:(SOURCE/name).read_text() for name in ['c29NativeHybridFoam.C','createC29Fields.H','C29Operators.H','C29HostSource.H']}
 original_files=dict(files)
 files['c29NativeHybridFoam.C']=replace_once(files['c29NativeHybridFoam.C'],'#include "C29BackendAudit.H"','#include "C29BackendAudit.H"\n#include "C29ManagedOwnership.H"')
 for name in ['initialU','initialP','initialPhi','rAU','HbyA','phiHbyA','pEqn']:
  typ={'initialU':'volVectorField','initialP':'volScalarField','initialPhi':'surfaceScalarField','rAU':'volScalarField','HbyA':'volVectorField','phiHbyA':'surfaceScalarField','pEqn':'fvScalarMatrix'}[name]
  files['c29NativeHybridFoam.C']=own(files['c29NativeHybridFoam.C'],typ,name,'c29NativeHybridFoam.C','matrix' if name=='pEqn' else 'geometric')
 files['c29NativeHybridFoam.C']=replace_once(files['c29NativeHybridFoam.C'],'            fvVectorMatrix& UEqn=tUEqn.ref();','            fvVectorMatrix& UEqn=tUEqn.ref();\n            C29::managedMatrix(UEqn,"UEqn_existing_tmp_heap");')
 files['c29NativeHybridFoam.C']=replace_once(files['c29NativeHybridFoam.C'],'                auto predictor=(UEqn == -fvc::grad(p));','                auto predictor=(UEqn == -fvc::grad(p));\n                C29::managedMatrix(predictor(),"predictor_existing_tmp_heap");')
 for name,typ in [('p','volScalarField'),('U','volVectorField'),('nuEff','volScalarField')]:files['createC29Fields.H']=own(files['createC29Fields.H'],typ,name,'createC29Fields.H')
 files['createC29Fields.H']=replace_once(files['createC29Fields.H'],'#include "createPhi.H"','#include "createC29ManagedPhi.H"')
 native_root=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/source/OpenFOAM-v2606')
 phi_source=next(p for p in (native_root/'src').rglob('createPhi.H') if 'lnInclude' not in p.parts)
 original_files['createC29ManagedPhi.H']=phi_source.read_text()
 files['createC29ManagedPhi.H']=own(phi_source.read_text(),'surfaceScalarField','phi','createC29ManagedPhi.H',reason='The U descriptor check precedes the unchanged fvc::flux(U) initializer')
 for name,typ in [('nuFace','surfaceScalarField'),('devTauCorrFlux','surfaceVectorField'),('dPhi','surfaceScalarField'),('coupling','surfaceScalarField')]:files['C29Operators.H']=own(files['C29Operators.H'],typ,name,'C29Operators.H')
 files['C29Operators.H']=replace_once(files['C29Operators.H'],'#include "C29BackendAudit.H"','#include "C29BackendAudit.H"\n#include "C29ManagedOwnership.H"')
 files['C29Operators.H']=replace_once(files['C29Operators.H'],'    sync("momentum assembly before temporary destruction");','    C29::managedMatrix(result(),"momentum_result_existing_tmp_heap");\n    sync("momentum assembly before temporary destruction");')
 files['C29Operators.H']=replace_once(files['C29Operators.H'],'    sync("Euler correction before temporary destruction");','    C29::managedGeometricField(result(),"Euler_result_existing_tmp_heap");\n    sync("Euler correction before temporary destruction");')
 files['C29HostSource.H']=own(files['C29HostSource.H'],'fvVectorMatrix','source','C29HostSource.H','matrix',reason='Matrix embeds source/internal/boundary coefficient Field descriptors')
 files['C29HostSource.H']=replace_once(files['C29HostSource.H'],'#include "C29BackendAudit.H"','#include "C29BackendAudit.H"\n#include "C29ManagedOwnership.H"')
 # Content-only copy: DrvFS cannot reproduce the Linux source metadata.
 TARGET.mkdir()
 for relative in originals:
  destination=TARGET/relative;destination.parent.mkdir(parents=True,exist_ok=True)
  destination.write_bytes((SOURCE/relative).read_bytes())
 for name,text in files.items():(TARGET/name).write_text(text)
 helper=WORK/'C29ManagedOwnership.H';shutil.copyfile(helper,TARGET/helper.name)
 patch=''
 for name,text in files.items():patch+=''.join(difflib.unified_diff(original_files[name].splitlines(keepends=True),text.splitlines(keepends=True),fromfile='native2.2/'+('vendor/createPhi.H' if name=='createC29ManagedPhi.H' else name),tofile='ownership_source_only/'+name))
 patch+=''.join(difflib.unified_diff([],helper.read_text().splitlines(keepends=True),fromfile='/dev/null',tofile='ownership_source_only/'+helper.name))
 (TARGET/'ownership_only.patch').write_text(patch)
 preserved=['C29_body_verbatim.inc','C29_includes_verbatim.inc','C29Restrictions.H','C29ValidationThresholds.H','C29ExperimentAdmission.H','C29SourceAccounting.H','C29BackendAudit.H','Make/files','Make/options']
 unchanged={name:sha(TARGET/name)==sha(SOURCE/name) for name in preserved}
 if not all(unchanged.values()):raise RuntimeError('Orthogonal/source fragment changed')
 expected={'initialU','initialP','initialPhi','rAU','HbyA','phiHbyA','pEqn','p','U','nuEff','phi','nuFace','devTauCorrFlux','dPhi','coupling','source'}
 if {x['name'] for x in inventory}!=expected:raise RuntimeError('Ownership inventory incomplete')
 result={'prepared_utc':datetime.now(timezone.utc).isoformat(),'status':'SOURCE_ONLY_PENDING_ROOT_AND_INDEPENDENT_REVIEW_NO_COMPILE_NO_RUN','reference_source':str(SOURCE),'reference_main_sha256':sha(SOURCE/'c29NativeHybridFoam.C'),'proposal':str(TARGET),'source_pin':'b239fea6e48922730477e218c44e8b6a8ab17ade','ownership_inventory':inventory,'existing_tmp_heap_preserved':['tUEqn/UEqn','momentum result','predictor','Euler result'],'host_only_unchanged':['IOdictionary controls and transportProperties','dimensioned scalars nu and rDeltaT','SourceObservation','std::vector accounting snapshots','labels/words/counters','NVTX Range and autoPtr handles'],'unmodified_fragment_and_orthogonal_files':unchanged,'phi_initializer_preserved_from':str(phi_source),'phi_initializer_original_sha256':sha(phi_source),'pointer_checks':'Each owned descriptor, primitive Field and data, boundary container/patch Field/data; matrix source/internalCoeffs/boundaryCoeffs/coeffsOffset and already-allocated diag/upper/lower. No accessor creates absent matrix storage or oldTime. U checks occur before fvc::flux(U).','no_vendor_SDK_library_case_or_policy_change':True,'strict_pressure_adapter_included':False,'original_candidate_manifest_is_historical_reference_only':True,'full_size_initial_CPU_GPU_field_parity_required_before_PDE':True,'actual_full_case_faulting_kernel_not_sanitizer_attributed':True,'files':{str(p.relative_to(TARGET)):sha(p) for p in TARGET.rglob('*') if p.is_file()},'ownership_patch_sha256':sha(TARGET/'ownership_only.patch'),'generator_sha256':sha(__file__),'original_reference_files_sha256':originals}
 (TARGET/'ownership_proposal_manifest.json').write_text(json.dumps(result,indent=2)+'\n')
 (TARGET/'ownership_declaration_reversal_map.json').write_text(json.dumps(reversals,indent=2)+'\n')
 print(json.dumps({'proposal':str(TARGET),'stack_descriptors_adapted':len(inventory),'patch_sha256':result['ownership_patch_sha256'],'manifest_sha256':sha(TARGET/'ownership_proposal_manifest.json'),'compile_or_run':False},indent=2))
if __name__=='__main__':main()
