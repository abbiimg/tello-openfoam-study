"""Offline replay of the original strict CPU mechanical analysis; no CFD.

Use a NEW restored evidence tree from restore_completed_evidence.py. Only path
constants/import lookup/cache location are adapted. Original source bytes,
numerical functions, d600 limits, input/field hashes and logs remain unchanged.
This does not issue runtime authorization or qualify the failed GPU transient.
"""
from pathlib import Path
import argparse, hashlib, importlib.util, json, os, stat, sys
sys.dont_write_bytecode=True
PACKAGE=Path(__file__).absolute().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def no_links(path):
    supplied=Path(path);require('..' not in supplied.parts,'Parent escape')
    p=supplied.absolute()
    for q in (p,*p.parents):
        require(not q.is_symlink() and not getattr(q,'is_junction',lambda:False)(),
                'Link/junction/ancestor: '+str(q))
        try:metadata=q.lstat()
        except FileNotFoundError:continue
        require(not (getattr(metadata,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0)),
                'Reparse point/ancestor: '+str(q))
    return p.resolve(strict=False)
def validate_paths(base,output,package=PACKAGE):
    package=no_links(package);base=no_links(base);out=no_links(output)
    require(base.is_dir() and package.is_dir(),'Missing evidence/package directory')
    require(not out.exists() and out.parent.is_dir(),'Use a new output file')
    for source in (base,package):
        require(not (out==source or out.is_relative_to(source) or source.is_relative_to(out)),
                'Output overlaps read-only evidence/package')
    return base,out,package
def validate_inputs(base,package):
    # Check explicit code/data paths before any included-code import. Preserve
    # lexical paths until link/junction/reparse ancestors have been rejected.
    names=['evidence/strict_pressure_proposal/analyze_five_steps_strict_candidate.py',
      'evidence/strict_pressure_proposal/strict_pressure_admission.py',
      'evidence/strict_pressure_proposal/strict_pressure_protocol.json',
      'evidence/strict_pressure_proposal/root_authorization.json',
      'source/managed_strict_v2_3/validation_thresholds.json',
      'recipes/execution/compare_initial_cpu.py','recipes/geometry_reference/reference_axial_speed.py',
      'geometry_cache/quadrature.csv','geometry_cache/rotors.csv',
      'evidence/strict_runs/f14_control_five_stdout.log','evidence/strict_runs/native_cpu_five_stdout.log']
    paths=[package/name for name in names]+[base/'OFFLINE_RELOCATION.json',base/'offline_relocated_input_audit.json']
    paths += [base/role/'system/fvSolution' for role in ('foundation14_control','native_cpu')]
    paths.append(base/'native_cpu/constant/c29PortControls')
    paths += [base/role/time/field for role in ('foundation14_control','native_cpu')
              for time in ('0.6','0.6001','0.6002','0.6003','0.6004','0.6005') for field in ('U','p','phi')]
    for path in paths:require(no_links(path).is_file(),'Missing regular input: '+str(path))
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();base,out,package=validate_paths(args.base,args.out)
    validate_inputs(base,package)
    relocation=json.loads((base/'OFFLINE_RELOCATION.json').read_text())
    require(relocation['runtime_admission'] is False,'Not offline-only restored evidence')
    proposal=package/'evidence/strict_pressure_proposal'
    source=proposal/'analyze_five_steps_strict_candidate.py'
    require(sha(source)=='300c9ce0ecdb83cc20899c1077c071f4dcb82d412de8ce73f9ba5ae0309c88c5','Historical analyzer changed')
    require(sha(proposal/'strict_pressure_admission.py')=='b4102dba7234d31413463975dc1050eb176261ce9d7773acf3c5f8e9b0a8765b','Audit binder changed')
    sys.path.insert(0,str(proposal))
    spec=importlib.util.spec_from_file_location('historical_c29_strict_analyzer',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.THRESHOLDS=package/'source/managed_strict_v2_3/validation_thresholds.json'
    module.HELPERS={
      'fields':(package/'recipes/execution/compare_initial_cpu.py','071202fdd5e9fa623f98701054e48ebea39d271be78171ce228a665b9292850c'),
      'axial':(package/'recipes/geometry_reference/reference_axial_speed.py','c223006e824d1d40cc5dcd5d42e8ebc0e3a9a151d5a25f8a3e40ea93faa9699f')}
    original_loader=module.load_helper
    def relocated_helper(name):
        helper=original_loader(name)
        if name=='axial':helper.CACHE=package/'geometry_cache'
        return helper
    module.load_helper=relocated_helper
    report=module.analyze(base,package/'evidence/strict_runs','f14-to-cpu','strict-pressure-v1',base/'offline_relocated_input_audit.json')
    report['offline_replay']={'compiler_or_CFD_run':False,'runtime_admission':False,
        'original_analysis_sha256':'9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e',
        'path_constants_and_geometry_cache_only_relocated':True,'numpy_version':module.np.__version__,
        'meaning':'Re-evaluated historical saved fields/logs; true runtime/loader/source receipts remain separate'}
    validate_paths(base,out,package)
    with out.open('x') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    checks=report['comparisons']['f14-to-cpu']['checks']
    print(json.dumps({'report':str(out),'sha256':sha(out),'checks':len(checks),'failed':sum(not x['pass'] for x in checks),
        'mechanical_passed':all(x['pass'] for x in checks),'runtime_admission':False},indent=2))
if __name__=='__main__':main()
