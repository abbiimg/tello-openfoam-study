from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
binary='/opt/openfoam-workspace/gpu-feasibility/spuma/source/platforms/linuxARM64NvidiaDPInt32Opt/bin/icoFoam'
observer='/opt/openfoam-workspace/gpu-feasibility/spuma/smoke/libspuma_cuda_observer.so'
inherited_preload=os.environ.get('LD_PRELOAD','')
env=dict(os.environ,LD_PRELOAD=observer+(':'+inherited_preload if inherited_preload else ''))
started=datetime.now(timezone.utc).isoformat()
result=subprocess.run([binary,'-pool','fixedSizeMemoryPool','-poolSize','1'],env=env)
receipt={'kind':'Actual child icoFoam exit observed after binary returned, distinct from profiler exit',
         'started_utc':started,'returned_utc':datetime.now(timezone.utc).isoformat(),
         'returncode':result.returncode,'binary':binary,
         'binary_sha256_after_return':hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
temp=Path('icoFoam_exit_receipt.json.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\n')
temp.replace('icoFoam_exit_receipt.json')
sys.exit(result.returncode if result.returncode>=0 else 128-result.returncode)
