"""Export the first run's trace; audit CUDA APIs only inside the SPUMA loop."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, shlex, sqlite3, subprocess

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma')
SOURCE=BASE/'source'
WORK=Path(__file__).resolve().parent
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/cavity_gpu_fixedpool_strict_v2')
NSYS=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/profilers/13.3/Nsight_Systems/bin/nsys')
RANGE='SPUMA_CFD_FIRST_COMPLETE_STEP'
trace=CASE/'cavity_first_step_trace'
assert os.getuid()==999
status=json.loads((CASE/'run_status.json').read_text())
receipt=json.loads((CASE/'icoFoam_exit_receipt.json').read_text())
assert status['state']=='succeeded' and status['returncode']==receipt['returncode']==0
assert not receipt['timed_out']
assert Path(str(trace)+'.nsys-rep').is_file()
log=CASE/'log.nsys_export'
assert not log.exists()
command=[str(NSYS),'stats','--force-export=true','--report','cuda_api_sum','--format','csv',str(trace)+'.nsys-rep']
shell='. '+shlex.quote(str(BASE/'env.sh'))+'; exec '+shlex.join(command)
with log.open('x') as output:
    result=subprocess.run(['bash','--noprofile','--norc','-c',shell],stdout=output,stderr=subprocess.STDOUT,timeout=300)
assert result.returncode==0,'Preserve export failure log; do not rerun CFD'
database=Path(str(trace)+'.sqlite')
connection=sqlite3.connect('file:'+str(database)+'?mode=ro',uri=True)
connection.row_factory=sqlite3.Row
tables={row[0] for row in connection.execute("select name from sqlite_master where type='table'")}
assert 'NVTX_EVENTS' in tables
columns={row[1] for row in connection.execute('pragma table_info(NVTX_EVENTS)')}
clauses=[];parameters=[]
if 'text' in columns:clauses.append('text=?');parameters.append(RANGE)
if 'textId' in columns:clauses.append('textId in (select id from StringIds where value=?)');parameters.append(RANGE)
assert clauses
ranges=[dict(row) for row in connection.execute('select * from NVTX_EVENTS where ('+' or '.join(clauses)+') and end is not null',parameters)]
assert len(ranges)==1,'Expected one complete SPUMA CFD-loop NVTX range'
start,end=ranges[0]['start'],ranges[0]['end']
assert end>start
assert 'globalTid' in ranges[0] and ranges[0]['globalTid'] is not None
thread=ranges[0]['globalTid']
launches=[];synchronizations=[];kernels={}
for table in sorted(tables):
    if not table.startswith('CUPTI_ACTIVITY_KIND_'):continue
    columns={row[1] for row in connection.execute('pragma table_info("'+table+'")')}
    if 'KERNEL' in table:
        kernels[table]=connection.execute('select count(*) from "'+table+'"').fetchone()[0]
    if not {'start','end','nameId','returnValue','globalTid'}.issubset(columns):continue
    query='select s.value as name,a.returnValue as return_value,count(*) as calls,min(a.start) as first_start_ns,max(a.end) as last_end_ns from "'+table+'" a join StringIds s on a.nameId=s.id where a.start>=? and a.end<=? and a.globalTid=? group by s.value,a.returnValue'
    for row in connection.execute(query,(start,end,thread)):
        item={'table':table,**dict(row)}
        if any(name in item['name'] for name in ['cudaLaunchKernel','cuLaunchKernel','cudaGraphLaunch','cuGraphLaunch','cudaLaunchCooperativeKernel']):launches.append(item)
        if any(name in item['name'] for name in ['cudaDeviceSynchronize','cudaStreamSynchronize','cuCtxSynchronize','cuStreamSynchronize']):synchronizations.append(item)
connection.close()
successful=sum(row['calls'] for row in launches if row['return_value']==0)
failed=sum(row['calls'] for row in launches if row['return_value']!=0)
successful_sync=sum(row['calls'] for row in synchronizations if row['return_value']==0)
failed_sync=sum(row['calls'] for row in synchronizations if row['return_value']!=0)
assert successful>0 and failed==failed_sync==0 and successful_sync>0
last_launch=max(row['last_end_ns'] for row in launches)
device_sync=[row for row in synchronizations if row['return_value']==0 and any(name in row['name'] for name in ['cudaDeviceSynchronize','cuCtxSynchronize'])]
assert device_sync,'Require completed device/context synchronization, not an unrelated stream'
last_sync=max(row['last_end_ns'] for row in device_sync)
assert last_sync>=last_launch,'No completed synchronization observed after final loop launch API'
annotation=json.loads((BASE/'provenance/ico_first_step_annotation.json').read_text())
assert hashlib.sha256((SOURCE/annotation['path']).read_bytes()).hexdigest()==annotation['annotated_sha256']
record=dict(kind='Actual successful CUDA API execution inside one complete strict-v2 SPUMA icoFoam CFD step',
    completed_utc=datetime.now(timezone.utc).isoformat(),state='passed',case=str(CASE),range_name=RANGE,
    nvtx_range=ranges[0],globalTid=thread,API_scope='Inside named range AND same globalTid as its owning thread/process',
    launch_api_rows=launches,synchronization_api_rows=synchronizations,
    successful_launch_api_calls_in_cfd_loop=successful,failed_launch_api_calls_in_cfd_loop=failed,
    successful_synchronization_api_calls_in_cfd_loop=successful_sync,failed_synchronization_api_calls_in_cfd_loop=failed_sync,
    last_launch_api_end_ns=last_launch,last_successful_sync_end_ns=last_sync,final_loop_sync_observed=True,
    kernel_activity_tables_whole_trace=kernels,kernel_activity_count_scope='Whole trace only; never used as CFD-loop activity proof',
    profiler_kernel_activity_proof=False,
    actual_icoFoam_exit_receipt=receipt,actual_Allrun_status=status,source_annotation=annotation,
    report=str(trace)+'.nsys-rep',sqlite=str(database),export_command=command,export_returncode=result.returncode,
    report_sha256=hashlib.sha256(Path(str(trace)+'.nsys-rep').read_bytes()).hexdigest(),
    sqlite_sha256=hashlib.sha256(database.read_bytes()).hexdigest(),
    count_scope='Launch API calls within one named CFD-loop range; runtime and driver layers may both be counted. Not unique GPU kernels or complete device-residence proof.',
    no_performance_inference=True,no_rotor_port_or_production_change=True)
target=BASE/'provenance/spuma_strict_v2_cfd_first_step_gpu_gate.json'
assert not target.exists()
target.write_text(json.dumps(record,indent=2)+'\n')
(WORK/'spuma_strict_v2_cfd_first_step_gpu_gate.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
