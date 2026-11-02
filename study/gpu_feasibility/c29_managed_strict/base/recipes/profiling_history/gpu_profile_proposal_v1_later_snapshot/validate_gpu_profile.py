"""Inspect recorded child/trace evidence only; never launches a solver or profiler."""
from pathlib import Path
import argparse,json,re,sqlite3
from profile_common import *
LAUNCH_NAMES=['cudaLaunchKernel','cuLaunchKernel','cudaGraphLaunch','cuGraphLaunch','cudaLaunchCooperativeKernel','cuLaunchCooperativeKernel']
SYNC_NAMES=['cudaDeviceSynchronize','cuCtxSynchronize','cudaStreamSynchronize','cuStreamSynchronize']
def is_launch(name):return any(x in name for x in LAUNCH_NAMES)
def is_sync(name):return any(x in name for x in SYNC_NAMES)
def device_sync(name):return 'cudaDeviceSynchronize' in name or 'cuCtxSynchronize' in name
def validate(approval_path,receipt_path):
 p,approval,receipt=load(approval_path,receipt_path);e=Path(p['evidence']);run=json.loads((e/'actual_solver_exit.json').read_text());child=run['actual_child']
 require(run['actual_child_waited'] and run['return_code']==0 and not run['timed_out'] and not run['cancelled'] and not run['forced_kill'],'Actual direct solver failed, cancelled or timed out')
 require(run['receipt_sha256']==sha(receipt_path) and run['approval_sha256']==sha(approval_path),'Different receipt/approval used by child')
 require(child['uid']==999 and child['cwd']==p['case'] and child['exe']==p['binary']['path'] and child['nice']>=15 and child['birth_start_ticks']>0,'Wrong actual child identity')
 require(run['binary_sha256']==run['binary_sha256_after']==p['binary']['sha256'],'Binary changed or wrong child')
 require(run['declared_libraries_actually_observed_unchanged'] and run['original_case_files_unchanged'],'Changed inputs/libraries or missing actual loader evidence')
 require(run['source_calls']==run['controller_updates']==len(run['time_values'])==5,'Expected exactly five source/controller/time updates')
 require(all(abs(a-b)<1e-12 for a,b in zip(run['time_values'],[.6001,.6002,.6003,.6004,.6005])) and run['End_marker'] and not run['nonfinite_log_token'],'Clock/End/finite log gate failed')
 require(sha(p['stdout_log'])==run['log_sha256'],'Solver log changed')
 prof=json.loads((e/'profiler_exit.json').read_text());exp=json.loads((e/'export_exit.json').read_text())
 require(prof['return_code']==exp['return_code']==0 and not prof['timed_out'],'Profiler/export failed independently of solver')
 text=(e/'profiler.log').read_text()+Path(p['stdout_log']).read_text()
 require('Capture range started in the application.' in text and 'Capture range ended in the application.' in text,'Named capture did not actually trigger and end')
 db=e/'first_complete_step.sqlite';con=sqlite3.connect('file:'+str(db)+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
 tables={x[0] for x in con.execute("select name from sqlite_master where type='table'")};require({'NVTX_EVENTS','PROCESSES','StringIds'}<=tables,'Missing trace identity/NVTX tables')
 cols={x[1] for x in con.execute('pragma table_info(NVTX_EVENTS)')}
 def ranges(name):
  clauses=[];params=[]
  if 'text' in cols:clauses.append('text=?');params.append(name)
  if 'textId' in cols:clauses.append('textId in(select id from StringIds where value=?)');params.append(name)
  require(clauses,'No readable NVTX names')
  return [dict(x) for x in con.execute('select * from NVTX_EVENTS where ('+' or '.join(clauses)+') and end is not null',params)]
 steps=ranges(p['first_step_range']);require(len(steps)==1,'Require exactly one complete captured time-step range')
 step=steps[0];gtid=step['globalTid'];pid=(gtid//0x1000000)%0x1000000;tid=gtid%0x1000000
 require(pid==tid==child['pid'] and step['end']>step['start'] and step.get('endGlobalTid') in [None,gtid],'Range does not bind actual solver main thread')
 procs=[dict(x) for x in con.execute('select * from PROCESSES where pid=? and globalPid=?',(pid,gtid-tid))]
 require(len(procs)==1 and Path(procs[0]['name']).name==Path(p['binary']['path']).name,'PROCESSES binary/globalPid mismatch')
 launches=[];syncs=[];post=[];kernel_tables={}
 for table in sorted(tables):
  if not table.startswith('CUPTI_ACTIVITY_KIND_'):continue
  columns={x[1] for x in con.execute('pragma table_info("'+table+'")')}
  if 'KERNEL' in table:kernel_tables[table]=con.execute('select count(*) from "'+table+'"').fetchone()[0]
  if not {'start','end','globalTid','nameId'}.issubset(columns):continue
  rows=con.execute('select a.*,s.value as api_name from "'+table+'" a join StringIds s on a.nameId=s.id where a.globalTid=?',(gtid,))
  for row in rows:
   x=dict(row);name=x['api_name']
   if not (is_launch(name) or is_sync(name)):continue
   require('returnValue' in columns and x['returnValue'] is not None,'Trace cannot prove API success: missing returnValue')
   require(x['returnValue']==0,'Failed launch/synchronization captured on solver thread')
   item={'table':table,'start':x['start'],'end':x['end'],'name':name,'returnValue':x['returnValue'],'globalTid':gtid}
   if x['start']>step['end'] and is_launch(name):post.append(item)
   if step['start']<=x['start'] and x['end']<=step['end']:
    if is_launch(name):launches.append(item)
    if is_sync(name):syncs.append(item)
 require(not post,'CUDA launches captured after the first step; stop coverage failed')
 def window_gate(window,name):
  require(window['globalTid']==gtid and window.get('endGlobalTid') in [None,gtid] and step['start']<=window['start']<window['end']<=step['end'],'Wrong nested range identity/bounds')
  launch=[x for x in launches if window['start']<=x['start'] and x['end']<=window['end']]
  require(launch,'No successful GPU launch inside '+name)
  last=max(x['end'] for x in launch)
  completion=[x for x in syncs if device_sync(x['name']) and last<=x['start'] and x['end']<=window['end']]
  require(completion,'No successful same-thread device/context completion after last launch in '+name)
  return {'name':name,'nvtx':window,'successful_launch_API_calls':len(launch),'failed_launch_or_sync_calls':0,'last_launch_end_ns':last,'completion_after_last_launch':completion,'launch_rows':launch}
 step_gate=window_gate(step,p['first_step_range']);nested=[]
 for name,count in p['required_subranges'].items():
  windows=ranges(name);require(len(windows)==count,'Unexpected complete '+name+' range count')
  for i,window in enumerate(sorted(windows,key=lambda x:x['start'])):nested.append(window_gate(window,name+'#'+str(i+1)))
 con.close()
 result={'schema':'c29-native-gpu-five-functional-profile-gate-v1','passed':True,'completed_utc':utc(),'actual_child':child,'binary_sha256':p['binary']['sha256'],'source_tree_sha256':p['source_tree_sha256'],'actual_solver_return_code':run['return_code'],'actual_profiler_return_code':prof['return_code'],'five_steps_completed':True,'actual_declared_libraries_observed_unchanged':True,'original_inputs_unchanged':True,'decoded_PID':pid,'decoded_TID':tid,'globalTid':gtid,'PROCESSES':procs[0],'PID_mapping':'PID=(globalTid//0x1000000)%0x1000000; TID=globalTid%0x1000000','mapping_source':'https://docs.nvidia.com/nsight-systems/AnalysisGuide/','first_step':step_gate,'subranges':nested,'synchronization_rows_in_first_step':syncs,'captured_launches_after_first_step':post,'kernel_activity_tables_whole_trace':kernel_tables,'kernel_timeline_proof':False,'report_sha256':sha(e/'first_complete_step.nsys-rep'),'sqlite_sha256':sha(db),'protocol_sha256':sha(HERE/'protocol.json'),'approval_sha256':sha(approval_path),'launch_receipt_sha256':sha(receipt_path),'actual_exit_receipt_sha256':sha(e/'actual_solver_exit.json'),'count_scope':'Successful launch API calls, not distinct kernels; runtime/driver layers may both appear. Exact CPU/GPU numerical acceptance requires separate frozen d600 analysis.','speedup_measured':False}
 target=e/'functional_profile_gate.json';require(not target.exists(),'Do not overwrite a prior GPU profile gate');save(target,result);return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True);parser.add_argument('--receipt',type=Path,required=True);args=parser.parse_args();print(json.dumps(validate(args.approval,args.receipt),indent=2))
