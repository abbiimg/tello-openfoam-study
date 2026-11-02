"""Restore one fresh benchmark from shared_seed.zip and a small override layer.

Requires the recorded Foundation14 runtime. This program never launches CFD.
CUDA additionally requires the verified private library closure at its recorded
paths; no SDK or build tree is embedded in this reproduction package.
"""
from pathlib import Path, PurePosixPath
import argparse
import grp
import hashlib
import json
import os
import pwd
import shutil
import stat
import subprocess
import zipfile


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): h.update(block)
    return h.hexdigest()


def safe_relative(value):
    relative=PurePosixPath(value)
    assert not relative.is_absolute() and '..' not in relative.parts
    return relative


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--variant',choices=('cpu_serial','cpu_mpi2','cuda_mpi2'),required=True)
    parser.add_argument('--dest',type=Path,required=True,help='Fresh native Linux directory; never an original case')
    parser.add_argument('--owner',help='Optional user:group, e.g. openfoam:openfoam when restoring as root')
    args=parser.parse_args()
    assert os.environ.get('WM_PROJECT_VERSION')=='14','Source /opt/openfoam14/etc/bashrc first'
    here=Path(__file__).resolve().parent
    package=json.loads((here/'reproduction_manifest.json').read_text())
    dest=args.dest.resolve()
    assert not dest.exists(),'Never overwrite an existing directory'
    for immutable in package['forbidden_destination_roots']:
        assert not dest.is_relative_to(Path(immutable).resolve()),'Use a fresh directory outside original studies/benchmarks'
    archive=here/'shared_seed.zip'
    assert digest(archive)==package['shared_seed_archive']['sha256'],'Shared seed archive changed'
    variant=package['variants'][args.variant]
    original_manifest=here/'overrides'/args.variant/'benchmark_manifest.json'
    assert digest(original_manifest)==variant['benchmark_manifest_sha256']
    case_manifest=json.loads(original_manifest.read_text())
    if case_manifest.get('gpu_library'):
        backend=case_manifest['gpu_library']
        assert Path(backend['path']).is_file() and digest(Path(backend['path']))==backend['sha256'], 'The recorded private CUDA adapter is required; see INSTRUCTIONS.txt'
        for item in backend['ginkgo_library_closure']:
            assert Path(item['path']).is_file() and digest(Path(item['path']))==item['sha256'],item['path']
    dest.mkdir(parents=True)
    with zipfile.ZipFile(archive) as stream:
        assert set(stream.namelist())==set(package['shared_seed_files'])
        for item in stream.infolist():
            relative=safe_relative(item.filename)
            assert not stat.S_ISLNK(item.external_attr>>16),'No symlink extraction'
            target=dest/relative
            assert target.resolve().is_relative_to(dest)
            target.parent.mkdir(parents=True,exist_ok=True)
            with stream.open(item) as source,target.open('xb') as output:
                shutil.copyfileobj(source,output,1024*1024)
    for relative,record in variant['override_files'].items():
        relative=safe_relative(relative)
        source=here/'overrides'/args.variant/relative
        assert digest(source)==record['sha256']
        target=dest/relative
        assert not target.exists(),'Override layers must be disjoint from shared seed files'
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
    for relative,record in case_manifest['frozen_inputs'].items():
        path=dest/safe_relative(relative)
        assert path.stat().st_size==record['size_bytes'] and digest(path)==record['sha256'],relative
    (dest/'Allrun').chmod(0o755)
    for directory in ('runtime_cache/cuda','runtime_cache/tmp'):
        (dest/directory).mkdir(parents=True,exist_ok=True)
    report=dict(schema='restored-shared-benchmark-seed-v1',variant=args.variant,
        source_archive_sha256=package['shared_seed_archive']['sha256'],
        benchmark_manifest_sha256=variant['benchmark_manifest_sha256'],
        solver_configuration_sha256=case_manifest['solver_configuration_sha256'],
        initial_inputs_byte_verified=True,solver_launched=False)
    (dest/'reproduction_initialization.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.owner:
        assert os.geteuid()==0,'Owner change requires root'
        user,group=args.owner.split(':',1)
        uid=pwd.getpwnam(user).pw_uid;gid=grp.getgrnam(group).gr_gid
        for path in (dest,*dest.rglob('*')):
            assert path.resolve().is_relative_to(dest)
            os.chown(path,uid,gid)
    subprocess.run(['python3',str(dest/'run_benchmark.py'),'--case',str(dest),'--verify-only'],check=True)
    print(json.dumps(dict(report,case=str(dest)),indent=2))


if __name__=='__main__': main()
