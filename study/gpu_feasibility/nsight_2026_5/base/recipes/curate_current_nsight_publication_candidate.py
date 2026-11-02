"""Curate only safe source/provenance from already CLOSED profiler evidence.

No GPU/profile/CFD/build/default/Git/archive action. The only tool invocation is
the installed nsys --version, which does not launch an application or collect.
"""
from pathlib import Path
from datetime import datetime,timezone
import ast,hashlib,json,os,re,subprocess

WORK=Path(__file__).resolve().parent.parent
TASK=WORK/'native_stdpar_install'
OUT=WORK/'current_nsight_publication_candidate'
P=Path('/opt/openfoam-workspace/gpu-feasibility/nsight-systems-2026.5.1')
NATIVE=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar')
E=P/'native_field_positive_control_20261102'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,message):
 if not ok:raise RuntimeError(message)
require(os.geteuid()==999 and not OUT.exists(),'Wrong UID or candidate already exists')
os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
OUT.mkdir();copies=[]
def put_bytes(relative,data,source=None):
 p=OUT/relative;p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
 require(p.read_bytes()==data,'Content copy differs: '+relative)
 if source:copies.append({'candidate_path':relative,'source_path':str(source),'source_sha256':sha(source),'copied_sha256':sha(p),'exact_content_copy':True})
 return p
def copy(src,relative):return put_bytes(relative,src.read_bytes(),src)
def save(relative,obj):return put_bytes(relative,(json.dumps(obj,indent=2)+'\n').encode())
receipt=json.loads((P/'installation_receipt.json').read_text())
require(sha(P/'installation_receipt.json')=='bee7c3f2dee1f71914e99c407c5fca0fe4b48b508f857f4f8220b13fd7609f59','Installation receipt differs')
archive=P/'nsight-systems-cli-2026.5.1_2026.5.1.161-1_arm64.deb'
require(archive.stat().st_size==208229554 and sha(archive)=='087c08b5ddf3ed6f913748f8206d6bbdc225f2aa275ff33af4c487e8b319c8ab','Official archive differs')
copy(P/'installation_receipt.json','installation/installation_receipt.json')
for name in ['install_current_nsight_private.py','install_current_nsight_private_initial_metadata_assert.py']:
 copy(WORK/name,'recipes/'+name)
nsys=Path(receipt['nsys_candidates'][0]['path']);require(sha(nsys)=='dbe02661b00efbfb4c9c3cd3c2d8df6fecd6e80ac794305892e233e0d712a527','Tool identity differs')
v=subprocess.run([str(nsys),'--version'],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
require(v.returncode==0 and '2026.5.1' in v.stdout,'Installed version check failed')
save('installation/installed_version_proof.json',{'command':[str(nsys),'--version'],'actual_return_code':v.returncode,'stdout':v.stdout,'stderr':v.stderr,'binary_sha256':sha(nsys),'observed_utc':datetime.now(timezone.utc).isoformat(),'application_profile_or_GPU_launched':False})
save('installation/official_sources.json',{'accessed_utc_date':'2026-11-02','download_page':'https://developer.nvidia.com/nsight-systems/get-started','release_notes':'https://docs.nvidia.com/nsight-systems/ReleaseNotes/','release_note_fact':'Nsight Systems2026.5.1 lists CUDA13.4 support.','canonical_archive_url':receipt['canonical_download_url'],'archive_bytes':archive.stat().st_size,'archive_sha256':sha(archive),'checksum_origin':receipt['checksum_origin'],'actual_package_metadata':receipt['package_metadata'],'package_extracted_not_installed_with_scripts':True,'historical_SDK_profiler_unchanged':True})
versions=['nsys_2026_5_positive_control_proposal','nsys_2026_5_positive_control_proposal_v2','nsys_2026_5_positive_control_proposal_v3']
for index,name in enumerate(versions,1):
 folder=TASK/name;m=json.loads((folder/'helper_manifest.json').read_text())
 for f,pin in m['files'].items():require(sha(folder/f)==pin,'Frozen helper changed: '+f)
 for f in sorted(folder.iterdir()):
  require(f.is_file() and f.suffix in {'.py','.json','.md','.diff'},'Unexpected proposal artifact')
  copy(f,'harness/v'+str(index)+'/'+f.name)
for name in ['nsys_2026_5_positive_control_independent_review.json','nsys_2026_5_positive_control_independent_review.md','nsys_2026_5_process_label_audit_independent_review.json','nsys_2026_5_process_label_audit_independent_review.md']:
 copy(TASK/name,'reviews/'+name)
for name in ['nsys_2026_5_positive_control_approval.json','nsys_2026_5_positive_control_audit_v3_approval.json','run_approved_new_nsight_control.sh','audit_existing_new_nsight_control_v3.sh']:
 copy(TASK/name,'approvals_and_commands/'+name)
copy(TASK/'nsys_2026_5_positive_control_original_audit_failure.json','evidence/original_V2_audit_metadata_failure.json')
for name in ['prepare_new_nsys_control_source_only.py','prepare_new_nsys_control_warning_v2.py','prepare_new_nsys_control_label_v3.py','extract_current_nsight_safe_subset.py','curate_current_nsight_publication_candidate.py']:
 copy(TASK/name,'recipes/'+name)
protocol=json.loads((TASK/versions[0]/'protocol.json').read_text());source=Path(protocol['source']['path'])
require(sha(source)==protocol['source']['sha256'] and sha(Path(protocol['binary']['path']))==protocol['binary']['sha256'] and sha(Path(protocol['core_library']['path']))==protocol['core_library']['sha256'],'Current probe/core/source differs')
copy(source,'probe_source/Test-nativeStdparFields.C')
for name in ['files','options']:copy(source.parent/'Make'/name,'probe_source/Make/'+name)
copy(Path(protocol['library_identity']['path']),'probe_source/linked_libraries.json')
libs=json.loads(Path(protocol['library_identity']['path']).read_text())['files'];require(len(libs)==22,'Expected22 declared linked libraries')
for item in libs:require(sha(Path(item['path']))==item['sha256'],'Linked dependency differs')
case=Path(protocol['case']);require({str(x.relative_to(case)):sha(x) for x in case.rglob('*') if x.is_file()}==protocol['case_files'],'Tiny control case changed')
for name in protocol['case_files']:copy(case/name,'tiny_Time_only_case/'+name)
env=NATIVE/'env.sh';require(sha(env)==protocol['native_environment']['sha256'],'Private environment changed')
allowed_env={'NVCOMPILERS','NVARCH','PATH','BISON_PKGDATADIR','LD_LIBRARY_PATH','TMPDIR','XDG_CONFIG_HOME','CUDA_CACHE_PATH','FOAM_CONFIG_MODE','WM_NCOMPPROCS','OMP_NUM_THREADS','FOAM_MODULE_PREFIX','WM_PROJECT_USER_DIR','FOAM_USER_APPBIN','FOAM_USER_LIBBIN','FOAM_JOB_DIR','FOAM_RUN','FOAM_MEMORY_POOL'}
env_text=env.read_text();exports=set(re.findall(r'^export ([A-Z0-9_]+)=',env_text,re.M));require(exports==allowed_env,'Unexpected private environment variable')
require(not any(t.lower() in env_text.lower() for t in ['token=','secret=','password=','api_key=']),'Unexpected environment content')
copy(env,'probe_source/private_native_environment.sh')
save('probe_source/identity_and_environment_scope.json',{'source':protocol['source'],'binary_identity_only_no_ELF':protocol['binary'],'core_library_identity_only_no_ELF':protocol['core_library'],'library_count':len(libs),'private_environment_sha256':sha(env),'private_environment_export_name_allowlist':sorted(allowed_env),'scope':'Only fixed compiler/SDK/loader/cache/run paths and flags are included. No captured process environment or environment table is included.','source_OpenCFD_pin':'b239fea6e48922730477e218c44e8b6a8ab17ade','compiler':'NVHPC26.9 nvc++26.9-0 CUDA13.3.73','compile_backend_flags':['-stdpar=gpu','-gpu=cc121,mem:managed','-DFOAM_OFFLOAD'],'tiny_case_file_count':9,'mesh_CFD_timesteps':0})
safe_evidence=['actual_start.json','actual_exit.json','actual_spawn.json','actual_wrapper_start.json','wrapper_exit.json','prelaunch.json','profile_exit.json','export_exit.json','probe_stdout.log','profile.log','export.log']
for name in safe_evidence:copy(E/name,'evidence/'+name)
gate=json.loads((E/'positive_control_gate.json').read_text());require(gate['passed'] and gate['launch_API_calls']==8 and len(gate['attributed_kernel_activity_rows'])==8,'Unexpected accepted small gate')
gpid=gate['process']['globalPid'];safe_diag={'Unified Memory trace is currently not supported for Tegra iGPU device, disabling.','Not all NVTX events might have been collected.','Not all CUDA events might have been collected.','Number of CUDA events collected: \t36.'}
safe_gate=dict(gate);safe_gate['diagnostic_events']=[r for r in gate['diagnostic_events'] if r.get('globalPid') in [None,0,gpid] and r.get('text') in safe_diag]
save('evidence/positive_control_gate.review_safe.json',safe_gate)
subset=OUT/'evidence/field_control_review_subset.sqlite';subset_receipt=OUT/'evidence/review_trace_subset.json'
extractor=TASK/'extract_current_nsight_safe_subset.py'
r=subprocess.run(['/usr/bin/python3','-B',str(extractor),'--source',str(E/'field_control.sqlite'),'--gate',str(E/'positive_control_gate.json'),'--target',str(subset),'--receipt',str(subset_receipt)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=30)
require(r.returncode==0,'Safe subset export failed: '+r.stderr)
proof=json.loads(subset_receipt.read_text())
save('evidence/private_original_hashes_and_safe_view.json',{'original_private_gate_sha256':sha(E/'positive_control_gate.json'),'original_report_sha256':sha(E/'field_control.nsys-rep'),'original_full_sqlite_sha256':sha(E/'field_control.sqlite'),'review_safe_gate_sha256':sha(OUT/'evidence/positive_control_gate.review_safe.json'),'transformation':'Only diagnostic_events is filtered to the actual target/global rows and four exact fixed diagnostic texts used by the subset. All other gate values are unchanged. Full original is retained privately and not published.','original_diagnostic_rows':len(gate['diagnostic_events']),'safe_diagnostic_rows':len(safe_gate['diagnostic_events']),'raw_report_or_full_SQLite_copied':False,'environment_tables_unrelated_process_rows_or_unrelated_StringIds_copied':False,'actual_probe_executions_total':1,'original_V2_audit_failure_retained':True,'V3_audit_only_no_GPU_repeat':True})
save('scope_and_limitations.json',{'new_tool_positive_control':'PASSED existing32768-element native Field arithmetic only','classification':gate['classification'],'actual_probe_PID':gate['actual_child']['pid'],'actual_probe_exit':0,'launch_API_calls':8,'successful_sync_API_calls':9,'attributed_GPU_kernel_rows':8,'named_range_complete':True,'whole_process_event_completeness_claimed':False,'retained_warning_limitations':['Not all NVTX events might have been collected.','Not all CUDA events might have been collected.','Unified Memory tracing was disabled by the tool.'],'unsupported_driver_warning_count':0,'runtime_toolkit':'NVHPC private CUDA13.3 runtime; current host driver API13.4','new_profiler':'Standalone2026.5.1; historical SDK profiler unchanged','large_C29_profiled_attempt':'FAILED SIGSEGV actualchild-11 before Courant/source; no qualification','large_C29_plain_attempt':'FAILED same SIGSEGV actualchild-11 without profiler; no qualification','plain_failure_reconciliation_sha256':protocol['plain_failure_reconciliation']['sha256'],'C29_2_4_built':False,'GPU_transient_or_rotor_lift_qualified':False,'timing_or_speedup_measured':False,'production_default_changed':False,'all84_CPU_CFD_results_changed':False})
readme="""The privately extracted standalone NVIDIA Nsight Systems2026.5.1 CLI is installed and verified. Its one existing32,768-element native OpenFOAM Field arithmetic control passed: true child/profiler/export exit0, exact host-reference arithmetic,8 successful launch API calls,9 successful synchronization API calls, a same-thread device completion after the final launch, and8 attributable GPU kernel records inside the complete named algebra range. Unsupported-driver warnings were absent. These API and kernel counts are separate observations, with no speed claim.

The official208,229,554-byte ARM64 package has SHA256087c08b5ddf3ed6f913748f8206d6bbdc225f2aa275ff33af4c487e8b319c8ab and actual metadata Version2026.5.1.161-265138896106v0. It was extracted privately without package scripts, driver changes or default changes. [NVIDIA's release notes](https://docs.nvidia.com/nsight-systems/ReleaseNotes/) list CUDA13.4 support; installation/ records the official download URL, locally calculated checksum origin and actual installed --version output. The package, installed executables, SDK and build trees are excluded.

The original V2 audit failed only because Nsight's raw PROCESSES name was the exact15-byte Linux comm label Test-nativeStdp. That failure remains preserved. After independent source/closed-data review, Root approved V3 AUDIT ONLY against the same closed trace; no second GPU execution occurred. V3 accepts only the exact approved full path, full ASCII basename, or computed15-byte ASCII comm value, and records which matched. PID birth/UID/cwd/executable hashes and NVTX/globalPid/API/math gates remain required. Historical V1/V2/V3 source freezes, limited diffs, reviews, approvals and exact shell commands are retained for review; do not execute any of them as part of reading this bundle.

The review SQLite contains only one actual process row, one named NVTX window,17 successful same-thread launch/sync API rows,8 target kernel rows, their required safe name StringIds, and the four allowlisted target/global diagnostic texts. Every selected row and column is copied losslessly; original/subset row multisets and SQLite integrity are checked. Full raw reports/SQLite, unrelated processes/strings and environment tables are excluded. The original hashes are retained. positive_control_gate.review_safe.json is an explicit safe view that filters only unrelated/non-allowlisted diagnostic rows; all other gate fields are unchanged.

Incomplete CUDA/NVTX event warnings and disabled Unified Memory tracing are preserved. Thus the complete named algebra range and its observed kernel execution are demonstrated, while complete coverage of every event in the whole process is not claimed. The922,576-cell C29 transient failed before source evaluation in both profiled and plain attempts. It remains UNQUALIFIED;2.4 was not built, timing remains prohibited, no rotor lift or speed result follows from this small control, and all84 production CPU CFD results remain unchanged.
"""
put_bytes('README.md',readme.encode())
save('copy_provenance.json',{'copies':copies,'method':'Exclusive content writes, flush/fsync and immediate byte equality; no filesystem metadata copying','source_or_case_or_binary_mutations':False})
ast_count=0
for p in OUT.rglob('*.py'):ast.parse(p.read_text(),filename=str(p));ast_count+=1
for p in OUT.rglob('*'):
 if not p.is_file():continue
 require(p.suffix.lower() not in {'.deb','.zip','.gz','.so','.o','.nsys-rep','.qdstrm'},'Excluded artifact leaked')
 require(p.read_bytes()[:4]!=b'\x7fELF','ELF leaked')
save('curation_harness_proof.json',{'status':'SOURCE_EVIDENCE_CANDIDATE_FOR_ROOT_REVIEW_NOT_PUBLISHED','AST_parsed_sources_no_imports':ast_count,'original_evidence_sha_bound':True,'original_frozen_helpers_rehashed_unchanged':True,'copied_content_exact':True,'subset_selected_row_multisets_all_equal':all(x['equal'] for x in proof['selected_table_multisets'].values()),'subset_integrity_check':proof['integrity_check'],'subset_tables':list(proof['selected_table_multisets']),'excluded':['archives','ELF','SDK','build trees','raw reports','full SQLite','captured environment tables','unrelated process rows','unrelated StringIds'],'GPU_profile_application_build_CFD_or_timing_executed_by_curation':False,'installed_nsys_version_only_invoked':True,'default_global_Git_output_ZIP_changes':False})
files={str(p.relative_to(OUT)):sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()}
save('manifest.json',{'kind':'Current standalone Nsight2026.5.1 source/evidence-only publication candidate','files':files,'file_count_excluding_manifest':len(files),'bytes_excluding_manifest':sum((OUT/n).stat().st_size for n in files),'large_CFD_qualified':False,'timing_measured':False,'published_by_this_script':False})
print(json.dumps({'candidate':str(OUT),'manifest_sha256':sha(OUT/'manifest.json'),'files_including_manifest':len(files)+1,'bytes_including_manifest':sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file()),'subset_table_counts':{n:x['rows'] for n,x in proof['selected_table_multisets'].items()},'private_raw_unchanged':True,'GPU_rerun':False},indent=2))
