from pathlib import Path
import hashlib
import json
import stat
out = Path(__file__).resolve().parent
base = Path('/opt/openfoam-workspace/cases/amgx_gpu_pilots_20261102')
assert base.resolve()==base
cases = {name:base/name for name in ['cavity-native','cavity-amgx']}
for case in cases.values():
    assert case.resolve().is_relative_to(base)
    script = case/'AllrunPilot'
    script.chmod(script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
shared = ['0/U','0/p','constant/physicalProperties','constant/momentumTransport','system/fvSchemes']
shared += ['constant/polyMesh/'+p.name for p in (cases['cavity-native']/'constant/polyMesh').iterdir() if p.is_file()]
hashes = {name:{rel:hashlib.sha256((case/rel).read_bytes()).hexdigest() for rel in shared} for name,case in cases.items()}
assert hashes['cavity-native']==hashes['cavity-amgx'], 'Shared physics/mesh inputs must match exactly'
report = {'kind':'Private functional adapter pilots, not performance/rotor CFD',
          'cases':{name:str(case) for name,case in cases.items()},
          'shared_input_hashes':hashes,'shared_inputs_identical':True,
          'dimensions':'2D 400-cell lid-driven cavity','nu_m2_s':0.01,'end_time_s':0.1,'delta_t_s':0.005,
          'expected_steps':20,'turbulence':'laminar','max_compile_jobs':1,
          'solver_process_threads':1,'solver_nice':15,'native_pressure_tolerance':1e-11,
          'adapter_extra_tolerance_safety_factor':0.1,'adapter_setup':'uncached each solve',
          'no_production_inputs_modified':True,'performance_comparison':False}
(out/'pilot_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='shared_input_hashes'},indent=2))
