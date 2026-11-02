from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys
files={'icoFoam': '/opt/openfoam-workspace/gpu-feasibility/spuma/source/platforms/linuxARM64NvidiaDPInt32Opt/bin/icoFoam', 'libOpenFOAM.so': '/opt/openfoam-workspace/gpu-feasibility/spuma/source/platforms/linuxARM64NvidiaDPInt32Opt/lib/libOpenFOAM.so', 'libfiniteVolume.so': '/opt/openfoam-workspace/gpu-feasibility/spuma/source/platforms/linuxARM64NvidiaDPInt32Opt/lib/libfiniteVolume.so', 'observer.so': '/opt/openfoam-workspace/gpu-feasibility/spuma/smoke/libspuma_cuda_observer.so', 'environment': '/opt/openfoam-workspace/gpu-feasibility/spuma/env.sh'}
result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'phase':sys.argv[1],
        'files':{name:{'path':p,'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest()} for name,p in files.items()}}
Path('runtime_artifacts_'+sys.argv[1]+'.json').write_text(json.dumps(result,indent=2)+'\n')
