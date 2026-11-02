from pathlib import Path
import hashlib,json
P=Path('/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/execution/strict_runs')
current=P/'gpu_profile_proposal';original=P/'gpu_profile_proposal_v1_frozen';later=P/'gpu_profile_proposal_v1_later_snapshot';new=P/'gpu_profile_proposal_v2'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p in [original,later,new]:assert not p.exists()
def copy(source,dest):
 dest.mkdir()
 for p in source.iterdir():
  if p.is_file():(dest/p.name).write_bytes(p.read_bytes())
copy(current,later);copy(current,original)
manifest=json.loads((original/'helper_manifest_initial_source_only.json').read_text())
t=(original/'run_actual_gpu_child.py').read_text()
for old,replacement in [
 ('seen=set();timed_out=False;forced=False;cancelled=False','seen=set();timed_out=False;forced=False'),
 ('  term_at=None\n  def forward(signum,frame):\n   nonlocal cancelled,term_at\n   cancelled=True\n   if term_at is None:term_at=time.monotonic()','  def forward(signum,frame):'),
 ('  begin=time.monotonic()\n','  begin=time.monotonic();term_at=None\n'),
 ('except (FileNotFoundError,ProcessLookupError,PermissionError):pass','except (FileNotFoundError,ProcessLookupError):pass'),
 ("   if not cancelled and (evidence/'outer_cancel_requested.json').exists():forward(signal.SIGTERM,None)\n",''),
 ("if (timed_out or cancelled) and not forced",'if timed_out and not forced'),
 ("'timed_out':timed_out,'cancelled':cancelled,'forced_kill'","'timed_out':timed_out,'forced_kill'")]:
 assert old in t,old;t=t.replace(old,replacement)
(original/'run_actual_gpu_child.py').write_text(t)
t=(original/'run_gpu_profile.py').read_text();old=" def request_stop(signum,frame):save(evidence/'outer_cancel_requested.json',{'requested_utc':utc(),'signal':signum,'meaning':'Actual-child wrapper must terminate/wait its own pidfd; no unrelated process signal'})\n signal.signal(signal.SIGTERM,request_stop);signal.signal(signal.SIGINT,request_stop)\n";assert old in t;t=t.replace(old,'');(original/'run_gpu_profile.py').write_text(t)
t=(original/'validate_gpu_profile.py').read_text();t=t.replace(" and not run['cancelled']",'').replace('Actual direct solver failed, cancelled or timed out','Actual direct solver failed or timed out');(original/'validate_gpu_profile.py').write_text(t)
(original/'helper_manifest.json').write_bytes((original/'helper_manifest_initial_source_only.json').read_bytes())
assert sha(original/'helper_manifest.json')=='fa8bc924e0e5de55457167c873f84d297a297c9679ced2e70316d313de455b93'
for n,pin in manifest['files'].items():assert sha(original/n)==pin,(n,sha(original/n),pin)
assert sha(later/'helper_manifest.json')=='784ab973ef7c6c783a3bad611934aa5408b6a3406823dc4ad907fdfc68a1df9f'
copy(original,new)
# The V2 helper manifest is regenerated after the narrow cleanup edits.
(new/'helper_manifest.json').unlink()
print(json.dumps({'original_fa8_manifest_restored_and_all_bound_files_exact':True,'original':str(original),'later_784_snapshot':str(later),'v2_pending':str(new),'runtime':False},indent=2))
