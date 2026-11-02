#!/usr/bin/env python3
"""Generate a separate math-identical first-step capture app; no vendor edits/build."""
import difflib,json,pathlib,shutil
from strict_common import WORK,load_protocol,save,sha,utc
def main():
 load_protocol();source=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/source/OpenFOAM-v2606/applications/solvers/incompressible/icoFoam")
 target=pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar/strict_v2_application")
 if target.exists():raise RuntimeError("Refusing to overlay an existing capture application")
 shutil.copytree(source,target,ignore=shutil.ignore_patterns("linuxARM64*","*.o","*.dep","lnInclude"))
 original=(source/"icoFoam.C").read_text();text=original
 pairs=[('#include "pisoControl.H"','#include "pisoControl.H"\n#include <nvtx3/nvToolsExt.h>\n#include <cuda_runtime_api.h>'),('    while (runTime.loop())\n    {','    bool strictFirstStep = true;\n    while (runTime.loop())\n    {\n        if (strictFirstStep) nvtxRangePushA("STRICT_CAVITY_V2_FIRST_COMPLETE_STEP");'),('        runTime.printExecutionTime(Info);','        runTime.printExecutionTime(Info);\n        if (strictFirstStep)\n        {\n            const cudaError_t strictSync = cudaDeviceSynchronize();\n            if (strictSync != cudaSuccess)\n            {\n                FatalErrorInFunction << "Strict first-step CUDA completion failed: "\n                    << cudaGetErrorString(strictSync) << exit(FatalError);\n            }\n            nvtxRangePop();\n            strictFirstStep = false;\n        }')]
 for before,after in pairs:
  if text.count(before)!=1:raise RuntimeError("Annotation match is not unique")
  text=text.replace(before,after)
 # Reversal proves that all upstream equations/operations remain identical.
 reversed_text=text
 for before,after in reversed(pairs):reversed_text=reversed_text.replace(after,before)
 if reversed_text!=original:raise RuntimeError("Non-instrumentation source difference")
 (target/"icoFoam.C").write_text(text)
 files=(target/"Make/files").read_text().replace("$(FOAM_APPBIN)/icoFoam","$(FOAM_USER_APPBIN)/icoFoamStrictV2")
 (target/"Make/files").write_text(files)
 patch="".join(difflib.unified_diff(original.splitlines(keepends=True),text.splitlines(keepends=True),fromfile="pristine/icoFoam.C",tofile="strict_v2_application/icoFoam.C"))
 (WORK/"icoFoamStrictV2.patch").write_text(patch)
 save(WORK/"gpu_probe_source.json",{"generated_utc":utc(),"original":str(source/"icoFoam.C"),"original_sha256":sha(source/"icoFoam.C"),"source":str(target/"icoFoam.C"),"source_sha256":sha(target/"icoFoam.C"),"patch_sha256":sha(WORK/"icoFoamStrictV2.patch"),"math_source_reversal_matches":True,"changes":"NVTX first complete loop body plus checked device completion before pop; no equation edits","vendor_source_or_SDK_changed":False,"binary_name":"icoFoamStrictV2"})
 print(json.dumps({"source":str(target),"compiled":False}))
if __name__=="__main__":main()
