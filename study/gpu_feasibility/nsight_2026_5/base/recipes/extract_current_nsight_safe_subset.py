"""Lossless selected-row export of CLOSED Field-control evidence; no GPU action.

Never copies an environment table, unrelated process, or unrelated StringId.
The original database/report and gate remain private and unchanged.
"""
from pathlib import Path
from collections import Counter
import argparse,base64,hashlib,json,re,sqlite3

DIAGNOSTIC_ALLOWLIST={
 'Unified Memory trace is currently not supported for Tegra iGPU device, disabling.',
 'Not all NVTX events might have been collected.',
 'Not all CUDA events might have been collected.',
 'Number of CUDA events collected: \t36.',
}
NAME_FIELDS={'nameId','textId','shortName','demangledName','mangledName','jsonTextId'}
API_NAMES={'cudaLaunchKernel_v7000','cudaStreamSynchronize_v3020','cudaDeviceSynchronize_v3020'}
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
 return h.hexdigest()
def json_value(x):return {'base64':base64.b64encode(x).decode()} if isinstance(x,bytes) else x
def row_key(row):return json.dumps([json_value(v) for v in row],separators=(',',':'),ensure_ascii=True)
def digest(rows):return hashlib.sha256('\n'.join(sorted(row_key(tuple(r)) for r in rows)).encode()).hexdigest()
def extract(source,gate_path,target,receipt_path):
 require(not target.exists() and not receipt_path.exists(),'Refuse overwrite')
 source_hash=sha(source);gate=json.loads(gate_path.read_text())
 require(gate['passed'] and gate['classification']=='CUDA_API_AND_KERNEL_TIMELINE_OBSERVED','Accepted existing small gate required')
 require(source_hash==gate['sqlite_sha256'],'Original full SQLite hash differs')
 c=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True);c.row_factory=sqlite3.Row
 require(c.execute('pragma integrity_check').fetchone()[0]=='ok','Original integrity check failed')
 window=gate['range'];gtid=window['globalTid'];pid=(gtid//0x1000000)%0x1000000;tid=gtid%0x1000000;gpid=gtid-tid
 require(pid==tid==gate['actual_child']['pid'],'Actual main-thread identity differs')
 selected={};columns={};schemas={}
 def select(table,where,args):
  schema=c.execute('select sql from sqlite_master where type=? and name=?',('table',table)).fetchone();require(schema,'Missing '+table)
  schemas[table]=schema[0];columns[table]=[r[1] for r in c.execute('pragma table_info('+table+')')]
  rows=[dict(r) for r in c.execute('select * from '+table+' where '+where,args)];selected[table]=rows;return rows
 processes=select('PROCESSES','pid=? and globalPid=?',(pid,gpid));require(processes==[gate['process']],'Actual process row differs')
 ranges=select('NVTX_EVENTS','globalTid=? and start=? and end=?',(gtid,window['start'],window['end']));require(ranges==[window],'Named range differs')
 require(window.get('jsonText') is None and window.get('jsonTextId') is None and window.get('binaryData') is None,'Unexpected NVTX payload')
 api_tables={r['table'] for r in gate['API_rows']};require(api_tables=={'CUPTI_ACTIVITY_KIND_RUNTIME'},'Unexpected API schema')
 table='CUPTI_ACTIVITY_KIND_RUNTIME'
 api_ids=[r[0] for r in c.execute('select id from StringIds where value in('+','.join('?' for _ in API_NAMES)+')',sorted(API_NAMES))]
 apis=select(table,'globalTid=? and start>=? and end<=? and nameId in('+','.join('?' for _ in api_ids)+')',(gtid,window['start'],window['end'],*api_ids))
 gate_apis=[{k:r[k] for k in columns[table]} for r in gate['API_rows']]
 require(Counter(map(lambda r:row_key(tuple(r[k] for k in columns[table])),apis))==Counter(map(lambda r:row_key(tuple(r[k] for k in columns[table])),gate_apis)),'Selected API row multiset differs')
 names={r[0]:r[1] for r in c.execute('select id,value from StringIds where id in('+','.join('?' for _ in api_ids)+')',api_ids)}
 require(all(r['returnValue']==0 and r['globalTid']==gtid for r in apis),'Failed/wrong-thread API')
 launches=[r for r in apis if names[r['nameId']]=='cudaLaunchKernel_v7000'];sync=[r for r in apis if names[r['nameId']]!='cudaLaunchKernel_v7000']
 require(len(launches)==8 and len(sync)==9,'Expected exact closed control API counts')
 last=max(r['end'] for r in launches);completion=[r for r in sync if names[r['nameId']]=='cudaDeviceSynchronize_v3020' and r['start']>=last]
 require(len(completion)==1,'Missing unique same-thread completion after last launch')
 kernels=select('CUPTI_ACTIVITY_KIND_KERNEL','globalPid=? and start>=? and end<=?',(gpid,window['start'],window['end']))
 kt='CUPTI_ACTIVITY_KIND_KERNEL';gate_kernels=[{k:r[k] for k in columns[kt]} for r in gate['attributed_kernel_activity_rows']]
 require(Counter(row_key(tuple(r[k] for k in columns[kt])) for r in kernels)==Counter(row_key(tuple(r[k] for k in columns[kt])) for r in gate_kernels),'Selected target kernel multiset differs')
 require(len(kernels)==8 and all(r['correlationId'] in {x['correlationId'] for x in launches} for r in kernels),'Kernel attribution differs')
 all_diagnostics=[dict(r) for r in c.execute('select * from DIAGNOSTIC_EVENT where globalPid=? or globalPid is null or globalPid=0',(gpid,))]
 diagnostics=[r for r in all_diagnostics if r['text'] in DIAGNOSTIC_ALLOWLIST]
 select('DIAGNOSTIC_EVENT','0',());selected['DIAGNOSTIC_EVENT']=diagnostics
 require(all(r['globalPid'] in (None,0,gpid) for r in diagnostics),'Unrelated diagnostics')
 require({r['text'] for r in diagnostics}>= {'Not all NVTX events might have been collected.','Not all CUDA events might have been collected.'},'Required incomplete-event warnings lost')
 ids=set()
 for table,rows in selected.items():
  for row in rows:
   for key in NAME_FIELDS:
    if isinstance(row.get(key),int):ids.add(row[key])
 strings=select('StringIds','id in('+','.join('?' for _ in ids)+')',tuple(sorted(ids)))
 require({r['id'] for r in strings}==ids,'Referenced name IDs missing')
 def safe_name(value):
  return isinstance(value,str) and len(value)<8192 and '\n' not in value and (value in API_NAMES or value in {'static_kernel','DeviceReduceKernel','DeviceReduceSingleTileKernel','NATIVE_STDPAR_FIELD_ALGEBRA'} or value.startswith('_ZN3cub22_V_300402_SM_121_NVHPC') or value.startswith('void cub::_V_300402_SM_121_NVHPC::'))
 require(all(safe_name(r['value']) for r in strings),'Non-allowlisted referenced string')
 out=sqlite3.connect(target)
 for table in selected:
  out.execute(schemas[table]);cols=columns[table];out.executemany('insert into '+table+' values('+','.join('?' for _ in cols)+')',[tuple(r[k] for k in cols) for r in selected[table]])
 out.commit();out.close()
 review=sqlite3.connect('file:'+str(target)+'?mode=ro',uri=True)
 require(review.execute('pragma integrity_check').fetchone()[0]=='ok','Subset integrity failed')
 kept={r[0] for r in review.execute("select name from sqlite_master where type='table'")};require(kept==set(selected),'Unexpected table retained')
 proof={}
 for table,rows in selected.items():
  original=[tuple(r[k] for k in columns[table]) for r in rows];copied=review.execute('select * from '+table).fetchall()
  require(Counter(map(row_key,original))==Counter(map(row_key,copied)),'Lossless multiset mismatch '+table)
  proof[table]={'rows':len(rows),'column_count':len(columns[table]),'original_selected_row_multiset_sha256':digest(original),'subset_row_multiset_sha256':digest(copied),'equal':True}
 review.close();c.close();require(sha(source)==source_hash,'Original changed during extraction')
 receipt={'kind':'Lossless safe selected-row subset of the ONE closed current-Nsight Field control','original_sqlite_sha256':source_hash,'original_report_sha256':gate['report_sha256'],'original_private_gate_sha256':sha(gate_path),'subset_sha256':sha(target),'selected_table_multisets':proof,'StringIds_exactly_referenced_and_allowlisted':sorted(ids),'actual_PID':pid,'actual_globalTid':gtid,'actual_globalPid':gpid,'launch_API_calls':len(launches),'successful_sync_API_calls':len(sync),'post_last_device_completion_count':len(completion),'attributed_kernel_rows':len(kernels),'all_kernel_correlations_match_actual_launches':True,'target_warning_text_allowlist':sorted(DIAGNOSTIC_ALLOWLIST),'retained_incomplete_event_warning_texts':[r['text'] for r in diagnostics],'environment_tables_or_unrelated_processes_or_strings_copied':False,'raw_private_evidence_changed':False,'GPU_application_or_CFD_rerun':False,'speedup_measured':False,'large_C29_transient_qualified':False,'integrity_check':'ok','qualification':'The named algebra range is complete; incomplete-event diagnostics prohibit claiming that every event in the whole process was captured.'}
 receipt_path.write_text(json.dumps(receipt,indent=2)+'\n');return receipt
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--gate',type=Path,required=True);ap.add_argument('--target',type=Path,required=True);ap.add_argument('--receipt',type=Path,required=True);a=ap.parse_args();print(json.dumps(extract(a.source,a.gate,a.target,a.receipt),indent=2))
