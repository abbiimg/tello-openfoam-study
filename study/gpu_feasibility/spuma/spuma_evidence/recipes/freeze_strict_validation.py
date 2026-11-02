"""Freeze mechanical gates before the explicitly authorized strict-v2 run."""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,os,re,shutil,subprocess
import numpy as np

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');WORK=Path(__file__).resolve().parent
CASE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102/cavity_gpu_fixedpool_strict_v2')
OLD=CASE.parent/'cavity_gpu_fixedpool'
assert os.getuid()==999 and not (CASE/'.strict-v2-started').exists()
target=BASE/'provenance/strict_v2_validation_frozen.json';assert not target.exists()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
protocol=json.loads((CASE/'protocol_strict_v2.json').read_text())
assert digest(CASE/'protocol_strict_v2.json')=='103e4fcfb1c9c08053f95a90afd91f62d14129da704731c80136449d2262fffe'
assert digest(Path(protocol['source_build']['binary']))=='b861d9d7e5cef7c4624585a9acc54c175220aeb026ade44447b9e69934fd6a1d'
for name,expected in protocol['input_hashes'].items():assert digest(CASE/name)==expected
files=['validate_strict_v2.py','audit_strict_v2_first_step.py']
trees={name:ast.parse((WORK/name).read_text()) for name in files}
for name in ['record_runtime_artifacts.py','run_profiled_ico.py']:ast.parse((CASE/name).read_text())
subprocess.run(['bash','-n',str(CASE/'Allrun')],check=True)
# Check only the format-handling functions against the already generated stock
# mesh from the terminated attempt; no new CFD or relaxed numeric acceptance.
nodes=[node for node in trees['validate_strict_v2.py'].body if isinstance(node,ast.FunctionDef) and node.name in ['mesh_list','block']]
namespace={'np':np,'re':re};exec(compile(ast.Module(body=nodes,type_ignores=[]),'frozen_mesh_format_preflight','exec'),namespace)
owner=namespace['mesh_list'](OLD/'constant/polyMesh/owner');neighbour=namespace['mesh_list'](OLD/'constant/polyMesh/neighbour')
points=namespace['mesh_list'](OLD/'constant/polyMesh/points',True)
assert len(owner)==1640 and len(neighbour)==760 and points.shape==(882,3) and owner.max()==399
boundary=(OLD/'constant/polyMesh/boundary').read_text()
assert all(namespace['block'](boundary,name) for name in ['movingWall','fixedWalls','frontAndBack'])
folder=BASE/'provenance/strict_v2_frozen_validators';assert not folder.exists();folder.mkdir()
hashes={name:digest(WORK/name) for name in files}
for name in files:shutil.copy2(WORK/name,folder/name);assert digest(folder/name)==hashes[name]
record=dict(kind='Mechanical strict-v2 validation frozen BEFORE first CFD launch',
    frozen_utc=datetime.now(timezone.utc).isoformat(),frozen_before_CFD_launch=True,
    case=str(CASE),protocol_sha256=digest(CASE/'protocol_strict_v2.json'),validator_sha256=hashes,
    frozen_copies=str(folder),runtime_scripts_and_Allrun_syntax_passed=True,
    independent_mesh_format_preflight=dict(owner_faces=len(owner),internal_faces=len(neighbour),points=len(points),cells=400),
    no_numerical_threshold_changed=True,no_CFDrun_or_compiler_started=True)
target.write_text(json.dumps(record,indent=2)+'\n');(WORK/'strict_v2_validation_frozen.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
