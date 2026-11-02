#!/usr/bin/env python3
"""Launch only the private CPU control as an auto-collected transient service."""
import datetime,json,os,pathlib,subprocess,time
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-cpu-control")
WORK=pathlib.Path(__file__).resolve().parent
def main():
 if os.geteuid()!=0:raise RuntimeError("Transient system service creation requires root")
 marker=P/"service.json"
 if marker.exists():
  previous=json.loads(marker.read_text())
  r=subprocess.run(["systemctl","is-active","--quiet",previous["unit"]])
  if r.returncode==0:print(json.dumps({"kept_active_unit":previous["unit"]}));return
 unit="native-cpu-control-"+datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")+".service"
 log=P/"logs"/(unit+".log")
 args=["systemd-run","--collect","--unit="+unit,"--uid=openfoam","--nice=15","--service-type=exec","--working-directory="+str(WORK),"--property=StandardInput=null","--property=StandardOutput=append:"+str(log),"--property=StandardError=append:"+str(log),"/usr/bin/python3",str(WORK/"build_cpu_control.py")]
 result=subprocess.run(args,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True)
 time.sleep(1)
 show=subprocess.check_output(["systemctl","show",unit,"--property=Id,MainPID,User,Nice,ActiveState,SubState,ControlGroup,CollectMode"],text=True)
 props=dict(x.split("=",1) for x in show.splitlines() if "=" in x)
 if props["User"]!="openfoam" or props["Nice"]!="15" or props["ActiveState"]!="active":raise RuntimeError("CPU service startup/property gate failed")
 evidence={"launched_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),"unit":unit,"argv":args,"systemd_output":result.stdout.strip(),"properties":props,"log":str(log),"budget":str(WORK/"build_budget.json"),"global_compiler_allocation":{"native_gpu":4,"SPUMA":2,"native_cpu":4,"maximum_combined":10},"no_global_configuration_change":True}
 marker.write_text(json.dumps(evidence,indent=2)+"\n");(P/"provenance"/(unit+".json")).write_text(json.dumps(evidence,indent=2)+"\n")
 print(json.dumps(evidence,indent=2))
if __name__=="__main__":main()
