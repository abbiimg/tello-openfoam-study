#!/usr/bin/env python3
"""Record the actual direct solver child's identity and exit, including signal exits."""
import argparse,os,pathlib,re,signal,subprocess,sys
from strict_common import check_freeze,load_protocol,save,sha,utc
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--root",type=pathlib.Path,required=True);parser.add_argument("--case",type=pathlib.Path,required=True);parser.add_argument("--evidence",type=pathlib.Path,required=True);parser.add_argument("command",nargs=argparse.REMAINDER)
 args=parser.parse_args();load_protocol();check_freeze(args.root)
 command=args.command[1:] if args.command and args.command[0]=="--" else args.command
 if not command or not pathlib.Path(command[0]).is_absolute():raise RuntimeError("Absolute binary command required")
 binary=pathlib.Path(command[0]).resolve()
 if not binary.is_file():raise RuntimeError("Existing binary required")
 args.evidence.mkdir(parents=True,exist_ok=True);receipt=args.evidence/"solver_exit.json";log=args.evidence/"solver.log"
 if receipt.exists() or log.exists():raise RuntimeError("Refusing to overwrite prior solver attempt")
 dependencies=subprocess.check_output(["ldd",str(binary)],text=True)
 libraries={x:sha(x) for x in re.findall(r"=>\s+(/\S+)",dependencies) if pathlib.Path(x).is_file()}
 initial={"started_utc":utc(),"argv":command,"binary":str(binary),"binary_sha256":sha(binary),"case":str(args.case.resolve()),"wrapper_pid":os.getpid(),"environment":{k:os.environ.get(k) for k in ["WM_OPTIONS","WM_COMPILER","WM_MPLIB","FOAM_MEMORY_POOL","LD_PRELOAD","NSYS_NVTX_PROFILER_REGISTER_ONLY"]},"loaded_library_candidates_sha256":libraries,"ldd":dependencies}
 with log.open("xb") as stream:
  child=subprocess.Popen(command,cwd=args.case,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  pidfd=os.pidfd_open(child.pid);q=pathlib.Path("/proc")/str(child.pid)
  stat=(q/"stat").read_text();tail=stat[stat.rfind(")")+2:].split()
  identity={"pid":child.pid,"uid":q.stat().st_uid,"birth_start_ticks":int(tail[19]),"state_at_receipt":tail[0]}
  for name in ["cwd","exe"]:
   try:identity[name]=os.readlink(q/name)
   except OSError:identity[name]=None
  initial["actual_child"]=identity;save(args.evidence/"solver_start.json",initial)
  def forward(signum,frame):
   if child.poll() is None:
    try:signal.pidfd_send_signal(pidfd,signum)
    except ProcessLookupError:pass
  signal.signal(signal.SIGTERM,forward);signal.signal(signal.SIGINT,forward)
  returncode=child.wait();os.close(pidfd)
 data={**initial,"completed_utc":utc(),"return_code":returncode,"binary_sha256_after":sha(binary),"log":str(log),"log_sha256":sha(log),"actual_child_waited":True,"outer_profiler_status_is_separate":True}
 save(receipt,data);print("ACTUAL_SOLVER_CHILD_EXIT "+str(returncode),flush=True)
 return returncode if returncode>=0 else 128-returncode
if __name__=="__main__":sys.exit(main())
