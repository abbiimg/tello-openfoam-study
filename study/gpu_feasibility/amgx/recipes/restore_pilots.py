"""Restore fresh portable cavity or C29 rotor pilot inputs; never launches CFD.

Requires Foundation14 sourced. The rotor mode requires the separate frozen
benchmark_reproduction package, including its checksum-verified shared_seed.zip.
The original machine reused a verified C29 library; this portable recipe allows
OpenFOAM to compile the identical coded source privately, one job per pilot.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import zipfile

SEED_SHA='89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb'
CPU_MANIFEST_SHA='5194b4442563947edc79af4f273dc67bc1b486b39e08d740352627d40c607f80'

def require(condition,message):
    if not condition: raise ValueError(message)

def safe_relative(value):
    """External catalogue names must be literal portable relative file paths."""
    require(isinstance(value,str) and bool(value),'Empty or non-string relative path')
    require(not any(c in value for c in ('\\',':','\x00')),'Non-portable path separator, drive or NUL: '+repr(value))
    require(all(part not in ('','.','..') for part in value.split('/')),'Absolute, empty, dot or traversal component: '+repr(value))
    result=PurePosixPath(value)
    require(not result.is_absolute(),'Absolute path: '+repr(value))
    return result

def no_symlink_path(path):
    """Reject existing symlinks at the leaf or any ancestor, including dangling links."""
    path=Path(path).absolute()
    for component in (path,*path.parents):
        require(not component.is_symlink(),'Symlink traversal is not supported: '+str(component))
    return path

def safe_join(root,value,must_exist=False):
    root=no_symlink_path(root)
    relative=safe_relative(value)
    target=no_symlink_path(root.joinpath(*relative.parts))
    require(target.resolve().is_relative_to(root.resolve()) and target.resolve()!=root.resolve(),
            'Path escaped its exact selected root: '+repr(value))
    if must_exist: require(target.is_file(),'Required regular file is absent: '+str(target))
    return target

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def rec(path): return dict(sha256=sha(path),size_bytes=path.stat().st_size)

def load_pinned_cpu_manifest(path,variant):
    require(variant['benchmark_manifest_sha256']==CPU_MANIFEST_SHA,'CPU manifest metadata does not match the fixed pin')
    original=safe_join(path,'overrides/cpu_serial/benchmark_manifest.json',must_exist=True)
    require(sha(original)==CPU_MANIFEST_SHA,'CPU benchmark manifest differs from the fixed pin')
    return json.loads(original.read_text())

def validate_catalogues(manifest,variant,original):
    """Validate every external name and expected record before destination creation."""
    for catalogue in (manifest['shared_seed_files'],variant['override_files'],original['frozen_inputs']):
        require(isinstance(catalogue,dict),'Expected a file catalogue')
        for relative in catalogue: safe_relative(relative)
    shared=manifest['shared_seed_files']; overrides=variant['override_files']; frozen=original['frozen_inputs']
    require(not set(shared)&set(overrides),'Shared seed and override layers overlap')
    require(set(shared)|set(overrides)==set(frozen)|{'benchmark_manifest.json'},'Unexpected source inventory')
    for relative,record in {**shared,**overrides}.items():
        if relative=='benchmark_manifest.json':
            require(record['sha256']==CPU_MANIFEST_SHA,'Override CPU manifest record differs from fixed pin')
        else:
            require(record==frozen[relative],'External record differs from pinned frozen inputs: '+relative)

def verify_seed(path):
    path=no_symlink_path(path)
    manifest=json.loads(safe_join(path,'reproduction_manifest.json',must_exist=True).read_text())
    require(manifest['shared_seed_archive']['sha256']==SEED_SHA,'Shared ZIP metadata differs from fixed pin')
    archive=safe_join(path,'shared_seed.zip',must_exist=True)
    require(sha(archive)==SEED_SHA,'Shared ZIP differs from fixed pin')
    variant=manifest['variants']['cpu_serial']
    original=load_pinned_cpu_manifest(path,variant)
    validate_catalogues(manifest,variant,original)
    override_root=no_symlink_path(path/'overrides/cpu_serial')
    for rel,record in variant['override_files'].items():
        require(rec(safe_join(override_root,rel,must_exist=True))==record,'Override hash or size changed: '+rel)
    with zipfile.ZipFile(archive) as z:
        require(len(z.namelist())==len(set(z.namelist())),'Duplicate ZIP member')
        require(set(z.namelist())==set(manifest['shared_seed_files']),'ZIP inventory mismatch')
        for item in z.infolist():
            safe_relative(item.filename)
            require(not stat.S_ISLNK(item.external_attr>>16),'Symlink ZIP member: '+item.filename)
    return manifest,variant,original

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--kind',choices=('cavity','rotor'),required=True)
    p.add_argument('--case-root',type=Path)
    p.add_argument('--amgx-prefix',type=Path)
    p.add_argument('--cuda-root',type=Path)
    p.add_argument('--seed-dir',type=Path)
    p.add_argument('--verify-seed-only',action='store_true')
    a=p.parse_args()
    bundle=Path(__file__).resolve().parents[1]
    if a.kind=='rotor':
        assert a.seed_dir
        seed,variant,original=verify_seed(a.seed_dir)
        if a.verify_seed_only:
            print(json.dumps(dict(verified=True,archive_sha256=SEED_SHA,solver_launched=False)))
            return
    assert not a.verify_seed_only
    assert os.environ.get('WM_PROJECT_VERSION')=='14'
    assert a.case_root and a.amgx_prefix and a.cuda_root
    base=no_symlink_path(a.case_root).resolve(); prefix=a.amgx_prefix.resolve(); cuda=a.cuda_root.resolve()
    assert not base.exists(), 'Use a fresh case root; nothing is overwritten'
    for file in ('libAmgXPressure.so','libamgxLaunchAudit.so','libamgxsh.so'):
        assert (prefix/'install/lib'/file).is_file()
    # Check all external destination names for both future cases before mkdir.
    if a.kind=='rotor':
        for backend in ('native','amgx'):
            case=safe_join(base,a.kind+'-'+backend)
            for relative in (*seed['shared_seed_files'],*variant['override_files'],*original['frozen_inputs']):
                safe_join(case,relative)
    base.mkdir(parents=True)
    reports={}
    def edit(case,file,entry,value):
        subprocess.run(['foamDictionary',str(case/file),'-entry',entry,'-set',value],check=True,stdout=subprocess.DEVNULL)
    for backend in ('native','amgx'):
        case=base/(a.kind+'-'+backend)
        if a.kind=='cavity':
            shutil.copytree(bundle/'case-inputs/cavity-native',case)
        else:
            case.mkdir()
            with zipfile.ZipFile(safe_join(a.seed_dir,'shared_seed.zip',must_exist=True)) as z:
                for item in z.infolist():
                    require(not stat.S_ISLNK(item.external_attr>>16),'Symlink ZIP member')
                    target=safe_join(case,item.filename)
                    target.parent.mkdir(parents=True,exist_ok=True)
                    target=safe_join(case,item.filename)
                    with z.open(item) as src,target.open('xb') as dst: shutil.copyfileobj(src,dst)
            for rel in variant['override_files']:
                target=safe_join(case,rel); assert not target.exists()
                source=safe_join(a.seed_dir/'overrides/cpu_serial',rel,must_exist=True)
                target.parent.mkdir(parents=True,exist_ok=True)
                target=safe_join(case,rel)
                with source.open('rb') as src,target.open('xb') as dst: shutil.copyfileobj(src,dst)
            for rel,record in original['frozen_inputs'].items(): assert rec(safe_join(case,rel,must_exist=True))==record
            edit(case,'system/controlDict','endTime','0.60085')
            edit(case,'system/controlDict','functions','''{
pilotFields {type writeObjects; libs ("libutilityFunctionObjects.so"); objects (U p phi);
writeOption anyWrite; writeControl timeStep; writeInterval 5;}}
''')
        gpu=backend=='amgx'
        if gpu:
            edit(case,'system/controlDict','libs',f'("{prefix}/install/lib/libAmgXPressure.so")')
            tolerance='1e-7' if a.kind=='rotor' else '1e-11'
            for field,reltol in (('p','.05' if a.kind=='rotor' else '0'),('pFinal','0')):
                edit(case,'system/fvSolution','solvers/'+field,
                     '{solver AmgXPressure; tolerance '+tolerance+'; relTol '+reltol+'; maxIter 1000; minIter 0;}')
        for rel in ('runtime_cache/cuda','runtime_cache/tmp'): (case/rel).mkdir(parents=True)
        environment=(f'export LD_LIBRARY_PATH="{prefix}/install/lib:{cuda}/lib:{cuda}/lib64:/usr/lib/wsl/lib:$LD_LIBRARY_PATH"\n'
                     f'export LD_PRELOAD="{prefix}/install/lib/libamgxLaunchAudit.so"\n') if gpu else ''
        runner=case/'AllrunPilot'
        runner.write_text(f'''#!/bin/bash
set -e
cd "$(dirname "$0")"
source "${{FOAM_BASHRC:-/opt/openfoam14/etc/bashrc}}"
set -u -o pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 WM_NCOMPPROCS=1
export CUDA_CACHE_PATH="$PWD/runtime_cache/cuda" TMPDIR="$PWD/runtime_cache/tmp" XDG_CACHE_HOME="$PWD/runtime_cache"
[[ -e constant/polyMesh/points ]] || nice -n 15 blockMesh
{environment}exec nice -n 15 timeout --signal=TERM --kill-after=15 900 foamRun
''')
        runner.chmod(0o755)
        # Disable the inherited historical benchmark launcher in this fresh copy.
        (case/'Allrun').write_text('#!/bin/bash\nset -e\nexec bash "$(dirname "$0")/AllrunPilot"\n')
        reports[case.name]={str(f.relative_to(case)):rec(f) for f in case.rglob('*') if f.is_file()}
    (base/'restoration.json').write_text(json.dumps(dict(kind=a.kind,solver_launched=False,
        seed_sha256=SEED_SHA if a.kind=='rotor' else None,inputs=reports),indent=2)+'\n')
    print(json.dumps(dict(case_root=str(base),cases=list(reports),solver_launched=False),indent=2))

if __name__=='__main__': main()
