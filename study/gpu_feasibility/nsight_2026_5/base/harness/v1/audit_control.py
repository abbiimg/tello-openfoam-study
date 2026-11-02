"""Read-only positive control audit. Scope is Field algebra/tool verification only."""
from pathlib import Path
import argparse,json,re,sqlite3
from control_common import *
def audit(approval):
 p,a=load(approval);e=Path(p['evidence']);x=json.loads((e/'actual_exit.json').read_text());c=x['actual_child']
 require(x['actual_child_waited'] and x['return_code']==0 and not x['cancelled'] and not x['timed_out'] and not x['wrapper_errors'] and not x['cleanup_errors'] and x['postprocessing_complete'],'Probe child/wrapper failed')
 require(x['case_before']==x['case_after']==p['case_files'] and x['declared_libraries_observed_unchanged'],'Inputs/loaded libraries changed')
 for name,key in [('binary','binary_sha256_after'),('source','source_sha256_after'),('core_library','core_sha256_after')]:require(x[key]==p[name]['sha256'],'Identity changed')
 result=x['arithmetic_result'];require(result==p['expected_arithmetic_result'],'Exact deterministic arithmetic result mismatch')
 prof=json.loads((e/'profile_exit.json').read_text());export=json.loads((e/'export_exit.json').read_text());require(prof['return_code']==export['return_code']==0 and not prof['wrapper_errors'] and not prof['timed_out'] and not prof['cancelled'],'Profiler/export failed')
 text=(e/'profile.log').read_text();require('Capture range started in the application.' in text and 'Capture range ended in the application.' in text,'Named capture not actually triggered')
 con=sqlite3.connect('file:'+str(e/'field_control.sqlite')+'?mode=ro',uri=True);con.row_factory=sqlite3.Row;tables={r[0] for r in con.execute('select name from sqlite_master where type=?',('table',))}
 require({'NVTX_EVENTS','PROCESSES','StringIds'}<=tables,'Missing identity/range tables')
 cols={r[1] for r in con.execute('pragma table_info(NVTX_EVENTS)')};clauses=[];params=[]
 if 'text' in cols:clauses.append('text=?');params.append(p['range'])
 if 'textId' in cols:clauses.append('textId in(select id from StringIds where value=?)');params.append(p['range'])
 require(clauses,'Missing NVTX name columns');ranges=[dict(r) for r in con.execute('select * from NVTX_EVENTS where ('+' or '.join(clauses)+') and end is not null',params)];require(len(ranges)==1,'Require one complete algebra range')
 window=ranges[0];gtid=window['globalTid'];pid=(gtid//0x1000000)%0x1000000;tid=gtid%0x1000000;require(pid==tid==c['pid'] and window['end']>window['start'] and window.get('endGlobalTid') in [None,gtid] and c['uid']==999 and c['cwd']==p['case'] and c['exe']==p['binary']['path'],'Wrong actual probe range PID/TID')
 processes=[dict(r) for r in con.execute('select * from PROCESSES where pid=? and globalPid=?',(pid,gtid-tid))];require(len(processes)==1 and Path(processes[0]['name']).name==Path(p['binary']['path']).name,'Wrong PROCESSES identity')
 launches=[];sync=[];kernels=[];kernel_counts={};apis=[]
 for table in sorted(tables):
  if not table.startswith('CUPTI_ACTIVITY_KIND_'):continue
  columns={r[1] for r in con.execute('pragma table_info('+table+')')}
  if {'start','end','nameId','globalTid'}.issubset(columns):
   for row in con.execute('select a.*,s.value as api_name from '+table+' a join StringIds s on a.nameId=s.id where a.globalTid=? and a.start>=? and a.end<=?',(gtid,window['start'],window['end'])):
    r=dict(row);n=r['api_name'];launch=any(v in n for v in ['cudaLaunchKernel','cuLaunchKernel','cudaGraphLaunch','cuGraphLaunch','LaunchCooperativeKernel']);synchronization=any(v in n for v in ['cudaDeviceSynchronize','cudaStreamSynchronize','cuCtxSynchronize','cuStreamSynchronize'])
    if not (launch or synchronization):continue
    require('returnValue' in columns and r['returnValue']==0,'Missing success returnValue or failed launch/sync')
    r={'table':table,**r};apis.append(r)
    if launch:launches.append(r)
    if synchronization:sync.append(r)
  if 'KERNEL' in table:kernel_counts[table]=con.execute('select count(*) from '+table).fetchone()[0]
 require(launches,'No actual CUDA launch APIs observed in algebra range')
 last=max(r['end'] for r in launches);completion=[r for r in sync if any(v in r['api_name'] for v in ['cudaDeviceSynchronize','cuCtxSynchronize']) and r['start']>=last];require(completion,'No same-thread device/context completion after final launch')
 correlations={r['correlationId'] for r in launches if r.get('correlationId') is not None}
 for table in kernel_counts:
  columns={r[1] for r in con.execute('pragma table_info('+table+')')}
  if not {'start','end'}.issubset(columns):continue
  for row in con.execute('select * from '+table+' where start>=? and end<=?',(window['start'],window['end'])):
   r=dict(row);by_pid=r.get('globalPid')==gtid-tid;by_correlation=r.get('correlationId') in correlations
   if by_pid or ('globalPid' not in columns and by_correlation):kernels.append({'table':table,**r})
 diagnostics=[dict(r) for r in con.execute('select * from DIAGNOSTIC_EVENT')] if 'DIAGNOSTIC_EVENT' in tables else [];con.close()
 unsupported=[r for r in diagnostics if re.search(r'driver.*not supported|unsupported.*driver',r.get('text',''),re.I)];require(not unsupported,'New profiler still reports unsupported driver')
 record={'kind':'New standalone profiler positive control on existing native Field algebra; NOT CFD or performance','passed':True,'classification':'CUDA_API_AND_KERNEL_TIMELINE_OBSERVED' if kernels else 'CUDA_API_OBSERVED_KERNEL_TIMELINE_UNAVAILABLE','actual_child':c,'arithmetic_result':result,'range':window,'process':processes[0],'launch_API_calls':len(launches),'API_rows':apis,'completion_after_last_launch':completion,'kernel_activity_tables_whole_trace':kernel_counts,'attributed_kernel_activity_rows':kernels,'diagnostic_events':diagnostics,'report_sha256':sha(e/'field_control.nsys-rep'),'sqlite_sha256':sha(e/'field_control.sqlite'),'protocol_sha256':sha(HERE/'protocol.json'),'source_sha256':p['source']['sha256'],'core_sha256':p['core_library']['sha256'],'binary_sha256':p['binary']['sha256'],'nsys_sha256':p['nsys']['sha256'],'C29_922576_cell_transient_qualified':False,'timing_authorized':False,'speedup_measured':False,'count_scope':'API counts are not distinct kernels; optional kernel activity is attributed separately. Small algebra success does not repair either failed large transient.'}
 target=e/'positive_control_gate.json';require(not target.exists(),'Do not overwrite control gate');save(target,record);return record
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--approval',type=Path,required=True);args=ap.parse_args();print(json.dumps(audit(args.approval),indent=2))
