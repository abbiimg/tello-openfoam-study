"""Source-only proposal support. No solver is launched by importing this module."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,importlib.util,json,os,re
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
 p=Path(record['path']);require(p.is_absolute() and p.is_file(),'Missing absolute bound file')
 require(sha(p)==record['sha256'],'Changed bound file: '+str(p));return p
def load(approval_path,receipt_path):
 protocol=json.loads((HERE/'protocol.json').read_text())
 approval=json.loads(Path(approval_path).read_text());manifest=HERE/'helper_manifest.json'
 require(approval.get('decision')=='APPROVED_FOR_ONE_GPU_FIVE_STEP_FUNCTIONAL_PROFILE','No explicit root profile approval')
 require(approval.get('protocol_sha256')==sha(HERE/'protocol.json'),'Protocol not approved')
 require(approval.get('helper_manifest_sha256')==sha(manifest),'Helpers not approved')
 for name,pin in json.loads(manifest.read_text())['files'].items():require(sha(HERE/name)==pin,'Frozen helper changed: '+name)
 receipt_path=Path(receipt_path);require(binding(approval['launch_receipt'])==receipt_path,'Different launch receipt')
 for name in ['exact_shared_startup_gate','f14_to_cpu_strict_numerical_gate']:
  require(approval[name]['root_asserted_pass'] is True,'Prerequisite not passed: '+name);binding(approval[name])
 receipt=json.loads(receipt_path.read_text())
 require(receipt['case']==protocol['case'] and receipt['backend']=='gpu' and receipt['phase']=='five_fixed_steps','Wrong backend/case/phase')
 require(receipt['private_root']==protocol['private_root'] and receipt['shared_phi_sha256']==protocol['shared_phi_sha256'],'Wrong private root/shared phi')
 require(receipt['manual_argv']==[protocol['binary']['path'],'-case',protocol['case']],'Unexpected solver argv')
 require(receipt['binary']['sha256']==protocol['binary']['sha256'] and receipt['library_identity']['sha256']==protocol['library_identity']['sha256'],'Receipt binary/library mismatch')
 for key in ['binary','library_identity','native_environment','nsys','linked_identity','source_manifest','root_input_audit','strict_pressure_protocol']:binding(protocol[key])
 return protocol,approval,receipt
def original_admission(protocol):
 file=binding(protocol['receipt_verifier']);spec=importlib.util.spec_from_file_location('c29_original_admission',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def same_bound_receipt_files(admission,receipt):
 require(admission.digest(receipt['inputs'])==receipt['input_snapshot_sha256'],'Corrupt receipt input snapshot')
 for item in [*receipt['inputs'].values(),receipt['binary'],receipt['library_identity'],*receipt['libraries']]:require(admission.same_record(item),'Receipt-bound bytes/mtime changed: '+item['path'])
def case_hashes(case):return {str(p.relative_to(case)):sha(p) for p in Path(case).rglob('*') if p.is_file()}
def proc_identity(pid):
 q=Path('/proc')/str(pid);s=(q/'stat').read_text();tail=s[s.rfind(')')+2:].split()
 return {'pid':pid,'uid':q.stat().st_uid,'birth_start_ticks':int(tail[19]),'cwd':os.readlink(q/'cwd'),'exe':os.readlink(q/'exe'),'nice':int(tail[16])}
def require_injection_overlay(base,current,nsys_root):
 """The sole receipt-environment exception is a preserved Nsight loader overlay."""
 extras={}
 for key,value in base.items():
  if key not in ['LD_PRELOAD','LD_LIBRARY_PATH']:require(current.get(key)==value,'Base environment changed: '+key);continue
  splitter=r'[:\s]+' if key=='LD_PRELOAD' else ':'
  before=[x for x in re.split(splitter,value or '') if x];after=[x for x in re.split(splitter,current.get(key) or '') if x]
  iterator=iter(after);require(all(any(x==wanted for x in iterator) for wanted in before),'Nsight discarded/reordered base '+key)
  added=[x for x in after if x not in before]
  for value in added:
   p=Path(value).resolve();require(p.is_relative_to(nsys_root) and p.exists(),'Non-Nsight loader overlay: '+value)
  extras[key]=added
 return extras
