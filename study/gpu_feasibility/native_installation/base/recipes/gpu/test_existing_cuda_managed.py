#!/usr/bin/env python3
"""Exercise basic managed-memory coherence with the existing CUDA runtime, not stdpar."""
import ctypes as C,json,os,pathlib,time
from datetime import datetime,timezone
P=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
LIB=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/pressure-offload/cuda13/lib/libcudart.so")
def main():
 os.nice(15)
 lib=C.CDLL(str(LIB))
 lib.cudaMallocManaged.argtypes=[C.POINTER(C.c_void_p),C.c_size_t,C.c_uint]
 lib.cudaMemset.argtypes=[C.c_void_p,C.c_int,C.c_size_t]
 lib.cudaFree.argtypes=[C.c_void_p]
 ptr=C.c_void_p();calls=[]
 def check(name,rc):
  calls.append({"call":name,"return_code":rc})
  if rc:raise RuntimeError(name+" failed with CUDA status"+str(rc))
 start=time.monotonic()
 count=1<<17
 check("cudaMallocManaged",lib.cudaMallocManaged(C.byref(ptr),count*C.sizeof(C.c_uint32),1))
 try:
  values=(C.c_uint32*count).from_address(ptr.value)
  for i in range(count):values[i]=i^0x13579bdf
  check("cudaMemset 0x5a",lib.cudaMemset(ptr,0x5a,count*4))
  check("cudaDeviceSynchronize after GPU fill",lib.cudaDeviceSynchronize())
  after_fill=all(values[i]==0x5a5a5a5a for i in range(count))
  for i in range(count):values[i]=i+7
  check("cudaMemset zero",lib.cudaMemset(ptr,0,count*4))
  check("cudaDeviceSynchronize after GPU clear",lib.cudaDeviceSynchronize())
  after_clear=all(values[i]==0 for i in range(count))
 finally:check("cudaFree",lib.cudaFree(ptr))
 result={"kind":"Actual basic CUDA managed-memory coherence smoke using pre-existing CUDA13.0 runtime; not stdpar, not CFD, not a kernel-profile proof","completed_utc":datetime.now(timezone.utc).isoformat(),"library":str(LIB),"elements":count,"bytes":count*4,"calls":calls,"host_read_after_device_fill_passed":after_fill,"host_read_after_device_clear_passed":after_clear,"passed":after_fill and after_clear,"elapsed_s":time.monotonic()-start,"synchronization":"CPU access occurs only before device operations or after cudaDeviceSynchronize; no concurrent CPU/GPU access required.","no_global_changes":True}
 (P/"provenance/basic_managed_memory_gate.json").write_text(json.dumps(result,indent=2)+"\n")
 print(json.dumps(result),flush=True)
 if not result["passed"]:raise RuntimeError("Managed-memory coherence did not pass")
if __name__=="__main__":main()
