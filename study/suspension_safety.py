"""Task-scoped, identity-checked SIGSTOP/CONT with a parent-death safety guard."""
from pathlib import Path
import argparse,fcntl,json,os,signal,subprocess,sys,time,uuid
from contextlib import contextmanager

ROOT=Path('/opt/openfoam-workspace/cases/tello_refinement').resolve()
JOURNAL=ROOT.parent/'tello_execution_supervisor/journal'
LEDGER=JOURNAL/'scheduler_pauses.json'
STATE=ROOT.parent/'.openfoam-mcp/jobs'

def stamp():return time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
def atomic(path,value):
    tmp=path.with_name(path.name+f'.{os.getpid()}.tmp')
    tmp.write_text(json.dumps(value,indent=2)+'\n');os.replace(tmp,path)
@contextmanager
def locked():
    JOURNAL.mkdir(parents=True,exist_ok=True)
    with (JOURNAL/'scheduler.lock').open('a+') as f:
        fcntl.flock(f,fcntl.LOCK_EX);yield
def read():return json.loads(LEDGER.read_text()) if LEDGER.exists() else dict(cases={},events=[])
def resume_budget():
    out=Path(__file__).resolve().parent
    plan=json.loads((out/'supervisor_plan.json').read_text());cap=plan['max_solver_ranks']
    control=json.loads((out/'supervisor_control.json').read_text());override=plan.get('pilot_phase_override',{})
    allowed=control.get('allowed_cases',[])
    if override and control.get('phase') in override['phases'] and allowed and set(allowed)<=set(override['cases']):
        complete=True
        for name in allowed:
            path=ROOT/name/'run_status.json'
            if not path.exists() or json.loads(path.read_text()).get('state')!='succeeded':complete=False
        if not complete:cap=override['max_solver_ranks']
    return cap
def active_ranks(data):
    plan=json.loads((Path(__file__).resolve().parent/'supervisor_plan.json').read_text())
    entries={e['case']:e for e in plan['cases']};live={}
    for path in STATE.glob('*.json'):
        try:
            j=json.loads(path.read_text());name=j.get('case','').removeprefix('tello_refinement/')
            if j.get('case')!='tello_refinement/'+name or name not in entries or j.get('app')!='Allrun':continue
            if j.get('returncode') is not None or (STATE/(j['id']+'.rc')).exists():continue
            p=proc(j['pid'])
            if p['os_state'] in ['Z','X']:continue
            row=data['cases'].get(name,{})
            if open_interval(row) and identity(row['identity'])['os_state']=='T':continue
            live[name]=entries[name]['mpi_ranks']
        except (FileNotFoundError,ProcessLookupError,PermissionError):continue
    return sum(live.values())
def proc(pid):
    p=Path('/proc')/str(pid);stat=(p/'stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=int(pid),birth_ticks=int(stat[19]),os_state=stat[0],cwd=str((p/'cwd').resolve()),
        uid=p.stat().st_uid,command=(p/'cmdline').read_bytes().replace(b'\x00',b' ').decode().strip(),
        cpu_ticks=int(stat[11])+int(stat[12]))
def identity(target):
    p=proc(target['pid']);c=ROOT/target['case']
    assert c.resolve().parent==ROOT and p['cwd']==str(c.resolve())==target['cwd']
    assert p['uid']==target['uid']==os.getuid() and p['birth_ticks']==target['birth_ticks']
    assert p['command']==target['command']=='foamRun'
    assert json.loads((c/'geometry.json').read_text())['execution']['mpi_ranks']==1
    j=json.loads((STATE/(target['job_id']+'.json')).read_text())
    assert j['case']=='tello_refinement/'+target['case'] and j['app']=='Allrun' and j['returncode'] is None
    assert not (STATE/(target['job_id']+'.rc')).exists()
    os.kill(j['pid'],0)
    return p
def open_interval(row):
    return row['intervals'][-1] if row.get('intervals') and row['intervals'][-1].get('resumed_epoch') is None else None
def event(data,kind,**kw):data['events'].append(dict(utc=stamp(),kind=kind,**kw))
def resume_locked(data,names,reason,owner=None):
    changed=[]
    for name in names:
        row=data['cases'].get(name);interval=open_interval(row or {})
        if interval is None or (owner is not None and interval['owner_id']!=owner):continue
        if active_ranks(data)+1>resume_budget():continue
        target=row['identity']
        try:
            p=identity(target);os.kill(target['pid'],signal.SIGCONT)
        except Exception as exc:
            event(data,'SIGCONT_identity_check_failed',case=name,pid=target['pid'],reason=reason,error=str(exc))
            atomic(LEDGER,data);continue
        interval.update(resumed_epoch=time.time(),resumed_utc=stamp(),resume_reason=reason,
            cpu_ticks_before_resume=p['cpu_ticks'])
        row['scheduler_state']='running';event(data,'SIGCONT',case=name,pid=target['pid'],owner_id=interval['owner_id'],reason=reason)
        atomic(LEDGER,data);changed.append(name)
    return changed
def resume_all(reason,owner=None):
    with locked():
        data=read();return resume_locked(data,list(data['cases']),reason,owner)

class Safety:
    def __init__(self,owner=None):
        self.owner=owner or uuid.uuid4().hex;self.closed=False
        self.stop_file=JOURNAL/('watchdog_stop_'+self.owner)
        with locked():
            data=read();data.setdefault('owners',{})[self.owner]=dict(pid=os.getpid(),birth_ticks=proc(os.getpid())['birth_ticks'])
            atomic(LEDGER,data)
        self.log=(JOURNAL/('watchdog_'+self.owner+'.log')).open('a')
        self.watchdog=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--watch',str(os.getpid()),
            '--birth',str(proc(os.getpid())['birth_ticks']),'--owner',self.owner],
            stdin=subprocess.DEVNULL,stdout=self.log,stderr=subprocess.STDOUT,start_new_session=True)
        time.sleep(.05);assert self.watchdog.poll() is None,'Safety watchdog did not start'
    def pause(self,target,reason):
        assert self.watchdog.poll() is None,'Safety watchdog is not alive'
        with locked():
            data=read();name=target['case'];row=data['cases'].setdefault(name,dict(identity=target,intervals=[]))
            assert row['identity']==target,'Suspension identity changed'
            previous=open_interval(row)
            if previous:
                if previous['owner_id']==self.owner:
                    assert identity(target)['os_state']=='T';return
                old=data.get('owners',{}).get(previous['owner_id'])
                if old:
                    try:
                        old_proc=proc(old['pid']);alive=old_proc['birth_ticks']==old['birth_ticks'] and old_proc['os_state'] not in ['Z','X']
                    except (FileNotFoundError,ProcessLookupError):alive=False
                    assert not alive,'Another live scheduler owns this suspended solver'
                assert identity(target)['os_state']=='T'
                previous.setdefault('owner_transfers',[]).append(dict(utc=stamp(),old_owner=previous['owner_id'],new_owner=self.owner))
                previous['owner_id']=self.owner;event(data,'paused_owner_adopted',case=name,owner_id=self.owner)
                atomic(LEDGER,data);return
            before=identity(target)
            assert before['os_state']!='T','Refuse to adopt an unexplained externally stopped solver'
            interval=dict(owner_id=self.owner,requested_epoch=time.time(),requested_utc=stamp(),reason=reason,
                cpu_ticks_before_stop=before['cpu_ticks'],resumed_epoch=None)
            row['intervals'].append(interval);row['scheduler_state']='pause_requested'
            event(data,'SIGSTOP_intent',case=name,pid=target['pid'],owner_id=self.owner,reason=reason)
            atomic(LEDGER,data)
            os.kill(target['pid'],signal.SIGSTOP)
            for attempt in range(100):
                after=identity(target)
                if after['os_state']=='T':break
                time.sleep(.01)
            else:raise RuntimeError('SIGSTOP not confirmed for '+name)
            interval.update(confirmed_epoch=time.time(),confirmed_utc=stamp(),cpu_ticks_after_stop=after['cpu_ticks'])
            row['scheduler_state']='suspended';event(data,'SIGSTOP_confirmed',case=name,pid=target['pid'],owner_id=self.owner)
            atomic(LEDGER,data)
    def snapshot(self):
        with locked():return read()
    def resume(self,names,reason):
        with locked():
            data=read();return resume_locked(data,names,reason,self.owner)
    def close(self,reason='Supervisor shutdown or exception'):
        if self.closed:return
        self.closed=True
        try:resume_all(reason,self.owner)
        finally:
            self.stop_file.touch()
            try:self.watchdog.wait(timeout=5)
            except subprocess.TimeoutExpired:pass
            self.log.close()

def watch(parent,birth,owner):
    stop=JOURNAL/('watchdog_stop_'+owner)
    draining=False;last_notice=0
    while True:
        try:p=proc(parent);alive=p['birth_ticks']==birth and p['os_state'] not in ['Z','X']
        except (FileNotFoundError,ProcessLookupError):alive=False
        if not alive or stop.exists() or draining:
            draining=True
            reason='Parent-death fail-safe' if not alive else 'Parent requested safety shutdown'
            try:
                changed=resume_all(reason,owner)
                with locked():pending=[n for n,row in read()['cases'].items() if open_interval(row) and open_interval(row)['owner_id']==owner]
                if changed or not pending or time.time()-last_notice>60:
                    print(json.dumps(dict(utc=stamp(),reason=reason,resumed=changed,pending_under_rank_cap=pending)),flush=True);last_notice=time.time()
            except Exception as exc:print(json.dumps(dict(utc=stamp(),reason=reason,error=str(exc))),flush=True);raise
            if not pending:return
        time.sleep(.5)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--watch',type=int,required=True);a.add_argument('--birth',type=int,required=True);a.add_argument('--owner',required=True)
    args=a.parse_args();watch(args.watch,args.birth,args.owner)
