#!/usr/bin/env python3
"""Frozen strict-v2 numerical/child-exit validator; no solver execution."""
import argparse,json,math,pathlib,re
from strict_common import check_freeze,field,load_protocol,save,sha,utc
from check_cavity_flux import audit
def validate(root,case,evidence):
 protocol=load_protocol();check_freeze(root);g=protocol["required_gates"];receipt=json.loads((evidence/"solver_exit.json").read_text());text=(evidence/"solver.log").read_text()
 checks={"actual_solver_child_exit0":receipt["return_code"]==0 and receipt["actual_child_waited"],"binary_stable":receipt["binary_sha256"]==receipt["binary_sha256_after"],"End":bool(re.search(r"^End\s*$",text,re.M)),"log_tokens_finite":not bool(re.search(r"\b(?:nan|[-+]?inf(?:inity)?)\b",text,re.I))}
 times=[float(x) for x in re.findall(r"^Time = (\S+)",text,re.M)];expected=g["time_values"]
 checks["exact_five_times"]=len(times)==len(expected) and all(abs(x-y)<=g["time_absolute_tolerance"] for x,y in zip(times,expected))
 continuity=[float(x) for x in re.findall(r"time step continuity errors\s*:\s*sum local =\s*([^,]+)",text)]
 rows=[(name,float(a),float(b),int(it)) for name,a,b,it in re.findall(r"Solving for (p|Ux|Uy|Uz), Initial residual = ([^,]+), Final residual = ([^,]+), No Iterations (\d+)",text)]
 p=[x for x in rows if x[0]=="p"];u=[x for x in rows if x[0]!="p"]
 checks["ten_pressure_correctors"]=len(p)==g["pressure_corrector_count"]
 checks["ten_continuity_records"]=len(continuity)==g["continuity_entry_count"]
 checks["all_corrector_continuity"]=bool(continuity) and all(math.isfinite(x) and 0<=x<=g["all_corrector_local_continuity_max"] for x in continuity)
 checks["finite_residuals"]=all(math.isfinite(x) for row in rows for x in row[1:3])
 checks["pressure_absolute_tolerance"]=bool(p) and max(x[2] for x in p)<=g["all_pressure_final_residual_max"]
 checks["velocity_absolute_tolerance"]=bool(u) and max(x[2] for x in u)<=g["all_velocity_final_residual_max"]
 flux=[]
 for i,t in enumerate(expected):
  name=format(t,".12g");field(case/name/"U",vector=True);field(case/name/"p")
  result=audit(case,name,protocol["controls"]["deltaT"]);logged=continuity[2*i+1] if len(continuity)==10 else math.inf
  result["own_final_corrector_logged"]=logged;result["own_final_corrector_difference"]=abs(result["dimensionless_local_continuity"]-logged)
  checks["independent_local_"+name]=result["dimensionless_local_continuity"]<=g["independent_flux_each_written_step_local_max"]
  checks["independent_global_"+name]=abs(result["dimensionless_global_continuity"])<=g["independent_flux_each_written_step_abs_global_max"]
  checks["independent_matches_log_"+name]=result["own_final_corrector_difference"]<=max(1e-12,1e-3*abs(logged))
  flux.append(result)
 checks["all_written_fields_finite"]=True
 result={"validated_utc":utc(),"case":str(case),"evidence":str(evidence),"protocol_sha256":sha(pathlib.Path(__file__).resolve().parent/"protocol.json"),"passed":all(checks.values()),"checks":checks,"times":times,"peak_all_corrector_local_continuity":max(continuity,default=None),"pressure_residual_rows":p,"velocity_residual_rows":u,"independent_flux":flux,"original_stock_screen_unchanged":True,"speedup_measured":False}
 save(evidence/"numerical_gate.json",result)
 if not result["passed"]:raise RuntimeError("Strict numerical gate failed: "+str([k for k,v in checks.items() if not v]))
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("root",type=pathlib.Path);p.add_argument("case",type=pathlib.Path);p.add_argument("evidence",type=pathlib.Path);a=p.parse_args();r=validate(a.root,a.case,a.evidence);print(json.dumps({"passed":r["passed"],"peak_local":r["peak_all_corrector_local_continuity"]}))
