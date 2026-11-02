"""SOURCE-ONLY restoration plan for four fixed C29 validation inputs.

Default prints a plan. --restore is a FUTURE root-reviewed preparation action;
it never builds, initializes phi, issues a launch receipt, or invokes a solver.
No subprocess/process runner is used. Run restoration as openfoam on Linux.
"""
from pathlib import Path,PurePosixPath
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import uuid
import zipfile

PROJECT=Path(__file__).resolve().parents[3]
WORK=PROJECT/'work/gpu_actuator_port'
CANDIDATE=WORK/'candidate'
PACKAGE=PROJECT/'outputs/tello_refinement/gpu_feasibility/benchmark_reproduction'
EVIDENCE=PROJECT/'outputs/tello_refinement/gpu_feasibility/amgx/evidence/rotor_pilot_manifest.json'
BASE=Path('/opt/openfoam-workspace/cases/native_c29_validation_20261102')
FROZEN=Path('/opt/openfoam-workspace/gpu-feasibility/pressure-offload/benchmarks_20261101/cpu_serial')
NAMES=('foundation14_control','native_cpu','native_gpu','foundation14_phi_seed')
PINS={
    'seed':'89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb',
    'reproduction':'e75dea5cbaaae870cf568266d95a61cc3fa28a288c4d39113e00aecc08a880c9',
    'cpu_manifest':'5194b4442563947edc79af4f273dc67bc1b486b39e08d740352627d40c607f80',
    'cached_library_evidence':'e3935d505571c807de60551137f043f89f2f826861ff5d288a4ca2dddf17e67e',
    'candidate':'562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7',
    'thresholds':'d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b',
    'model':'29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd',
    'cached_library':'402b112e09f36444ac13d19a3a04f3aca24344a632eb7a258fd11fc3a33392ce',
}
LIBREL='platforms/linuxArm64GccDPInt32Opt/lib/librotors_7ae57bb77feaae19c26ff305b44ebb5a6819f2ef.so'
DIGEST='_7ae57bb77feaae19c26ff305b44ebb5a6819f2ef'
REFERENCES={
    'published_safe_restore_sha256':'efc6962bb6ab3eab351b875704d5b9369adf8311c30e75b3142e75415545f7ed',
    'workstation_cached_library_method_sha256':'96a80d438f81dac212cffb77a22fe9999f4c3baa4c5156a90c944dffcf177618',
}
def require(ok,message):
    if not ok:raise ValueError(message)
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def rec(path):return {'sha256':sha(path),'size_bytes':path.stat().st_size}
def observed(path):return {**rec(path),'mtime_ns':path.stat().st_mtime_ns}
def safe_relative(value):
    require(isinstance(value,str) and bool(value),'Invalid catalogue name')
    require(not any(c in value for c in ('\\',':','\x00')),'Unsafe catalogue separator/drive/NUL')
    require(all(part not in ('','.','..') for part in value.split('/')),'Unsafe catalogue component')
    p=PurePosixPath(value);require(not p.is_absolute(),'Absolute catalogue name');return p
def no_links(path):
    p=Path(path)
    require(p.is_absolute() and '..' not in p.parts,'Absolute literal path required: '+str(p))
    for item in (p,*p.parents):
        require(not item.is_symlink(),'Symlink/ancestor rejected: '+str(item))
        require(not getattr(item,'is_junction',lambda:False)(),'Junction rejected: '+str(item))
    return p
def join(root,relative,exists=False):
    root=no_links(root);parts=safe_relative(relative).parts
    p=no_links(root.joinpath(*parts))
    require(p.resolve().is_relative_to(root.resolve()) and p.resolve()!=root.resolve(),'Escaped selected root')
    if exists:require(p.is_file(),'Missing regular file: '+str(p))
    return p
def pinned_json(path,pin):
    no_links(path);require(path.is_file() and sha(path)==pin,'Pinned JSON differs: '+str(path))
    return json.loads(path.read_text())
def verify_candidate(expected_sha):
    manifest=pinned_json(CANDIDATE/'candidate_manifest.json',expected_sha)
    require(sha(CANDIDATE/'validation_thresholds.json')==PINS['thresholds'],'Threshold pin differs')
    require(manifest['original_fvModels_sha256']==PINS['model'],'C29 model identity differs')
    for rel,record in manifest['candidate_files'].items():
        require(rec(join(CANDIDATE,rel,True))==record,'Candidate source differs: '+rel)
    return manifest
def verify_package():
    package=pinned_json(PACKAGE/'reproduction_manifest.json',PINS['reproduction'])
    original=pinned_json(PACKAGE/'overrides/cpu_serial/benchmark_manifest.json',PINS['cpu_manifest'])
    archive=join(PACKAGE,'shared_seed.zip',True)
    require(archive.stat().st_size==62823211 and sha(archive)==PINS['seed'],'Seed ZIP pin differs')
    variant=package['variants']['cpu_serial']
    require(package['shared_seed_archive']['sha256']==PINS['seed']
        and variant['benchmark_manifest_sha256']==PINS['cpu_manifest'],'Outer pins disagree')
    for catalogue in (package['shared_seed_files'],variant['override_files'],original['frozen_inputs']):
        require(isinstance(catalogue,dict),'Invalid catalogue')
        for name in catalogue:safe_relative(name)
    shared=package['shared_seed_files'];overrides=variant['override_files'];frozen=original['frozen_inputs']
    require(not any(name.startswith('dynamicCode/') for name in frozen),
        'Portable seed must not carry an unreviewed dynamicCode layer')
    require(not set(shared)&set(overrides),'Overlapping seed/override layers')
    require(set(shared)|set(overrides)==set(frozen)|{'benchmark_manifest.json'},'Inventory differs')
    for name,record in {**shared,**overrides}.items():
        expected={'sha256':PINS['cpu_manifest'],'size_bytes':(PACKAGE/'overrides/cpu_serial/benchmark_manifest.json').stat().st_size} if name=='benchmark_manifest.json' else frozen[name]
        require(record==expected,'Catalogue record not bound to CPU pin: '+name)
    for name,record in overrides.items():
        require(rec(join(PACKAGE/'overrides/cpu_serial',name,True))==record,'Override differs: '+name)
    with zipfile.ZipFile(archive) as z:
        require(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(shared),'ZIP inventory/duplicates differ')
        for info in z.infolist():
            safe_relative(info.filename)
            mode=info.external_attr>>16
            require(not info.is_dir() and not stat.S_ISLNK(mode)
                and stat.S_IFMT(mode) in (0,stat.S_IFREG),'Nonregular ZIP member')
            require(not info.flag_bits&1,'Encrypted ZIP member unsupported')
    return package,variant,original
def verify_cached_source(original):
    # Source leaf symlinks are permitted ONLY inside this exact frozen dynamic
    # tree (standard lnInclude). Destinations are always private regular bytes.
    evidence=pinned_json(EVIDENCE,PINS['cached_library_evidence'])
    expected=evidence['actuator_dynamic_code_hashes']
    dynamic=no_links(FROZEN/'dynamicCode');require(dynamic.is_dir(),'Frozen cache missing')
    inventory={}
    for p in dynamic.rglob('*'):
        if p.is_symlink():
            target=p.resolve(strict=True)
            require(target.is_relative_to(dynamic.resolve()) and target.is_file(),
                'Only contained cached-source leaf links supported: '+str(p))
        if p.is_file():inventory[p.relative_to(dynamic).as_posix()]=observed(p)
        else:require(p.is_dir() and not p.is_symlink(),'Unexpected cached artifact type')
    require(set(inventory)==set(expected),'Frozen cache inventory differs')
    for name,record in expected.items():
        safe_relative(name)
        require({key:inventory[name][key] for key in ('sha256','size_bytes')}==record,
            'Frozen cached source/digest/library differs: '+name)
    require((dynamic/'rotors/Make/SHA1Digest').read_text().strip()==DIGEST,'Wrong cached digest')
    require(inventory[LIBREL]['sha256']==PINS['cached_library'],'Wrong cached library')
    frozen={name:observed(join(FROZEN,name,True)) for name in original['frozen_inputs']}
    require({name:{key:r[key] for key in ('sha256','size_bytes')} for name,r in frozen.items()}
        ==original['frozen_inputs'],'Original frozen CPU inputs differ')
    require(frozen['constant/fvModels']['sha256']==PINS['model'],'Model/cache context differs')
    return dynamic,inventory,frozen
def write_new(case,name,text):
    p=join(case,name);require(not p.exists(),'Refusing new-file overwrite: '+str(p))
    p.parent.mkdir(parents=True,exist_ok=True);p=join(case,name)
    with p.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
def replace_fresh(case,name,text,allowed):
    require(name in allowed,'Undeclared fresh-input adaptation')
    p=join(case,name,True);p.write_text(text,encoding='utf-8',newline='\n')
def control_text(application):
    solver='solver incompressibleFluid;\n' if application=='foamRun' else ''
    return ('FoamFile {format ascii;class dictionary;object controlDict;}\n'
        +'application '+application+';\n'+solver
        +'startFrom startTime;startTime 0.6;stopAt endTime;endTime 0.6005;\n'
        +'deltaT 0.0001;adjustTimeStep false;runTimeModifiable false;\n'
        +'writeControl timeStep;writeInterval 1;purgeWrite 0;writeFormat ascii;\n'
        +'writePrecision 17;timeFormat general;timePrecision 8;functions {};libs ();\n')
def custom_controls(name,backend,receipt,experiment):
    template='c29InitialPhiControls.txt' if name=='foundation14_phi_seed' else 'c29PortControls.txt'
    text=(CANDIDATE/'recipe_templates'/template).read_text()
    text=text.replace('"ROOT_CHOOSE_UNIQUE_ID"',json.dumps(experiment))
    text=text.replace('"/ROOT_CHOOSE_NEW_PRIVATE_RECEIPT.foam"',json.dumps(str(receipt)))
    if name=='foundation14_phi_seed':text=text.replace('allowInitialPhiExperiment false;','allowInitialPhiExperiment true;')
    else:
        text=text.replace('backend gpu;','backend '+backend+';')
        text=text.replace('allowUnvalidatedBackendExperiment false;','allowUnvalidatedBackendExperiment true;')
        text=text.replace('allowInitialFieldsOnlyExperiment false;','allowInitialFieldsOnlyExperiment true;')
        require('allowFiveStepSourceExperiment false;' in text,'Initial-only restriction lost')
    require('ROOT_CHOOSE' not in text,'Unfilled control placeholder')
    return text
def restore(expected_candidate):
    require(os.name=='posix','Restoration is Linux-only')
    import pwd
    require(os.geteuid()!=0 and pwd.getpwuid(os.geteuid()).pw_name=='openfoam','Restore as openfoam, never root')
    base=no_links(BASE);require(base.parent.is_dir() and not base.exists(),'Fixed root must be entirely fresh')
    manifest=verify_candidate(expected_candidate)
    package,variant,original=verify_package()
    dynamic,dynamic_before,frozen_before=verify_cached_source(original)
    package_sources=[PACKAGE/'shared_seed.zip',PACKAGE/'reproduction_manifest.json',
        PACKAGE/'overrides/cpu_serial/benchmark_manifest.json',EVIDENCE]
    package_sources += [join(PACKAGE/'overrides/cpu_serial',rel,True)
        for rel in variant['override_files']]
    package_before={str(p):observed(p) for p in package_sources}
    # Validate all external destination names for ALL four cases before mkdir.
    for name in NAMES:
        case=join(base,name)
        for rel in (*package['shared_seed_files'],*variant['override_files'],*original['frozen_inputs']):join(case,rel)
        for rel in dynamic_before:join(case,'dynamicCode/'+rel)
    base.mkdir();(base/'receipts').mkdir()
    report={}
    try:
        for name in NAMES:
            case=join(base,name);case.mkdir()
            with zipfile.ZipFile(PACKAGE/'shared_seed.zip') as archive:
                for info in archive.infolist():
                    target=join(case,info.filename);target.parent.mkdir(parents=True,exist_ok=True)
                    target=join(case,info.filename)
                    with archive.open(info) as source,target.open('xb') as dest:shutil.copyfileobj(source,dest,1024*1024)
            for rel in variant['override_files']:
                source=join(PACKAGE/'overrides/cpu_serial',rel,True);target=join(case,rel)
                require(not target.exists(),'Override destination already exists')
                target.parent.mkdir(parents=True,exist_ok=True)
                with source.open('rb') as src,target.open('xb') as dest:shutil.copyfileobj(src,dest,1024*1024)
            for rel,record in original['frozen_inputs'].items():require(rec(join(case,rel,True))==record,'Restored byte mismatch: '+rel)
            require(not (case/'0.6/phi').exists() and not (case/'0.6/phi.gz').exists(),'Seed unexpectedly has phi')
            changes=['system/controlDict','Allrun']
            phase='foundation_initial_phi' if name=='foundation14_phi_seed' else 'initial_fields_only'
            backend='gpu' if name=='native_gpu' else 'cpu'
            application='foamRun' if name=='foundation14_control' else ('c29FoundationInitialPhi' if name=='foundation14_phi_seed' else 'c29NativeHybridFoam')
            replace_fresh(case,'system/controlDict',control_text(application),set(changes))
            replace_fresh(case,'Allrun','#!/bin/sh\necho "Prepared inputs only; no solver/initialization is authorized by this file." >&2\nexit 64\n',set(changes))
            if name=='foundation14_control':
                for rel,record in dynamic_before.items():
                    source=dynamic.joinpath(*safe_relative(rel).parts)
                    dest=join(case,'dynamicCode/'+rel);dest.parent.mkdir(parents=True,exist_ok=True)
                    require(not dest.exists(),'Cached destination already exists')
                    with source.open('rb') as src,dest.open('xb') as out:shutil.copyfileobj(src,out,1024*1024)
                    os.utime(dest,ns=(source.stat().st_atime_ns,record['mtime_ns']))
                    require(rec(dest)=={key:record[key] for key in ('sha256','size_bytes')},'Private cached copy differs')
                # Block any automatic compiler write; a cache mismatch must fail.
                for p in (case/'dynamicCode').rglob('*'):
                    if p.is_file():p.chmod(0o444)
                for p in sorted((p for p in (case/'dynamicCode').rglob('*') if p.is_dir()),key=lambda p:len(p.parts),reverse=True):p.chmod(0o555)
                (case/'dynamicCode').chmod(0o555)
            else:
                require(not (case/'dynamicCode').exists(),'Non-F14-control must have no dynamicCode')
                experiment='c29_'+name+'_'+uuid.uuid4().hex
                receipt=base/'receipts'/(experiment+'.foam')
                key='c29InitialPhiControls' if name=='foundation14_phi_seed' else 'c29PortControls'
                write_new(case,'constant/'+key,custom_controls(name,backend,receipt,experiment))
                if name.startswith('native_'):
                    old=join(case,'system/fvSolution',True).read_text()
                    adapted,count=re.subn(r'\bPIMPLE\s*\{','PISO\n{',old)
                    require(count==1,'Expected exactly one pinned PIMPLE block')
                    replace_fresh(case,'system/fvSolution',adapted,{'system/fvSolution'})
                    changes.append('system/fvSolution')
                    write_new(case,'constant/transportProperties',(CANDIDATE/'recipe_templates/native_transportProperties.txt').read_text())
            # All physical bytes and schemes remain fixed; F14 PIMPLE also stays fixed.
            preserved=['0.6/U','0.6/p','constant/fvModels','constant/rotorParameters','constant/physicalProperties',
                'constant/momentumTransport','system/fvSchemes','geometry.json']
            preserved += [r for r in original['frozen_inputs'] if r.startswith('constant/polyMesh/')]
            if not name.startswith('native_'):preserved.append('system/fvSolution')
            for rel in preserved:require(rec(join(case,rel,True))==original['frozen_inputs'][rel],'Preserved input changed: '+rel)
            details={'case':str(case),'role':name,'application':application,'backend':backend,
                'candidate_manifest_sha256':expected_candidate,'thresholds_sha256':PINS['thresholds'],
                'configured_time_controls':{'start':.6,'end':.6005,'dt':1e-4,'adjustTimeStep':False},
                'initial_phase_executes_time_steps':name=='foundation14_control',
                'configured_five_step_comparison':name!='foundation14_phi_seed',
                'utility_has_no_time_or_source_loop':name=='foundation14_phi_seed',
                'initial_phi':'absent; exact startup comparison/common-phi gate still pending',
                'source_controller':'fresh warm reinitialization only; no transferred history',
                'historical_geometry_metadata_preserved':True,'adapted_existing_files':changes,
                'initial_only':name!='foundation14_control','five_step_native_permission':False,
                'cached_dynamic_code_reused':name=='foundation14_control','cached_rebuild_allowed':False,
                'foundation_reference_environment':{'WM_PROJECT_VERSION':'14','WM_OPTIONS':'linuxArm64GccDPInt32Opt'},
                'runtime_or_source_acceptance':'NOT ASSESSED','no_launch_receipt_issued':True,
                'solver_or_initializer_launched':False,'performance_claim':False}
            write_new(case,'case_preparation.json',json.dumps(details,indent=2)+'\n')
            report[name]=details
        for rel,record in frozen_before.items():require(observed(join(FROZEN,rel,True))==record,'Frozen original changed')
        for rel,record in dynamic_before.items():require(observed(dynamic.joinpath(*safe_relative(rel).parts))==record,'Original cache changed')
        for path,record in package_before.items():require(observed(Path(path))==record,'Original package/evidence changed')
        verify_candidate(expected_candidate)
        output={'kind':'Prepared four fresh experimental input sets only','cases':report,
            'pins':{**PINS,'candidate':expected_candidate},
            'candidate_manifest_sha256':expected_candidate,'sources_before_after_unchanged':True,
            'restored_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'no_solver_no_initializer_no_build':True,'next':'Root reviews inputs, builds separate approved applications, issues phase receipts, and performs exact startup gate before any five-step comparison'}
        write_new(base,'preparation_manifest.json',json.dumps(output,indent=2)+'\n')
        return output
    except Exception:
        # Never remove/reuse a partial root automatically; all later runs refuse it.
        raise
def plan():
    return {'state':'Source-only plan; restoration/build/initialization/solver NOT EXECUTED',
        'fixed_root':str(BASE),'exact_cases':list(NAMES),'pins':PINS,'references':REFERENCES,
        'scope':'No extra matrix or generic runner; no subprocess calls',
        'sequence':['Review script','Root explicitly authorizes restore','Verify every source pin before mkdir',
            'Restore four fresh inputs; native initial-only permissions, no receipts',
            'Separate reviewed utility/candidate build when global compiler slots permit',
            'Input/binary/library receipts; exact startup U/p/phi gate or one pinned common phi',
            'Root separately admits F14-to-nativeCPU five steps, then nativeCPU-to-GPU',
            'No source-acceptance, convergence or timing claim from preparation']}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--restore',action='store_true')
    ap.add_argument('--candidate-manifest-sha256',default=PINS['candidate'],
        help='Explicit root-approved pin; never inferred automatically after source changes')
    args=ap.parse_args()
    require(re.fullmatch('[0-9a-f]{64}',args.candidate_manifest_sha256) is not None,'Invalid candidate pin')
    print(json.dumps(restore(args.candidate_manifest_sha256) if args.restore else plan(),indent=2))
if __name__=='__main__':main()
