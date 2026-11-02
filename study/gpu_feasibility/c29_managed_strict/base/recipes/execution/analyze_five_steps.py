"""Mechanical read-only five-step gate; no runner, source/case edits or timings.

--stage f14-to-cpu is evaluated first. cpu-to-gpu/all also require that stage to
pass. Runtime/input/loader/framework receipts remain separate root-owned gates.
Outputs must be outside the cases and never overwrite an existing report.
"""
import argparse
import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path
sys.dont_write_bytecode=True
import numpy as np

WORK=Path(__file__).resolve().parent
BASE=Path('/opt/openfoam-workspace/cases/native_c29_validation_20261102')
THRESHOLDS=WORK.parent/'candidate/validation_thresholds.json'
THRESHOLD_SHA='d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b'
HELPERS={
    'fields':(WORK/'compare_initial_cpu.py','071202fdd5e9fa623f98701054e48ebea39d271be78171ce228a665b9292850c'),
    'axial':(WORK.parent/'geometry_reference/reference_axial_speed.py','c223006e824d1d40cc5dcd5d42e8ebc0e3a9a151d5a25f8a3e40ea93faa9699f'),
}
NUM=r'[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
TIMES=[.6+i*1e-4 for i in range(1,6)]
PREVIOUS=['0.6','0.6001','0.6002','0.6003','0.6004']
SAVED=['0.6001','0.6002','0.6003','0.6004','0.6005']
ROLES={'f14':'foundation14_control','cpu':'native_cpu','gpu':'native_gpu'}
LOGS={'f14':'f14_control_five_stdout.log','cpu':'native_cpu_five_stdout.log','gpu':'native_gpu_five_stdout.log'}
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def require(ok,reason):
    if not ok:raise ValueError(reason)
def load_helper(name):
    p,expected=HELPERS[name];require(sha(p)==expected,'Helper changed: '+str(p))
    spec=importlib.util.spec_from_file_location('c29_readonly_'+name,p)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def near_time(a,b):
    # Exact fixed clock protocol, using approved C29Restrictions::near (not a
    # new CFD tolerance): decimal output and repeated binary increments differ.
    return math.isfinite(a) and abs(a-b)<=64*np.finfo(float).eps*max(1,abs(b))
def step_for(t):
    found=[i+1 for i,x in enumerate(TIMES) if near_time(t,x)]
    require(len(found)==1,'Unexpected/ambiguous source/time sample: '+str(t))
    return found[0]
def numbers(text):return [float(x) for x in re.findall(NUM,text)]
def key_values(text):
    result={}
    for m in re.finditer(r'(\w+)=(\([^)]*\)|\[[^]]*\]|\S+)',text):
        value=m[2]
        if value.startswith(('(','[')):result[m[1]]=numbers(value)
        else:result[m[1]]=float(value)
    return result
def add(checks,name,ok,observed=None,limit=None):
    checks.append({'check':name,'pass':bool(ok),'observed':observed,'limit':limit})
def finite(value):return bool(np.isfinite(np.asarray(value,dtype=float)).all())
def parse_log(path,role):
    result={'role':role,'path':str(path),'missing':not path.is_file(),'errors':[],
        'times':[],'tilt':[],'volumes':[],'courant':[],'residuals':[],
        'continuity':[],'selections':[],'rotor':[],'source':[],'applied':[]}
    if result['missing']:return result
    result['sha256']=sha(path);text=path.read_text();lines=text.splitlines();current=None
    time_lines=[]
    for n,line in enumerate(lines):
        try:
            m=re.match(r'^\s*Time\s*=\s*('+NUM+r')\s*s?\s*$',line)
            if m:
                current=step_for(float(m[1]));time_lines.append((n,current))
                result['times'].append({'step':current,'time':float(m[1]),'line':n+1});continue
            if line.startswith('TILT '):
                v=[float(x) for x in line.split()[1:]];require(len(v)==8,'TILT needs8 numbers')
                result['tilt'].append({'step':step_for(v[0]),'time':v[0],'force':[v[6],v[7],v[1]],
                    'air':v[2],'shaft':v[3],'electrical':v[4],'total_thrust':v[5]});continue
            if line.startswith('DISK_VOLUME '):
                _,r,v=line.split();result['volumes'].append({'rotor':int(r),'volume':float(v)});continue
            m=re.search(r'Courant Number mean:\s*('+NUM+r')\s+max:\s*('+NUM+r')',line)
            if m:result['courant'].append({'line':n+1,'mean':float(m[1]),'max':float(m[2])});continue
            if 'Solving for ' in line:
                m=re.search(r'Solving for\s+(\w+),\s*Initial residual\s*=\s*(\([^)]*\)|'+NUM+r'),\s*Final residual\s*=\s*(\([^)]*\)|'+NUM+r'),\s*No Iterations\s+(\d+)',line)
                require(m is not None,'Unparsed solver residual line')
                result['residuals'].append({'step':current,'field':m[1],
                    'initial':numbers(m[2]),'final':numbers(m[3]),'iterations':int(m[4]),'line':n+1});continue
            if 'continuity errors' in line:
                m=re.search(r'sum local\s*=\s*('+NUM+r'),\s*global\s*=\s*('+NUM+r')(?:,\s*cumulative\s*=\s*('+NUM+r'))?',line)
                require(m is not None,'Unparsed continuity line')
                require('cumulative' not in line or m[3] is not None,
                    'Printed cumulative continuity was not parsed as a finite number')
                entry={'step':current,'local':float(m[1]),'global':float(m[2]),'line':n+1}
                if m[3] is not None:entry['cumulative']=float(m[3])
                result['continuity'].append(entry);continue
            if line.startswith('C29_SOLVER '):
                result['selections'].append({'step':current,'text':line.split(' ',1)[1]});continue
            for tag,key in [('C29_ROTOR_AUDIT ','rotor'),('C29_SOURCE_AUDIT ','source'),('C29_APPLIED_AIR_AUDIT ','applied')]:
                if line.startswith(tag):
                    rest=line[len(tag):];parts=rest.split(None,2)
                    t=float(parts[0]);payload=rest[len(parts[0]):].strip();entry={'step':step_for(t),'time':t}
                    if key=='rotor':
                        r,_,payload=payload.partition(' ');entry['rotor']=int(r)
                    entry.update(key_values(payload));result[key].append(entry);break
        except (ValueError,AssertionError) as e:result['errors'].append({'line':n+1,'reason':str(e),'text':line})
    # F14 reports Co in preSolve BEFORE clock increment; native app reports it
    # after Time=. Both use the same fixed step. Inspect all startup extras too.
    for event in result['courant']:
        n=event['line']-1
        candidates=[s for ln,s in time_lines if (ln>n if role=='f14' else ln<n)]
        event['step']=(candidates[0] if role=='f14' else candidates[-1]) if candidates else None
    result['end']=bool(re.search(r'(?m)^\s*End\s*$',text))
    patterns=r'FOAM FATAL|FOAM exiting|Segmentation fault|Floating point exception|cudaError|thrust::system_error|failed to synchronize|did not converge|not converged|reached.*(?:maxIter|maximum.*iterations)'
    unsupported_trap_banner=r'^\s*sigFpe\s*:\s*Floating point exception trapping\s*-\s*not supported on this platform\s*$'
    enabled_trap_banner=r'^\s*trapFpe:\s*Floating point exception trapping enabled \(FOAM_SIGFPE\)\.\s*$'
    result['fatal_or_solver_warning_lines']=[line for line in lines
        if re.search(patterns,line,re.I)
        and not re.match(unsupported_trap_banner,line,re.I)
        and not re.match(enabled_trap_banner,line)]
    return result
def one(items,step):
    matches=[r for r in items if r.get('step')==step]
    require(len(matches)==1,'Expected one observation at step'+str(step))
    return matches[0]
def source_close(error,reference,absolute,relative):
    return finite([error,reference]) and abs(error)<=absolute+relative*abs(reference)
def check_log(log,role,thresholds):
    checks=[];native=role!='f14';flow=thresholds['solver_and_flow_checks']
    add(checks,'stdout present',not log['missing'])
    if log['missing']:return checks
    add(checks,'parser complete',not log['errors'],log['errors'])
    add(checks,'ordinary End present',log['end'])
    add(checks,'no fatal/solver failure',not log['fatal_or_solver_warning_lines'],log['fatal_or_solver_warning_lines'])
    add(checks,'five consecutive times',[r['step'] for r in log['times']]==list(range(1,6)))
    add(checks,'five source TILT samples',[r['step'] for r in log['tilt']]==list(range(1,6)))
    add(checks,'eight initial cached volumes',sorted(r['rotor'] for r in log['volumes'])==list(range(8)))
    for tag in ('tilt','volumes','courant','residuals','continuity','rotor','source','applied'):
        # Numeric finiteness is checked recursively without treating string labels as data.
        vals=[]
        def visit(x):
            if isinstance(x,(int,float)):vals.append(x)
            elif isinstance(x,list):
                for y in x:visit(y)
            elif isinstance(x,dict):
                for y in x.values():visit(y)
        visit(log[tag]);add(checks,tag+' finite',finite(vals))
    for c in log['courant']:add(checks,'Courant line'+str(c['line']),0<=c['max']<=flow['maximum_Courant'],c['max'],flow['maximum_Courant'])
    for step in range(1,6):
        add(checks,'Co coverage step'+str(step),any(c['step']==step for c in log['courant']))
        rs=[r for r in log['residuals'] if r['step']==step]
        add(checks,'only velocity/pressure solves step'+str(step),all(r['field'] in ('U','Ux','Uy','Uz','p') for r in rs))
        ps=[r for r in rs if r['field']=='p'];us=[r for r in rs if r['field'] in ('U','Ux','Uy','Uz')]
        components=[]
        for r in us:
            if r['field']=='U' and len(r['initial'])==len(r['final'])==3:
                components+=list(zip(('Ux','Uy','Uz'),r['initial'],r['final']))
            elif r['field'] in ('Ux','Uy','Uz') and len(r['initial'])==len(r['final'])==1:
                components.append((r['field'],r['initial'][0],r['final'][0]))
        add(checks,'three U components step'+str(step),sorted(c[0] for c in components)==['Ux','Uy','Uz'])
        add(checks,'two pressure solves step'+str(step),len(ps)==2)
        for field,initial,final in components:
            limit=1e-7+1e-12
            add(checks,f'{field} final residual step{step}',initial>=0 and 0<=final<=limit,final,limit)
        for k,r in enumerate(ps):
            valid=len(r['initial'])==len(r['final'])==1
            limit=max(1e-7,(.05 if k==0 else 0)*r['initial'][0])+1e-12 if valid else 0
            add(checks,f'p corrector{k+1} residual step{step}',valid and r['initial'][0]>=0 and 0<=r['final'][0]<=limit,r['final'],limit)
        cs=[c for c in log['continuity'] if c['step']==step]
        add(checks,'two continuity correctors step'+str(step),len(cs)==2)
        for k,c in enumerate(cs):
            for key,limit in [('local',flow['each_corrector_local_continuity_max']),('global',flow['each_corrector_abs_global_continuity_max'])]:
                add(checks,f'{key} continuity step{step} corr{k+1}',abs(c[key])<=limit,c[key],limit)
            if k==1:add(checks,'actual final cumulative step'+str(step),'cumulative' in c)
            if 'cumulative' in c:
                limit=flow['abs_cumulative_continuity_max']
                add(checks,f'cumulative continuity step{step} corr{k+1}',abs(c['cumulative'])<=limit,c['cumulative'],limit)
        if native:
            expected=['momentum=UFinal','pressure=p','pressure=pFinal']
            add(checks,'explicit alias order step'+str(step),[r['text'] for r in log['selections'] if r['step']==step]==expected)
    if native:
        s=thresholds['source_identity_tolerances'];indices=[]
        add(checks,'five source audits',len(log['source'])==5)
        add(checks,'five applied-air audits',len(log['applied'])==5)
        add(checks,'forty rotor observations',len(log['rotor'])==40)
        for step in range(1,6):
            try:
                a=one(log['source'],step);b=one(log['applied'],step);t=one(log['tilt'],step)
                indices.append(int(a['index']))
                add(checks,'integer time index step'+str(step),a['index']==int(a['index']))
                add(checks,'source dimensions step'+str(step),a['dimensions']==[0,4,-2,0,0,0,0])
                add(checks,'zero matrix accounting step'+str(step),a['implicitBefore']==a['sourceBefore']==a['implicitAfter']==0)
                add(checks,'call ordinal step'+str(step),a['call']==step)
                force=np.asarray(a['craftForce']);size=float(np.linalg.norm(force))
                for label,error in [('positive force',np.linalg.norm(np.asarray(a['integralPositiveForce'])-force)),('logged positive force error',a['forceError']),('TILT force identity',np.linalg.norm(np.asarray(t['force'])-force)),('negative applied force',np.linalg.norm(np.asarray(b['force'])+force)),('logged applied force error',b['forceError'])]:
                    add(checks,label+' step'+str(step),source_close(error,size,s['force_abs_N'],s['force_rel']),float(error))
                for label,error in [('positive work',a['positiveSourceWork']+a['airPower']),('logged positive work error',a['workError']),('TILT power identity',t['air']-a['airPower']),('applied work',b['work']-a['airPower']),('logged applied work error',b['workError'])]:
                    add(checks,label+' step'+str(step),source_close(error,a['airPower'],s['work_abs_W'],s['work_rel']),error)
                rotors=[r for r in log['rotor'] if r['step']==step]
                add(checks,'eight rotor IDs step'+str(step),sorted(r['rotor'] for r in rotors)==list(range(8)))
                for r in rotors:add(checks,f'rotor{r["rotor"]} update/index/dt step{step}',r['index']==a['index'] and r['controllerUpdateObserved']==1 and near_time(r['dt'],1e-4))
            except (ValueError,KeyError) as e:add(checks,'native source observations step'+str(step),False,str(e))
        add(checks,'consecutive source indices',len(indices)==5 and indices==list(range(indices[0],indices[0]+5)),indices)
    return checks
def field_metrics(reference,candidate,floor):
    count=max(len(reference),len(candidate));components=reference.shape[1]
    require(components==candidate.shape[1] and len(reference) in (1,count) and len(candidate) in (1,count),'Field shape/broadcast mismatch')
    a=np.broadcast_to(reference,(count,components));b=np.broadcast_to(candidate,(count,components))
    require(finite(a) and finite(b),'Nonfinite field block')
    error=np.sqrt(np.sum((b-a)**2,axis=1));size=np.sqrt(np.sum(a*a,axis=1))
    rms=float(np.sqrt(np.mean(error*error)));ref_rms=float(np.sqrt(np.mean(size*size)))
    maximum=float(np.max(error));ref_max=float(np.max(size))
    result={'values_after_uniform_broadcast':count,'components':components,
        'absolute_RMS':rms,'reference_RMS':ref_rms,'absolute_max':maximum,'reference_max':ref_max,
        'normalization_floor':floor,'normalized_RMS':rms/max(ref_rms,floor),
        'normalized_max':maximum/max(ref_max,floor),'exact':bool(np.array_equal(a,b))}
    require(finite([v for v in result.values() if isinstance(v,(int,float))]),'Nonfinite field norm')
    return result
def compare_fields(left,right,criterion,thresholds,reader):
    out=[];checks=[];floors=thresholds['normalization_floors']
    for time in SAVED:
        for field,key in [('U','U_m_per_s'),('p','p_m2_per_s2'),('phi','phi_m3_per_s')]:
            a=left/time/field;b=right/time/field
            row={'time':time,'field':field,'reference':str(a),'candidate':str(b),'blocks':[]}
            try:
                require(a.is_file() and b.is_file(),'Missing saved field')
                aa=reader.field_values(a);bb=reader.field_values(b)
                require(len(aa)==len(bb),'Different internal/boundary block inventory')
                row.update(reference_sha256=sha(a),candidate_sha256=sha(b))
                for i,((ak,av),(bk,bv)) in enumerate(zip(aa,bb)):
                    require(ak==bk,'Different field block order/key')
                    metric=field_metrics(av,bv,floors[key]);metric.update(index=i,key=ak)
                    row['blocks'].append(metric)
                    for kind in ('RMS','max'):
                        limit=criterion[field+'_normalized_'+kind]
                        add(checks,f'{field} {time} block{i} {kind}',metric['normalized_'+kind]<=limit,metric['normalized_'+kind],limit)
            except (OSError,ValueError,AssertionError) as e:
                row['error']=str(e);add(checks,field+' '+time+' complete fields',False,str(e))
            out.append(row)
    return out,checks
def compare_samples(left,right,criterion,thresholds,reference_rotors):
    checks=[];rows=[];floors=thresholds['normalization_floors']
    for step in range(1,6):
        row={'step':step,'source_time':TIMES[step-1]}
        try:
            a=one(left['tilt'],step);b=one(right['tilt'],step)
            relative=float(np.linalg.norm(np.asarray(b['force'])-a['force']))/max(float(np.linalg.norm(a['force'])),floors['force_N'])
            row['craft_force_relative_difference']=relative
            add(checks,'force sample'+str(step),relative<=criterion['each_sample_craft_force_norm_rel'],relative,criterion['each_sample_craft_force_norm_rel'])
            for key in ('air','shaft','electrical'):
                relative=abs(b[key]-a[key])/max(abs(a[key]),floors['power_W'])
                row[key+'_power_relative_difference']=relative
                add(checks,key+' power sample'+str(step),relative<=criterion['each_sample_air_shaft_electrical_power_rel'],relative,criterion['each_sample_air_shaft_electrical_power_rel'])
            refs=reference_rotors[step] if reference_rotors else [r for r in left['rotor'] if r['step']==step]
            candidates=[r for r in right['rotor'] if r['step']==step]
            require(sorted(r['rotor'] for r in refs)==sorted(r['rotor'] for r in candidates)==list(range(8)),'Missing/duplicate rotor observations')
            row['rotors']=[]
            for r in range(8):
                rr=next(x for x in refs if x['rotor']==r);cc=next(x for x in candidates if x['rotor']==r)
                rv=rr['cached_volume_m3'] if reference_rotors else rr['volume']
                rw=rr['mean_axial_speed_m_per_s'] if reference_rotors else rr['w']
                dv=abs(cc['volume']-rv)/abs(rv);dw=abs(cc['w']-rw)/max(abs(rw),floors['axial_speed_m_per_s'])
                row['rotors'].append({'rotor':r,'volume_relative_difference':dv,'axial_speed_relative_difference':dw,'reference_volume':rv,'reference_w':rw,'candidate_volume':cc['volume'],'candidate_w':cc['w']})
                add(checks,f'rotor{r} volume sample{step}',dv<=criterion['per_rotor_volume_rel'],dv,criterion['per_rotor_volume_rel'])
                add(checks,f'rotor{r} axial sample{step}',dw<=criterion['per_rotor_mean_axial_speed_rel'],dw,criterion['per_rotor_mean_axial_speed_rel'])
        except (ValueError,KeyError) as e:row['error']=str(e);add(checks,'source sample'+str(step)+' complete',False,str(e))
        rows.append(row)
    return rows,checks
def clean(value):
    if isinstance(value,float) and not math.isfinite(value):return 'NONFINITE:'+str(value)
    if isinstance(value,dict):return {k:clean(v) for k,v in value.items()}
    if isinstance(value,list):return [clean(v) for v in value]
    return value
def analyze(base,logdir,stage):
    require(sha(THRESHOLDS)==THRESHOLD_SHA,'Approved thresholds changed')
    thresholds=json.loads(THRESHOLDS.read_text());reader=load_helper('fields');axial=load_helper('axial')
    roles=('f14','cpu','gpu') if stage!='f14-to-cpu' else ('f14','cpu')
    logs={role:parse_log(logdir/LOGS[role],role) for role in roles}
    log_checks={role:check_log(log,role,thresholds) for role,log in logs.items()}
    for role,checks in log_checks.items():
        for check in checks:check['role']=role
    references={};reference_records=[];reference_checks=[]
    for step,time in enumerate(PREVIOUS,1):
        path=base/'foundation14_control'/time/'U'
        try:
            measured=axial.measure(path);references[step]=measured['rotors']
            measured.update(source_time_s=TIMES[step-1],pre_predictor_time_s=float(time))
            reference_records.append(measured)
        except (OSError,ValueError,AssertionError) as e:add(reference_checks,'F14 rotor reference step'+str(step),False,str(e))
    if references and logs['f14']['volumes']:
        for original in logs['f14']['volumes']:
            if 1 not in references:break
            r=original['rotor'];matches=[x for x in references[1] if x['rotor']==r]
            if not matches:continue
            expected=matches[0]['cached_volume_m3'];s=thresholds['source_identity_tolerances']
            add(reference_checks,'F14 original/cache volume'+str(r),source_close(original['volume']-expected,expected,s['cached_volume_abs_m3'],s['cached_volume_rel']),original['volume']-expected)
    report={'schema':'c29-mechanical-five-step-analysis-v3','requested_stage':stage,
        'thresholds':{'path':str(THRESHOLDS),'sha256':THRESHOLD_SHA},
        'helper_hashes':{k:{'path':str(p),'sha256':h} for k,(p,h) in HELPERS.items()},
        'logs':logs,'log_checks':log_checks,'F14_per_rotor_references':reference_records,
        'F14_reference_checks':reference_checks,'comparisons':{},
        'scope':'Read-only mechanical observations. Terminal exit/input/loader receipts, framework qualification and root protocol approval are separate mandatory gates; this script does not adopt a backend.',
        'field_policy':'Every saved step; internal and each boundary value block separately, with uniform broadcasting. All blocks pass; no sample averaging, pressure-mean subtraction or volume weighting.',
        'F14_solver_alias_limit':'Original stdout does not print UFinal/pFinal aliases. Residual/order checks use the reviewed unchanged one-outer PIMPLE protocol; exact alias/input/loader identity still requires root source/protocol receipts.',
        'cache_meaning':'Frozen F14 repeated cache accounting; no geometry/controller/source reconstruction or independent geometry validation',
        'overall_acceptance_decided_here':False}
    pairs=[('f14-to-cpu','f14','cpu','cross_branch_Foundation14_to_native_CPU',references)]
    if stage!='f14-to-cpu':pairs.append(('cpu-to-gpu','cpu','gpu','same_native_application_CPU_to_GPU',None))
    first_pass=False
    for label,left,right,key,refs in pairs:
        if label=='cpu-to-gpu' and not first_pass:
            report['comparisons'][label]={'status':'BLOCKED: F14-to-nativeCPU mechanical gate not passed','mechanical_passed':False};continue
        criterion=thresholds[key]
        fields,fc=compare_fields(base/ROLES[left],base/ROLES[right],criterion,thresholds,reader)
        samples,sc=compare_samples(logs[left],logs[right],criterion,thresholds,refs)
        checks=log_checks[left]+log_checks[right]+fc+sc+(reference_checks if left=='f14' else [])
        if left=='f14':add(checks,'all five F14 per-rotor references',set(references)==set(range(1,6)))
        passed=bool(checks) and all(c['pass'] for c in checks)
        report['comparisons'][label]={'status':'MECHANICAL PASS; external gates still required' if passed else 'MECHANICAL FAIL OR INCOMPLETE',
            'mechanical_passed':passed,'criterion_key':key,'field_comparisons':fields,'source_samples':samples,
            'checks':checks,'failed_checks':[c for c in checks if not c['pass']]}
        if label=='f14-to-cpu':first_pass=passed
    return clean(report)
def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--base',type=Path,default=BASE);ap.add_argument('--log-dir',type=Path,default=WORK)
    ap.add_argument('--stage',choices=('f14-to-cpu','cpu-to-gpu','all'),default='f14-to-cpu')
    ap.add_argument('--out',type=Path,required=True)
    args=ap.parse_args();dest=args.out.resolve();base=args.base.resolve()
    require(not dest.is_relative_to(base),'Output must be outside read-only cases')
    require(not dest.exists() and dest.parent.is_dir(),'Use a NEW report in an existing directory')
    report=analyze(base,args.log_dir,args.stage)
    with dest.open('x',encoding='utf-8') as stream:json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'report':str(dest),'report_sha256':sha(dest),'mechanical_results':{k:v['status'] for k,v in report['comparisons'].items()},'overall_acceptance_decided_here':False},indent=2))
if __name__=='__main__':main()
