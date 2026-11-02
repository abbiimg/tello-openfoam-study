"""Retain the failed original screen and its actual termination evidence."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,shutil

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/cavity_gpu_fixedpool')
assert os.getuid()==999
target=BASE/'provenance/original_attempt';assert not target.exists();target.mkdir()
binary=SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt/bin/icoFoam'
receipt=json.loads((CASE/'icoFoam_exit_receipt.json').read_text());assert receipt['returncode']==-15
assert hashlib.sha256(binary.read_bytes()).hexdigest()==receipt['binary_sha256_after_return']
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:assert os.readlink(proc/'cwd')!=str(CASE),'Owned original process still alive'
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
annotation=json.loads((BASE/'provenance/ico_time_loop_annotation.json').read_text())
shutil.copy2(binary,target/'icoFoam.original_binary')
shutil.copy2(SOURCE/annotation['path'],target/'icoFoam.annotated_original.C')
shutil.copy2(BASE/'provenance/ico_time_loop_annotation.json',target/'ico_time_loop_annotation.json')
shutil.copy2(Path(annotation['patch']),target/'ico_time_loop_annotation.patch')
for name in ['prepare_smoke_case.py','validate_smoke_result.py','audit_cfd_time_loop.py','cuda_runtime_observer.cpp']:
    shutil.copy2(WORK/name,target/name)
text=(CASE/'log.icoFoam').read_text()
all_values=[float(x) for x in re.findall(r'sum local =\s*([0-9.eE+-]+)',text)]
sections=re.split(r'^Time = ',text,flags=re.M)[1:]
completed=[float(section.splitlines()[0]) for section in sections if 'ExecutionTime =' in section]
started=[float(section.splitlines()[0]) for section in sections]
record=dict(kind='Original SPUMA cavity screen FAILED and intentionally terminated; not a completed functional gate',
    frozen_utc=datetime.now(timezone.utc).isoformat(),case=str(CASE),mcp_job_id='Allrun-08c608',
    state='intentionally_terminated_original_screen_failed',returncode=None,
    connector_reported_state='stopped',connector_reported_returncode=-1,
    connector_returncode_is_actual_child_status=False,actual_icoFoam_returncode=receipt['returncode'],actual_child_receipt=receipt,
    original_protocol=dict(mesh_cells=400,delta_t_s=.005,end_s=.5,planned_steps=100,p_first_relTol=.05,pFinal_relTol=0,
        all_corrector_local_continuity_limit=1e-5,criterion='max of ALL logged local continuity values < 1e-5'),
    original_all_corrector_screen_passed=False,observed_peak_all_corrector_continuity=max(all_values),
    last_completed_time_s=max(completed),last_started_time_s=max(started),completed_steps=len(completed),
    full_horizon_completed=False,old_binary_preserved=str(target/'icoFoam.original_binary'),
    old_binary_sha256=receipt['binary_sha256_after_return'],source_annotation=annotation,
    control_input_unchanged_by_connector=(CASE/'system/controlDict').read_bytes()==(CASE/'controlDict.before_intentional_stop').read_bytes(),
    partial_trace=str(CASE/'cavity_icoFoam_time_loop_trace.nsys-rep'),
    partial_trace_sha256=hashlib.sha256((CASE/'cavity_icoFoam_time_loop_trace.nsys-rep').read_bytes()).hexdigest(),
    stop_audit=json.loads((CASE/'intentional_stop_audit.json').read_text()),
    no_threshold_relaxation=True,no_performance_inference=True,no_CPU_study_change=True)
assert record['observed_peak_all_corrector_continuity']>=1e-5
(target/'original_attempt_diagnostic.json').write_text(json.dumps(record,indent=2)+'\n')
(CASE/'run_status.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'original_attempt_diagnostic.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
