"""Read-only control admission/support; no GPU action on import."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os
HERE=Path(__file__).resolve().parent
def require(ok,message):
 if not ok:raise RuntimeError(message)
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as stream:
  for b in iter(lambda:stream.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def utc():return datetime.now(timezone.utc).isoformat()
def save(path,data):
 path=Path(path);tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(json.dumps(data,indent=2)+'\n');tmp.replace(path)
def binding(record):
 p=Path(record['path']);require(p.is_absolute() and p.is_file() and sha(p)==record['sha256'],'Changed bound file: '+str(p));return p
def load(approval_path):
 p=json.loads((HERE/'protocol.json').read_text());a=json.loads(Path(approval_path).read_text())
 require(a.get('decision')=='APPROVED_ONE_SMALL_FIELD_NEW_PROFILER_CONTROL','No explicit Root control approval')
 require(a['protocol_sha256']==sha(HERE/'protocol.json') and a['helper_manifest_sha256']==sha(HERE/'helper_manifest.json'),'Wrong protocol/helpers')
 for name,pin in json.loads((HERE/'helper_manifest.json').read_text())['files'].items():require(sha(HERE/name)==pin,'Helper changed: '+name)
 for name in ['binary','source','core_library','nsys','native_environment','library_identity','plain_failure_reconciliation']:binding(p[name])
 for record in json.loads(Path(p['library_identity']['path']).read_text())['files']:binding(record)
 for name,pin in p['case_files'].items():require(sha(Path(p['case'])/name)==pin,'Existing control input changed: '+name)
 require(os.geteuid()==999 and os.environ.get('WM_OPTIONS')=='linuxARM64Nvidia-gpuDPInt32Opt','Wrong private native environment')
 require(int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))>=20*1024**2,'Less than 20 GiB reserve')
 return p,a
def case_hashes(case):return {str(x.relative_to(case)):sha(x) for x in Path(case).rglob('*') if x.is_file()}
def identity(pid):
 q=Path('/proc')/str(pid);s=(q/'stat').read_text();tail=s[s.rfind(')')+2:].split()
 return {'pid':pid,'uid':q.stat().st_uid,'birth_start_ticks':int(tail[19]),'cwd':os.readlink(q/'cwd'),'exe':os.readlink(q/'exe'),'nice':int(tail[16])}
