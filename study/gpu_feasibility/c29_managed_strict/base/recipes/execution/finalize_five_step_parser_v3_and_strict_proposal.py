"""Read-only report comparison + source-only proposal hashes; no case writes."""
from pathlib import Path
import ast,datetime,hashlib,json,math,sys
W=Path(__file__).resolve().parent;P=W/'strict_pressure_proposal';C=W.parent/'candidate'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def nodes(path):return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
assert sha(W/'analyze_five_steps.py')=='74df3cf053b8596ae57d5a04792867130392ca5ef31b59de526b0d1810d4ee16'
assert sha(W/'analyze_five_steps_v2_1310a87.py')=='1310a87b6997b6babf3cf4859fc80a8d27564c8a195b7449cf6fad7ef4cc1e53'
assert sha(C/'candidate_manifest.json')=='562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7'
assert sha(C/'validation_thresholds.json')=='d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b'
oldpath=W/'f14_to_native_cpu_validation_v2.json';newpath=W/'f14_to_native_cpu_validation_v3.json'
assert sha(oldpath)=='5d50d0314f9dd6ce332d40aa436fc42532f08a70d791b2719a04498746543be1'
assert sha(newpath)=='9ac760b08a489047db94a3b98ff9733f1569f86f9efaa250999a45f7b3ca61e3'
a,b=json.loads(oldpath.read_text()),json.loads(newpath.read_text())
x,y=a['comparisons']['f14-to-cpu'],b['comparisons']['f14-to-cpu']
roundoff=[];environment_differences=[]
def same_data(left,right,path):
    if isinstance(left,dict):
        assert isinstance(right,dict) and set(left)==set(right),path
        for key in left:same_data(left[key],right[key],path+'/'+key)
    elif isinstance(left,list):
        assert isinstance(right,list) and len(left)==len(right),path
        for i,(aa,bb) in enumerate(zip(left,right)):same_data(aa,bb,path+'/'+str(i))
    elif left!=right:
        if path.endswith('/numpy_version'):
            environment_differences.append({'path':path,'old':left,'new':right});return
        assert isinstance(left,float) and isinstance(right,float),path
        relative=abs(left-right)/max(abs(left),abs(right),sys.float_info.min)
        # Report-reduction reproducibility diagnostic ONLY, not CFD acceptance.
        assert math.isfinite(relative) and relative<=64*sys.float_info.epsilon,(path,left,right)
        roundoff.append({'path':path,'old':left,'new':right,'relative_difference':relative})
for key in ('field_comparisons','source_samples'):same_data(x[key],y[key],key)
for key in ('F14_per_rotor_references','F14_reference_checks','thresholds','helper_hashes'):same_data(a[key],b[key],key)
old_checks=[(z['check'],z['pass']) for z in x['checks'] if z['check']!='no fatal/solver failure']
new_checks=[(z['check'],z['pass']) for z in y['checks'] if z['check']!='no fatal/solver failure']
assert old_checks==new_checks
failures=y['failed_checks'];assert len(failures)==4
assert all(z['check'] in ('global continuity step1 corr1','global continuity step2 corr1') and z['limit']==1e-7 for z in failures)
assert {z['role'] for z in failures}=={'f14','cpu'}
report={'kind':'Parser-only v3 reanalysis of existing failed five-step experiment',
 'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'analyzer_sha256':sha(W/'analyze_five_steps.py'),'preserved_v2_report_sha256':sha(oldpath),
 'new_v3_report_sha256':sha(newpath),'field_and_reference_file_hashes_identical':True,
 'numerical_classifications_identical_except_benign_banner':True,
 'reduction_last_bit_differences':roundoff,
 'analysis_environment_differences':environment_differences,
 'roundoff_audit_meaning':'Repeated reduction summaries differ only at last bits; this diagnostic does not change any solver/source/field acceptance criterion.',
 'remaining_real_failures':failures,'all_other_checks_passed':True,
 'numerical_acceptance_limits_changed':False,'CFD_or_case_changes':False,
 'interpretation':'MECHANICAL FAIL remains. Only benign trapFpe false-positive removed; no continuity failures waived.'}
with (W/'five_step_parser_v3_reanalysis_record.json').open('x') as stream:json.dump(report,stream,indent=2);stream.write('\n')
baseline=nodes(W/'analyze_five_steps.py');candidate=nodes(P/'analyze_five_steps_strict_candidate.py')
same=('field_metrics','compare_fields','compare_samples','source_close','near_time','parse_log')
assert all(baseline[k]==candidate[k] for k in same)
for path in P.glob('*.py'):ast.parse(path.read_text())
protocol=json.loads((P/'strict_pressure_protocol.json').read_text())
assert protocol['validation_thresholds_sha256']==sha(C/'validation_thresholds.json')
manifest={'schema':'c29-strict-pressure-source-proposal-manifest-v1',
 'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'status':'SOURCE ONLY; root review and separate authorization required before build/case/runtime',
 'base_analyzer_sha256':sha(W/'analyze_five_steps.py'),
 'base_candidate_manifest_sha256':sha(C/'candidate_manifest.json'),
 'validation_thresholds_sha256':sha(C/'validation_thresholds.json'),
 'unchanged_analyzer_functions_AST':list(same),
 'numerical_policy_delta':'Only configured first p relTol0 instead of .05, as new prospective solve protocol. All acceptance limits/metrics unchanged.',
 'no_build_case_preparation_initialization_solver_or_receipt_issuance':True,
 'verbatim_C29_fragments_unchanged':{
 'body_sha256':sha(C/'C29_body_verbatim.inc'),'includes_sha256':sha(C/'C29_includes_verbatim.inc')},
 'files':{str(p.relative_to(P)):{'sha256':sha(p),'size_bytes':p.stat().st_size} for p in sorted(P.rglob('*')) if p.is_file()}}
with (P/'source_proposal_manifest.json').open('x') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
print(json.dumps({'v3_report':sha(newpath),'real_failures':failures,
 'strict_source_manifest_sha256':sha(P/'source_proposal_manifest.json'),
 'strict_protocol_sha256':sha(P/'strict_pressure_protocol.json'),
 'strict_analyzer_candidate_sha256':sha(P/'analyze_five_steps_strict_candidate.py'),
 'strict_admission_helper_sha256':sha(P/'strict_pressure_admission.py')},indent=2))
