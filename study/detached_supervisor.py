"""Task-scoped, rank-aware OpenFOAM queue; no service or external notifications.

Launch through the supplied Allrun wrapper as the openfoam account. The explicit
JSON plan is the authorization boundary. It may be extended by root through a
new revision, never by discovering arbitrary case directories.
"""
from pathlib import Path
import argparse,atexit,fcntl,hashlib,json,math,os,re,signal,subprocess,sys,time,uuid
from dataclasses import asdict
import numpy as np
from openfoam_mcp.foam import FoamEnv
from openfoam_mcp.jobs import JobManager

SOURCE_SHA='29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
ROOT=Path('/opt/openfoam-workspace/cases/tello_refinement')
STATE=Path('/opt/openfoam-workspace/cases/.openfoam-mcp')
OUT=Path(__file__).resolve().parent
JOURNAL=ROOT.parent/'tello_execution_supervisor'/'journal'
sys.path.insert(0,str(OUT))
from suspension_safety import Safety,open_interval
INPUTS=['geometry.json','Allrun','0/U','0/p','constant/fvModels','constant/rotorParameters',
    'constant/physicalProperties','constant/momentumTransport','system/blockMeshDict',
    'system/controlDict','system/fvSchemes','system/fvSolution','system/decomposeParDict',
    'initialization.json','prepare_mapped.py','0.6/U','0.6/p']

def utc(t=None):return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime(time.time() if t is None else t))
def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
def atomic(p,data):
    text=json.dumps(data,indent=2)+'\n'
    if p.parent==OUT:
        # Windows readers can temporarily deny replacement. Linux is the
        # authoritative runtime journal; publishing a mirror must not halt CFD.
        JOURNAL.mkdir(parents=True,exist_ok=True)
        atomic(JOURNAL/p.name,data)
    tmp=p.with_name(p.name+f'.{os.getpid()}.tmp');tmp.write_text(text)
    for delay in [0,.05,.2,.5]:
        if delay:time.sleep(delay)
        try:os.replace(tmp,p);return True
        except PermissionError:
            if p.parent!=OUT:raise
    try:tmp.unlink()
    except OSError:pass
    event('mirror_publication_deferred',path=str(p),authoritative=str(JOURNAL/p.name))
    return False

class TaskJobManager(JobManager):
    def _save(self,job):
        # A unique temp name avoids collisions with another read-only MCP
        # client's refresh of the same shared job record.
        atomic(self._path(job.id),asdict(job))
def event(kind,**kwargs):print(json.dumps(dict(utc=utc(),event=kind,**kwargs)),flush=True)
def casepath(name):
    assert re.fullmatch(r'[A-Za-z0-9_.-]+',name),name
    c=ROOT/name;assert c.resolve().parent==ROOT.resolve(),name
    return c
def inputs(c):return {f:digest(c/f) for f in INPUTS if (c/f).is_file()}
def geometry(e):
    c=casepath(e['case']);g=json.loads((c/'geometry.json').read_text())
    assert g['rotors'] in [4,8] and math.isclose(g['diameter_m'],.0762,abs_tol=1e-12)
    assert math.isclose(g['battery_power_W'],19.29230769230769,abs_tol=1e-10)
    assert digest(c/'constant/fvModels')==SOURCE_SHA,e['case']+' source changed'
    assert int(g['execution']['mpi_ranks'])==e['mpi_ranks'] and e['mpi_ranks'] in [1,2]
    return c,g
def ready(e):
    if not e.get('readiness_journal'):return True
    p=Path(e['readiness_journal'])
    if not p.exists():return False
    try:items=json.loads(p.read_text())['cases']
    except (ValueError,KeyError):return False
    return any(x.get('case')==e['case'] and x.get('state')=='ready' for x in items)
def tail_progress(c):
    p=c/'log.foamRun'
    if not p.exists():return {}
    with p.open('rb') as f:f.seek(max(0,p.stat().st_size-32768));s=f.read().decode(errors='replace')
    rows=re.findall(r'^TILT\s+([\deE.+-]+)\s',s,re.M)
    clock=re.findall(r'ExecutionTime = ([\deE.+-]+) s\s+ClockTime = ([\deE.+-]+) s',s)
    return dict(physical_time_s=float(rows[-1]) if rows else None,
        solver_cpu_s=float(clock[-1][0]) if clock else None,solver_clock_s=float(clock[-1][1]) if clock else None)
def field_check(p,kind,n):
    s=p.read_text();m=re.search(r'internalField\s+nonuniform\s+List<'+kind+r'>\s+(\d+)\s*\((.*?)\)\s*;',s,re.S)
    assert m and int(m[1])==n,str(p)+' count'
    a=np.fromstring(m[2].replace('(',' ').replace(')',' '),sep=' ')
    assert a.size==n*(3 if kind=='vector' else 1) and np.isfinite(a).all(),str(p)+' values'
def validate(e):
    c,g=geometry(e);s=(c/'log.foamRun').read_text()
    for relative,expected_hash in e.get('input_hashes',{}).items():
        assert digest(c/relative)==expected_hash,e['case']+' input changed: '+relative
    assert re.search(r'^End\s*$',s,re.M) and not re.search(r'FOAM FATAL|MPI_ABORT',s),e['case']+' solver End/fatal'
    rows=[list(map(float,x.split()[1:])) for x in s.splitlines() if x.startswith('TILT ')]
    assert rows and all(len(r)==8 and all(map(math.isfinite,r)) for r in rows)
    assert len(rows)==len(set(r[0] for r in rows)) and rows[-1][0]>=g['averaging_stop_s']-1e-7
    assert 'Mesh OK.' in (c/'log.checkMesh').read_text()
    if e['mpi_ranks']>1:assert re.search(r'^End\s*$',(c/'log.reconstructPar').read_text(),re.M)
    targets=[]
    for d in c.iterdir():
        if d.is_dir():
            try:
                if abs(float(d.name)-g['averaging_stop_s'])<1e-7:targets.append(d)
            except ValueError:pass
    assert len(targets)==1,e['case']+' terminal saved time'
    field_check(targets[0]/'U','vector',g['mesh_cells']);field_check(targets[0]/'p','scalar',g['mesh_cells'])
    volumes=[float(v) for v in re.findall(r'^DISK_VOLUME\s+\d+\s+([\deE.+-]+)',s,re.M)]
    expected=math.pi*g['radius_m']**2*g['thickness_m']
    assert len(volumes)==g['rotors'] and max(abs(v/expected-1) for v in volumes)<.005
    return dict(final_time_s=rows[-1][0],terminal_time_directory=targets[0].name,
        actuator_volume_max_error_percent=100*max(abs(v/expected-1) for v in volumes))
def load_plan(path):
    plan=json.loads(path.read_text());entries=plan['cases']
    assert len(entries)==plan['authorized_case_count'] and len({e['case'] for e in entries})==len(entries)
    assert plan['source_sha256']==SOURCE_SHA and 0<plan['max_solver_ranks']<=16 and 0<plan['max_jobs']<=16
    for e in entries:casepath(e['case']);assert e['mpi_ranks'] in [1,2]
    override=plan.get('pilot_phase_override',{})
    if override:
        assert 0<override['max_solver_ranks']<=18 and 0<override['max_jobs']<=18
        assert set(override['phases'])<=set(['layout_flat_pilots','rotor_count_control'])
        assert 1<=len(override['cases'])<=3 and set(override['cases'])<=set(e['case'] for e in entries)
        for e in entries:
            if e['case'] in override['cases']:
                assert e['mpi_ranks']==1 and e['level']=='coarse' and e['tilt_deg']==0
    for e in entries:assert set(e.get('prerequisites',[]))<=set(x['case'] for x in entries)
    return plan,{e['case']:e for e in entries}
def eligible_case(name,entry,records,control):
    if control.get('stop_launching',False):return False
    allowed=control.get('allowed_cases')
    if allowed is not None and name not in allowed:return False
    return all(records.get(n,{}).get('state')=='succeeded' for n in entry.get('prerequisites',[]))
def dispatch_policy(plan,entries,records,control):
    allowed=control.get('allowed_cases')
    if allowed is not None:
        assert isinstance(allowed,list) and len(allowed)==len(set(allowed)) and set(allowed)<=set(entries)
    policy=dict(max_solver_ranks=plan['max_solver_ranks'],max_jobs=plan['max_jobs'],pilot_override_active=False)
    override=plan.get('pilot_phase_override',{})
    if (override and not control.get('stop_launching',False) and allowed
        and control.get('phase') in override['phases'] and set(allowed)<=set(override['cases'])
        and any(records.get(n,{}).get('state')!='succeeded' for n in allowed)):
        policy.update(max_solver_ranks=override['max_solver_ranks'],max_jobs=override['max_jobs'],pilot_override_active=True)
    return policy
def saved_jobs_for_case(jm,name):
    found=[]
    for p in jm.dir.glob('*.json'):
        try:d=json.loads(p.read_text())
        except (ValueError,OSError):continue
        if d.get('case')=='tello_refinement/'+name and d.get('app')=='Allrun':found.append(d['id'])
    return found
def pause_details(ledger,name):
    row=ledger.get('cases',{}).get(name,{})
    intervals=row.get('intervals',[]);now=time.time()
    seconds=sum(max(0.,(i.get('resumed_epoch') or now)-i.get('confirmed_epoch',i['requested_epoch'])) for i in intervals)
    return dict(scheduler_state='suspended' if open_interval(row) else 'running',scheduler_paused_seconds=seconds,
        scheduler_pause_intervals=intervals)
def apply_scheduling(safety,plan,entries,records,failed):
    path=OUT/'scheduling_control.json'
    schedule=json.loads(path.read_text()) if path.exists() else {}
    targets=schedule.get('suspend_targets',[])
    assert len({t['case'] for t in targets})==len(targets)
    for target in targets:
        assert target['case'] in entries and entries[target['case']]['mpi_ranks']==1
        assert records.get(target['case'],{}).get('job_id')==target['job_id']
    milestones=schedule.get('resume_after_succeeded',[])
    assert set(milestones)<=set(entries)
    reached=bool(milestones) and all(records.get(n,{}).get('state')=='succeeded' for n in milestones)
    held=set(schedule.get('keep_suspended_after_milestones',[]));assert held<=set(t['case'] for t in targets)
    desired_names=(held if reached else set(t['case'] for t in targets)) if schedule.get('mode')=='pause_during_pilots' and not failed else set()
    if reached and schedule.get('mode')=='pause_during_pilots' and not failed:
        for rule in schedule.get('conditional_resume_rules',[]):
            name=rule['case'];required=rule['after_cases_started']
            assert name in {t['case'] for t in targets} and set(required)<=set(entries)
            launched=all(records.get(n,{}).get('state') in ['running','succeeded'] for n in required)
            if launched:desired_names.discard(name)
            else:desired_names.add(name)
    if desired_names:
        for target in targets:
            if target['case'] in desired_names and records[target['case']]['state']=='running':safety.pause(target,schedule['reason'])
    ledger=safety.snapshot()
    stopped={n for n,row in ledger['cases'].items() if open_interval(row)}
    pending=[n for n in stopped if n not in desired_names and open_interval(ledger['cases'][n])['owner_id']==safety.owner]
    used=sum(entries[n]['mpi_ranks'] for n,r in records.items() if r['state']=='running' and n not in stopped)
    reserve=int(schedule.get('reserve_solver_ranks_after_milestones',0)) if reached and not failed else 0
    assert 0<=reserve<plan['max_solver_ranks']
    for name in pending:
        if used+entries[name]['mpi_ranks']<=plan['max_solver_ranks']-reserve:
            resumed=safety.resume([name],'Supervisor error fail-safe' if failed else 'Staged pilots complete; resume released group within reserved rank budget')
            if resumed:used+=entries[name]['mpi_ranks']

def main():
    a=argparse.ArgumentParser();a.add_argument('--plan',type=Path,required=True);a.add_argument('--check',action='store_true');args=a.parse_args()
    assert os.getuid()!=0,'Use the non-root openfoam account'
    plan,entries=load_plan(args.plan)
    source_manifest=JOURNAL/'run_manifest.json'
    if not source_manifest.exists():source_manifest=OUT/'run_manifest.json'
    manifest=json.loads(source_manifest.read_text())
    records={r['case']:r for r in manifest['cases']}
    assert set(records)<=set(entries)
    if args.check:
        for e in entries.values():
            if ready(e):geometry(e)
        event('preflight_passed',authorized=len(entries),recorded=len(records),
            active=sum(r['state']=='running' for r in records.values()),
            reserved_ranks=sum(entries[n]['mpi_ranks'] for n,r in records.items() if r['state']=='running'))
        return 0
    lock=(ROOT.parent/'tello_execution_supervisor'/'supervisor.lock').open('a+')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    lock.seek(0);lock.truncate();lock.write(str(os.getpid()));lock.flush()
    jm=TaskJobManager(STATE);foam=FoamEnv.detect(bashrc='/opt/openfoam14/etc/bashrc')
    run_id=uuid.uuid4().hex;paused=False;errors=[];control={}
    safety=Safety(run_id);atexit.register(safety.close)
    def shutdown(signum,frame):raise SystemExit('Supervisor signal '+str(signum))
    signal.signal(signal.SIGTERM,shutdown);signal.signal(signal.SIGINT,shutdown)
    event('supervisor_started',pid=os.getpid(),run_id=run_id,plan=str(args.plan),authorized=len(entries))
    previous_revision=plan['revision']
    def save():
        queued=[n for n,e in entries.items() if n not in records and ready(e)]
        preferred=control.get('priority_cases',[])
        assert len(preferred)==len(set(preferred)) and set(preferred)<=set(entries)
        order={n:i for i,n in enumerate(preferred)}
        queued.sort(key=lambda n:(0,order[n]) if n in order else (1,entries[n]['priority']))
        pending=[n for n,e in entries.items() if n not in records and not ready(e)]
        live=[(n,r) for n,r in records.items() if r['state']=='running']
        ledger=safety.snapshot()
        for n,r in live:r.update(pause_details(ledger,n))
        cpu_live=[(n,r) for n,r in live if r.get('scheduler_state')!='suspended']
        stopped=[(n,r) for n,r in live if r.get('scheduler_state')=='suspended']
        policy=dispatch_policy(plan,entries,records,control)
        eligible=[n for n in queued if eligible_case(n,entries[n],records,control)]
        deferred=[n for n in queued if n not in eligible]
        state=dict(total_planned=len(entries),max_solver_ranks=policy['max_solver_ranks'],max_concurrent_cases=policy['max_jobs'],
            base_max_solver_ranks=plan['max_solver_ranks'],phase=control.get('phase'),dispatch_hold=control.get('stop_launching',False),
            concurrency_scope='CPU-active jobs; suspended memory holders are tracked separately',
            suspended_cases=[n for n,r in stopped],cpu_active_cases=[n for n,r in cpu_live],
            eligible_queue=eligible,deferred_queue=deferred,pilot_override_active=policy['pilot_override_active'],
            executor='task_scoped_detached_supervisor',supervisor_run_id=run_id,supervisor_pid=os.getpid(),
            supervisor_plan_revision=plan['revision'],authoritative_journal=str(JOURNAL),pending_preparation_count=len(pending),
            pending_preparation=pending,cases=list(records.values()),queued=queued)
        atomic(OUT/'run_manifest.json',state)
        summary=dict(sampled_utc=utc(),pid=os.getpid(),run_id=run_id,authorized=len(entries),
            complete=sum(r['state']=='succeeded' for r in records.values()),active=len(live),
            active_solver_ranks=sum(entries[n]['mpi_ranks'] for n,r in cpu_live),queued=len(queued),
            live_solver_ranks=sum(entries[n]['mpi_ranks'] for n,r in live),cpu_active_cases=len(cpu_live),
            suspended_cases=len(stopped),suspended_solver_ranks=sum(entries[n]['mpi_ranks'] for n,r in stopped),
            awaiting_preparation=len(pending),paused=paused,errors=errors,authoritative_journal=str(JOURNAL),
            phase=control.get('phase'),dispatch_hold=control.get('stop_launching',False),eligible_queued=len(eligible),
            deferred_queued=len(deferred),**policy,
            progress=[dict(case=n,scheduler_state=r.get('scheduler_state'),**tail_progress(casepath(n))) for n,r in live])
        atomic(OUT/'scheduler_pauses.json',ledger)
        atomic(OUT/'supervisor_state.json',summary)
        return queued,pending,live,summary
    while True:
        fresh,new_entries=load_plan(args.plan)
        if fresh['revision']!=previous_revision:
            assert set(entries)<=set(new_entries),'Plan cannot remove existing cases'
            for n in entries:assert entries[n]==new_entries[n],'Existing authorization changed: '+n
            plan,entries=fresh,new_entries;previous_revision=plan['revision'];event('plan_extended',revision=previous_revision,authorized=len(entries))
        for name,r in list(records.items()):
            if r['state']!='running':continue
            try:
                job=jm.get(r['job_id'])
                r.update(tail_progress(casepath(name)))
                if job.running:continue
                rc=jm.dir/(job.id+'.rc')
                finished=rc.stat().st_mtime if rc.exists() else time.time()
                elapsed=max(0.,finished-job.started)
                r.update(returncode=job.returncode,elapsed_s=elapsed,state='failed',mpi_ranks=entries[name]['mpi_ranks'])
                details={}
                if job.returncode==0:
                    details=validate(entries[name]);r['state']='succeeded'
                status=dict(case=name,job_id=job.id,returncode=job.returncode,state=r['state'],wall_seconds=elapsed,
                    wall_seconds_source='Durable wrapper exit-file mtime minus recorded launch time',mpi_ranks=entries[name]['mpi_ranks'],
                    validated=r['state']=='succeeded',execution_backend='MCP JobManager detached supervisor',
                    finished_utc=utc(finished),actual_exit_code_known=rc.exists(),**details)
                pause=pause_details(safety.snapshot(),name)
                status.update(scheduler_paused_seconds=pause['scheduler_paused_seconds'],
                    active_wall_seconds_excluding_scheduler_pause=max(0.,elapsed-pause['scheduler_paused_seconds']),
                    scheduler_pause_intervals=pause['scheduler_pause_intervals'])
                sp=casepath(name)/'run_status.json'
                if sp.exists():
                    old=json.loads(sp.read_text());assert old['job_id']==job.id and old['state']==r['state'] and old['returncode']==job.returncode
                else:atomic(sp,status)
                event('case_terminal',case=name,job_id=job.id,returncode=job.returncode,state=r['state'],actual_wall_s=elapsed)
                if r['state']!='succeeded':raise RuntimeError('Nonzero case exit '+str(job.returncode))
            except Exception as exc:
                paused=True;msg=dict(case=name,error=str(exc));errors.append(msg);event('case_error',**msg)
                if r.get('returncode') is not None and not (casepath(name)/'run_status.json').exists():
                    atomic(casepath(name)/'run_status.json',dict(case=name,job_id=r['job_id'],state='failed_validation',
                        returncode=r['returncode'],validated=False,mpi_ranks=entries[name]['mpi_ranks'],
                        wall_seconds=r.get('elapsed_s'),validation_error=str(exc)))
        control_path=OUT/'supervisor_control.json'
        control=json.loads(control_path.read_text()) if control_path.exists() else {}
        apply_scheduling(safety,plan,entries,records,paused)
        queued,pending,live,summary=save()
        used=summary['active_solver_ranks']
        active_count=summary['cpu_active_cases']
        if not paused and not control.get('stop_launching',False):
            for name in queued:
                e=entries[name]
                if not eligible_case(name,e,records,control):continue
                if active_count>=summary['max_jobs'] or used+e['mpi_ranks']>summary['max_solver_ranks']:continue
                try:
                    c,g=geometry(e)
                    existing=saved_jobs_for_case(jm,name)
                    if existing:
                        assert len(existing)==1,'Duplicate persisted jobs for '+name
                        job=jm.get(existing[0]);records[name]=dict(case=name,job_id=job.id,state='running',returncode=None,
                            elapsed_s=job.public()['elapsed_s'],mpi_ranks=e['mpi_ranks'],adopted=True)
                        event('case_adopted',case=name,job_id=job.id)
                    else:
                        assert not (c/'log.Allrun').exists() and not (c/'log.foamRun').exists() and not list(c.glob('processor*')),name+' already started'
                        fingerprint=inputs(c)
                        if e.get('input_hashes'):assert fingerprint==e['input_hashes'],name+' prepared input change'
                        if (c/'initialization.json').exists():
                            check=subprocess.run(['python3','prepare_mapped.py','--case','.','--verify-only'],cwd=c,env=foam.host_env,
                                capture_output=True,text=True,timeout=180)
                            assert check.returncode==0,check.stdout+check.stderr
                        claim=c/'supervisor_claim.json'
                        with claim.open('x') as f:json.dump(dict(case=name,run_id=run_id,claim_utc=utc(),input_hashes=fingerprint),f)
                        argv=foam.resolve_app('Allrun',c,allow_scripts=True)
                        job=jm.start(c,'tello_refinement/'+name,'Allrun',argv,c/'log.Allrun',foam,np=1)
                        records[name]=dict(case=name,job_id=job.id,state='running',returncode=None,elapsed_s=0.,mpi_ranks=e['mpi_ranks'])
                        atomic(claim,dict(case=name,run_id=run_id,claim_utc=utc(),job_id=job.id,input_hashes=fingerprint))
                        event('case_launched',case=name,job_id=job.id,solver_ranks=e['mpi_ranks'])
                    used+=e['mpi_ranks'];active_count+=1;live.append((name,records[name]));save()
                except Exception as exc:
                    paused=True;msg=dict(case=name,error=str(exc));errors.append(msg);event('launch_error',**msg);break
        queued,pending,live,summary=save()
        if not live and not queued and not pending:
            event('all_cases_terminal',**{k:summary[k] for k in ['complete','authorized']});return 1 if paused else 0
        if not live and (paused or control.get('stop_launching',False)):
            event('supervisor_drained',paused=paused,queued=len(queued),pending=len(pending));return 1 if paused else 0
        time.sleep(10)

if __name__=='__main__':raise SystemExit(main())
