"""UNUSED proposal: pure CPU/GKO method identity; no file or solver operations.

Not imported by production preparation, auditing or analysis. Adoption requires
the controlled accuracy/full-wall gate and separate integration review. This
module validates records; it does not re-hash installed libraries, prove their
runtime loading, authorize adoption, or prepare cases. A future collector and
runner must independently verify every recorded file before using this identity.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re


def canonical_digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),
                                     ensure_ascii=True).encode()).hexdigest()


def pressure_metadata(configuration):
    """Read canonical pressure dictionaries; GAMG switches are not GKO switches."""
    solvers=configuration['fvSolution']['solvers']
    names=[solvers[field].get('solver') for field in ('p','pFinal')]
    if names==[['GAMG'],['GAMG']]:
        direct={}
        for field in ('p','pFinal'):
            switch=solvers[field].get('directSolveCoarsest')
            if switch not in (['true'],['false']):
                raise ValueError('Use the existing GAMG canonicalizer, including its effective default switch')
            direct[field]=switch==['true']
        return dict(backend='native_openfoam',pressure_solver='GAMG',direct_coarsest=direct)
    if names!=[['GKOCG'],['GKOCG']]:
        raise ValueError('Unsupported or mixed pressure solver family')
    if configuration['decomposition']['numberOfSubdomains']!=['2']:
        raise ValueError('This proposal supports only the benchmarked two-rank GKO profile')
    expected=dict(executor=['cuda'],ranksPerGPU=['2'],forceHostBuffer=['true'],
                  splitMPIComm=['true'],MPIxRankOffload=['false'])
    for field in ('p','pFinal'):
        settings=solvers[field]
        if 'directSolveCoarsest' in settings:
            raise ValueError('Do not attach a GAMG direct-coarsest switch to GKO')
        if any(settings.get(key)!=value for key,value in expected.items()):
            raise ValueError('GKO executor/host-buffer/MPI policy differs from the proposed profile')
    return dict(backend='ogl_ginkgo_cuda',pressure_solver='GKOCG',
                direct_coarsest=dict(p=None,pFinal=None))


def _hash(value,description,length=64):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{'+str(length)+'}',value):
        raise ValueError('Invalid '+description)
    return value


def backend_identity(runtime):
    """Path-independent identity from structurally valid, externally verified records.

    Runtime paths, driver/device observations, gate decisions and case caches
    belong in the sidecar/provenance, rather than portable method identity.
    Scientific solver controls are already signed by fvSolution.
    """
    if runtime.get('schema')!='proposed-ogl-ginkgo-cuda-runtime-v1':
        raise ValueError('Unsupported proposed runtime schema')
    commits=runtime['source_commits']
    commits={name:_hash(commits[name],name+' commit',40) for name in ('OGL','Ginkgo')}
    patches=runtime['patch_sha256']
    patches={name:_hash(patches[name],name+' patch') for name in
             ('foundation14_compatibility','cuda_runtime_executor_audit')}
    source=runtime['patched_source_sha256']
    if not isinstance(source,dict) or not source:
        raise ValueError('Require recorded patched source hashes')
    source={name:_hash(value,'patched source hash') for name,value in sorted(source.items())}
    records=[]
    for record in runtime['library_records']:
        name=record['logical_name']
        if not isinstance(name,str) or not name or '/' in name or '\\' in name:
            raise ValueError('A library identity needs a portable logical name')
        size=record['size_bytes']
        if isinstance(size,bool) or not isinstance(size,int) or size<=0:
            raise ValueError('A library identity needs a positive byte count')
        records.append(dict(logical_name=name,sha256=_hash(record['sha256'],'library hash'),size_bytes=size))
    names=[record['logical_name'] for record in records]
    if len(names)!=len(set(names)):
        raise ValueError('Duplicate logical library name')
    for required in ('libOGL.so','libginkgo.so','libginkgo_cuda.so','libginkgo_reference.so',
                     'libcudart.so','libcusparse.so'):
        if required not in names:
            raise ValueError('Incomplete external library closure: '+required)
    if runtime.get('closure_complete') is not True:
        raise ValueError('The future collector must attest a complete loaded/runtime dependency closure')
    build=runtime['build']
    required=dict(openfoam_family='Foundation',openfoam_major_version=14,
                  label_bits=32,precision='double',architecture='SM121',fast_math=False)
    if any(build.get(k)!=v for k,v in required.items()):
        raise ValueError('Build target/precision differs from the proposed benchmark profile')
    for name in ('compiler_version','cuda_toolkit_version','build_flags_sha256'):
        if not isinstance(build.get(name),str) or not build[name]:
            raise ValueError('Missing build identity: '+name)
    _hash(build['build_flags_sha256'],'build flags')
    execution=runtime['execution_policy']
    expected=dict(mpi_ranks=2,threads_per_rank=1,gpu_owners=1,device_id=0,
                  force_host_buffer=True,gpu_aware_mpi=False,split_mpi_comm=True)
    if execution!=expected:
        raise ValueError('Runtime rank/device/staging policy differs from the proposed profile')
    return dict(schema=runtime['schema'],source_commits=commits,patch_sha256=patches,
        patched_source_sha256=source,library_records=sorted(records,key=lambda r:r['logical_name']),
        build=copy.deepcopy(build),execution_policy=copy.deepcopy(expected))


def bind_method_identity(configuration,runtime=None):
    """Keep CPU digests byte-for-byte equivalent; add identity only to GKO.

    Input configuration must already be expanded/canonicalized by OpenFOAM's
    dictionary machinery. No defaults or new fields are added to native CPU
    configurations, preserving be7fb…/1bc1e… and all existing CPU signatures.
    """
    result=copy.deepcopy(configuration)
    pressure=pressure_metadata(result)
    if pressure['backend']=='native_openfoam':
        if runtime is not None or 'external_pressure_backend' in result:
            raise ValueError('A native CPU method cannot acquire an external backend identity')
    else:
        if runtime is None:
            raise ValueError('An external pressure solver requires verified runtime records')
        identity=backend_identity(runtime)
        prior=result.get('external_pressure_backend')
        # The experimental benchmark's weaker e382… signature is retained in
        # its frozen files, never silently promoted to a production identity.
        if prior is not None and prior!=identity:
            raise ValueError('Existing external identity differs; preserve benchmark and create a fresh production configuration')
        result['external_pressure_backend']=identity
    return result,canonical_digest(result),pressure
