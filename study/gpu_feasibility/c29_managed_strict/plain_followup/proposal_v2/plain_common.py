"""Source-only single unprofiled diagnostic admission/support; no launch on import."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,os
HERE=Path(__file__).resolve().parent
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for part in iter(lambda:stream.read(1024*1024),b''):h.update(part)
 return h.hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(path)
def binding(record):
 p=Path(record['path']);require(p.is_absolute() and p.is_file(),'Missing bound absolute file');require(sha(p)==record['sha256'],'Changed bound file: '+str(p));return p
def load(approval_path,receipt_path):
 p=json.loads((HERE/'protocol.json').read_text());approval=json.loads(Path(approval_path).read_text())
 require(approval.get('decision')=='APPROVED_FOR_ONE_UNPROFILED_GPU_DIAGNOSTIC_SAME_2_3','No explicit Root plain diagnostic approval')
 require(approval['protocol_sha256']==sha(HERE/'protocol.json') and approval['helper_manifest_sha256']==sha(HERE/'helper_manifest.json'),'Wrong protocol/helper freeze')
 for name,pin in json.loads((HERE/'helper_manifest.json').read_text())['files'].items():require(sha(HERE/name)==pin,'Helper changed: '+name)
 require(binding(approval['launch_receipt'])==Path(receipt_path),'Wrong fresh diagnostic receipt')
 for name in ['root_f14_cpu_external_gate','exact_shared_startup_gate','native_windows_31_field_integrity_gate']:
  require(approval[name]['root_asserted_pass'] is True,'Prerequisite not passed: '+name);binding(approval[name])
 binding(approval['fresh_clone_preparation'])
 for key in ['binary','library_identity','native_environment','source_manifest','linked_identity','receipt_verifier']:binding(p[key])
 r=json.loads(Path(receipt_path).read_text())
 require(r['backend']=='gpu' and r['phase']=='five_fixed_steps' and r['case']==p['case'] and r['private_root']==p['private_root'],'Wrong diagnostic case/backend/phase')
 require(r['case']!='/opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102/native_gpu','Do not rerun failed original case')
 require(r['manual_argv']==[p['binary']['path'],'-case',p['case']] and r['binary']['sha256']==p['binary']['sha256'] and r['library_identity']['sha256']==p['library_identity']['sha256'],'Wrong binary/library/argv')
 require(r['shared_phi_sha256']==p['shared_phi_sha256'],'Wrong shared initial phi')
 require(r['experiment_id']==p['required_fresh_experiment_id'],'Wrong unique diagnostic ID')
 require(not os.environ.get('LD_PRELOAD') and not any(os.environ.get(k) for k in ['CUDA_INJECTION64_PATH','CUDA_INJECTION32_PATH','NVTX_INJECTION64_PATH','NVTX_INJECTION32_PATH']),'No profiler/observer/tool injection allowed')
 require('Nsight' not in os.environ.get('LD_LIBRARY_PATH',''),'No Nsight loader overlay allowed')
 available=int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
 require(available>=20*1024**2,'Less than 20 GiB reserve; no launch')
 return p,approval,r
def original_admission(protocol):
 file=binding(protocol['receipt_verifier']);spec=importlib.util.spec_from_file_location('c29_original_admission',file);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def same_bound_receipt_files(admission,receipt):
 require(admission.digest(receipt['inputs'])==receipt['input_snapshot_sha256'],'Corrupt receipt snapshot')
 for item in [*receipt['inputs'].values(),receipt['binary'],receipt['library_identity'],*receipt['libraries']]:require(admission.same_record(item),'Receipt-bound bytes/mtime changed: '+item['path'])
def case_hashes(case):return {str(x.relative_to(case)):sha(x) for x in Path(case).rglob('*') if x.is_file()}
def proc_identity(pid):
 q=Path('/proc')/str(pid);text=(q/'stat').read_text();tail=text[text.rfind(')')+2:].split()
 return {'pid':pid,'uid':q.stat().st_uid,'birth_start_ticks':int(tail[19]),'cwd':os.readlink(q/'cwd'),'exe':os.readlink(q/'exe'),'nice':int(tail[16])}
