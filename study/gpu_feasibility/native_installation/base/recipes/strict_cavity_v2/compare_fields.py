#!/usr/bin/env python3
"""Apply preregistered weighted field-parity thresholds to the matched mesh."""
import argparse,json,math,pathlib
from strict_common import check_freeze,field,load_protocol,save,utc
from check_cavity_flux import audit
def compare(root,cpu,gpu):
 protocol=load_protocol();check_freeze(root);g=protocol["proposed_cross_backend_field_gates"];rows=[]
 for t in protocol["required_gates"]["time_values"]:
  name=format(t,".12g");volumes=audit(cpu,name)["cell_volumes"]
  for key,vector in [("U",True),("p",False)]:
   a=field(cpu/name/key,vector=vector);b=field(gpu/name/key,vector=vector)
   sqdiff=[sum((y-x)**2 for x,y in zip(u,v)) for u,v in zip(a,b)] if vector else [(v-u)**2 for u,v in zip(a,b)]
   sqref=[sum(x*x for x in u) for u in a] if vector else [u*u for u in a]
   relative=math.sqrt(sum(v*d for v,d in zip(volumes,sqdiff)))/max(math.sqrt(sum(v*x for v,x in zip(volumes,sqref))),1e-30)
   maximum=math.sqrt(max(sqdiff));limit_rel=g["velocity_relative_L2_max"] if vector else g["pressure_relative_L2_max"];limit_abs=g["velocity_max_absolute_difference_m_per_s"] if vector else g["pressure_max_absolute_difference_m2_per_s2"]
   rows.append({"time":name,"field":key,"relative_L2":relative,"max_absolute":maximum,"relative_limit":limit_rel,"absolute_limit":limit_abs,"passed":relative<=limit_rel and maximum<=limit_abs})
 result={"checked_utc":utc(),"passed":all(x["passed"] for x in rows),"rows":rows,"pressure_offset_fitted":False,"speedup_measured":False};save(root/"field_parity_gate.json",result)
 if not result["passed"]:raise RuntimeError("Preregistered CPU/GPU field parity gate failed")
 return result
if __name__=="__main__":
 p=argparse.ArgumentParser();p.add_argument("root",type=pathlib.Path);p.add_argument("cpu",type=pathlib.Path);p.add_argument("gpu",type=pathlib.Path);a=p.parse_args();print(json.dumps(compare(a.root,a.cpu,a.gpu)))
