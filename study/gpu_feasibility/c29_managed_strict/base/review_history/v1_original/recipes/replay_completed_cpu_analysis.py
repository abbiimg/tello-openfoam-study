"""Offline replay of the original strict CPU mechanical analysis; no CFD.

Use a NEW restored evidence tree from restore_completed_evidence.py. Only path
constants/import lookup/cache location are adapted. Original source bytes,
numerical functions, d600 limits, input/field hashes and logs remain unchanged.
This does not issue runtime authorization or qualify the failed GPU transient.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, sys
sys.dont_write_bytecode=True
PACKAGE=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();base=args.base.resolve();out=args.out.absolute()
    require(not out.exists() and out.parent.is_dir(),'Use a new output file')
    require(not out.is_relative_to(base) and not out.is_relative_to(PACKAGE),'Output must be outside read-only evidence/package')
    relocation=json.loads((base/'OFFLINE_RELOCATION.json').read_text())
    require(relocation['runtime_admission'] is False,'Not offline-only restored evidence')
    proposal=PACKAGE/'evidence/strict_pressure_proposal'
    source=proposal/'analyze_five_steps_strict_candidate.py'
    require(sha(source)=='300c9ce0ecdb83cc20899c1077c071f4dcb82d412de8ce73f9ba5ae0309c88c5','Historical analyzer changed')
    require(sha(proposal/'strict_pressure_admission.py')=='b4102dba7234d31413463975dc1050eb176261ce9d7773acf3c5f8e9b0a8765b','Audit binder changed')
    sys.path.insert(0,str(proposal))
    spec=importlib.util.spec_from_file_location('historical_c29_strict_analyzer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.THRESHOLDS=PACKAGE/'source/managed_strict_v2_3/validation_thresholds.json'
    module.HELPERS={
      'fields':(PACKAGE/'recipes/execution/compare_initial_cpu.py','071202fdd5e9fa623f98701054e48ebea39d271be78171ce228a665b9292850c'),
      'axial':(PACKAGE/'recipes/geometry_reference/reference_axial_speed.py','c223006e824d1d40cc5dcd5d42e8ebc0e3a9a151d5a25f8a3e40ea93faa9699f')}
    original_loader=module.load_helper
    def relocated_helper(name):
        helper=original_loader(name)
        if name=='axial':helper.CACHE=PACKAGE/'geometry_cache'
        return helper
    module.load_helper=relocated_helper
    report=module.analyze(base,PACKAGE/'evidence/strict_runs','f14-to-cpu','strict-pressure-v1',base/'offline_relocated_input_audit.json')
    report['offline_replay']={'compiler_or_CFD_run':False,'runtime_admission':False,
        'original_analysis_sha256':'9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e',
        'path_constants_and_geometry_cache_only_relocated':True,'numpy_version':module.np.__version__,
        'meaning':'Re-evaluated historical saved fields/logs; true runtime/loader/source receipts remain separate'}
    with out.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    checks=report['comparisons']['f14-to-cpu']['checks']
    print(json.dumps({'report':str(out),'sha256':sha(out),'checks':len(checks),'failed':sum(not x['pass'] for x in checks),
        'mechanical_passed':all(x['pass'] for x in checks),'runtime_admission':False},indent=2))
if __name__=='__main__':main()
