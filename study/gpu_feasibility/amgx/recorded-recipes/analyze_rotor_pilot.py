"""Read-only independent comparison of actual five-step C29 rotor pilots.

No CFD is launched. All fields are read in full. Volume weights use the exact
frozen rectilinear mesh ordering independently checked in the seed's benchmark
accuracy evidence; point ordering and hashes are rechecked here.
"""
from pathlib import Path
import hashlib
import json
import math
import os
import re
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[key]='1'
import numpy as np

os.nice(15)
out = Path(__file__).resolve().parent
manifest = json.loads((out/'rotor_pilot_manifest.json').read_text())
criteria = json.loads((out/'rotor_acceptance.json').read_text())
cases = {name:Path(item['path']) for name,item in manifest['cases'].items()}
number = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def record(path): return dict(sha256=sha(path),size_bytes=path.stat().st_size)

def list_body(text,start=0):
    m=re.search(r'\n\s*(\d+)\s*\n\s*\(\s*\n',text[start:]); assert m
    begin=start+m.end()
    end=re.search(r'(?m)^\s*\)\s*;?\s*$',text[begin:]); assert end
    return int(m[1]),text[begin:begin+end.start()]

def arrays(path):
    text=path.read_text(); assert re.search(r'\bformat\s+ascii\s*;',text)
    result=[]
    for m in re.finditer(r'\b(internalField|value)\s+nonuniform\s+List<(scalar|vector)>',text):
        count,body=list_body(text,m.end())
        a=np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ')
        components=3 if m[2]=='vector' else 1
        assert a.size==count*components and np.isfinite(a).all(),path
        result.append((m[1],m[2],a.reshape(count,components) if components==3 else a))
    assert result and result[0][0]=='internalField',path
    return result,text

def relative(candidate,reference,weights=None):
    d=candidate-reference
    if d.ndim==2: d2=np.sum(d*d,axis=1); r2=np.sum(reference*reference,axis=1)
    else: d2=d*d; r2=reference*reference
    num=float(np.sum(d2 if weights is None else weights*d2))
    den=float(np.sum(r2 if weights is None else weights*r2))
    assert den>1e-30
    return dict(relative_L2=math.sqrt(num/den),max_abs_difference=float(np.max(np.abs(d))),
                reference_L2_norm=math.sqrt(den))

checks={}
logs={name:(case/'log.rotor-pilot').read_text() for name,case in cases.items()}
metadata={}
histories={}
for name,case in cases.items():
    response=json.loads((out/('mcp_rotor_'+('amgx' if name.endswith('amgx') else 'native')+'_run.json')).read_text())
    result=json.loads(next(x['text'] for x in response['content'] if x['type']=='text'))
    checks[name+'_exit_zero']=not response.get('isError') and result.get('returncode')==0
    text=logs[name]
    checks[name+'_end']=bool(re.search(r'^\s*End\s*$',text,re.M))
    checks[name+'_no_fatal']='FOAM FATAL' not in text
    checks[name+'_no_actuator_recompile']='Creating new library' not in text and 'wmake libso' not in text
    times=[float(x) for x in re.findall(r'^Time = ('+number+r')s?\s*$',text,re.M)]
    checks[name+'_five_steps']=len(times)==5
    times_saved=sorted((p for p in case.iterdir() if p.is_dir() and re.fullmatch(number,p.name) and float(p.name)>.6),key=lambda p:float(p.name))
    assert times_saved
    saved=times_saved[-1]
    checks[name+'_fields_saved']=all((saved/f).is_file() for f in ('U','p','phi'))
    continuity=[]
    for m in re.finditer(r'time step continuity errors\s*:\s*sum local\s*=\s*('+number+r'),\s*global\s*=\s*('+number+r')(?:,\s*cumulative\s*=\s*('+number+r'))?',text):
        continuity.append(dict(local=float(m[1]),global_value=float(m[2]),cumulative=float(m[3]) if m[3] is not None else None))
    assert len(continuity)==10
    final=[x for x in continuity if x['cumulative'] is not None]
    peaks={key:max(abs(x[key]) for x in continuity if x[key] is not None) for key in ('local','global_value','cumulative')}
    final_peaks={key:max(abs(x[key]) for x in final) for key in ('local','global_value','cumulative')}
    checks[name+'_bounded_final_continuity']=all(final_peaks[k]<=1e-7 for k in ('local','global_value'))
    rows=[[float(x) for x in line.split()[1:]] for line in text.splitlines() if line.startswith('TILT ')]
    history=np.asarray(rows)
    assert history.shape==(5,8) and np.isfinite(history).all()
    histories[name]=history
    metadata[name]=dict(job_id=result['job_id'],returncode=result.get('returncode'),steps=len(times),
                        times_s=times,final_directory=saved.name,continuity=continuity,
                        continuity_peaks_all=peaks,continuity_peaks_final=final_peaks,
                        actual_actuator_samples=rows,log_sha256=sha(case/'log.rotor-pilot'))
    frozen_inputs=manifest['cases'][name]['input_hashes']
    checks[name+'_all_frozen_inputs_unchanged']=all(record(case/rel)==rec for rel,rec in frozen_inputs.items())

checks['same_physical_time_steps']=np.allclose(metadata['rotor-native']['times_s'],metadata['rotor-amgx']['times_s'],rtol=0,atol=1e-8)
# Volumes: tensor-product ordering already verified against every owned face in
# the frozen benchmark. The exact mesh hashes are reverified above.
point_path=cases['rotor-native']/'constant/polyMesh/points'
point_text=point_path.read_text(); count,body=list_body(point_text)
points=np.fromstring(body.replace('(',' ').replace(')',' '),sep=' ').reshape(-1,3)
assert len(points)==count and np.isfinite(points).all()
counts=[len(np.unique(np.round(points[:,k],12))) for k in range(3)]
nx,ny,nz=[n-1 for n in counts]
assert nx*ny*nz==922576 and points.shape[0]==(nx+1)*(ny+1)*(nz+1)
grid=points.reshape(nz+1,ny+1,nx+1,3)
axes=[grid[0,0,:,0].copy(),grid[0,:,0,1].copy(),grid[:,0,0,2].copy()]
for k,a in enumerate(axes):
    expected=(a[None,None,:] if k==0 else a[None,:,None] if k==1 else a[:,None,None])
    assert np.allclose(grid[...,k],expected,rtol=0,atol=1e-12)
volume=(np.diff(axes[2])[:,None,None]*np.diff(axes[1])[None,:,None]*np.diff(axes[0])[None,None,:]).ravel()
assert volume.size==922576 and np.all(volume>0)
comparisons={}
for field in ('U','p','phi'):
    native,ntext=arrays(cases['rotor-native']/metadata['rotor-native']['final_directory']/field)
    gpu,gtext=arrays(cases['rotor-amgx']/metadata['rotor-amgx']['final_directory']/field)
    assert len(native)==len(gpu)
    assert all((a[0],a[1],a[2].shape)==(b[0],b[1],b[2].shape) for a,b in zip(native,gpu))
    internal=relative(gpu[0][2],native[0][2],volume if field in ('U','p') else None)
    internal.update(components=int(native[0][2].size),norm='volume-weighted cell L2' if field in ('U','p') else 'unweighted internal-face flux L2')
    boundary=[dict(list_index=i,components=int(a[2].size),**relative(b[2],a[2])) for i,(a,b) in enumerate(zip(native[1:],gpu[1:]),1)]
    comparisons[field]=dict(internal=internal,nonuniform_boundary_values=boundary)
    gate=criteria['max_volume_weighted_'+field+'_relative_L2'] if field in ('U','p') else criteria['max_internal_face_phi_relative_L2']
    checks[field+'_internal_field_agreement']=internal['relative_L2']<=gate
    if field=='phi': checks['phi_boundary_field_agreement']=bool(boundary) and all(x['relative_L2']<=gate for x in boundary)
    if field=='p':
        checks['same_pressure_gauge']=all(re.search(r'\bp0\s+uniform\s+0\s*;',t) for t in (ntext,gtext))

pattern=re.compile(r'AMGX_PRESSURE_SOLVE rows=(\d+) nnz=(\d+) iterations=(\d+) kernels=(\d+) initial=('+number+r') final=('+number+r') converged=(true|false)')
diagnostics=[]
for i,m in enumerate(pattern.finditer(logs['rotor-amgx'])):
    initial=float(m[5]); final=float(m[6]); reltol=.05 if i%2==0 else 0.
    threshold=max(1e-7,reltol*initial)
    diagnostics.append(dict(rows=int(m[1]),nnz=int(m[2]),iterations=int(m[3]),
                            successful_cuda_launch_api_calls=int(m[4]),initial_residual=initial,
                            native_final_residual=final,relTol=reltol,threshold=threshold,
                            native_stopping_test_passed=m[7]=='true' and math.isfinite(final) and final<=threshold))
checks['ten_actual_gpu_pressure_solves']=len(diagnostics)==10
checks['every_pressure_solve_observed_gpu_work']=bool(diagnostics) and all(x['successful_cuda_launch_api_calls']>0 for x in diagnostics)
checks['every_pressure_solve_native_residual_passed']=bool(diagnostics) and all(x['native_stopping_test_passed'] for x in diagnostics)
checks['all_pressure_systems_full_cell_count']=all(x['rows']==922576 and x['nnz']==6400992 for x in diagnostics)
start=max(h[0,0] for h in histories.values()); end=min(h[-1,0] for h in histories.values())
assert end>start
trap=np.trapezoid if hasattr(np,'trapezoid') else np.trapz
means={}
for name,h in histories.items():
    times=np.r_[start,h[(h[:,0]>start)&(h[:,0]<end),0],end]
    means[name]={key:float(trap(np.interp(times,h[:,0],h[:,col]),times)/(end-start))
                 for key,col in (('vertical_lift_N',1),('axial_air_work_W',2),('inferred_shaft_W',3),('inferred_electrical_W',4))}
mean_differences={key:(means['rotor-amgx'][key]/means['rotor-native'][key]-1) for key in means['rotor-native']}
checks['mean_lift_agreement']=abs(mean_differences['vertical_lift_N'])<=criteria['max_mean_lift_relative_difference']
checks['mean_inferred_electrical_agreement']=abs(mean_differences['inferred_electrical_W'])<=criteria['max_mean_inferred_electrical_relative_difference']
continuity_flags=[]
for kind in ('continuity_peaks_all','continuity_peaks_final'):
    for key in ('local','global_value','cumulative'):
        a=metadata['rotor-amgx'][kind][key]; b=metadata['rotor-native'][kind][key]
        if a>b+1e-12: continuity_flags.append(dict(metric=kind+'/'+key,amgx=a,native=b))
checks['no_continuity_deterioration_flags']=not continuity_flags
source=Path(manifest['source_case'])
checks['frozen_original_inputs_unchanged']=all(record(source/rel)==rec for rel,rec in manifest['source_input_hashes'].items())
checks['shared_seed_unchanged']=sha(Path(manifest['source_seed']))==manifest['source_seed_sha256']
checks['all_private_gpu_libraries_unchanged']=all(sha(Path(item['path']))==item['sha256'] for item in manifest['libraries'].values())
report=dict(kind='Actual five-step C29 rotor AmgX/Foundation14 compatibility check; no performance inference',
            passed=all(checks.values()),checks=checks,fields=comparisons,means=means,
            mean_relative_differences=mean_differences,mean_window_s=[start,end],
            cases=metadata,amgx_pressure_solves=diagnostics,
            successful_cuda_launch_api_calls_total=sum(x['successful_cuda_launch_api_calls'] for x in diagnostics),
            max_native_pressure_final_corrector_residual=max(x['native_final_residual'] for x in diagnostics[1::2]),
            continuity_flags=continuity_flags,mesh_shape=[nx,ny,nz],volume_sum_m3=float(volume.sum()),
            actuator_library=manifest['actuator_generated_library'],adapter_source_sha256=manifest['adapter_source_sha256'],
            adapter_extra_tolerance_safety_factor=.1,adapter_setup='uncached each solve',
            performance_comparison=False,full_field_gpu_offload=False,production_default_changed=False,
            limitations=['Five transient steps only, not a stationary lift study or timing benchmark.',
                         'Serial symmetric noncoupled pressure only; velocity, C29 source and other flow work remain CPU.',
                         'Native pressure stopping tolerance retained, but AmgX uses an extra tenfold L2 safety margin.',
                         'Launch counter reports successful CUDA launch API calls, not distinct kernels or a GPU timeline.',
                         'Electrical input is inferred from the unchanged assumed loss map, not measured battery power.',
                         'Both pilots identically reset the actuator controller from the warm flow state; no full source-history continuation claimed.'])
(out/'rotor_smoke.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('cases','amgx_pressure_solves')},indent=2))
raise SystemExit(0 if report['passed'] else 1)
