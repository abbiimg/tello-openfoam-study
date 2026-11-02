"""Configure only pinned SPUMA child environments; reuse the SDK read-only."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shlex,subprocess
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');R=BASE/'source'
NATIVE=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar');SDK=NATIVE/'nvhpc/Linux_aarch64/26.9';CUDA=SDK/'cuda/13.3'
WORK=Path(__file__).resolve().parent
assert os.getuid()==999 and BASE.resolve()==BASE and R.resolve().is_relative_to(BASE)
assert subprocess.check_output(['git','-C',str(R),'rev-parse','HEAD'],text=True).strip()=='1ff2d45c002b7afb599b9dd8c4c6874666242349'
gate=json.loads((NATIVE/'provenance/stdpar_compiler_gate.json').read_text());marker=json.loads((NATIVE/'provenance/stdpar_device_marker_gate.json').read_text())
assert gate['result']['exact_element_check'] and gate['result']['pointer_memory_type']==3 and marker['result']['passed']
assert (SDK/'compilers/bin/nvc++').is_file() and (CUDA/'bin/nvcc').is_file()
for name in ['logs','build','tmp','runtime-config/CudaCache','runtime/jobControl','user','provenance','patches','smoke']:(BASE/name).mkdir(parents=True,exist_ok=True)
env=f'''# Private SPUMA environment. Never source from global/user profiles.
export NVCOMPILERS={shlex.quote(str(NATIVE/'nvhpc'))}
export NVHPC_CUDA_HOME={shlex.quote(str(CUDA))}
export CUDA_HOME={shlex.quote(str(CUDA))}
export CUDA_PATH={shlex.quote(str(CUDA))}
export PATH={shlex.quote(str(SDK/'compilers/bin')+':'+str(CUDA/'bin')+':'+str(NATIVE/'tools/bison/usr/bin')+':/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin')}
export BISON_PKGDATADIR={shlex.quote(str(NATIVE/'tools/bison/usr/share/bison'))}
export LD_LIBRARY_PATH={shlex.quote('/usr/lib/wsl/lib:'+str(SDK/'compilers/lib')+':'+str(CUDA/'lib64'))}
export TMPDIR={shlex.quote(str(BASE/'tmp'))}
export XDG_CONFIG_HOME={shlex.quote(str(BASE/'runtime-config'))}
export CUDA_CACHE_PATH={shlex.quote(str(BASE/'runtime-config/CudaCache'))}
export FOAM_CONFIG_MODE=o
export have_cuda=true
export have_umpire=false
export NVARCH=121
. {shlex.quote(str(R/'etc/bashrc'))} WM_COMPILER=Nvidia WM_MPLIB=none FOAM_SIGFPE=false
export have_cuda=true
export have_umpire=false
export NVARCH=121
export FOAM_SIGFPE=false
export WM_NCOMPPROCS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
export WM_PROJECT_USER_DIR={shlex.quote(str(BASE/'user'))}
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR={shlex.quote(str(BASE/'runtime/jobControl'))}
export FOAM_RUN={shlex.quote(str(BASE/'smoke'))}
export PATH="$FOAM_USER_APPBIN:$PATH"
'''
target=BASE/'env.sh';target.write_text(env)
clean={k:v for k,v in os.environ.items() if not k.startswith(('FOAM','WM_','MPI_','OPAL_'))}
probe=subprocess.run(['bash','--noprofile','--norc','-c','. '+shlex.quote(str(target))+'; env -0'],env=clean,capture_output=True)
assert probe.returncode==0,probe.stderr.decode(errors='replace')
actual=dict(x.decode().split('=',1) for x in probe.stdout.split(b'\0') if x and b'=' in x)
assert actual['WM_PROJECT_DIR']==str(R) and actual['WM_OPTIONS']=='linuxARM64NvidiaDPInt32Opt' and actual['FOAM_MPI']=='dummy'
assert actual['have_cuda']=='true' and actual['have_umpire']=='false' and actual['NVARCH']=='121' and actual['WM_NCOMPPROCS']=='1'
record=dict(recorded_utc=datetime.now(timezone.utc).isoformat(),source_pin='1ff2d45c002b7afb599b9dd8c4c6874666242349',sdk=str(SDK),cuda=str(CUDA),
    sdk_reused_readonly=True,environment=str(target),environment_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    max_build_jobs=1,required_nice=15,pool='fixedSizeMemoryPool',optional_umpire_enabled=False,
    selected_environment={k:actual[k] for k in ['WM_PROJECT_DIR','WM_OPTIONS','WM_COMPILER','WM_MPLIB','FOAM_MPI','FOAM_APPBIN','FOAM_LIBBIN','NVARCH','have_cuda','have_umpire','NVHPC_CUDA_HOME','FOAM_SIGFPE','WM_NCOMPPROCS']},
    managed_compiler_gate=str(NATIVE/'provenance/stdpar_compiler_gate.json'),device_gate=str(NATIVE/'provenance/stdpar_device_marker_gate.json'),
    no_global_environment_or_CPU_study_change=True,no_compiler_invoked=True)
(BASE/'provenance/private_build_configuration.json').write_text(json.dumps(record,indent=2)+'\n')
(WORK/'private_build_configuration.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
