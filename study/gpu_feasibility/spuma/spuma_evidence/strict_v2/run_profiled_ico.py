from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
binary='/opt/openfoam-workspace/gpu-feasibility/spuma/source/platforms/linuxARM64NvidiaDPInt32Opt/bin/icoFoam'
observer='/opt/openfoam-workspace/gpu-feasibility/spuma/smoke/libspuma_cuda_observer.so'
existing=os.environ.get('LD_PRELOAD','')
env=dict(os.environ,LD_PRELOAD=observer+(':'+existing if existing else ''))
started=datetime.now(timezone.utc).isoformat()
child=subprocess.Popen([binary,'-pool','fixedSizeMemoryPool','-poolSize','1'],env=env)
identity={'pid':child.pid,'uid':os.getuid(),'cwd':str(Path.cwd()),'binary':binary,
          'birth_tick':int((Path('/proc')/str(child.pid)/'stat').read_text().rsplit(')',1)[1].split()[19]),'started_utc':started}
Path('icoFoam_child_identity.json').write_text(json.dumps(identity,indent=2)+'\n')
timed_out=False
try: rc=child.wait(timeout=600)
except subprocess.TimeoutExpired:
    timed_out=True;child.terminate()
    try:rc=child.wait(timeout=30)
    except subprocess.TimeoutExpired:child.kill();rc=child.wait()
receipt={'kind':'Actual strict-v2 child exit after cleanup, separate from profiler/Allrun',
         'started_utc':started,'returned_utc':datetime.now(timezone.utc).isoformat(),'returncode':rc,
         'timed_out':timed_out,'child_identity':identity,'binary':binary,
         'binary_sha256_after_return':hashlib.sha256(Path(binary).read_bytes()).hexdigest()}
temp=Path('icoFoam_exit_receipt.json.tmp');temp.write_text(json.dumps(receipt,indent=2)+'\n');temp.replace('icoFoam_exit_receipt.json')
sys.exit(rc if rc>=0 else 128-rc)
