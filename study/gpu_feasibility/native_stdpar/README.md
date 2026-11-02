# Official stdpar OpenFOAM: separate, untested GPU route

Assessment date: 2026-11-02 UTC. This route was researched and the local environment inspected. It was **not installed, built, ported or benchmarked here**. The lift study continues with Foundation OpenFOAM 14 on CPU. The measured Ginkgo experiment elsewhere in this folder concerns a different pressure-only adapter.

## What the primary sources establish

OpenCFD's [v2606 infrastructure announcement](https://www.openfoam.com/news/main-news/openfoam-v2606/infrastructure) describes GPU offloading of field algebra, linear solvers and related operations using C++ standard parallelism. Its separate-branch description is the status at that release. At this assessment, the [official core/develop repository](https://gitlab.com/openfoam/core/openfoam/-/tree/develop) identifies a GPU-branch merge in commit `68a81857`, API 2609. The current development source was not downloaded or built during this check.

The [authors' PASC paper description](https://pasc-conference.org/pasc26/presentation/?id=pap122&sess=sess174) reports tests of incompressible `icoFoam` and `simpleFoam`, with speedups from 0.5 to 18 across different cases and systems. This is relevant full-flow work; the Foundation/Ginkgo result cannot establish its performance.

The user's [GPU OpenFOAM slides](https://wiki.openfoam.com/images/4/45/GpuFOAM.pdf) report the following average speed ratios for an `icoFoam`/PCG cavity benchmark, GH200 versus a 72-core Grace CPU:

| Cells | Reported average CPU/GPU speed ratio |
|---:|---:|
| 1 million | 0.31 |
| 8 million | 2.6 |
| 64 million | 4.5 |

A ratio below one means the GPU took longer. Our fine mesh has 922,576 cells on RTX Spark N1X. Different physics, algorithms and hardware prevent treating this table as a prediction for our case. The larger-grid speedup is real evidence for that benchmark, not a measured speedup for this study.

## Local evidence and compatibility

[local_inventory.json](local_inventory.json) records the inspection and a fresh CUDA Driver API query. The environment has ARM64 Foundation 14 and a private CUDA `nvcc`, but no installed NVIDIA HPC SDK `nvc++` or ready native stdpar OpenFOAM executable/container. `nvcc` alone does not supply the required stdpar compiler.

The GPU reports compute capability 12.1. The [NVHPC 26.9 compiler guide](https://docs.nvidia.com/hpc-sdk/compilers/hpc-compilers-user-guide/) documents support through 12.1 and an ARM64 toolchain. It distinguishes managed memory, which covers suitable dynamic allocations, from full unified memory, which also permits broader host-data access. These are compiler capabilities, not a successful test of this computer's runtime.

Local device queries succeeded and returned managed memory = 1, concurrent managed access = 0, pageable memory access = 0, pageable access using host page tables = 0, and direct managed access from host = 0. Thus the GH200 unified-memory defaults cannot be assumed suitable. These flags do **not** prove managed-mode stdpar is impossible.

The [official GPU project's build wiki](https://gitlab.com/openfoam/gpu/openfoam-ecse/-/wikis/build) documents ARM64 NVIDIA GPU build rules and a managed-memory alternative to its GH200 configuration. Its [dependency notes](https://gitlab.com/openfoam/gpu/openfoam-ecse/-/wikis/dependencies) describe a CUDA-enabled Umpire memory pool. These older feature-branch instructions are guidance: the exact merged development build rules were not retrieved and verified byte for byte.

Our actuator is Foundation 14 `codedFvModel` source SHA-256 `29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd`. It uses host callbacks, cached cell weights, reductions and direct momentum-source access. A target-branch port must preserve source normalization, power/work integration, force sign, controller lifecycle and initial state. Existing host loops do not automatically offload. Any parallel accumulation must handle cells shared by overlapping rotors safely. Target source APIs, dynamic compilation and `pimpleFoam` compatibility remain unverified.

## Gate before adoption

A separate trial would require a pinned private ARM64 NVHPC/GPU OpenFOAM build, a managed-memory stdpar smoke test, a supported incompressible tutorial, and an actuator port. It would then need matched CPU/GPU numerical and end-to-end timing checks, including startup and output costs. GPU-compatible solver/smoother changes also require validation. No build-time or speedup estimate is claimed.

The current study's CPU results and the earlier measured Ginkgo benchmark retain their original methods and provenance. This feasibility check does not change any CFD input, result, production backend or GPU acceptance decision.
