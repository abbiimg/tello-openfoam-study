"""Verify/restore completed historical CPU evidence for offline analysis only.

No compiler, solver, profiler, subprocess, GPU call or launch authorization.
Default is read-only validation. --restore-to creates an EXCLUSIVE NEW tree.
Requires the pinned existing benchmark_reproduction/shared_seed.zip; it is not
duplicated in this addendum. Imported historical sources remain byte-identical.
"""
from pathlib import Path, PurePosixPath
import argparse, hashlib, json, os, shutil, stat, sys, zipfile
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
SEED_SHA='89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb'
SEED_BYTES=62823211
REPRO_SHA='e75dea5cbaaae870cf568266d95a61cc3fa28a288c4d39113e00aecc08a880c9'
CPU_MANIFEST_SHA='5194b4442563947edc79af4f273dc67bc1b486b39e08d740352627d40c607f80'

def require(ok,msg):
    if not ok:raise ValueError(msg)
def no_links(path):
    p=Path(path).absolute();require('..' not in p.parts,'Parent escape')
    for q in (p,*p.parents):require(not q.is_symlink(),'Symlink/ancestor: '+str(q))
    return p
def relative(name):
    require(isinstance(name,str) and name and not any(x in name for x in ('\\',':','\0')),'Unsafe name')
    require(all(x not in ('','.','..') for x in name.split('/')),'Unsafe component')
    p=PurePosixPath(name);require(not p.is_absolute(),'Absolute member');return p
def joined(root,name):
    return no_links(root/relative(name))
def digest(path):
    h=hashlib.sha256()
    with no_links(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(2**20),b''):h.update(chunk)
    return h.hexdigest()
def checked(path,record):
    p=no_links(path);require(p.is_file(),'Missing '+str(p))
    require(digest(p)==record['sha256'],'Hash differs '+str(p))
    if 'size_bytes' in record:require(p.stat().st_size==record['size_bytes'],'Size differs '+str(p))
    return p
def read_json(path,pin=None):
    if pin:checked(path,{'sha256':pin})
    return json.loads(no_links(path).read_text())
def copy(source,target):
    target=no_links(target);target.parent.mkdir(parents=True,exist_ok=True)
    with no_links(source).open('rb') as src,target.open('xb') as dst:shutil.copyfileobj(src,dst,2**20)
    require(digest(target)==digest(source),'Copy hash differs')

def preflight(package,seed):
    package=no_links(package);seed=checked(seed,{'sha256':SEED_SHA,'size_bytes':SEED_BYTES})
    # The existing published catalogue supplies initial U/p and the unchanged mesh.
    repro=read_json(seed.parent/'reproduction_manifest.json',REPRO_SHA)
    original=read_json(seed.parent/'overrides/cpu_serial/benchmark_manifest.json',CPU_MANIFEST_SHA)
    shared=repro['shared_seed_files'];overrides=repro['variants']['cpu_serial']['override_files']
    require(not set(shared)&set(overrides),'Overlapping seed/override names')
    for name in (*shared,*overrides):relative(name)
    with zipfile.ZipFile(seed) as z:
        names=z.namelist();require(len(names)==len(set(names)) and set(names)==set(shared),'ZIP catalogue differs')
        for info in z.infolist():
            relative(info.filename);mode=info.external_attr>>16
            require(not stat.S_ISLNK(mode) and not info.is_dir(),'Nonregular seed member')
            h=hashlib.sha256()
            with z.open(info) as stream:
                for b in iter(lambda:stream.read(2**20),b''):h.update(b)
            require(h.hexdigest()==shared[info.filename]['sha256'] and info.file_size==shared[info.filename]['size_bytes'],'Seed member differs')
    for name,rec in overrides.items():checked(joined(seed.parent/'overrides/cpu_serial',name),rec)
    fields=read_json(package/'SAVED_FIELD_CATALOGUE.json')
    expected={(r,t,f) for r in ('foundation14_control','native_cpu')
              for t in ('0.6001','0.6002','0.6003','0.6004','0.6005') for f in ('U','p','phi')}
    observed=[]
    for rec in fields['saved_fields']:
        selection=(rec['role'],rec['time'],rec['field']);require(selection in expected,'Unexpected field selection')
        require(rec['path']=='saved_fields/'+'/'.join(selection),'Field path/selection disagree')
        observed.append(selection)
    require(len(observed)==len(set(observed)) and set(observed)==expected,'Unknown/duplicate/omitted fields')
    require(fields['canonical_initial_phi']['path']=='shared_initial/phi','Unexpected canonical phi path')
    for rec in fields['saved_fields']+[fields['canonical_initial_phi']]:checked(joined(package,rec['path']),rec)
    require(len(fields['saved_fields'])==30,'All30 saved fields required')
    inputs=read_json(package/'CASE_INPUT_CATALOGUE.json')
    for role,catalogue in inputs.items():
        require(role in ('foundation14_control','native_cpu'),'Unknown role')
        for name,rec in catalogue.items():
            relative(name)
            if rec['delivery'].startswith('case_inputs/'):checked(joined(package,rec['delivery']),rec)
            elif name.startswith('dynamicCode/'):pass # intentionally excluded compiled historical cache
            elif name in ('0.6/c29_initialU','0.6/c29_initialP','0.6/c29_initialPhi'):
                pass # startup audit observations: recorded hashes/results; not used by mechanical replay
            elif name=='0.6/phi':require(rec['sha256']==fields['canonical_initial_phi']['sha256'],'Initial phi differs')
            else:require(name in original['frozen_inputs'] and rec['sha256']==original['frozen_inputs'][name]['sha256'],'Seed dependency unresolved: '+name)
    return repro,fields,inputs

def restore(package,seed,destination,repro,fields,inputs):
    destination=no_links(destination)
    require(not destination.exists() and destination.parent.is_dir(),'Use a new tree in an existing parent')
    names_by_role={r:set(repro['shared_seed_files'])|set(repro['variants']['cpu_serial']['override_files'])|set(c) for r,c in inputs.items()}
    for role,names in names_by_role.items():
        for name in names:
            if not name.startswith('dynamicCode/'):joined(destination/role,name)
    for rec in fields['saved_fields']:joined(destination/rec['role'],rec['time']+'/'+rec['field'])
    destination.mkdir()
    for role in inputs:
        root=destination/role;root.mkdir()
        with zipfile.ZipFile(seed) as z:
            for info in z.infolist():
                p=joined(root,info.filename);p.parent.mkdir(parents=True,exist_ok=True)
                with z.open(info) as src,p.open('xb') as dst:shutil.copyfileobj(src,dst,2**20)
        # Published overrides and strict inputs intentionally replace only exact
        # seed/override bytes in this NEW destination, never the evidence sources.
        layers=[(seed.parent/'overrides/cpu_serial',repro['variants']['cpu_serial']['override_files']),
                (package/'case_inputs'/role,{n:r for n,r in inputs[role].items() if r['delivery'].startswith('case_inputs/')})]
        for source,catalogue in layers:
            for name,rec in catalogue.items():
                src=checked(joined(source,name),rec);target=joined(root,name)
                if target.exists():
                    require(name in repro['shared_seed_files'] or name in repro['variants']['cpu_serial']['override_files'],'Unexpected collision')
                    target.unlink() # only exact known newly extracted regular file
                copy(src,target)
        copy(package/fields['canonical_initial_phi']['path'],root/'0.6/phi')
    for rec in fields['saved_fields']:
        copy(package/rec['path'],destination/rec['role']/rec['time']/rec['field'])
    # Relocate only historical audit paths, preserving audited byte hashes and
    # published original audit. This DERIVED copy grants no runtime permission.
    audit=read_json(package/'evidence/strict_runs/root_input_audit.json')
    audit['cases']={role:record for role,record in audit['cases'].items() if role in ('f14','cpu')}
    for role,record in audit['cases'].items():
        directory='foundation14_control' if role=='f14' else 'native_cpu'
        record['case']=str(destination/directory)
        record['fvSolution']['path']=str(destination/directory/'system/fvSolution')
        if role=='cpu':record['c29PortControls']['path']=str(destination/directory/'constant/c29PortControls')
    audit['root_authorization']['path']=str(package/'evidence/strict_pressure_proposal/root_authorization.json')
    path=destination/'offline_relocated_input_audit.json'
    path.write_text(json.dumps(audit,indent=2)+'\n')
    receipt={'schema':'offline-historical-evidence-relocation-v1','runtime_admission':False,'compiler_or_CFD_run':False,
        'original_input_audit_sha256':digest(package/'evidence/strict_runs/root_input_audit.json'),
        'derived_input_audit_sha256':digest(path),'source_package':str(package),'seed_sha256':SEED_SHA,
        'compiled_F14_dynamicCode_intentionally_absent':True,'no_source_evidence_modified':True}
    (destination/'OFFLINE_RELOCATION.json').write_text(json.dumps(receipt,indent=2)+'\n')

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package',type=Path,default=HERE.parent)
    ap.add_argument('--seed',type=Path,required=True)
    ap.add_argument('--restore-to',type=Path)
    args=ap.parse_args();package=no_links(args.package);seed=no_links(args.seed)
    repro,fields,inputs=preflight(package,seed)
    if args.restore_to:restore(package,seed,no_links(args.restore_to),repro,fields,inputs)
    print(json.dumps({'read_only_preflight_passed':True,'saved_fields':30,'seed_not_duplicated_in_package':True,
        'restored_to':str(args.restore_to) if args.restore_to else None,'compiler_or_CFD_run':False,'runtime_admission':False},indent=2))
if __name__=='__main__':main()
