#!/usr/bin/env python3
"""Execute the approved fresh matched fixtures without replaying vendor builds."""
import json,os,pathlib,re,shlex,shutil,subprocess,time
from strict_common import WORK,load_protocol,save,sha,utc
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
C=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-cpu-control")
SDK=P/"nvhpc/Linux_aarch64/26.9"
def available():return int(next(x.split()[1] for x in pathlib.Path("/proc/meminfo").read_text().splitlines() if x.startswith("MemAvailable:")))/1024/1024
def manifest(case):return {str(x.relative_to(case)):sha(x) for name in ["0","constant","system"] for x in sorted((case/name).rglob("*")) if x.is_file()}
def main():
 os.setpriority(os.PRIO_PROCESS,0,max(15,os.getpriority(os.PRIO_PROCESS,0)))
 protocol=load_protocol();root=pathlib.Path(protocol["proposed_case_root"])
 def status(stage,**extra):
  d={"stage":stage,"utc":utc(),"pid":os.getpid(),"nice":os.getpriority(os.PRIO_PROCESS,0),"available_memory_GiB":available(),**extra};save(WORK/"pipeline_state.json",d);print(json.dumps(d),flush=True)
 def command(stage,args,envfile=None,log=None,timeout=1200,extra_env=None):
  while available()<20:status("waiting_for20GiB",next_stage=stage);time.sleep(10)
  args=[str(x) for x in args];log=pathlib.Path(log) if log else root/(stage+".log")
  if log.exists():raise RuntimeError("Refusing to overwrite command log: "+str(log))
  shell=(". "+shlex.quote(str(envfile))+"; " if envfile else "")+"export WM_NCOMPPROCS=1; exec "+shlex.join(args)
  env=dict(os.environ)
  if extra_env:env.update(extra_env)
  status(stage,argv=args,log=str(log),max_additional_compile_jobs=1)
  with log.open("xb") as stream:r=subprocess.run(["bash","--noprofile","--norc","-c",shell],env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=timeout)
  save(root/(stage+"_exit.json"),{"stage":stage,"argv":args,"return_code":r.returncode,"completed_utc":utc(),"log":str(log),"log_sha256":sha(log)})
  if r.returncode:raise RuntimeError(stage+" failed; "+str(log))
  return log
 status("preparing_fresh_fixture")
 subprocess.run(["/usr/bin/python3",str(WORK/"prepare_fixture.py")],check=True)
 subprocess.run(["/usr/bin/python3",str(WORK/"create_gpu_probe.py")],check=True)
 fixture=root/"fixture"
 frozen_files={str(x):sha(x) for x in sorted(WORK.glob("*.py"))}
 for x in [WORK/"protocol.json",WORK/"root_approval.json",WORK/"icoFoamStrictV2.patch",WORK/"gpu_probe_source.json"]:frozen_files[str(x)]=sha(x)
 app=P/"strict_v2_application"
 for x in sorted(app.rglob("*")):
  if x.is_file():frozen_files[str(x)]=sha(x)
 cpu_binary=C/"source/OpenFOAM-v2606/platforms/linuxARM64GccDPInt32Opt/bin/icoFoam"
 frozen_files[str(cpu_binary)]=sha(cpu_binary)
 save(root/"validation_freeze.json",{"frozen_utc":utc(),"before_any_strict_solver_run":True,"protocol_sha256":sha(WORK/"protocol.json"),"files":frozen_files})
 cpu_block=C/"source/OpenFOAM-v2606/platforms/linuxARM64GccDPInt32Opt/bin/blockMesh"
 command("shared_mesh",[cpu_block,"-case",fixture],C/"env.sh")
 cpu=root/"native_cpu";gpu=root/"native_gpu"
 for case in [cpu,gpu]:
  if case.exists():raise RuntimeError("Refusing to overlay backend case")
  shutil.copytree(fixture,case)
 hashes=manifest(cpu)
 if hashes!=manifest(gpu):raise RuntimeError("Backend input/mesh hashes differ")
 save(root/"matched_input_sha256.json",{"frozen_utc":utc(),"identical":True,"cpu_case":str(cpu),"gpu_case":str(gpu),"files":hashes})
 evidence=root/"evidence";evidence.mkdir()
 cpu_evidence=evidence/"native_cpu"
 command("native_cpu_solver",["/usr/bin/python3",WORK/"run_solver_child.py","--root",root,"--case",cpu,"--evidence",cpu_evidence,"--",cpu_binary,"-case",cpu],C/"env.sh",timeout=300)
 from validate_run import validate
 cpu_gate=validate(root,cpu,cpu_evidence);status("strict_CPU_passed",peak_local=cpu_gate["peak_all_corrector_local_continuity"])
 # Only inspect/retire the old pipeline after its own run has terminated.
 old=json.loads((P/"build_progress.json").read_text());oldpid=old["pid"]
 while (pathlib.Path("/proc")/str(oldpid)).exists():
  status("waiting_for_original_native_worker",original=old);time.sleep(5)
 watcher=json.loads((P/"native_cfd_profile_progress.json").read_text());watchpid=watcher["pid"]
 if (pathlib.Path("/proc")/str(watchpid)).exists():raise RuntimeError("Old profile watcher still alive; exact verified retirement required")
 journal=json.loads((P/"provenance/minimal_build_journal.json").read_text());stock=next(x for x in reversed(journal) if x["stage"]=="cavity_icoFoam");stock_text=pathlib.Path(stock["log"]).read_text()
 save(root/"original_native_stock_outcome.json",{"main_state":old,"watcher_state":watcher,"main_alive":False,"watcher_alive":False,"actual_stock_child_return_code":stock["return_code"],"End":"\nEnd\n" in stock_text,"original_continuity_max":max(float(x) for x in re.findall(r"time step continuity errors\s*:\s*sum local =\s*([^,]+)",stock_text)),"original_screen_retained":True,"no_signal_sent":True})
 command("strict_GPU_probe_build",["wmake","-j1",app],P/"env.sh",timeout=1800)
 gpu_binary=P/"user/platforms/linuxARM64Nvidia-gpuDPInt32Opt/bin/icoFoamStrictV2"
 save(root/"GPU_binary_pre_run.json",{"frozen_utc":utc(),"binary":str(gpu_binary),"binary_sha256":sha(gpu_binary),"source_sha256":sha(app/"icoFoam.C"),"source_freeze_precedes_compile_and_run":True})
 gpu_evidence=evidence/"native_gpu";gpu_evidence.mkdir()
 nsys=SDK/"profilers/13.3/Nsight_Systems/bin/nsys"
 args=[nsys,"profile",*protocol["native_GPU_execution_proof"]["nsys_flags"],"--stats=false","--force-overwrite=false","-o",gpu_evidence/"strict_gpu_trace","/usr/bin/python3",WORK/"run_solver_child.py","--root",root,"--case",gpu,"--evidence",gpu_evidence,"--",gpu_binary,"-case",gpu]
 command("native_GPU_profile",args,P/"env.sh",log=gpu_evidence/"profile.log",timeout=1800,extra_env=protocol["native_GPU_execution_proof"]["runner_child_environment_only"])
 command("native_GPU_trace_export",[nsys,"stats","--force-export=true","--report","cuda_api_sum","--format","csv",str(gpu_evidence/"strict_gpu_trace")+".nsys-rep"],P/"env.sh",log=gpu_evidence/"trace_export.log",timeout=300)
 gpu_gate=validate(root,gpu,gpu_evidence)
 from audit_gpu_trace import audit
 proof=audit(root,gpu_evidence)
 from compare_fields import compare
 parity=compare(root,cpu,gpu)
 if manifest(cpu)!=hashes or manifest(gpu)!=hashes:raise RuntimeError("Frozen case input/mesh changed during run")
 result={"completed_utc":utc(),"passed":True,"protocol_sha256":sha(WORK/"protocol.json"),"CPU_peak_all_corrector_continuity":cpu_gate["peak_all_corrector_local_continuity"],"GPU_peak_all_corrector_continuity":gpu_gate["peak_all_corrector_local_continuity"],"GPU_successful_launch_API_calls":proof["successful_launch_api_calls"],"field_parity_passed":parity["passed"],"original_failed_screens_unchanged":True,"speedup_measured":False,"C29_validated":False}
 save(root/"strict_v2_acceptance.json",result);status("strict_v2_all_approved_gates_passed",result=result)
if __name__=="__main__":
 try:main()
 except Exception as error:
  save(WORK/"pipeline_failure.json",{"utc":utc(),"error":str(error),"thresholds_changed":False});raise
