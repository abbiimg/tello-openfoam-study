from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,sys
WORK=Path(__file__).resolve().parent;BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');BUDGET=WORK/'build_budget.json'
CASE=Path(sys.argv[1]);claim=sys.argv[2]
current_nice=os.getpriority(os.PRIO_PROCESS,0)
if current_nice<15:os.nice(15-current_nice)
assert CASE==Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/pool_executor_marker') and os.getuid()==999
assert json.loads(BUDGET.read_text())['extra_probe_claim']==claim and not (CASE/'.started').exists()
(CASE/'.started').touch();binary=BASE/'user/platforms/linuxARM64NvidiaDPInt32Opt/bin/Test-spumaPoolDevice'
result=None
try:
    env=dict(os.environ,SPUMA_PROBE_SEED='324508639')
    with (CASE/'log.poolDeviceMarker').open('x') as output:run=subprocess.run([str(binary),'-pool','fixedSizeMemoryPool','-poolSize','1'],cwd=CASE,env=env,stdout=output,stderr=subprocess.STDOUT,timeout=180)
    assert run.returncode==0,'Marker process failed; inspect log.poolDeviceMarker'
    data=json.loads(next(s for s in reversed((CASE/'log.poolDeviceMarker').read_text().splitlines()) if s.startswith('{')))
    assert data['passed'] and data['mismatches']==0 and data['pool_input_memory_type']==3 and data['output_memory_type']==2 and data['output_host_pointer_null']
    assert data['double_reduction_exact'] and data['compute_capability']==121
    result=dict(kind='Actual private SPUMA fixed-pool and own CUDA executor functional gate, not CFD',completed_utc=datetime.now(timezone.utc).isoformat(),
        state='passed',returncode=0,result=data,source_pin='1ff2d45c002b7afb599b9dd8c4c6874666242349',
        binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),case=str(CASE),no_performance_claim=True,no_solver_coverage_claim=True)
    (BASE/'provenance/core_executor_gate.json').write_text(json.dumps(result,indent=2)+'\n');(WORK/'core_executor_gate.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result),flush=True)
finally:
    b=json.loads(BUDGET.read_text())
    if b.get('extra_probe_claim')==claim:
        b.update(max_jobs=2,extra_probe_claim=None,extra_probe_reserved_jobs=0)
        temp=BUDGET.with_suffix('.restore.tmp');temp.write_text(json.dumps(b,indent=2)+'\n');temp.replace(BUDGET)
