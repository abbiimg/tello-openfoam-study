# SPUMA review candidate: bounded GPU functional test

SPUMA v2512 at `1ff2d45c002b7afb599b9dd8c4c6874666242349` built privately on ARM64
and passed a distinct, preregistered five-step CUDA cavity functional test.
It reached 0.025 s with actual icoFoam and Allrun returncodes zero. This is an
installation/coverage result, not a rotor result, steady cavity benchmark,
CPU accuracy-equivalence claim or speed comparison.

The original 100-step/0.5 s fixture did **not** pass. Its loose first pressure
correction (`relTol=0.05`) exceeded the original all-corrector continuity screen;
the observed maximum was 0.000255613348367.
It was intentionally stopped after 12 completed steps,
with actual child returncode -15. The connector's stop request killed only its
outer shell; a verified pidfd stop of the orphaned solver allowed the child
wrapper to record its real returncode and flush the partial trace. The original
input, logs, trace, old source/patch and binary hashes remain documented. The old
ELF binary is retained privately and excluded from this export.

## Distinct strict fixture and unchanged acceptance limits

The new fixture starts from fresh stock initial fields: 400 cells, dt 0.005,
five steps through 0.025, output each step at precision 17. Both pressure
correctors use `relTol=0` at the original absolute tolerance 1e-6. The selected
GPU numerical path is aDIC and twoStageSymGaussSeidel. Mesh, viscosity, initial
fields and boundary conditions remain the stock cavity. The all-corrector
continuity limit was not relaxed; the shorter/tighter protocol and exact
mechanical validator hashes were recorded before the new run.

- Peak local continuity over every corrector: 8.77077684475e-09
  (required ≤1e-5).
- Independent CPU sum of final saved internal and boundary flux imbalance:
  6.92117027084e-09 (required <1e-5).
- Maximum pressure/U final residual: 9.8995021988e-07 /
  9.65924767314e-06.
- All five saved U, p and phi fields are finite; final physical/recirculation,
  closed-wall flux and pressure-reference checks passed.

## What establishes GPU execution

The independent core marker uses SPUMA's own `foamExecutor::parallelFor` to write
a CUDA DEVICE-only output, with 65,536 exact value checks and an exact double
reduction. It also verifies SPUMA's actual 1 GiB managed fixed pool. That passed
marker is retained separately and was not rerun or replaced.

The strict CFD binary has only recorded NVTX annotations added. Nsight captured
one complete first time-step body, after initialization, then stopped collecting
while the same child completed four more steps. Inside that named range on its
own exact globalTid, the audit observed 2445
successful CUDA launch API calls, no failed launch/synchronization calls, and
a successful device/context synchronization after the last launch API.
The documented globalTid decoding and the trace's PROCESSES table independently
match that thread to the actual child PID 367774; its birth/cwd identity is in
the receipt. Both owned case process lists are empty after completion.
API counts can include runtime and driver layers and are not unique kernels.
No GPU kernel-activity timeline or complete device residence is claimed.
The actual child exit receipt is independent of profiler/Allrun status; binary,
core, finiteVolume, observer and environment hashes match at start and completion.

The raw-string range capture uses the documented child-only
`NSYS_NVTX_PROFILER_REGISTER_ONLY=0` setting. See the
[NVIDIA Nsight Systems guide](https://docs.nvidia.com/nsight-systems/UserGuide/).

## Build pins, fixes and reproduction

The private build reuses read-only NVHPC 26.9 and CUDA 13.3, with SM121,
`have_cuda=true`, `have_umpire=false`, `FOAM_SIGFPE=false` and the explicit
fixedSizeMemoryPool. Umpire was inspected/staged but was not used by this route.
No global compiler, driver, shell profile or OpenFOAM connector configuration
changed. No completed rotor-study input/result changed.

NVHPC warns (#3560-D) that CUDA C++ in nvc++ is unsupported and recommends nvcc.
The pinned upstream rules use nvc++ for this path; actual functional gates passed,
but that vendor-support caveat remains. The finiteVolume link also hit the
confirmed AArch64 GOT limit in a generated CUDA registration stub. A private GCC
trampoline changes only that exact stub's -fpic to -fPIC. The relink passed with
all 432 cached objects byte- and timestamp-identical. Failure logs, forwarded
arguments and the inventory are retained. The SDK/system compiler stayed intact.

Recipes and the exact two case setups are included. They retain task-specific
paths/guards and intentionally refuse to overwrite completed evidence; inspect
and adapt paths in a fresh private tree. Fetch the exact upstream pin, source
only the private environment, build the minimal libraries/apps, apply recorded
annotation patches, and use the provided core marker source and strict case.
The historical core-marker preparer requires its original concurrent base-build
stage; after a complete build, compile that source in a fresh wmake app with
`EXE_INC = -I$(LIB_SRC)/OpenFOAM/lnInclude` and `EXE_LIBS = -lcudart`, then run
with `-pool fixedSizeMemoryPool -poolSize 1`. Do not rerun the evidence cases.

The large SDK, full source tree, build objects and all binaries are excluded.
Raw traces are functional coverage evidence under build load; none of their
durations should be used to infer speed. No actuator model was ported here.


The review candidate omits the raw .nsys-rep files and full trace SQLite, which remain private with recorded hashes. It supplies a lossless SQLite subset containing only the API/NVTX/process rows used by the frozen checks and only their referenced safe names. Environment/unrelated metadata is excluded; see review_trace_subset.json and its exact extraction recipe.
