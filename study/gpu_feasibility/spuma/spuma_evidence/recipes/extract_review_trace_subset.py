"""Copy ONLY frozen-check API/NVTX/process rows and their referenced strings."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,sqlite3

WORK=Path(__file__).resolve().parent;BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma')
CANDIDATE=WORK/'publication_candidate';EVIDENCE=CANDIDATE/'spuma_evidence'
PRIVATE=Path('/opt/openfoam-workspace/cases/spuma_gpu_pilots_20261102')
gate=json.loads((BASE/'provenance/spuma_strict_v2_cfd_first_step_gpu_gate.json').read_text())
source=Path(gate['sqlite']);destination=EVIDENCE/'strict_v2/cavity_first_step_trace_review_subset.sqlite'
assert os.getuid()==999 and CANDIDATE.resolve()==CANDIDATE and not destination.exists()
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
assert digest(source)==gate['sqlite_sha256']
raw=sqlite3.connect('file:'+str(source)+'?mode=ro',uri=True);raw.row_factory=sqlite3.Row
out=sqlite3.connect(destination)
thread=gate['globalTid'];lo=gate['nvtx_range']['start'];hi=gate['nvtx_range']['end'];pid=(thread//0x1000000)%0x1000000
launch_names=['cudaLaunchKernel','cuLaunchKernel','cudaGraphLaunch','cuGraphLaunch','cudaLaunchCooperativeKernel']
sync_names=['cudaDeviceSynchronize','cudaStreamSynchronize','cuCtxSynchronize','cuStreamSynchronize']
counts={};string_ids=set();launch_calls=sync_calls=bad_calls=0

def transfer(table,rows):
    schema=raw.execute('select sql from sqlite_master where type=? and name=?',('table',table)).fetchone()[0]
    out.execute(schema)
    if rows:
        columns=list(rows[0].keys());marks=','.join('?' for _ in columns)
        out.executemany('insert into "'+table+'" ('+','.join('"'+column+'"' for column in columns)+') values ('+marks+')',
                        [tuple(row[column] for column in columns) for row in rows])
    counts[table]=len(rows)

tables=[row[0] for row in raw.execute("select name from sqlite_master where type='table'")]
for table in sorted(tables):
    if not table.startswith('CUPTI_ACTIVITY_KIND_'):continue
    columns={row[1] for row in raw.execute('pragma table_info("'+table+'")')}
    if not {'start','end','globalTid','nameId','returnValue'}.issubset(columns):continue
    rows=[]
    for row in raw.execute('select a.*,s.value as safe_name from "'+table+'" a join StringIds s on a.nameId=s.id where a.start>=? and a.end<=? and a.globalTid=?',(lo,hi,thread)):
        is_launch=any(name in row['safe_name'] for name in launch_names)
        is_sync=any(name in row['safe_name'] for name in sync_names)
        if not (is_launch or is_sync):continue
        assert row['safe_name'].replace('_','').isalnum(),'Unexpected API name; do not copy arbitrary strings'
        item=dict(row);item.pop('safe_name');rows.append(item);string_ids.add(row['nameId'])
        launch_calls+=int(is_launch);sync_calls+=int(is_sync);bad_calls+=int(row['returnValue']!=0)
    if rows:transfer(table,rows)
nvtx=[dict(row) for row in raw.execute('select * from NVTX_EVENTS where globalTid=? and start=? and end=?',(thread,lo,hi))]
assert len(nvtx)==1 and nvtx[0]['text']==gate['range_name']
assert all(nvtx[0].get(name) is None for name in ['jsonText','binaryData'])
if nvtx[0].get('textId') is not None:string_ids.add(nvtx[0]['textId'])
transfer('NVTX_EVENTS',nvtx)
process=[dict(row) for row in raw.execute('select * from PROCESSES where pid=?',(pid,))]
assert len(process)==1 and process[0]['name']=='icoFoam';transfer('PROCESSES',process)
strings=[dict(raw.execute('select * from StringIds where id=?',(identifier,)).fetchone()) for identifier in sorted(string_ids)]
for row in strings:
    assert row['value']==gate['range_name'] or any(name in row['value'] for name in launch_names+sync_names)
transfer('StringIds',strings)
assert launch_calls==gate['successful_launch_api_calls_in_cfd_loop']==2445
assert sync_calls==gate['successful_synchronization_api_calls_in_cfd_loop']==2445 and bad_calls==0
provenance=dict(kind='Lossless subset of ONLY rows and strings used by frozen first-step checks',
    extracted_utc=datetime.now(timezone.utc).isoformat(),source_private_sqlite=str(source),source_sqlite_sha256=gate['sqlite_sha256'],
    source_private_report=gate['report'],source_report_sha256=gate['report_sha256'],
    predicate=dict(start_at_least=lo,end_at_most=hi,globalTid=thread,launch_name_contains=launch_names,sync_name_contains=sync_names),
    row_counts=counts,successful_launch_rows=launch_calls,successful_sync_rows=sync_calls,failed_rows=bad_calls,
    StringIds_policy='Only ids referenced by copied API nameId or NVTX textId; no other StringIds copied',
    process_policy='Only the actual icoFoam pid row; only the complete named NVTX range row',
    environment_values_read_or_copied=False,unrelated_process_or_environment_tables_copied=False,
    original_full_report_and_SQLite_unchanged=True,frozen_gate_or_threshold_changed=False,no_speed_inference=True)
out.execute('create table REVIEW_SUBSET_PROVENANCE (json TEXT NOT NULL)');out.execute('insert into REVIEW_SUBSET_PROVENANCE values (?)',(json.dumps(provenance),))
out.commit();assert out.execute('pragma integrity_check').fetchone()[0]=='ok';out.close();raw.close()
assert digest(source)==gate['sqlite_sha256']
references=[]
for label,case in [('strict_v2',PRIVATE/'cavity_gpu_fixedpool_strict_v2'),('original_failed',PRIVATE/'cavity_gpu_fixedpool')]:
    for name in ['cavity_first_step_trace.nsys-rep','cavity_first_step_trace.sqlite','cavity_icoFoam_time_loop_trace.nsys-rep']:
        original=case/name;copied=EVIDENCE/label/name
        if not original.is_file():continue
        assert copied.is_file() and digest(copied)==digest(original)
        assert copied.resolve().is_relative_to(CANDIDATE.resolve())
        references.append(dict(private_path=str(original),sha256=digest(original),bytes=original.stat().st_size,
            omitted_from_candidate=str(copied.relative_to(CANDIDATE)),reason='Raw report can store target environment by default; full SQLite/StringIds contains unnecessary metadata; private original retained'))
        copied.unlink()
provenance.update(review_subset=str(destination.relative_to(CANDIDATE)),review_subset_sha256=digest(destination),
    private_raw_references=references,extraction_recipe_sha256=digest(Path(__file__)))
(EVIDENCE/'review_trace_subset.json').write_text(json.dumps(provenance,indent=2)+'\n')
recipe=EVIDENCE/'recipes/extract_review_trace_subset.py';recipe.write_bytes(Path(__file__).read_bytes())
note='\n\nThe review candidate omits the raw .nsys-rep files and full trace SQLite, which remain private with recorded hashes. It supplies a lossless SQLite subset containing only the API/NVTX/process rows used by the frozen checks and only their referenced safe names. Environment/unrelated metadata is excluded; see review_trace_subset.json and its exact extraction recipe.\n'
for document in [EVIDENCE/'README.md',CANDIDATE/'SPUMA_FUNCTIONAL_TEST.md']:document.write_text(document.read_text()+note)
manifest_path=EVIDENCE/'manifest.json';manifest=json.loads(manifest_path.read_text())
manifest['review_trace_subset']=provenance;manifest['files']={str(p.relative_to(EVIDENCE)):{'bytes':p.stat().st_size,'sha256':digest(p)}
    for p in sorted(EVIDENCE.rglob('*')) if p.is_file() and p!=manifest_path}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
record=dict(state='source_evidence_candidate_ready_FOR_REVIEW_NOT_PUBLISHED',candidate=str(CANDIDATE),
    manifest=str(manifest_path),manifest_sha256=digest(manifest_path),file_count=len(manifest['files']),
    total_bytes=sum(p.stat().st_size for p in CANDIDATE.rglob('*') if p.is_file()),
    review_subset_row_counts=counts,private_raw_payloads_not_exported=True,
    SDK_ELF_build_trees_credentials_and_unrelated_helpers_excluded=True,no_new_CFDrun_timing_default_Git_or_CPU84_mutation=True)
prior=WORK/'publication_candidate_prepared.json';before=WORK/'publication_candidate_prepared.before_trace_subset.json'
assert not before.exists();before.write_bytes(prior.read_bytes());prior.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
