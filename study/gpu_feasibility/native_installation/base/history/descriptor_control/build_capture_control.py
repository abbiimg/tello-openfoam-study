from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,shutil,subprocess
WORK=Path(__file__).resolve().parent
P=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar')
TARGET=P/'diagnostics/descriptor_capture_20261102_b'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
if TARGET.exists():raise RuntimeError('Refusing existing diagnostic build destination')
(TARGET/'Make').mkdir(parents=True)
shutil.copyfile(WORK/'descriptor_capture_control.C',TARGET/'descriptor_capture_control.C')
(TARGET/'Make/files').write_text('descriptor_capture_control.C\n\nEXE = $(FOAM_USER_APPBIN)/descriptorCaptureControl\n')
(TARGET/'Make/options').write_text('EXE_INC = -gpu=cc121,mem:managed,lineinfo\n\nEXE_LIBS =\n')
log=WORK/'capture_control_build_b.log'
before={'source_sha256':sha(TARGET/'descriptor_capture_control.C'),'source':str(TARGET/'descriptor_capture_control.C'),'before_any_control_run':True,'max_compile_jobs':1,'nice':os.getpriority(os.PRIO_PROCESS,0)}
(WORK/'capture_control_prebuild_b.json').write_text(json.dumps(before,indent=2)+'\n')
with log.open('x') as f:r=subprocess.run(['wmake','-j1',str(TARGET)],stdout=f,stderr=subprocess.STDOUT)
record={**before,'completed_utc':datetime.now(timezone.utc).isoformat(),'return_code':r.returncode,'log_sha256':sha(log)}
binary=P/'user/platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin/descriptorCaptureControl'
if r.returncode==0:record.update(binary=str(binary),binary_sha256=sha(binary))
(WORK/'capture_control_build_b.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
raise SystemExit(r.returncode)
