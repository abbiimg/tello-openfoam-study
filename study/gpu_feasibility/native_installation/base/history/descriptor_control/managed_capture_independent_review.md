# Managed capture and application ownership review

Read-only review, 2 November 2026. The source pattern and the completed descriptor control support a managed-memory descriptor hazard. The exact faulting instruction in the full rotor initialization remains unattributed. No compiler, CFD, GPU test or target process was launched by this reviewer; only these review artifacts were written.

NVIDIA’s 26.9 guide distinguishes an accessible element buffer from the container object used to find it. Managed mode does not automatically make stack/static objects accessible to GPU code. The guide discusses heap-owning containers and extracting element pointers; its scalar capture example uses value capture. These restrictions are relevant here. [NVIDIA guide, §8.2.5.2](https://docs.nvidia.com/hpc-sdk/compilers/hpc-compilers-user-guide/#data-management-in-parallel-algorithms). A separate NVIDIA staff example explains why a stack composite descriptor fails while a dynamically allocated descriptor works. Its old hardware-availability statement is not used as a current hardware claim. [NVIDIA forum](https://forums.developer.nvidia.com/t/stdpar-runtime-crash-related-to-stack-memory/279901).

Local source establishes the access chain: `surfaceInterpolationScheme.C:250` aliases `vfi` to the field; its inner `[&]` kernel at289–292 subscripts that descriptor. `Field` inherits `List`→`UList`; `UList` contains `v_` at108, and its subscript at`UListI.H:449` reads that member. `apply_policy` at`UListI.H:35–48` selects GPU policy only with offload enabled and length≥1000 (`ListPolicy.H:164–166`). The 760-face cavity therefore did not test this interpolation kernel. Exact source hashes and paths are in the JSON companion.

The owner’s frozen diagnostic (`descriptor_control_results.json`, SHA`6ab17b91…`) uses one binary: raw managed data at4096 passes; the same reference-capture kernel with a managed-heap descriptor passes; stack descriptor at400/sequential passes; stack descriptor at4096/offloaded aborts−6. Descriptor attributes distinguish stack type0 from heap type3 while both array buffers are type3. This establishes the failure class on this installation, not the full case’s exact operand.

## Application-local ownership inventory

| Location | Owning descriptors to cover |
|---|---|
| `createC29Fields.H` | p, U, phi from createPhi.H, nuEff |
| Initial audit scope | initialU, initialP, initialPhi |
| Momentum helper | nuFace, devTauCorrFlux |
| Euler helper | dPhi, coupling |
| Pressure loop | rAU, HbyA, phiHbyA, pEqn |
| Host-source wrapper | temporary source matrix |

`fvMatrix.H:166–177` stores source and boundary-coefficient Field descriptors inline. Heap-owning the application matrices therefore covers those descriptors too. `tUEqn`, predictor and helper-result `tmp<>` objects already own heap objects; retain them. No evidence justifies moving host-only controls, snapshots or dimensioned constants. Library-internal automatic captures remain outside this inventory and still need runtime coverage.

Use local owners plus the existing references, preserving constructors, IO/registry choices, expressions and lexical lifetimes. Keep checked fences before destruction. Require type3 for each owning object, its primitive/inline Field descriptor, and its separate buffer. In particular, check U before constructing phi: the existing data-only audit occurs after the failing operation. Observe geometry/addressing/weight and old-time descriptors at their natural accesses; do not prime oldTime history just to inspect it. Keep the separate strict-pressure numerical proposal orthogonal.

A raw-pointer/value-capture kernel is the other narrow option. Preserve the original interpolation arithmetic/addressing and boundary handling. Do not blindly capture owning Fields by value, and do not assume every generic SFType has `cdata()`: this template also handles stateless `geometricOneField`.

## Sanitizer limitation

The failed injection attempt supplies no valid memory-check result. NVIDIA’s relevant forum guidance recommends locating `cuInit()` with a GDB call stack, then deferring a global-initializer call if that is the cause. It does not provide a universal flag workaround. [NVIDIA early-initialization thread](https://forums.developer.nvidia.com/t/getting-cuda-initialized-before-the-sanitizer-but-not-sure-how/344601). `require-cuda-init=no` concerns targets that do not use CUDA; `injection-path` selects tool libraries. Neither is documented as a general early-initialization repair. [Compute Sanitizer options](https://docs.nvidia.com/compute-sanitizer/ComputeSanitizer/index.html).

No proposed ownership diff was available at review time. Source review can admit a controlled candidate, but acceptance still requires same-source CPU/GPU builds, exact full-size startup fields, the individual five-step gates and actual coverage of the large interpolation path.

