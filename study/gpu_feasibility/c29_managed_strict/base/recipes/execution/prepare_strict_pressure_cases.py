"""SOURCE-ONLY guarded three-role strict-pressure restoration.

Default prints a plan. --restore is for Root AFTER source review, as openfoam.
No builds, utilities, initializer, solver, launch receipts or subprocess calls.
The pinned existing safe-copy module is imported without executing its main.
"""
from pathlib import Path
import argparse,datetime,hashlib,importlib.util,json,os,pwd,shutil,sys,uuid,zipfile
sys.dont_write_bytecode=True

HERE=Path(__file__).resolve().parent
LEGACY_SCRIPT=HERE/'prepare_native_c29_cases.py'
LEGACY_SCRIPT_SHA='d7064bde61a40764965436b4c1935d1a3cd63e54f5a2cf694fae898014c7135c'
BASE=Path('/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102')
NAMES=('foundation14_control','native_cpu','native_gpu')
PROPOSAL=HERE/'strict_pressure_proposal'
PROTOCOL='c29-native-five-fixed-steps-strict-pressure-v1'
PROTOCOL_SHA='946e8c2a0e566cbfb5e494af2da1cf94ba3f3102567c8db36135fd1a758de8fd'
AUTHORIZATION_SHA='8ea985fb7143d34fecfa2e6b7277b971466fbe9426a5013db98f4ebdfd259b56'
APPLICATION='c29ManagedHybridFoamStrict'
EXPECTED_CRITERIA={'p':{'tolerance':1e-7,'relTol':0},'pFinal':{'tolerance':1e-7,'relTol':0},
    'U':{'tolerance':1e-7,'relTol':.05},'UFinal':{'tolerance':1e-7,'relTol':0}}
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
    return h.hexdigest()
def safe_module():
    require(sha(LEGACY_SCRIPT)==LEGACY_SCRIPT_SHA,'Reviewed safe restoration module changed')
    spec=importlib.util.spec_from_file_location('pinned_c29_safe_restore',LEGACY_SCRIPT)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def protocol_authorization(L):
    protocol=L.pinned_json(PROPOSAL/'strict_pressure_protocol.json',PROTOCOL_SHA)
    auth=L.pinned_json(PROPOSAL/'root_authorization.json',AUTHORIZATION_SHA)
    require(protocol['protocol']==auth['protocol']==PROTOCOL,'Strict protocol identity differs')
    require(auth['protocol_sha256']==PROTOCOL_SHA and auth['validation_thresholds_sha256']==L.PINS['thresholds'],
        'Strict authorization/threshold binding differs')
    require(auth['decision']=='APPROVED_FOR_UNVALIDATED_FIVE_STEPS'
        and auth['fresh_case_root']==str(BASE),'Wrong authorization/root')
    require(auth['runtime_validated'] is False,'Input permission must not claim runtime proof')
    return auth
def strict_solution(original,native):
    # An exact adapter for the CHECKSUM-PINNED input, not a dictionary parser.
    # Preserve inheritance and every byte except p relTol and native PISO name.
    old='p {directSolveCoarsest yes; solver GAMG; smoother GaussSeidel; tolerance 1e-7; relTol .05;}'
    new=old.replace('relTol .05;','relTol 0;')
    require(original.count(old)==1,'Pinned first-p literal block unexpectedly differs')
    changed=original.replace(old,new,1)
    require(changed.replace(new,old,1)==original,'Extra strict adaptation detected')
    if native:
        before='PIMPLE {nOuterCorrectors 1; nCorrectors 2; nNonOrthogonalCorrectors 0;}'
        after=before.replace('PIMPLE','PISO',1)
        require(changed.count(before)==1,'Pinned PIMPLE block unexpectedly differs')
        changed=changed.replace(before,after,1)
    return changed
def controls(L,role,backend,receipt,experiment):
    name='c29InitialPhiControls.txt' if role=='foundation14_control' else 'c29PortControls.txt'
    text=(L.CANDIDATE/'recipe_templates'/name).read_text()
    text=text.replace('"ROOT_CHOOSE_UNIQUE_ID"',json.dumps(experiment))
    text=text.replace('"/ROOT_CHOOSE_NEW_PRIVATE_RECEIPT.foam"',json.dumps(str(receipt)))
    if role!='foundation14_control':
        text=text.replace('protocol c29-native-five-fixed-steps-v1;','protocol '+PROTOCOL+';')
        text=text.replace('backend gpu;','backend '+backend+';')
        require(all(flag+' false;' in text for flag in ('allowUnvalidatedBackendExperiment',
            'allowInitialFieldsOnlyExperiment','allowFiveStepSourceExperiment')),
            'Native preparation must keep all experimental permissions false')
    else:require('allowInitialPhiExperiment false;' in text,'F14 initializer permission must remain false')
    require('ROOT_CHOOSE' not in text,'Unfilled template placeholder')
    return text
def restore(L):
    require(os.name=='posix' and os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='openfoam',
        'Restore only as Linux openfoam, never root')
    base=L.no_links(BASE);require(base.parent.is_dir() and not base.exists(),'Fixed strict root must be fresh')
    authorization=protocol_authorization(L)
    L.verify_candidate(L.PINS['candidate'])
    package,variant,original=L.verify_package()
    dynamic,dynamic_before,frozen_before=L.verify_cached_source(original)
    sources=[L.PACKAGE/'shared_seed.zip',L.PACKAGE/'reproduction_manifest.json',
        L.PACKAGE/'overrides/cpu_serial/benchmark_manifest.json',L.EVIDENCE,
        LEGACY_SCRIPT,Path(__file__).resolve(),PROPOSAL/'strict_pressure_protocol.json',PROPOSAL/'root_authorization.json']
    sources += [L.join(L.PACKAGE/'overrides/cpu_serial',rel,True) for rel in variant['override_files']]
    sources_before={str(p):L.observed(p) for p in sources}
    # All catalogue/key/ZIP/cache/source checks and all destinations precede mkdir.
    for role in NAMES:
        case=L.join(base,role)
        for rel in (*package['shared_seed_files'],*variant['override_files'],*original['frozen_inputs']):L.join(case,rel)
        for rel in dynamic_before:L.join(case,'dynamicCode/'+rel)
    base.mkdir();(base/'receipts').mkdir()
    report={};audit_cases={}
    for role in NAMES:
        case=L.join(base,role);case.mkdir()
        with zipfile.ZipFile(L.PACKAGE/'shared_seed.zip') as archive:
            for info in archive.infolist():
                target=L.join(case,info.filename);target.parent.mkdir(parents=True,exist_ok=True)
                target=L.join(case,info.filename)
                with archive.open(info) as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        for rel in variant['override_files']:
            source=L.join(L.PACKAGE/'overrides/cpu_serial',rel,True);target=L.join(case,rel)
            require(not target.exists(),'Override destination already exists');target.parent.mkdir(parents=True,exist_ok=True)
            with source.open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
        for rel,record in original['frozen_inputs'].items():require(L.rec(L.join(case,rel,True))==record,'Restored byte mismatch: '+rel)
        require(not (case/'0.6/phi').exists() and not (case/'0.6/phi.gz').exists(),'Pinned seed unexpectedly has phi')
        native=role.startswith('native_');backend='gpu' if role=='native_gpu' else 'cpu'
        application=APPLICATION if native else 'foamRun'
        L.replace_fresh(case,'system/controlDict',L.control_text(application),{'system/controlDict'})
        L.replace_fresh(case,'Allrun','#!/bin/sh\necho "Prepared inputs only; no execution authorized by Allrun." >&2\nexit 64\n',{'Allrun'})
        solution_path=L.join(case,'system/fvSolution',True);before=solution_path.read_bytes().decode('utf-8')
        solution=strict_solution(before,native)
        L.replace_fresh(case,'system/fvSolution',solution,{'system/fvSolution'})
        changes=['system/controlDict','Allrun','system/fvSolution']
        if not native:
            for rel,record in dynamic_before.items():
                source=dynamic.joinpath(*L.safe_relative(rel).parts);dest=L.join(case,'dynamicCode/'+rel)
                dest.parent.mkdir(parents=True,exist_ok=True)
                with source.open('rb') as src,dest.open('xb') as dst:shutil.copyfileobj(src,dst,1024*1024)
                os.utime(dest,ns=(source.stat().st_atime_ns,record['mtime_ns']))
                require(L.rec(dest)=={k:record[k] for k in ('sha256','size_bytes')},'Private cached copy differs')
            for p in (case/'dynamicCode').rglob('*'):
                if p.is_file():p.chmod(0o444)
            for p in sorted((p for p in (case/'dynamicCode').rglob('*') if p.is_dir()),key=lambda q:len(q.parts),reverse=True):p.chmod(0o555)
            (case/'dynamicCode').chmod(0o555)
        else:
            require(not (case/'dynamicCode').exists(),'Native must not carry F14 dynamicCode/runtime source')
            L.write_new(case,'constant/transportProperties',(L.CANDIDATE/'recipe_templates/native_transportProperties.txt').read_text())
        experiment='c29_strict_'+role+'_'+uuid.uuid4().hex
        receipt=base/'receipts'/(experiment+'.foam')
        key='c29PortControls' if native else 'c29InitialPhiControls'
        L.write_new(case,'constant/'+key,controls(L,role,backend,receipt,experiment))
        preserved=['0.6/U','0.6/p','constant/fvModels','constant/rotorParameters','constant/physicalProperties',
            'constant/momentumTransport','system/fvSchemes','geometry.json']
        preserved += [rel for rel in original['frozen_inputs'] if rel.startswith('constant/polyMesh/')]
        for rel in preserved:require(L.rec(L.join(case,rel,True))==original['frozen_inputs'][rel],'Preserved physical input changed: '+rel)
        details={'case':str(case),'role':role,'application':application,'backend':backend,
            'strict_protocol':PROTOCOL,'strict_protocol_sha256':PROTOCOL_SHA,
            'thresholds_sha256':L.PINS['thresholds'],'base_candidate_manifest_sha256':L.PINS['candidate'],
            'combined_candidate_binary_and_source_identity':'NOT PROVIDED; root review/build/identity still required',
            'time_controls':{'start':.6,'end':.6005,'dt':1e-4,'steps':5,'write_precision':17},
            'only_changed_linear_setting':'First p relTol .05 -> 0; tolerance1e-7, U/UFinal/pFinal unchanged',
            'foundation_PIMPLE_retained':not native,'native_PISO_adapter':native,
            'adapted_existing_files':changes,'added_passive_control':str(Path('constant')/key),
            'initial_phi':'Absent; exact initialized U/p/phi gate must be repeated',
            'source_controller':'Fresh warm reinitialization; no advanced state transferred',
            'all_custom_experimental_permissions':False,
            'unique_future_receipt':str(receipt),'launch_receipt_issued':False,
            'F14_cached_library_only':not native,'cached_rebuild_allowed':False,
            'foundation_reference_environment':{'WM_PROJECT_VERSION':'14','WM_OPTIONS':'linuxArm64GccDPInt32Opt'},
            'no_initializer_solver_or_build':True,'runtime_validated':False,'performance_claim':False}
        L.write_new(case,'case_preparation.json',json.dumps(details,indent=2)+'\n');report[role]=details
        label={'foundation14_control':'f14','native_cpu':'cpu','native_gpu':'gpu'}[role]
        audit_cases[label]={'case':str(case),'fvSolution':{'path':str(solution_path),'sha256':sha(solution_path)},
            'audited_solver_criteria':None}
        if native:audit_cases[label]['c29PortControls']={'path':str(case/'constant/c29PortControls'),'sha256':sha(case/'constant/c29PortControls')}
    for rel,record in frozen_before.items():require(L.observed(L.join(L.FROZEN,rel,True))==record,'Frozen original input changed')
    for rel,record in dynamic_before.items():require(L.observed(dynamic.joinpath(*L.safe_relative(rel).parts))==record,'Original cached library/source changed')
    for path,record in sources_before.items():require(L.observed(Path(path))==record,'Pinned package/source changed')
    L.verify_candidate(L.PINS['candidate'])
    pending={'schema':'c29-strict-pressure-input-audit-v1','protocol':PROTOCOL,'protocol_sha256':PROTOCOL_SHA,
        'validation_thresholds_sha256':L.PINS['thresholds'],'inputs_audited':False,
        'root_authorization':{'path':str(PROPOSAL/'root_authorization.json'),'sha256':AUTHORIZATION_SHA},
        'cases':audit_cases,'expected_solver_criteria':EXPECTED_CRITERIA,
        'status':'PENDING independent resolved dictionary audit; this template CANNOT pass strict analyzer admission',
        'warning':'Populate audited criteria only from actual resolved dictionary queries after all phase control changes; update control hashes then. No claim of solver execution.'}
    L.write_new(base,'strict_protocol_input_audit.pending.json',json.dumps(pending,indent=2)+'\n')
    manifest={'schema':'c29-strict-pressure-three-role-preparation-v1','restored_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'script_sha256':sha(Path(__file__).resolve()),'legacy_safe_module_sha256':LEGACY_SCRIPT_SHA,
        'root_authorization_sha256':AUTHORIZATION_SHA,'strict_protocol_sha256':PROTOCOL_SHA,
        'pins':L.PINS,'cases':report,'all_source_records_before_after_unchanged':True,
        'original_failed_case_root_preserved':str(L.BASE),'no_launch_receipt_issued':True,
        'no_solver_initializer_build_or_dictionary_utility_invoked':True,
        'next':'Root reviews prepared bytes, merged source/binary identities and actual resolved input audit; separately authorizes startup then F14-to-nativeCPU then GPU.'}
    L.write_new(base,'preparation_manifest.json',json.dumps(manifest,indent=2)+'\n')
    return manifest
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--restore',action='store_true');args=ap.parse_args()
    L=safe_module();protocol_authorization(L)
    result=restore(L) if args.restore else {'state':'SOURCE ONLY; no restoration/execution performed','fixed_fresh_root':str(BASE),
        'roles':NAMES,'application_expected_for_native':APPLICATION,'strict_protocol':PROTOCOL,
        'strict_protocol_sha256':PROTOCOL_SHA,'root_authorization_sha256':AUTHORIZATION_SHA,
        'safe_module_sha256':LEGACY_SCRIPT_SHA,'pins':L.PINS,
        'all_permissions_start_false':True,'pending_dictionary_audit_not_acceptance':True}
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
