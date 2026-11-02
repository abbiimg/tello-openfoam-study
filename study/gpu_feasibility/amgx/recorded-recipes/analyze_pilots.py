"""Independent field/residual checks for actual private Foundation14 AmgX pilots."""
from pathlib import Path
import hashlib
import json
import math
import os
import re
import subprocess

os.nice(15)
out = Path(__file__).resolve().parent
base = Path('/opt/openfoam-workspace/cases/amgx_gpu_pilots_20261102')
root = Path('/opt/openfoam-workspace/gpu-feasibility/amgx-cuda')
number = r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'

def field(path):
    text = path.read_text()
    m = re.search(r'internalField\s+nonuniform\s+List<(scalar|vector)>\s+(\d+)\s*\((.*?)\)\s*;',text,re.S)
    assert m, 'Expected complete ASCII nonuniform field '+str(path)
    values = [float(x) for x in re.findall(number,m[3])]
    assert len(values)==int(m[2])*(3 if m[1]=='vector' else 1)
    assert all(math.isfinite(x) for x in values)
    return values

def job(name):
    result = json.loads((out/('mcp_'+name+'_run.json')).read_text())
    assert not result.get('isError')
    text = next(item['text'] for item in result['content'] if item['type']=='text')
    return json.loads(text)

native_job, gpu_job = job('native'),job('gpu')
checks = {'native_exit_zero':native_job['returncode']==0,'gpu_exit_zero':gpu_job['returncode']==0}
logs = {name:(base/name/'log.pilot').read_text() for name in ['cavity-native','cavity-amgx']}
for name,text in logs.items():
    checks[name+'_end'] = bool(re.search(r'^\s*End\s*$',text,re.M))
    checks[name+'_20steps'] = len(re.findall(r'^Time = ',text,re.M))==20
    checks[name+'_no_fatal'] = 'FOAM FATAL' not in text
    checks[name+'_written_time'] = (base/name/'0.1/U').is_file() and (base/name/'0.1/p').is_file()
comparisons = {}
for name in ['U','p']:
    native = field(base/'cavity-native/0.1'/name)
    gpu = field(base/'cavity-amgx/0.1'/name)
    assert len(native)==len(gpu)
    delta = [a-b for a,b in zip(native,gpu)]
    absolute = max(abs(x) for x in delta)
    relative = math.sqrt(sum(x*x for x in delta)/max(sum(x*x for x in native),1e-300))
    comparisons[name] = {'components':len(native),'max_abs_difference':absolute,
                         'relative_l2_difference':relative,'gate_max_abs':1e-8,'gate_relative_l2':1e-8}
    checks[name+'_field_agreement'] = absolute<=1e-8 and relative<=1e-8

pattern = re.compile(r'AMGX_PRESSURE_SOLVE rows=(\d+) nnz=(\d+) iterations=(\d+) kernels=(\d+) initial=('+number+r') final=('+number+r') converged=(true|false)')
diagnostics = [{'rows':int(m[1]),'nnz':int(m[2]),'iterations':int(m[3]),
                'successful_cuda_launch_api_calls':int(m[4]),'initial_residual':float(m[5]),
                'native_final_residual':float(m[6]),'converged':m[7]=='true'}
               for m in pattern.finditer(logs['cavity-amgx'])]
checks['40_amgx_pressure_solves'] = len(diagnostics)==40
checks['all_amgx_solves_launched_gpu_work'] = bool(diagnostics) and all(d['successful_cuda_launch_api_calls']>0 for d in diagnostics)
checks['all_native_residuals_meet_tolerance'] = bool(diagnostics) and all(d['converged'] and math.isfinite(d['native_final_residual']) and d['native_final_residual']<=1e-11 for d in diagnostics)
manifest = json.loads((out/'pilot_manifest.json').read_text())
current = {name:{rel:hashlib.sha256((base/name/rel).read_bytes()).hexdigest() for rel in hashes}
           for name,hashes in manifest['shared_input_hashes'].items()}
checks['shared_physics_mesh_inputs_unchanged'] = current==manifest['shared_input_hashes']
git_status = subprocess.check_output(['git','-C',str(root/'AMGX'),'status','--porcelain'],text=True)
checks['upstream_amgx_source_clean'] = not git_status.strip()
report = {'kind':'Actual OpenFOAM Foundation14 AmgX functional integration verification',
          'passed':all(checks.values()),'checks':checks,'field_comparisons':comparisons,
          'amgx_pressure_solves':len(diagnostics),
          'successful_cuda_launch_api_calls_total':sum(d['successful_cuda_launch_api_calls'] for d in diagnostics),
          'max_native_normalized_pressure_residual':max((d['native_final_residual'] for d in diagnostics),default=None),
          'native_job_id':native_job['job_id'],'gpu_job_id':gpu_job['job_id'],
          'pilot_root':str(base),'source_commit':json.loads((out/'source_pin.json').read_text())['commit'],
          'source_git_status':git_status,'library_gpu_smoke_passed':json.loads((out/'smoke.json').read_text())['passed'],
          'adapter_library':str(root/'install/lib/libAmgXPressure.so'),
          'adapter_library_sha256':hashlib.sha256((root/'install/lib/libAmgXPressure.so').read_bytes()).hexdigest(),
          'diagnostics':diagnostics,
          'limitations':['400-cell 2D cavity only; rotor CFD not tested','serial symmetric noncoupled pressure only','uncached setup every solve','extra tenfold backend tolerance safety margin','no performance benchmark or production adoption'],
          'no_production_inputs_modified':True}
(out/'adapter_smoke.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='diagnostics'},indent=2))
raise SystemExit(0 if report['passed'] else 1)
