"""Freeze an audit-only Linux comm schema correction; no helper import/run."""
from pathlib import Path
import ast,difflib,hashlib,json
HERE=Path(__file__).resolve().parent
old=HERE/'nsys_2026_5_positive_control_proposal_v2'
new=HERE/'nsys_2026_5_positive_control_proposal_v3'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not new.exists(),'Refuse to overwrite proposal'
manifest=json.loads((old/'helper_manifest.json').read_text())
for n,pin in manifest['files'].items():assert sha(old/n)==pin,n
old_manifest_sha=sha(old/'helper_manifest.json')
new.mkdir()
for p in old.iterdir():
 assert p.is_file()
 with (new/p.name).open('xb') as stream:stream.write(p.read_bytes())
f=new/'audit_control.py';s=f.read_text()
needle=" processes=[dict(r) for r in con.execute('select * from PROCESSES where pid=? and globalPid=?',(pid,gtid-tid))];require(len(processes)==1 and Path(processes[0]['name']).name==Path(p['binary']['path']).name,'Wrong PROCESSES identity')\n"
replacement=""" processes=[dict(r) for r in con.execute('select * from PROCESSES where pid=? and globalPid=?',(pid,gtid-tid))];require(len(processes)==1,'Wrong PROCESSES identity')
 start=json.loads((e/'actual_start.json').read_text());require(start['actual_child']==c and isinstance(c['birth_start_ticks'],int) and c['birth_start_ticks']>0,'Actual child start/exit birth identity differs')
 for name,key in [('binary','binary_sha256'),('source','source_sha256'),('core_library','core_sha256')]:require(start[key]==x[key]==p[name]['sha256'],'Prelaunch identity differs')
 approved_basename=Path(p['binary']['path']).name;require(approved_basename.isascii(),'Linux comm fallback requires the exact approved ASCII basename')
 approved_comm15=approved_basename.encode('ascii')[:15].decode('ascii');process_label=processes[0]['name']
 if process_label==p['binary']['path']:process_label_mode='EXACT_APPROVED_EXECUTABLE_PATH'
 elif process_label==approved_basename:process_label_mode='EXACT_APPROVED_BASENAME'
 elif len(approved_basename.encode('ascii'))>15 and process_label==approved_comm15:process_label_mode='EXACT_APPROVED_ASCII_LINUX_COMM_15_BYTES'
 else:require(False,'Wrong PROCESSES label; arbitrary prefixes are forbidden')
 process_label_policy={'mode':process_label_mode,'observed_label':process_label,'approved_basename':approved_basename,'approved_comm15':approved_comm15,'documentation':'https://man7.org/linux/man-pages/man5/proc_pid_comm.5.html','identity_scope':'Label is supplementary to exact executable hashes, start/exit PID birth UID cwd, and NVTX/globalPid identity; it is never standalone executable proof.'}
"""
assert s.count(needle)==1;s=s.replace(needle,replacement)
needle="'process':processes[0],"
assert s.count(needle)==1;s=s.replace(needle,"'process':processes[0],'process_label_policy':process_label_policy,")
f.write_text(s,newline='\n')
f=new/'README.md'
f.write_text(f.read_text()+"\nV3 is an AUDIT-ONLY schema correction for the already completed single control. Do not run run_control.py again. Preserve the V2 audit failure and raw trace unchanged. The PROCESSES label must equal the exact approved full executable path, its exact ASCII basename, or (only for a basename longer than15bytes) exactly its first15ASCIIbytes. Arbitrary prefixes and paths with merely matching basenames are rejected. The chosen label mode is explicit and supplementary to unchanged PID/globalPid/NVTX, executable SHA, UID/cwd and numerical gates; start/exit PID birth identity and prelaunch binary/source/core SHA are explicitly reconciled. [Linux proc_pid_comm(5)](https://man7.org/linux/man-pages/man5/proc_pid_comm.5.html) documents TASK_COMM_LEN16 including the terminating null byte. This documents a possible schema label, without claiming Nsight always uses comm. Root may invoke audit_control.py only with a fresh V3-bound audit approval; this causes no application/profile/kernel rerun.\n",newline='\n')
documentation={'source':'Linux man-pages proc_pid_comm(5)','url':'https://man7.org/linux/man-pages/man5/proc_pid_comm.5.html','accessed_UTC_date':'2026-11-02','supported_fact':'Linux comm truncates labels to TASK_COMM_LEN16 including the terminating null, hence15 bytes for this ASCII executable basename.','selected_probe_basename':'Test-nativeStdparFields','exact_comm15':'Test-nativeStdp','qualification':'This is an exact alternative metadata label only. It is not independent executable identity or a blanket assertion about every Nsight PROCESSES.name value.','no_GPU_rerun':True}
(new/'linux_comm_label_documentation.json').write_text(json.dumps(documentation,indent=2)+'\n',newline='\n')
changed=[];diff=[]
for n in manifest['files']:
 if (old/n).read_bytes()!=(new/n).read_bytes():
  changed.append(n);diff.extend(difflib.unified_diff((old/n).read_text().splitlines(True),(new/n).read_text().splitlines(True),fromfile='v2/'+n,tofile='v3/'+n))
assert changed==['README.md','audit_control.py'],changed
assert sha(old/'protocol.json')==sha(new/'protocol.json')
for p in new.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
patch=new/'v3_process_label_audit.diff';patch.write_text(''.join(diff),newline='\n')
v3=dict(manifest);v3['schema']='new-nsys-native-field-control-helper-freeze-v3-audit-only'
v3['status']='SOURCE_ONLY_AUDIT_SCHEMA_CORRECTION_PENDING_ROOT_REVIEW_NO_GPU_REPEAT'
v3['files']={n:sha(new/n) for n in manifest['files']};v3['files']['linux_comm_label_documentation.json']=sha(new/'linux_comm_label_documentation.json')
v3['previous_frozen_manifest_sha256']=old_manifest_sha
v3['source_only_correction']='Audit only: exact approved ASCII15-byte Linux comm metadata alternative, explicit label mode and start/exit identity reconciliation; no application rerun.'
v3['limited_diff_sha256']=sha(patch);v3['generator_sha256']=sha(Path(__file__))
(new/'helper_manifest.json').write_text(json.dumps(v3,indent=2)+'\n',newline='\n')
for n,pin in manifest['files'].items():assert sha(old/n)==pin
assert sha(old/'helper_manifest.json')==old_manifest_sha
print(json.dumps({'directory':str(new),'protocol_sha256':sha(new/'protocol.json'),'helper_manifest_sha256':sha(new/'helper_manifest.json'),'diff_sha256':sha(patch),'GPU_or_application_or_audit_run':False},indent=2))
