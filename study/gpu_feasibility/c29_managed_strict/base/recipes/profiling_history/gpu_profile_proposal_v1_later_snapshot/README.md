This is a source-only proposal for one native GPU five-step functional profile. Nothing here has been run against the case. It changes no source, build, case, control, receipt, permission, SDK or library. Root owns runtime and must first pass the external F14-to-CPU strict numerical gate.

The future outer runner requires both an explicit Root approval JSON and an existing fresh five-step receipt, plus the explicit --execute-approved-receipt flag. It never issues a receipt or enables a permission. The approval must bind protocol.json and helper_manifest.json SHA256, the receipt path/hash, and the exact shared-startup and external F14-to-CPU numerical gate paths/hashes with root_asserted_pass true. A case's allowFive flag alone cannot authorize this runner.

Approval schema (a contract only; this example is not an approval):

```
{
  "decision": "APPROVED_FOR_ONE_GPU_FIVE_STEP_FUNCTIONAL_PROFILE",
  "protocol_sha256": "ROOT_REVIEWED_PROTOCOL_HASH",
  "helper_manifest_sha256": "ROOT_REVIEWED_HELPER_MANIFEST_HASH",
  "launch_receipt": {"path": "ABSOLUTE_FRESH_RECEIPT", "sha256": "HASH"},
  "exact_shared_startup_gate": {"path": "ABSOLUTE_GATE", "sha256": "HASH", "root_asserted_pass": true},
  "f14_to_cpu_strict_numerical_gate": {"path": "ABSOLUTE_EXTERNAL_ROOT_GATE", "sha256": "HASH", "root_asserted_pass": true}
}
```

The outer runner verifies the original receipt before profiler injection. The actual-child wrapper rechecks the receipt-bound bytes/mtime and freshness immediately before its direct Popen. It verifies that any injected loader additions belong to the pinned Nsight installation and that original loader components remain in order. It passes the inherited LD_PRELOAD unchanged. No extra return observer is needed: actual SQLite CUDA API rows must contain non-null returnValue values. The companion Foam receipt is hash-bound to the outer check.

Installed Nsight help confirms --discard-environment=true. Capture uses cuda/nvtx, no CPU sampling/context switches, the FIRST C29_NATIVE_TIME_STEP occurrence, stop at its end, kill=none, process-tree tracing and wait=all. NSYS_NVTX_PROFILER_REGISTER_ONLY=0 applies only to this profile child environment. The remaining four steps continue after capture stops. The direct solver's PID, birth ticks, UID, cwd, executable, binary SHA, actual wait returncode and sampled loaded libraries are separate from profiler/export statuses. Timeout signals use the exact owned child's pidfd; no device reset or unrelated process stop exists.

The validator requires five complete source/controller/time updates, End, finite logs, unchanged original case files, real loaded declared libraries, and an actual successful direct-child exit. First-step proof binds the NVIDIA documented globalTid PID/TID mapping and PROCESSES row. In addition to the full step, it requires successful launches and a subsequent successful device/context completion in each of C29_CORE_MOMENTUM_ASSEMBLY (one), C29_CORE_MOMENTUM_PREDICTOR_UFINAL (one) and C29_CORE_PRESSURE_CORRECTOR (two). Each API and nested range must belong to the actual solver main thread and lie wholly within the complete first-step window. Captured launch/sync failures, missing returnValue, missing completion, extra captured steps, or post-window launches fail the gate. Startup kernels cannot meet these nested-range gates.

The proposal allows one owned GPU solver, nice15, at least 20 GiB available memory, a 900-second solver bound plus 30-second termination grace, a 1050-second profiler bound with separate cleanup, and a 300-second export bound. These are containment limits, not predicted run times. Existing evidence/log paths are refused. Partial failures are preserved and require review rather than automatic rerun.

The runner is not imported or executed during preparation; only Python AST parsing and the installed profiler's --help are used. Full numerical acceptance still requires the unchanged frozen strict d600 analysis after the GPU experiment. API counts are not distinct kernel counts or proof of complete device residency. This instrumented functional profile supports no speed or lift conclusion. Raw reports remain private; minimal source/API/NVTX/process evidence can be curated separately after review.
