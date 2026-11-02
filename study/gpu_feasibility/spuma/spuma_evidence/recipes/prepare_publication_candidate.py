"""Prepare a work-only source/evidence candidate for root review; no publishing."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess

def copy_exact(source,destination):
    source=Path(source);destination=Path(destination)
    data=source.read_bytes();destination.parent.mkdir(parents=True,exist_ok=True)
    if destination.exists():
        assert destination.read_bytes()==data,'Refuse to overwrite different candidate bytes'
        return str(destination)
    with destination.open('xb') as stream:stream.write(data)
    assert destination.read_bytes()==data
    return str(destination)

def copy_tree_exact(source,destination):
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    for path in sorted(source.rglob('*')):
        assert not path.is_symlink()
        if path.is_dir():(destination/path.relative_to(source)).mkdir(parents=True,exist_ok=True)
        elif path.is_file():copy_exact(path,destination/path.relative_to(source))
    return str(destination)

WORK=Path(__file__).resolve().parent;PROJECT=WORK.parents[1]
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source'
CASES=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102')
CANDIDATE=WORK/'publication_candidate'
assert os.getuid()==999
if CANDIDATE.exists():
    # The first byte copy succeeded but DrvFS rejected copy2 metadata. Permit
    # only exact matching core bytes from that recorded partial attempt.
    for path in CANDIDATE.rglob('*'):
        if not path.is_file():continue
        relative=path.relative_to(CANDIDATE)
        assert relative.parts[:2]==('spuma_evidence','core')
        original=PROJECT/'outputs/tello_refinement/gpu_feasibility'/relative
        assert original.is_file() and path.read_bytes()==original.read_bytes()
else:CANDIDATE.mkdir()
OUTPUT=CANDIDATE;EVIDENCE=CANDIDATE/'spuma_evidence'
copy_tree_exact(PROJECT/'outputs/tello_refinement/gpu_feasibility/spuma_evidence/core',EVIDENCE/'core')
assert os.getuid()==999;os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
gate=json.loads((BASE/'provenance/spuma_strict_v2_tutorial_gate.json').read_text());assert gate['state']=='passed'
original=json.loads((BASE/'provenance/original_attempt/original_attempt_diagnostic.json').read_text())
assert original['original_all_corrector_screen_passed'] is False and original['actual_icoFoam_returncode']==-15
annotation=gate['protocol']['source_annotation']
assert subprocess.check_output(['git','-C',str(SOURCE),'rev-parse','HEAD'],text=True).strip()==gate['protocol']['source_pin']
assert subprocess.check_output(['git','-C',str(SOURCE),'diff','--name-only','HEAD'],text=True).splitlines()==[annotation['path']]
assert digest(SOURCE/annotation['path'])==annotation['annotated_sha256']
assert (EVIDENCE/'core/manifest.json').is_file()
for name in ['strict_v2','original_failed','recipes','build_logs']:
    folder=EVIDENCE/name;assert not folder.exists();folder.mkdir(parents=True)
for label,case in [('strict_v2',CASES/'cavity_gpu_fixedpool_strict_v2'),('original_failed',CASES/'cavity_gpu_fixedpool')]:
    for proc in Path('/proc').iterdir():
        if not proc.name.isdigit():continue
        try:assert os.readlink(proc/'cwd')!=str(case),'Owned case process still active'
        except (FileNotFoundError,PermissionError,ProcessLookupError):pass
    for path in sorted(case.rglob('*')):
        if not path.is_file() or path.is_symlink():continue
        assert path.stat().st_size<(512 if path.suffix in ['.sqlite','.nsys-rep'] else 16)*1024**2
        dest=EVIDENCE/label/path.relative_to(case);dest.parent.mkdir(parents=True,exist_ok=True);copy_exact(path,dest)
for name in ['source_staging.json','build_progress.json']:copy_exact(BASE/name,EVIDENCE/name)
for name in ['private_build_configuration.json','minimal_build_journal.json','stub_pic_wrapper_install.json',
             'finiteVolume_link_retry.json','finiteVolume_preserved_objects.json','ico_time_loop_annotation.json',
             'ico_first_step_annotation.json','ico_first_step_build.json','protocol_strict_v2.json',
             'strict_v2_validation_frozen.json','spuma_strict_v2_cfd_first_step_gpu_gate.json','spuma_strict_v2_tutorial_gate.json',
             'strict_v2_process_identity_audit.json']:
    copy_exact(BASE/'provenance'/name,EVIDENCE/name)
copy_exact(BASE/'provenance/original_attempt/original_attempt_diagnostic.json',EVIDENCE/'original_attempt_diagnostic.json')
for path in sorted((BASE/'logs').iterdir()):
    if path.is_file() and path.suffix in ['.log','.jsonl']:
        assert path.stat().st_size<128*1024**2;copy_exact(path,EVIDENCE/'build_logs'/path.name)
stub=BASE/'provenance/stub_compilations'
if stub.is_dir():copy_tree_exact(stub,EVIDENCE/'build_logs/generated_registration_sources')
for name in ['configure_private_build.py','build_minimal_spuma.py','build_budget.json','spuma_pool_device_marker.C',
             'prepare_core_executor_gate.py','run_core_executor_gate.py','stub_gcc_wrapper.py','install_stub_pic_wrapper.py',
             'retry_finiteVolume_link.py','instrument_ico_time_loop.py','instrument_first_step.py','rebuild_first_step_ico.py',
             'prepare_smoke_case.py','freeze_original_attempt.py','build_smoke_helpers.py','cuda_runtime_observer.cpp',
             'prepare_strict_v2.py','freeze_strict_validation.py','audit_strict_v2_first_step.py','validate_strict_v2.py',
             'audit_strict_process_identity.py','prepare_publication_candidate.py']:
    copy_exact(WORK/name,EVIDENCE/'recipes'/name)
copy_exact(PROJECT/'work/stage_private_spuma_sources.py',EVIDENCE/'recipes/stage_private_spuma_sources.py')
copy_exact(BASE/'env.sh',EVIDENCE/'recipes/private_env.sh')
for name in ['ico_time_loop_annotation.patch','ico_first_step_annotation.patch']:copy_exact(BASE/'patches'/name,EVIDENCE/'recipes'/name)
if (SOURCE/'COPYING').is_file():copy_exact(SOURCE/'COPYING',EVIDENCE/'UPSTREAM_COPYING')
# Exact small upstream source/rules only, not the SDK or a build tree.
source_dir=EVIDENCE/'upstream_source';source_dir.mkdir()
for path,name in [(BASE/'provenance/icoFoam.upstream.C','icoFoam.upstream.C'),
                  (BASE/'provenance/original_attempt/icoFoam.annotated_original.C','icoFoam.original_full_loop_annotation.C'),
                  (SOURCE/annotation['path'],'icoFoam.first_step_annotation.C')]:
    copy_exact(path,source_dir/name)
rules={}
for relative in ['wmake/rules/linuxARM64Nvidia','wmake/rules/General/Nvidia']:
    for path in sorted((SOURCE/relative).rglob('*')):
        if not path.is_file():continue
        assert path.stat().st_size<256*1024
        dest=EVIDENCE/'upstream_rules'/path.relative_to(SOURCE);dest.parent.mkdir(parents=True,exist_ok=True);copy_exact(path,dest)
        rules[str(path.relative_to(SOURCE))]=digest(path)
for relative in ['applications/solvers/incompressible/icoFoam/Make/options','applications/solvers/incompressible/icoFoam/Make/files',
                 'applications/utilities/mesh/generation/blockMesh/Make/options']:
    dest=EVIDENCE/'upstream_rules'/relative;dest.parent.mkdir(parents=True,exist_ok=True);copy_exact(SOURCE/relative,dest)
    rules[relative]=digest(SOURCE/relative)
(EVIDENCE/'upstream_rules_manifest.json').write_text(json.dumps({'source_pin':gate['protocol']['source_pin'],'sha256':rules},indent=2)+'\n')
prerequisites={'kind':'References only: shared SDK/tool prerequisite installation is not copied',
    'shared_SDK_root':'/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9',
    'CUDA_subdirectory':'cuda/13.3','SDK_reused_readonly':True,
    'shared_compiler_gate':'/opt/openfoam-workspace/gpu-feasibility/native-stdpar/provenance/stdpar_compiler_gate.json',
    'shared_device_gate':'/opt/openfoam-workspace/gpu-feasibility/native-stdpar/provenance/stdpar_device_marker_gate.json',
    'shared_bison_prefix':'/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/bison',
    'CFD_seed':'Fresh stock cavity 0/U and 0/p included; no rotor or mapped CFD seed is used',
    'Umpire_mode':'Not used by this fixed-pool SPUMA test',
    'excluded':['SDK/archive/compiler/ELF/binaries','full upstream or build trees','credentials','unrelated private helpers'],
    'source_and_binary_identities':{'old_binary_sha256':original['old_binary_sha256'],
       'strict_binary_sha256':gate['protocol']['source_build']['binary_sha256'],
       'original_upstream_source_sha256':annotation['upstream_sha256'],
       'original_full_loop_annotation_sha256':annotation['previous_annotated_sha256'],
       'strict_first_step_annotation_sha256':annotation['annotated_sha256']}}
(EVIDENCE/'prerequisite_references_and_identities.json').write_text(json.dumps(prerequisites,indent=2)+'\n')

api=gate['first_complete_CFD_step_API_gate']
document=f'''# SPUMA review candidate: bounded GPU functional test

SPUMA v2512 at `{gate['protocol']['source_pin']}` built privately on ARM64
and passed a distinct, preregistered five-step CUDA cavity functional test.
It reached 0.025 s with actual icoFoam and Allrun returncodes zero. This is an
installation/coverage result, not a rotor result, steady cavity benchmark,
CPU accuracy-equivalence claim or speed comparison.

The original 100-step/0.5 s fixture did **not** pass. Its loose first pressure
correction (`relTol=0.05`) exceeded the original all-corrector continuity screen;
the observed maximum was {original['observed_peak_all_corrector_continuity']:.12g}.
It was intentionally stopped after {original['completed_steps']} completed steps,
with actual child returncode -15. The connector's stop request killed only its
outer shell; a verified pidfd stop of the orphaned solver allowed the child
wrapper to record its real returncode and flush the partial trace. The original
input, logs, trace, old source/patch and binary hashes remain documented. The old
ELF binary is retained privately and excluded from this export.

## Distinct strict fixture and unchanged acceptance limits

The new fixture starts from fresh stock initial fields: 400 cells, dt 0.005,
five steps through 0.025, output each step at precision 17. Both pressure
correctors use `relTol=0` at the original absolute tolerance 1e-6. The selected
GPU numerical path is aDIC and twoStageSymGaussSeidel. Mesh, viscosity, initial
fields and boundary conditions remain the stock cavity. The all-corrector
continuity limit was not relaxed; the shorter/tighter protocol and exact
mechanical validator hashes were recorded before the new run.

- Peak local continuity over every corrector: {gate['peak_all_corrector_local_continuity']:.12g}
  (required ≤1e-5).
- Independent CPU sum of final saved internal and boundary flux imbalance:
  {gate['independent_CPU_final_flux_continuity']:.12g} (required <1e-5).
- Maximum pressure/U final residual: {gate['maximum_pressure_final_residual']:.12g} /
  {gate['maximum_U_final_residual']:.12g}.
- All five saved U, p and phi fields are finite; final physical/recirculation,
  closed-wall flux and pressure-reference checks passed.

## What establishes GPU execution

The independent core marker uses SPUMA's own `foamExecutor::parallelFor` to write
a CUDA DEVICE-only output, with 65,536 exact value checks and an exact double
reduction. It also verifies SPUMA's actual 1 GiB managed fixed pool. That passed
marker is retained separately and was not rerun or replaced.

The strict CFD binary has only recorded NVTX annotations added. Nsight captured
one complete first time-step body, after initialization, then stopped collecting
while the same child completed four more steps. Inside that named range on its
own exact globalTid, the audit observed {api['successful_launch_api_calls_in_cfd_loop']}
successful CUDA launch API calls, no failed launch/synchronization calls, and
a successful device/context synchronization after the last launch API.
The documented globalTid decoding and the trace's PROCESSES table independently
match that thread to the actual child PID 367774; its birth/cwd identity is in
the receipt. Both owned case process lists are empty after completion.
API counts can include runtime and driver layers and are not unique kernels.
No GPU kernel-activity timeline or complete device residence is claimed.
The actual child exit receipt is independent of profiler/Allrun status; binary,
core, finiteVolume, observer and environment hashes match at start and completion.

The raw-string range capture uses the documented child-only
`NSYS_NVTX_PROFILER_REGISTER_ONLY=0` setting. See the
[NVIDIA Nsight Systems guide](https://docs.nvidia.com/nsight-systems/UserGuide/).

## Build pins, fixes and reproduction

The private build reuses read-only NVHPC 26.9 and CUDA 13.3, with SM121,
`have_cuda=true`, `have_umpire=false`, `FOAM_SIGFPE=false` and the explicit
fixedSizeMemoryPool. Umpire was inspected/staged but was not used by this route.
No global compiler, driver, shell profile or OpenFOAM connector configuration
changed. No completed rotor-study input/result changed.

NVHPC warns (#3560-D) that CUDA C++ in nvc++ is unsupported and recommends nvcc.
The pinned upstream rules use nvc++ for this path; actual functional gates passed,
but that vendor-support caveat remains. The finiteVolume link also hit the
confirmed AArch64 GOT limit in a generated CUDA registration stub. A private GCC
trampoline changes only that exact stub's -fpic to -fPIC. The relink passed with
all 432 cached objects byte- and timestamp-identical. Failure logs, forwarded
arguments and the inventory are retained. The SDK/system compiler stayed intact.

Recipes and the exact two case setups are included. They retain task-specific
paths/guards and intentionally refuse to overwrite completed evidence; inspect
and adapt paths in a fresh private tree. Fetch the exact upstream pin, source
only the private environment, build the minimal libraries/apps, apply recorded
annotation patches, and use the provided core marker source and strict case.
The historical core-marker preparer requires its original concurrent base-build
stage; after a complete build, compile that source in a fresh wmake app with
`EXE_INC = -I$(LIB_SRC)/OpenFOAM/lnInclude` and `EXE_LIBS = -lcudart`, then run
with `-pool fixedSizeMemoryPool -poolSize 1`. Do not rerun the evidence cases.

The large SDK, full source tree, build objects and all binaries are excluded.
Raw traces are functional coverage evidence under build load; none of their
durations should be used to infer speed. No actuator model was ported here.
'''
(EVIDENCE/'README.md').write_text(document)
(OUTPUT/'SPUMA_FUNCTIONAL_TEST.md').write_text(document)
for source,name in [(BASE/'provenance/spuma_strict_v2_tutorial_gate.json','spuma_strict_v2_tutorial_gate.json'),
                    (BASE/'provenance/spuma_strict_v2_cfd_first_step_gpu_gate.json','spuma_strict_v2_first_step_gpu_gate.json'),
                    (BASE/'provenance/original_attempt/original_attempt_diagnostic.json','spuma_original_attempt_diagnostic.json')]:
    copy_exact(source,OUTPUT/name)
manifest=dict(kind='SPUMA functional evidence: failed original plus distinct preregistered strict-v2 pass',
    created_utc=datetime.now(timezone.utc).isoformat(),source_pin=gate['protocol']['source_pin'],
    SDK_full_source_builds_and_binaries_excluded=True,no_speed_actuator_or_production_claim=True,
    files={str(path.relative_to(EVIDENCE)):{'bytes':path.stat().st_size,'sha256':digest(path)} for path in sorted(EVIDENCE.rglob('*')) if path.is_file()})
(EVIDENCE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
# Reject executable/build/dependency payloads. Nsight reports/SQLite are data evidence.
for path in CANDIDATE.rglob('*'):
    if not path.is_file():continue
    assert path.suffix not in ['.so','.o','.a','.deb','.tar','.zip','.exe','.dll']
    with path.open('rb') as stream:assert stream.read(4)!=b'\x7fELF'
result=dict(state='source_evidence_candidate_prepared_NOT_PUBLISHED',candidate=str(CANDIDATE),
    manifest=str(EVIDENCE/'manifest.json'),manifest_sha256=digest(EVIDENCE/'manifest.json'),
    file_count=len(manifest['files']),total_bytes=sum(p.stat().st_size for p in CANDIDATE.rglob('*') if p.is_file()),
    SDK_ELF_build_trees_and_credentials_excluded=True,no_new_CFDrun_timing_default_Git_or_CPU84_mutation=True)
(WORK/'publication_candidate_prepared.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
