"""Mechanically apply the preregistered five-step protocol; no relaxed screen."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re
import numpy as np

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');SOURCE=BASE/'source';WORK=Path(__file__).resolve().parent
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/cavity_gpu_fixedpool_strict_v2')
protocol=json.loads((CASE/'protocol_strict_v2.json').read_text());limits=protocol['criteria']
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
frozen=json.loads((BASE/'provenance/strict_v2_validation_frozen.json').read_text())
assert frozen['frozen_before_CFD_launch']
for name,expected in frozen['validator_sha256'].items():assert digest(WORK/name)==expected,'Validator changed after freeze: '+name
def field(path,vector=False):
    text=path.read_text();assert not re.search(r'\b(?:nan|inf)\b',text,re.I)
    match=re.search(r'internalField\s+nonuniform\s+List<'+('vector' if vector else 'scalar')+r'>\s+(\d+)\s*\((.*?)\)\s*;',text,re.S)
    assert match,'Missing nonuniform field '+str(path)
    values=np.fromstring(re.sub(r'[()]',' ',match[2]),sep=' ');count=int(match[1]);assert values.size==count*(3 if vector else 1) and np.isfinite(values).all()
    return values.reshape(count,3) if vector else values
def block(text,name):
    match=re.search(r'(?<![\w])(?:"'+re.escape(name)+r'"|'+re.escape(name)+r')\s*\{',text);assert match
    start=match.end();index=start;depth=1
    while depth:
        assert index<len(text);depth+=(text[index]=='{')-(text[index]=='}');index+=1
    return text[start:index-1]
def mesh_list(path,vector=False):
    match=re.search(r'\n\s*(\d+)\s*\((.*?)\)\s*(?://.*)?\s*$',path.read_text(),re.S);assert match
    data=np.fromstring(re.sub(r'[()]',' ',match[2]),sep=' ');assert data.size==int(match[1])*(3 if vector else 1)
    return data.reshape(int(match[1]),3) if vector else data.astype(np.int64)
def patch_flux(text,name,count):
    content=block(block(text,'boundaryField'),name)
    value=re.search(r'\bvalue\s+uniform\s+([0-9.eE+-]+)\s*;',content)
    if value:return np.full(count,float(value[1]))
    value=re.search(r'\bvalue\s+nonuniform\s+List<scalar>\s+(\d+)\s*\((.*?)\)\s*;',content,re.S)
    assert value and int(value[1])==count
    values=np.fromstring(value[2],sep=' ');assert len(values)==count and np.isfinite(values).all();return values

for name,expected in protocol['input_hashes'].items():assert digest(CASE/name)==expected,'Preregistered input changed: '+name
assert digest(BASE/'provenance/protocol_strict_v2.json')==digest(CASE/'protocol_strict_v2.json')
terminal=json.loads((CASE/'run_status.json').read_text());assert terminal['state']=='succeeded' and terminal['returncode']==0
receipt=json.loads((CASE/'icoFoam_exit_receipt.json').read_text());assert receipt['returncode']==0 and not receipt['timed_out']
start=json.loads((CASE/'runtime_artifacts_start.json').read_text());end=json.loads((CASE/'runtime_artifacts_complete.json').read_text())
assert start['files']==end['files']
for item in end['files'].values():assert digest(Path(item['path']))==item['sha256']
assert receipt['binary_sha256_after_return']==end['files']['icoFoam']['sha256']==protocol['source_build']['binary_sha256']
annotation=protocol['source_annotation'];assert digest(SOURCE/annotation['path'])==annotation['annotated_sha256']
loop=json.loads((BASE/'provenance/spuma_strict_v2_cfd_first_step_gpu_gate.json').read_text())
assert loop['state']=='passed' and loop['range_name']==protocol['profiling']['range'] and loop['final_loop_sync_observed']
assert loop['successful_launch_api_calls_in_cfd_loop']>0 and loop['failed_launch_api_calls_in_cfd_loop']==loop['failed_synchronization_api_calls_in_cfd_loop']==0
marker_text=(CASE/'log.poolDeviceMarker').read_text();marker=json.loads(next(s for s in reversed(marker_text.splitlines()) if s.startswith('{')))
assert marker['passed'] and marker['mismatches']==0 and marker['double_reduction_exact']
assert marker['pool_input_memory_type']==3 and marker['output_memory_type']==2 and marker['output_host_pointer_null'] and marker['compute_capability']==121
mesh=(CASE/'log.blockMesh').read_text();assert re.search(r'^End\s*$',mesh,re.M) and int(re.search(r'\bnCells:\s*(\d+)',mesh)[1])==400
text=(CASE/'log.icoFoam').read_text();assert re.search(r'^End\s*$',text,re.M)
assert not re.search(r'FOAM FATAL|CUDA ERROR|illegal memory access',text,re.I)
times=[float(v) for v in re.findall(r'^Time = ([0-9.eE+-]+)',text,re.M)]
assert len(times)==5 and np.allclose(times,np.arange(1,6)*.005,rtol=0,atol=1e-12)
continuity=[float(v) for v in re.findall(r'time step continuity errors\s*:\s*sum local =\s*([0-9.eE+-]+)',text)]
assert len(continuity)==10 and np.isfinite(continuity).all() and max(continuity)<=limits['all_corrector_local_continuity_max']
pressure=re.findall(r'Solving for p, Initial residual = [^,]+, Final residual = ([0-9.eE+-]+), No Iterations (\d+)',text)
assert len(pressure)==10 and max(float(row[0]) for row in pressure)<=limits['all_pressure_final_residual_max']
assert max(int(row[1]) for row in pressure)<limits['max_pressure_iterations_exclusive']
velocity=[float(v) for v in re.findall(r'Solving for U[xyz], Initial residual = [^,]+, Final residual = ([0-9.eE+-]+)',text)]
assert len(velocity)>=10 and np.isfinite(velocity).all() and max(velocity)<=limits['all_U_final_residual_max']
summary=re.findall(r'^SPUMA_CUDA_SUMMARY (\{.*\})$',text,re.M);assert len(summary)==1
observation=json.loads(summary[0]);assert observation['successful_kernel_launch_apis']>100 and observation['failed_kernel_launch_apis']==0
assert observation['successful_device_synchronizations']>0 and observation['failed_device_synchronizations']==0 and observation['last_device_synchronize_status']==0
assert observation['successful_managed_allocations']>=1 and observation['managed_allocated_bytes']>=1024**3
assert observation['nice']>=15 and observation['OMP_NUM_THREADS']==observation['OPENBLAS_NUM_THREADS']=='1'
for time in times:
    folder=CASE/format(time,'.12g');U=field(folder/'U',True);p=field(folder/'p');phi=field(folder/'phi')
    assert len(U)==len(p)==400 and np.isfinite(phi).all()
assert np.linalg.norm(U,axis=1).max()<limits['U_norm_max_exclusive']
assert U[:,0].max()>limits['Ux_max_min_exclusive'] and U[:,0].min()<limits['Ux_min_max_exclusive']
assert np.abs(p).max()<limits['p_abs_max_exclusive'] and np.ptp(p)>limits['p_range_min_exclusive'] and abs(p[0])<limits['p_reference_abs_max_exclusive']
owner=mesh_list(CASE/'constant/polyMesh/owner');neighbour=mesh_list(CASE/'constant/polyMesh/neighbour')
assert len(phi)==len(neighbour) and owner.max()==399
imbalance=np.zeros(400);np.add.at(imbalance,owner[:len(phi)],phi);np.add.at(imbalance,neighbour,-phi)
boundary=(CASE/'constant/polyMesh/boundary').read_text();saved=(CASE/'0.025/phi').read_text();covered=0;wall_max={}
for name in ['movingWall','fixedWalls','frontAndBack']:
    item=block(boundary,name);count=int(re.search(r'\bnFaces\s+(\d+)\s*;',item)[1]);start_face=int(re.search(r'\bstartFace\s+(\d+)\s*;',item)[1]);covered+=count
    if re.search(r'\btype\s+empty\s*;',item):assert re.search(r'\btype\s+empty\s*;',block(block(saved,'boundaryField'),name));continue
    assert re.search(r'\btype\s+wall\s*;',item);values=patch_flux(saved,name,count)
    maximum=float(np.abs(values).max(initial=0));assert maximum<limits['verify_all_closed_wall_fluxes_abs_max_exclusive']
    wall_max[name]=maximum;np.add.at(imbalance,owner[start_face:start_face+count],values)
assert covered==len(owner)-len(neighbour)
points=mesh_list(CASE/'constant/polyMesh/points',True);volume=float(np.prod(points.max(axis=0)-points.min(axis=0)))
independent=.005*float(np.abs(imbalance).sum())/volume
assert independent<limits['independent_final_saved_flux_continuity_max_exclusive']
libraries=(CASE/'runtime_libraries.txt').read_text();assert str(SOURCE/'platforms/linuxARM64NvidiaDPInt32Opt/lib/libOpenFOAM.so') in libraries
result=dict(kind='Actual distinct strict-v2 five-step SPUMA CUDA functional gate, not rotor or timing result',
    completed_utc=datetime.now(timezone.utc).isoformat(),state='passed',case=str(CASE),protocol_sha256=digest(CASE/'protocol_strict_v2.json'),protocol=protocol,
    actual_terminal_status=terminal,actual_child_receipt=receipt,runtime_artifacts_unchanged=end,
    GPU_executor_device_only_marker=marker,first_complete_CFD_step_API_gate=loop,process_API_observations=observation,
    steps=5,final_time_s=.025,all_corrector_local_continuity_values=continuity,peak_all_corrector_local_continuity=max(continuity),
    maximum_pressure_final_residual=max(float(row[0]) for row in pressure),maximum_U_final_residual=max(velocity),
    independent_CPU_final_flux_continuity=independent,verified_saved_wall_flux_maxima=wall_max,domain_volume_m3=volume,
    all_five_written_U_p_phi_finite=True,final_field_checks=dict(U_min=U.min(axis=0).tolist(),U_max=U.max(axis=0).tolist(),p_min=float(p.min()),p_max=float(p.max())),
    original_full_horizon_screen_still_failed=True,original_attempt=str(BASE/'provenance/original_attempt/original_attempt_diagnostic.json'),
    no_threshold_relaxation=True,no_unique_kernel_activity_claim=True,no_complete_device_residence_claim=True,
    no_performance_inference=True,no_actuator_or_CPU_study_change=True)
target=BASE/'provenance/spuma_strict_v2_tutorial_gate.json';assert not target.exists();target.write_text(json.dumps(result,indent=2)+'\n')
(WORK/'spuma_strict_v2_tutorial_gate.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
