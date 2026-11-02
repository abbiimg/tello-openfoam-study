"""Byte verification and OPTIONAL receipt publication; never a process runner."""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time

HERE=Path(__file__).resolve().parent
ENV_KEYS=('LD_LIBRARY_PATH','LD_PRELOAD','CUDA_VISIBLE_DEVICES',
    'NVCOMPILER_ACC_DEVICE_TYPE','NVCOMPILER_ACC_CUDA_VISIBLE_DEVICES','OMP_NUM_THREADS')
PHASES=('initial_fields_only','five_fixed_steps','foundation_initial_phi')
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as stream:
        for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
    return h.hexdigest()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def digest(value):return hashlib.sha256(canonical(value)).hexdigest()
def check(ok,reason):
    if not ok:raise ValueError(reason)
def real_path(value,must_exist=True):
    p=Path(value)
    check(p.is_absolute() and '..' not in p.parts,'Absolute path without .. required: '+str(p))
    for item in (p,*p.parents):
        check(not item.is_symlink(),'Symlink path/ancestor rejected: '+str(item))
        check(not getattr(item,'is_junction',lambda:False)(),'Junction rejected: '+str(item))
    if must_exist:check(p.exists(),'Missing path: '+str(p))
    return p.resolve(strict=must_exist)
def file_record(p):
    p=real_path(p);check(p.is_file(),'Regular file required: '+str(p))
    before=p.stat()
    result={'path':str(p),'sha256':sha(p),'size_bytes':before.st_size,'mtime_ns':before.st_mtime_ns}
    after=p.stat()
    check((before.st_size,before.st_mtime_ns)==(after.st_size,after.st_mtime_ns),
        'File changed while auditing: '+str(p))
    return result
def same_record(record):return file_record(record['path'])==record
def plain_variants(case,rel,required=False):
    p=case/rel
    # Broken links are rejected too. Runtime isFile also recognizes gzip.
    for q in (p,p.with_name(p.name+'.gz')):
        for ancestor in (q,*q.parents):
            check(not ancestor.is_symlink(),'Symlink variant/ancestor: '+str(ancestor))
            check(not getattr(ancestor,'is_junction',lambda:False)(),'Junction variant: '+str(ancestor))
    check(not p.with_name(p.name+'.gz').exists(),'Compressed variant rejected: '+str(p)+'.gz')
    if required:check(p.is_file(),'Plain file required: '+str(p))
    return p
def setting(text,key):
    # Deliberately limited to flat custom controls, not an OpenFOAM parser.
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    check('#' not in text and '$' not in text,'Directives/expansion unsupported in admission controls')
    matches=re.findall(r'\b'+re.escape(key)+r'\s+("[^"\n]*"|[^;\s]+)\s*;',text)
    check(len(matches)==1,'Exactly one admission key required: '+key)
    return matches[0].strip('"')
def source_audit():
    manifest=json.loads((HERE/'candidate_manifest.json').read_text())
    for name,record in manifest['candidate_files'].items():
        p=real_path(HERE/name)
        check(p.is_file() and sha(p)==record['sha256'],'Candidate mismatch: '+name)
    return manifest
def case_audit(args,manifest):
    case=real_path(args.case);private=real_path(args.private_root)
    check(case.is_dir() and private.is_dir() and case.is_relative_to(private)
        and case!=private,'Case must be a child of the explicit private root')
    forbidden=(Path('/opt/openfoam14'),Path('/opt/openfoam-workspace/cases/tello_refinement'),
        Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/source'),
        Path('/opt/openfoam-workspace/gpu-feasibility/pressure-offload/benchmarks_20261101'))
    check(not any(case==p or case.is_relative_to(p) for p in forbidden),
        'Study/vendor/original benchmark roots are not fresh candidate roots')
    plan=json.loads((HERE/'validation_recipe.json').read_text());files={}
    for rel,expected in plan['unchanged_input_hashes'].items():
        if args.phase=='foundation_initial_phi' and not (rel=='0.6/U' or rel.startswith('constant/polyMesh/')):
            continue
        record=file_record(plain_variants(case,rel,required=True))
        check(record['sha256']==expected['sha256'],'Pinned seed mismatch: '+rel)
        files[rel]=record
    phi=plain_variants(case,'0.6/phi')
    if args.shared_phi_sha256:
        check(args.phase!='foundation_initial_phi','Fallback initializer requires absent phi')
        check(re.fullmatch('[0-9a-f]{64}',args.shared_phi_sha256) is not None,'Invalid common phi SHA')
        check(phi.is_file() and sha(phi)==args.shared_phi_sha256,'Common phi mismatch')
        files['0.6/phi']=file_record(phi)
    else:check(not phi.exists(),'No-phi policy violated; shared phi requires a separate approved pin')
    for name in ('dynamicMeshDict','MRFProperties','fvOptions','fvConstraints'):
        for folder in ('constant','system'):
            check(not (case/folder/name).exists() and not (case/folder/(name+'.gz')).exists(),
                'Unsupported optional input: '+folder+'/'+name)
    control_name='c29InitialPhiControls' if args.phase=='foundation_initial_phi' else 'c29PortControls'
    new_files=['system/controlDict','constant/'+control_name]
    if args.phase!='foundation_initial_phi':new_files+=['system/fvSolution','constant/transportProperties']
    for rel in new_files:
        path=plain_variants(case,rel,required=True)
        files[rel]=file_record(path)
        text=re.sub(r'/\*.*?\*/|//[^\n]*','',path.read_text(),flags=re.S)
        check('#' not in text,'Unhashed code/include directive in fresh input: '+rel)
        if rel=='system/fvSolution':
            text=re.sub(r'\$(?:p|U)\s*;','',text)
        check('$' not in text,'Unhashed expansion in fresh input: '+rel)
    controls=(case/'constant'/control_name).read_text()
    if args.phase=='foundation_initial_phi':
        check(args.backend=='cpu','Foundation initializer is CPU only');permission='allowInitialPhiExperiment'
    else:
        check(setting(controls,'backend')==args.backend,'Admission backend mismatch')
        expected='sharedPinnedPhi' if args.shared_phi_sha256 else 'computeFromPinnedU'
        check(setting(controls,'initialPhiPolicy')==expected,'Declared phi policy mismatch')
        check(setting(controls,'allowUnvalidatedBackendExperiment') in ('yes','true','on','1'),
            'Explicit unvalidated-backend permission is false')
        permission='allowInitialFieldsOnlyExperiment' if args.phase=='initial_fields_only' else 'allowFiveStepSourceExperiment'
    check(setting(controls,permission) in ('yes','true','on','1'),'Phase-specific experimental permission is false')
    experiment=setting(controls,'experimentId')
    check(experiment!='ROOT_CHOOSE_UNIQUE_ID' and re.fullmatch('[A-Za-z0-9_.-]{8,100}',experiment),
        'Choose a non-placeholder unique experiment ID before input auditing')
    return case,private,files,controls,experiment
def write_receipt(args,manifest):
    check(args.case and args.private_root and args.binary and args.library_identity,
        'Receipt needs existing case/private-root/binary/library-identity')
    case,private,files,controls,experiment=case_audit(args,manifest)
    output=real_path(args.write_launch_receipt,False);foam=output.with_suffix('.foam')
    check(output.suffix=='.json' and output.parent.is_dir(),'Use a new JSON receipt in an existing directory')
    check(not output.is_relative_to(case) and not output.exists() and not foam.exists(),
        'Receipt must be NEW and outside audited case; no overwrite')
    check(real_path(setting(controls,'experimentReceiptFile'),False)==foam,
        'Predeclared experimentReceiptFile must match new external companion')
    binary=file_record(real_path(args.binary));identity=file_record(real_path(args.library_identity))
    library_json=json.loads(Path(identity['path']).read_text())
    check(library_json.get('backend')==args.backend
        and isinstance(library_json.get('files'),list) and library_json['files'],
        'Library identity must declare backend and canonical file records')
    libraries=[]
    for expected in library_json['files']:
        check(isinstance(expected,dict) and 'path' in expected and 'sha256' in expected,
            'Malformed library identity record')
        record=file_record(real_path(expected['path']))
        check(record['sha256']==expected['sha256'],'Library identity file mismatch');libraries.append(record)
    argv=[binary['path'],'-case',str(case)]
    if args.phase=='initial_fields_only':argv+=['-initialFieldsOnly']
    receipt=dict(schema='c29-unvalidated-experiment-launch-receipt-v2',
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        created_epoch=time.time(),max_age_s=args.max_age_s,experiment_id=experiment,
        phase=args.phase,backend=args.backend,case=str(case),private_root=str(private),
        inputs=files,input_snapshot_sha256=digest(files),binary=binary,
        library_identity=identity,libraries=libraries,
        candidate_manifest_sha256=sha(HERE/'candidate_manifest.json'),
        validation_thresholds_sha256=sha(HERE/'validation_thresholds.json'),
        environment={key:os.environ.get(key) for key in ENV_KEYS},manual_argv=argv,
        shared_phi_sha256=args.shared_phi_sha256,inputs_audited=True,runtime_validated=False,
        scientific_acceptance='NOT ASSESSED',
        limitations='No launch. Recheck immediately before exact manual argv under frozen inputs/environment. C++ logs bindings but does not hash files. Root must compare declared libraries with actual loader evidence.')
    data=json.dumps(receipt,indent=2)+'\n';json_sha=hashlib.sha256(data.encode()).hexdigest()
    values={'schema':'c29-unvalidated-input-admission-v2','experimentId':experiment,
        'phase':args.phase,'backend':args.backend,'casePath':str(case),
        'inputsAudited':'true','runtimeValidated':'false',
        'inputSnapshotSha256':receipt['input_snapshot_sha256'],'launchReceiptJsonSha256':json_sha,
        'candidateManifestSha256':receipt['candidate_manifest_sha256'],
        'binarySha256':binary['sha256'],'libraryIdentitySha256':identity['sha256']}
    literal={'schema','phase','backend','inputsAudited','runtimeValidated'}
    text='\n'.join(k+' '+(v if k in literal else json.dumps(v))+';' for k,v in values.items())+'\n'
    # Exclusive publication: no existing receipt is overwritten; a partial pair cannot verify.
    with output.open('x',encoding='utf-8',newline='\n') as stream:stream.write(data)
    with foam.open('x',encoding='utf-8',newline='\n') as stream:stream.write(text)
    return {'launch_receipt':str(output),'launch_receipt_sha256':json_sha,
        'foam_receipt':str(foam),'foam_receipt_sha256':sha(foam),'manual_argv':argv,
        'runtime_validated':False,'solver_launched':False}
def verify_receipt(path):
    p=real_path(path);receipt=json.loads(p.read_text())
    check(receipt['schema']=='c29-unvalidated-experiment-launch-receipt-v2'
        and receipt['runtime_validated'] is False,'Wrong/validated receipt type')
    age=time.time()-receipt['created_epoch']
    check(0<=age<=receipt['max_age_s'],'Receipt expired/not yet valid; audit anew')
    check(sha(HERE/'candidate_manifest.json')==receipt['candidate_manifest_sha256'],'Candidate changed')
    check(digest(receipt['inputs'])==receipt['input_snapshot_sha256'],'Input snapshot corrupt')
    for record in [*receipt['inputs'].values(),receipt['binary'],receipt['library_identity'],*receipt['libraries']]:
        check(same_record(record),'Audited bytes/mtime changed: '+record['path'])
    check(receipt['environment']=={key:os.environ.get(key) for key in ENV_KEYS},'Environment changed')
    case=real_path(receipt['case']);plain_variants(case,'0.6/phi')
    for rel in receipt['inputs']:plain_variants(case,rel,required=True)
    if not receipt['shared_phi_sha256']:check(not (case/'0.6/phi').exists(),'New phi appeared')
    text=real_path(p.with_suffix('.foam')).read_text()
    expected={'schema':'c29-unvalidated-input-admission-v2','experimentId':receipt['experiment_id'],
        'phase':receipt['phase'],'backend':receipt['backend'],'casePath':receipt['case'],
        'inputsAudited':'true',
        'runtimeValidated':'false','launchReceiptJsonSha256':sha(p),
        'inputSnapshotSha256':receipt['input_snapshot_sha256'],
        'candidateManifestSha256':receipt['candidate_manifest_sha256'],
        'binarySha256':receipt['binary']['sha256'],
        'libraryIdentitySha256':receipt['library_identity']['sha256']}
    for key,value in expected.items():check(setting(text,key)==value,'Companion binding mismatch: '+key)
    return {'receipt_recheck':'ok; runtime remains UNVALIDATED',
        'manual_argv':receipt['manual_argv'],'solver_launched':False}
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case',type=Path);ap.add_argument('--private-root',type=Path)
    ap.add_argument('--shared-phi-sha256');ap.add_argument('--phase',choices=PHASES,default='five_fixed_steps')
    ap.add_argument('--backend',choices=('cpu','gpu'),default='cpu')
    ap.add_argument('--binary',type=Path);ap.add_argument('--library-identity',type=Path)
    ap.add_argument('--write-launch-receipt',type=Path);ap.add_argument('--verify-launch-receipt',type=Path)
    ap.add_argument('--max-age-s',type=int,default=300)
    args=ap.parse_args()
    try:
        manifest=source_audit();check(1<=args.max_age_s<=900,'Receipt age must be 1..900 s')
        if args.verify_launch_receipt:
            check(not args.case and not args.write_launch_receipt,'Receipt recheck is a separate mode')
            result=verify_receipt(args.verify_launch_receipt)
        elif args.write_launch_receipt:result=write_receipt(args,manifest)
        elif args.case:
            check(args.private_root,'Case audit needs explicit private root')
            case,_,files,_,_=case_audit(args,manifest)
            result={'case':str(case),'input_snapshot_sha256':digest(files),
                'admission':'No receipt issued; no launch; runtime UNVALIDATED'}
        else:
            check(not args.shared_phi_sha256,'Shared phi pin requires --case')
            result={'scope':'source-only','source_hashes':'ok','runtime_validated':False}
        result.update(status='ok',compiled=False,case_created=False)
        print(json.dumps(result,indent=2))
    except (OSError,ValueError,KeyError) as error:
        print(json.dumps({'status':'failed','error':str(error),'solver_launched':False},indent=2))
        raise SystemExit(1)
