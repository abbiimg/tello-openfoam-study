"""Preserve linked artifact/dependency identities; never run application main."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,shutil
OUT=Path(__file__).resolve().parent
PARENT=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation')
PROJECT=OUT.parents[2]
CANDIDATE=PROJECT/'work/gpu_actuator_port/candidate'
PIN='562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(CANDIDATE/'candidate_manifest.json')==PIN
targets={'foundation14_phi':(PARENT/'f14_phi_compat_v2_2_20261102','c29FoundationInitialPhi','cpu'),
    'native_cpu':(PARENT/'native_cpu_compat_v2_1_20261102','c29NativeHybridFoam','cpu'),
    'native_gpu':(PARENT/'native_gpu_compat_v2_1_20261102','c29NativeHybridFoam','gpu')}
results={}
for name,(prefix,exe,backend) in targets.items():
    binary=prefix/'bin'/exe;dependency=prefix/'runtime_dependency_audit.log'
    if not binary.is_file() or not dependency.is_file():continue
    raw=dependency.read_text();assert 'not found' not in raw
    libraries={}
    for line in raw.splitlines():
        match=re.search(r'=>\s+(/\S+)\s+\(',line)
        if not match:match=re.match(r'\s*(/\S+)\s+\(',line)
        if match:
            p=Path(match.group(1)).resolve();assert p.is_file()
            assert 'stubs' not in p.parts,'Runtime resolved a stub path: '+str(p)
            libraries[str(p)]={'path':str(p),'sha256':sha(p),'size_bytes':p.stat().st_size}
    assert libraries
    foam_libs=[p for p in libraries if Path(p).name.startswith(('libOpenFOAM','libfiniteVolume','libmeshTools','libPstream'))]
    expected='/opt/openfoam14/' if name=='foundation14_phi' else '/opt/openfoam-workspace/gpu-feasibility/native-'+('cpu-control/' if backend=='cpu' else 'stdpar/')
    assert all(p.startswith(expected) for p in foam_libs),'Wrong Foamy framework resolution'
    if backend=='cpu':assert not any('libcudart' in p or '/nvhpc/' in p for p in libraries),'CPU linked GPU runtime'
    identity={'schema':'c29-private-linked-library-identity-v1','backend':backend,
        'files':list(libraries.values()),'application_main_executed':False,
        'basis':'ldd dependency inspection in matching reviewed environment, not runtime/CFD evidence'}
    identity_path=prefix/'library_identity.json';identity_path.write_text(json.dumps(identity,indent=2)+'\n')
    copied={}
    for rel in ('build.log','environment.log','runtime_dependency_audit.log','elf_dynamic.log','elf_header.log','source_compatibility.json','source_clone.json','compatibility.patch','compatibility_from_v2_1.patch'):
        p=prefix/rel
        if p.is_file():
            dest=OUT/(name+'_'+rel.replace('/','_'))
            shutil.copyfile(p,dest);copied[rel]={'path':str(p),'sha256':sha(p),'portable_copy':str(dest)}
    result={'prefix':str(prefix),'binary':{'path':str(binary),'sha256':sha(binary),'size_bytes':binary.stat().st_size},
        'backend':backend,'library_identity':{'path':str(identity_path),'sha256':sha(identity_path)},
        'resolved_library_count':len(libraries),'framework_libraries':foam_libs,'artifacts':copied,
        'state':'LINKED ONLY; application/utility main NOT executed; no initialization or CFD/parity claim',
        'candidate_manifest_sha256':PIN,'compiler_jobs_max':1,'nice':15}
    results[name]=result
    (OUT/(name+'_linked_identity.json')).write_text(json.dumps(result,indent=2)+'\n')
(OUT/'linked_builds_summary.json').write_text(json.dumps({'recorded_utc':datetime.now(timezone.utc).isoformat(),
    'candidate_manifest_sha256':PIN,'builds':results,'no_case_or_solver_or_utility_execution':True},indent=2)+'\n')
print(json.dumps({name:{'binary':record['binary'],'library_identity':record['library_identity'],'state':record['state']} for name,record in results.items()},indent=2))
