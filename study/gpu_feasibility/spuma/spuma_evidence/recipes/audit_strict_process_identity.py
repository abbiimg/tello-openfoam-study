"""Supplement frozen gates with documented PID decoding and no-orphan audit."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sqlite3

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');WORK=Path(__file__).resolve().parent
CASES=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102')
CASE=CASES/'cavity_gpu_fixedpool_strict_v2'
gate=json.loads((BASE/'provenance/spuma_strict_v2_cfd_first_step_gpu_gate.json').read_text())
receipt=json.loads((CASE/'icoFoam_exit_receipt.json').read_text())
thread=gate['globalTid'];pid=(thread//0x1000000)%0x1000000;tid=thread%0x1000000
assert pid==tid==receipt['child_identity']['pid']
database=Path(gate['sqlite']);assert hashlib.sha256(database.read_bytes()).hexdigest()==gate['sqlite_sha256']
con=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
processes=[dict(row) for row in con.execute('select * from PROCESSES where pid=?',(pid,))]
assert len(processes)==1 and processes[0]['globalPid']==(thread//0x1000000)*0x1000000
con.close()
owned=[];targets={str(CASE),str(CASES/'cavity_gpu_fixedpool')}
for proc in Path('/proc').iterdir():
    if not proc.name.isdigit():continue
    try:
        if os.readlink(proc/'cwd') in targets:owned.append({'pid':int(proc.name),'uid':proc.stat().st_uid,'exe':os.readlink(proc/'exe')})
    except (FileNotFoundError,PermissionError,ProcessLookupError):pass
assert not owned
record=dict(kind='Supplementary read-only identity/retirement verification; frozen validators unchanged',
    completed_utc=datetime.now(timezone.utc).isoformat(),globalTid=thread,decoded_pid=pid,decoded_tid=tid,
    actual_child_identity=receipt['child_identity'],PROCESSES_table_row=processes[0],identity_matches=True,
    documented_formula='PID=(globalTid // 0x1000000) % 0x1000000; TID=globalTid % 0x1000000',
    primary_source='https://docs.nvidia.com/nsight-systems/AnalysisGuide/',
    both_owned_case_process_lists_empty=True,remaining_owned_jobs=owned,
    frozen_gate_or_criteria_changed=False,no_CFDrun_or_performance_inference=True)
target=BASE/'provenance/strict_v2_process_identity_audit.json';assert not target.exists();target.write_text(json.dumps(record,indent=2)+'\n')
(WORK/'strict_v2_process_identity_audit.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record),flush=True)
