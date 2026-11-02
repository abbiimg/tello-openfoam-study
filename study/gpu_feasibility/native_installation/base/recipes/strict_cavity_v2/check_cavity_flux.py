#!/usr/bin/env python3
"""Independent ASCII face-flux/geometry audit for the exact400-cell cavity fixture."""
import argparse,json,math,pathlib,re
def clean(path):
 text=path.read_text()
 if not re.search(r"format\s+ascii\s*;",text):raise ValueError("ASCII input required: "+str(path))
 text=re.sub(r"/\*.*?\*/|//[^\n]*","",text,flags=re.S)
 header=re.search(r"\bFoamFile\s*\{[^{}]*\}",text,re.S)
 if not header:raise ValueError("Missing FoamFile header")
 return text[header.end():].strip()
def mesh_list(path):
 match=re.fullmatch(r"\s*(\d+)\s*\((.*)\)\s*",clean(path),re.S)
 if not match:raise ValueError("Unsupported mesh list: "+str(path))
 return int(match[1]),match[2]
def labels(path):
 n,body=mesh_list(path);data=[int(x) for x in body.split()]
 if len(data)!=n:raise ValueError("Label count mismatch")
 return data
def scalar_values(text,key,expected):
 m=re.search(r"\b"+key+r"\s+nonuniform\s+List<scalar>\s+(\d+)\s*\(([^()]*)\)\s*;",text,re.S)
 if m:
  values=[float(x) for x in m[2].split()]
  if int(m[1])!=expected or len(values)!=expected:raise ValueError("Scalar field count mismatch")
  return values
 m=re.search(r"\b"+key+r"\s+uniform\s+([-+0-9.eE]+)\s*;",text)
 if m:return [float(m[1])]*expected
 raise ValueError("Unsupported scalar field encoding")
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def audit(case,time_name,dt=.005):
 mesh=case/"constant/polyMesh";owner=labels(mesh/"owner");neighbour=labels(mesh/"neighbour")
 np,body=mesh_list(mesh/"points");points=[tuple(float(x) for x in q.split()) for q in re.findall(r"\(([^()]*)\)",body)]
 nf,body=mesh_list(mesh/"faces");faces=[]
 for size,ids in re.findall(r"(\d+)\s*\(([^()]*)\)",body):
  ids=[int(x) for x in ids.split()]
  if len(ids)!=int(size):raise ValueError("Face vertex count mismatch")
  faces.append(ids)
 if len(points)!=np or len(faces)!=nf or len(owner)!=nf:raise ValueError("Mesh count mismatch")
 nc=max(owner+neighbour)+1
 if (nc,nf,len(neighbour),np)!=(400,1640,760,882):raise ValueError("Exact400-cell cavity mesh required")
 volumes=[0.0]*nc
 for fi,vertices in enumerate(faces):
  p0=points[vertices[0]];contribution=0.0
  for j in range(1,len(vertices)-1):contribution+=dot(p0,cross(points[vertices[j]],points[vertices[j+1]]))/6
  volumes[owner[fi]]+=contribution
  if fi<len(neighbour):volumes[neighbour[fi]]-=contribution
 if not all(math.isfinite(x) and x>0 for x in volumes):raise ValueError("Invalid independently reconstructed cell volumes")
 extents=[max(x[j] for x in points)-min(x[j] for x in points) for j in range(3)]
 box_volume=math.prod(extents)
 if not box_volume>0 or abs(sum(volumes)-box_volume)>1e-12:raise ValueError("Cell-volume sum differs from the Cartesian fixture box")
 phi_text=clean(case/time_name/"phi")
 dims=re.search(r"dimensions\s*\[([^]]*)\]",phi_text)
 if not dims or [int(x) for x in dims[1].split()]!=[0,3,-1,0,0,0,0]:raise ValueError("Volumetric phi dimensions required")
 phi=scalar_values(phi_text,"internalField",len(neighbour))+[0.0]*(nf-len(neighbour))
 boundary=clean(mesh/"boundary");covered=set()
 for patch in ["movingWall","fixedWalls","frontAndBack"]:
  block=re.search(r"\b"+patch+r"\s*\{([^{}]*)\}",boundary,re.S)
  field=re.search(r"\b"+patch+r"\s*\{([^{}]*)\}",phi_text,re.S)
  if not block or not field:raise ValueError("Expected fixture patch unavailable")
  start=int(re.search(r"startFace\s+(\d+)\s*;",block[1])[1]);count=int(re.search(r"nFaces\s+(\d+)\s*;",block[1])[1])
  if patch=="frontAndBack":
   if not re.search(r"type\s+empty\s*;",field[1]):raise ValueError("Expected empty2D patch")
   values=[0.0]*count
  else:values=scalar_values(field[1],"value",count)
  phi[start:start+count]=values;covered.update(range(start,start+count))
 if covered!=set(range(len(neighbour),nf)):raise ValueError("Boundary coverage mismatch")
 if not all(math.isfinite(x) for x in phi):raise ValueError("Nonfinite phi")
 imbalance=[0.0]*nc
 for fi,flux in enumerate(phi):
  imbalance[owner[fi]]+=flux
  if fi<len(neighbour):imbalance[neighbour[fi]]-=flux
 total=sum(volumes)
 return {"method":"Independent signed face balance and face-triangle tetrahedral cell volumes from ASCII points/faces/owner/neighbour/phi; empty2D faces contribute zero","case":str(case),"time":time_name,"deltaT":dt,"cells":nc,"faces":nf,"mesh_extents_m":extents,"total_volume":total,"box_volume_crosscheck":box_volume,"min_cell_volume":min(volumes),"max_cell_volume":max(volumes),"cell_volumes":volumes,"dimensionless_local_continuity":dt*sum(abs(x) for x in imbalance)/total,"dimensionless_global_continuity":dt*sum(imbalance)/total,"max_cell_dimensionless_divergence":dt*max(abs(x)/v for x,v in zip(imbalance,volumes)),"net_boundary_flux_m3_per_s":sum(phi[len(neighbour):]),"finite":True}
if __name__=="__main__":
 parser=argparse.ArgumentParser();parser.add_argument("case",type=pathlib.Path);parser.add_argument("time");parser.add_argument("--deltaT",type=float,default=.005)
 args=parser.parse_args();print(json.dumps(audit(args.case,args.time,args.deltaT),indent=2))
