"""Compile two private identical-source apps. Never execute application main."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,shlex,subprocess,time,traceback
WORK=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/managed_strict_combined_v2_3')
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/native-c29-validation')
CUDA=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3')
JOURNAL=WORK/'build_progress.json'
def now():return datetime.now(timezone.utc).isoformat()
def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(2**20),b''):h.update(chunk)
 return h.hexdigest()
def dump(path,obj):
 path=Path(path);temp=path.with_suffix(path.suffix+'.tmp');temp.write_text(json.dumps(obj,indent=2)+'\n');temp.replace(path)
def memory_kib():return int(next(x.split()[1] for x in Path('/proc/meminfo').read_text().splitlines() if x.startswith('MemAvailable:')))
def fingerprint(path):
 p=Path(path).resolve();return {'path':str(p),'sha256':sha(p),'size_bytes':p.stat().st_size}
def command(prefix,script,filename):
 output=prefix/filename
 with output.open('w') as log:r=subprocess.run(['/bin/bash','-c',script],stdout=log,stderr=subprocess.STDOUT,text=True)
 if r.returncode:raise RuntimeError(filename+' failed '+str(r.returncode))
 return output.read_text()
def collect(backend,prefix,method,manifest,child):
 assert child['exit_code']==0,'wmake failed; preserve objects/logs, no rebuild'
 binary=prefix/'bin/c29ManagedHybridFoamStrict';assert binary.is_file()
 for name,pin in manifest['files'].items():assert sha(prefix/'source'/name)==pin
 env=prefix/'build_environment.sh'
 shell='. '+shlex.quote(str(env))+'\n'
 ldd=command(prefix,shell+'ldd '+shlex.quote(str(binary)),'runtime_dependency_audit.log')
 assert 'not found' not in ldd
 dependencies=[]
 for line in ldd.splitlines():
  match=re.search(r'(?:=>\s+)?(/\S+)\s+\(',line)
  if match:
   record=fingerprint(match[1])
   if record['path'] not in [x['path'] for x in dependencies]:dependencies.append(record)
 assert dependencies
 library_names=[x['path'] for x in dependencies]
 expected_backend='/native-cpu-control/' if backend=='cpu' else '/native-stdpar/'
 for x in dependencies:
  if Path(x['path']).name in ['libfiniteVolume.so','libmeshTools.so','libOpenFOAM.so']:
   assert expected_backend in x['path']
 if backend=='cpu':assert not any(any(k in x.lower() for k in ['libcudart','libnvhpc','libaccdevice','native-stdpar/']) for x in library_names)
 else:assert str((CUDA/'targets/sbsa-linux/lib/libcudart.so.13.3.29').resolve()) in library_names
 identity={'schema':'c29-private-linked-library-identity-v1','backend':backend,'files':dependencies,'identity_collector_executed_main':False,'basis':'ldd in matching private reviewed environment; no application main/initialization/CFD run','method_identity_sha256':sha(prefix/'method_identity.json'),'source_tree_sha256':manifest['source_tree_sha256']}
 dump(prefix/'library_identity.json',identity)
 command(prefix,'readelf -d '+shlex.quote(str(binary)),'elf_dynamic.log')
 command(prefix,'readelf -h '+shlex.quote(str(binary)),'elf_header.log')
 log=(prefix/'build.log').read_text()
 commands=[x for x in log.splitlines() if re.match(r'^(?:g\+\+|nvc\+\+|/\S*/(?:g\+\+|nvc\+\+))\s',x)]
 assert commands,'Missing actual compiler/link command evidence'
 compile_lines=[x for x in commands if ' -c ' in x]
 assert len(compile_lines)==1
 if backend=='cpu':assert '-DC29_USE_CUDA=0' in compile_lines[0] and not any(x in compile_lines[0] for x in ['-DFOAM_OFFLOAD','-stdpar','-gpu='])
 else:assert all(x in compile_lines[0] for x in ['-DC29_USE_CUDA=1','-DFOAM_OFFLOAD','-stdpar=gpu','-gpu=cc121,mem:managed'])
 artifacts={}
 for name in ['build.log','environment.log','build_environment.sh','environment_selected.json','compiler_version.log','runtime_dependency_audit.log','elf_dynamic.log','elf_header.log','method_identity.json','actual_child.json']:
  p=prefix/name;artifacts[name]=fingerprint(p);(WORK/f'{backend}_{name}').write_bytes(p.read_bytes())
 record={'schema':'c29-managed-strict-linked-app-v2.3','backend':backend,'prefix':str(prefix),'completed_utc':now(),'state':'LINKED_ONLY_NO_APPLICATION_MAIN_INITIALIZATION_OR_CFD_RUN','binary':fingerprint(binary),'library_identity':fingerprint(prefix/'library_identity.json'),'method_identity':fingerprint(prefix/'method_identity.json'),'source_tree_sha256':manifest['source_tree_sha256'],'source_files_identical_to_combined_manifest':True,'source_manifest':fingerprint(WORK/'combined_source_manifest.json'),'compiler_jobs_max':1,'both_backends_compiler_jobs_total_max':2,'nice':15,'actual_wmake_child':child,'actual_compile_and_link_commands':commands,'artifacts':artifacts,'loaded_at_future_solver_runtime_identity_not_yet_observed':True,'case_inputs_untouched':True}
 dump(prefix/'linked_identity.json',record);dump(WORK/f'{backend}_linked_identity.json',record)
 return record
def main():
 assert os.geteuid()!=0 and os.getpriority(os.PRIO_PROCESS,0)>=15
 manifest=json.loads((WORK/'combined_source_manifest.json').read_text())
 expected_manifest='7e4492d4d644e3b03211315f0a0c692db5b6652edb063cf2779a6ff1db9cbaf5'
 assert sha(WORK/'combined_source_manifest.json')==expected_manifest
 state={'schema':'c29-managed-strict-compile-only-worker-v2.3','worker_pid':os.getpid(),'started_utc':now(),'status':'preflight','jobs_max_total':2,'nice':os.getpriority(os.PRIO_PROCESS,0),'minimum_reserve_GiB':20,'backends':{},'application_executed':False,'case_mutated':False,'worker_source_sha256':sha(__file__)};dump(JOURNAL,state)
 running={}
 for backend in ['cpu','gpu']:
  assert memory_kib()>=20*1024**2
  prefix=BASE/f'native_{backend}_managed_strict_v2_3_20261102';method=json.loads((prefix/'method_identity.json').read_text())
  assert sha(method['environment']['path'])==method['environment']['sha256']
  for name,pin in manifest['files'].items():assert sha(prefix/'source'/name)==pin
  assert not (prefix/'bin/c29ManagedHybridFoamStrict').exists() and not (prefix/'build.log').exists()
  (prefix/'tmp').mkdir(exist_ok=True)
  settings='. '+shlex.quote(method['environment']['path'])+'\n'
  variables={'WM_NCOMPPROCS':'1','CMAKE_BUILD_PARALLEL_LEVEL':'1','OMP_NUM_THREADS':'1','C29_APPBIN':str(prefix/'bin'),'C29_USE_CUDA':str(int(backend=='gpu')),'C29_USE_NVTX':'1','C29_NVTX_INCLUDE':str(CUDA/'include'),'TMPDIR':str(prefix/'tmp')}
  if backend=='gpu':variables.update({'C29_CUDA_INCLUDE':str(CUDA/'include'),'C29_CUDA_LIBDIR':str((CUDA/'targets/sbsa-linux/lib/libcudart.so').resolve().parent)})
  for key,value in variables.items():settings+='export '+key+'='+shlex.quote(value)+'\n'
  (prefix/'build_environment.sh').write_text(settings)
  selected=['WM_PROJECT_DIR','WM_OPTIONS','WM_COMPILER','WM_PRECISION_OPTION','WM_LABEL_SIZE','WM_MPLIB','FOAM_LIBBIN','FOAM_EXT_LIBBIN','FOAM_MEMORY_POOL','PATH','LD_LIBRARY_PATH','C29_APPBIN','C29_USE_CUDA','C29_USE_NVTX','C29_CUDA_INCLUDE','C29_CUDA_LIBDIR','C29_NVTX_INCLUDE','WM_NCOMPPROCS','OMP_NUM_THREADS','TMPDIR']
  python='import json,os;print(json.dumps({k:os.environ.get(k) for k in '+repr(selected)+'},indent=2))'
  setup=settings+'python3 -c '+shlex.quote(python)+' > '+shlex.quote(str(prefix/'environment_selected.json'))+'\n'
  setup+=('g++ --version' if backend=='cpu' else 'nvc++ --version')+' > '+shlex.quote(str(prefix/'compiler_version.log'))+' 2>&1\n'
  command(prefix,setup,'environment.log')
  log=(prefix/'build.log').open('w')
  # OpenFOAM setup functions are not errexit-safe; enable it AFTER sourcing.
  script='. '+shlex.quote(str(prefix/'build_environment.sh'))+'\nset -e\ncd '+shlex.quote(str(prefix/'source'))+'\nwmake -j1\n'
  process=subprocess.Popen(['/bin/bash','-c',script],stdout=log,stderr=subprocess.STDOUT)
  stat=Path(f'/proc/{process.pid}/stat').read_text();start_ticks=stat[stat.rfind(')')+2:].split()[19]
  child={'pid':process.pid,'start_ticks':start_ticks,'uid':os.geteuid(),'nice':os.getpriority(os.PRIO_PROCESS,process.pid),'argv':['/bin/bash','-c',script],'started_utc':now(),'MemAvailable_kib_at_start':memory_kib()}
  dump(prefix/'actual_child.json',child);state['backends'][backend]=dict(child,status='building',prefix=str(prefix));state['status']='building';dump(JOURNAL,state)
  running[backend]=(process,log,prefix,method,child)
 while running:
  state['MemAvailable_kib']=memory_kib()
  for backend,(process,log,prefix,method,child) in list(running.items()):
   code=process.poll()
   if code is None:continue
   log.close();child.update(exit_code=code,ended_utc=now());dump(prefix/'actual_child.json',child)
   state['backends'][backend].update(exit_code=code,status='linked_identity_collection' if code==0 else 'build_failed')
   dump(JOURNAL,state)
   try:
    result=collect(backend,prefix,method,manifest,child)
    state['backends'][backend].update(status='linked_no_runtime',binary_sha256=result['binary']['sha256'],linked_identity_sha256=sha(prefix/'linked_identity.json'))
   except Exception as error:
    state['backends'][backend].update(status='failed_preserve_evidence',error=str(error),traceback=traceback.format_exc())
   del running[backend];dump(JOURNAL,state)
  if running:time.sleep(2)
 state['status']='complete_linked_no_runtime' if all(x['status']=='linked_no_runtime' for x in state['backends'].values()) else 'failed_preserve_evidence'
 state['ended_utc']=now();dump(JOURNAL,state)
 print(json.dumps(state,indent=2))
 if state['status']!='complete_linked_no_runtime':raise SystemExit(1)
if __name__=='__main__':main()
