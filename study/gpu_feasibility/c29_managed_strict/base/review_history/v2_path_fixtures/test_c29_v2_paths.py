"""Isolated adapter path fixtures; never call restore/main/analyze/replay."""
from pathlib import Path
import argparse,ast,hashlib,importlib.util,json,os,subprocess,sys,tempfile
sys.dont_write_bytecode=True
WORK=Path(__file__).absolute().parent
V2=WORK/'c29_managed_strict_publication_candidate_v2'
def load(name):
 p=V2/'recipes'/name;ast.parse(p.read_text())
 spec=importlib.util.spec_from_file_location(name.replace('.','_'),p)
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--platform-label',required=True);args=ap.parse_args()
 root=Path(tempfile.mkdtemp(prefix='c29_v2_path_fixtures_',dir=WORK if os.name=='nt' else '/tmp'))
 package=root/'sources/package';seed_dir=root/'sources/seed';base=root/'evidence';outside=root/'outside'
 for p in (package,seed_dir,base,outside):p.mkdir(parents=True)
 seed=seed_dir/'shared_seed.zip';seed.write_bytes(b'fixture-only-not-a-scientific-archive')
 (package/'sentinel.txt').write_text('package unchanged');(base/'sentinel.txt').write_text('evidence unchanged')
 restore=load('restore_completed_evidence.py');replay=load('replay_completed_cpu_analysis.py')
 results=[]
 def refused(label,call,kind=None):
  try:call();ok=False;reason='unexpectedly accepted'
  except ValueError as exc:reason=str(exc);ok=kind is None or kind in reason
  results.append({'fixture':label,'pass':ok,'reason':reason})
 dest=outside/'new_evidence'
 results.append({'fixture':'restore-disjoint-new-accepted-without-creation',
  'pass':restore.disjoint_destination(dest,package,seed)==dest.resolve() and not dest.exists()})
 for label,d in [('package-equal',package),('package-child',package/'new'),('package-descendant',package/'a/new'),
                 ('seed-dir-equal',seed_dir),('seed-dir-child',seed_dir/'new'),('seed-dir-descendant',seed_dir/'a/new'),
                 ('package-parent',package.parent),('common-ancestor',root),('seed-file-as-destination',seed)]:
  refused('restore-'+label,lambda d=d:restore.disjoint_destination(d,package,seed),'overlaps')
 good=replay.validate_paths(base,outside/'new_report.json',package)
 results.append({'fixture':'replay-disjoint-new-accepted-without-creation',
  'pass':good==(base.resolve(),(outside/'new_report.json').resolve(),package.resolve()) and not (outside/'new_report.json').exists()})
 for label,out in [('inside-package',package/'new.json'),('inside-evidence',base/'new.json'),('existing-ancestor',root)]:
  refused('replay-'+label,lambda out=out:replay.validate_paths(base,out,package))
 # Prepare only inert fixture placeholders to exercise a linked data input
 # after all earlier path requirements. No included analyzer is imported.
 names=['evidence/strict_pressure_proposal/analyze_five_steps_strict_candidate.py',
  'evidence/strict_pressure_proposal/strict_pressure_admission.py',
  'evidence/strict_pressure_proposal/strict_pressure_protocol.json',
  'evidence/strict_pressure_proposal/root_authorization.json',
  'source/managed_strict_v2_3/validation_thresholds.json','recipes/execution/compare_initial_cpu.py',
  'recipes/geometry_reference/reference_axial_speed.py','geometry_cache/quadrature.csv','geometry_cache/rotors.csv',
  'evidence/strict_runs/f14_control_five_stdout.log','evidence/strict_runs/native_cpu_five_stdout.log']
 for name in names:
  p=package/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('INERT PATH FIXTURE')
 initial=[base/'OFFLINE_RELOCATION.json',base/'offline_relocated_input_audit.json',base/'native_cpu/constant/c29PortControls']
 initial += [base/r/'system/fvSolution' for r in ('foundation14_control','native_cpu')]
 initial += [base/r/t/f for r in ('foundation14_control','native_cpu')
             for t in ('0.6','0.6001','0.6002','0.6003','0.6004','0.6005') for f in ('U','p','phi')]
 for p in initial:p.parent.mkdir(parents=True,exist_ok=True);p.write_text('INERT PATH FIXTURE')
 replay.validate_inputs(base,package)
 before={str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file()}
 symlink_available=True;symlink_reason=None
 try:
  (root/'package_link').symlink_to(package,target_is_directory=True)
  (root/'base_link').symlink_to(base,target_is_directory=True)
  (root/'dangling').symlink_to(root/'absent',target_is_directory=True)
  (root/'leaf_link').symlink_to(package/'not_created.json')
 except OSError as exc:symlink_available=False;symlink_reason=str(exc)
 if symlink_available:
  refused('restore-symlink-parent',lambda:restore.disjoint_destination(root/'package_link/new',package,seed),'Link')
  refused('restore-dangling-symlink-parent',lambda:restore.disjoint_destination(root/'dangling/new',package,seed),'Link')
  refused('restore-symlink-leaf',lambda:restore.disjoint_destination(root/'leaf_link',package,seed),'Link')
  refused('restore-linked-source-package',lambda:restore.disjoint_destination(dest,root/'package_link',seed),'Link')
  refused('replay-symlink-output-parent',lambda:replay.validate_paths(base,root/'package_link/new.json',package),'Link')
  refused('replay-symlink-output-leaf',lambda:replay.validate_paths(base,root/'leaf_link',package),'Link')
  refused('replay-dangling-output-parent',lambda:replay.validate_paths(base,root/'dangling/new.json',package),'Link')
  refused('replay-symlink-base-before-resolve',lambda:replay.validate_paths(root/'base_link',outside/'new.json',package),'Link')
  refused('replay-symlink-package-before-resolve',lambda:replay.validate_paths(base,outside/'new.json',root/'package_link'),'Link')
  linked=base/'foundation14_control/0.6001/U';unchanged=linked.read_bytes();linked.unlink();linked.symlink_to(package/'sentinel.txt')
  refused('replay-linked-field-input-before-import',lambda:replay.validate_inputs(base,package),'Link')
  linked.unlink();linked.write_bytes(unchanged)
 junctions=[]
 if os.name=='nt':
  # Creation only, using native PowerShell. No removal/move/recursive cleanup.
  for name,target in [('junction_package',package),('junction_base',base)]:
   link=root/name
   command="New-Item -ItemType Junction -Path '"+str(link).replace("'","''")+"' -Target '"+str(target).replace("'","''")+"' -ErrorAction Stop | Out-Null"
   run=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],capture_output=True,text=True)
   if run.returncode:raise RuntimeError('Windows junction fixture creation failed: '+run.stderr)
   junctions.append({'path':str(link),'lstat_reparse_attribute':bool(link.lstat().st_file_attributes&0x400),
      'is_junction':getattr(link,'is_junction',lambda:None)()})
  refused('restore-real-Windows-junction-parent',lambda:restore.disjoint_destination(root/'junction_package/new',package,seed),'Link')
  refused('restore-real-Windows-junction-source',lambda:restore.disjoint_destination(dest,root/'junction_package',seed),'Link')
  refused('replay-real-Windows-junction-output',lambda:replay.validate_paths(base,root/'junction_package/new.json',package),'Link')
  refused('replay-real-Windows-junction-base',lambda:replay.validate_paths(root/'junction_base',outside/'new.json',package),'Link')
  # Demonstrate lstat-based reparse rejection independently of is_junction.
  original=getattr(Path,'is_junction',None)
  try:
   Path.is_junction=lambda self:False
   refused('restore-Windows-reparse-attribute-fallback',lambda:restore.no_links(root/'junction_package/new'),'Reparse')
   refused('replay-Windows-reparse-attribute-fallback',lambda:replay.no_links(root/'junction_base/new'),'Reparse')
  finally:
   if original is not None:Path.is_junction=original
   else:delattr(Path,'is_junction')
 after={name:sha(root/name) for name in before}
 results.append({'fixture':'inert-source-payloads-unchanged','pass':before==after})
 results.append({'fixture':'no-restored-tree-or-report-created','pass':not dest.exists() and not (outside/'new_report.json').exists()})
 result={'schema':'c29-v2-isolated-path-fixtures-v1','platform':args.platform_label,'python':sys.version,
  'adapter_sha256':{name:sha(V2/'recipes'/name) for name in ('restore_completed_evidence.py','replay_completed_cpu_analysis.py')},
  'fixture_source_sha256':sha(Path(__file__)),
  'fixture_root':str(root),'results':results,'all_pass':all(x['pass'] for x in results),
  'symlink_available':symlink_available,'symlink_unavailable_reason':symlink_reason,'Windows_junctions':junctions,
  'source_helpers_imported_but_no_main_restore_analyze_or_replay_called':True,
  'only_inert_private_fixture_files_created':True,'case_output_Git_ZIP_CFD_build_GPU_writes':False}
 output=WORK/('c29_v2_path_fixtures_'+args.platform_label+'.json');assert not output.exists()
 output.write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({'platform':args.platform_label,'fixtures':len(results),'all_pass':result['all_pass'],
                  'symlink_available':symlink_available,'junctions':len(junctions)},indent=2))
 assert result['all_pass']
if __name__=='__main__':main()
