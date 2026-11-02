# Independent first GPU profile helper review: original proposal

Reviewed 2026-11-02 by `stdpar_memory_review`. **Original proposal requires a cleanup correction before execution.** No solver, profiler capture, or proposed helper was run by this reviewer.

Requested proposal: `gpu_profile_proposal/`, protocol SHA256 `ef302349a02d6fc507773e9a7ec70d8c7176db51fbf3046f424e7e8381148cf0`, Root-supplied original helper-manifest SHA256 `fa8bc924e0e5de55457167c873f84d297a297c9679ced2e70316d313de455b93`. The original script text was read before revisions. During review the owner revised helpers in place: the subsequently checked helper manifest was `784ab973ef7c6c783a3bad611934aa5408b6a3406823dc4ad907fdfc68a1df9f`. Its seven entries matched the then-current files, but this does not attest the original manifest hash. This report describes the original text, not approval of the revised text. A stable corrected freeze must receive a separate review.

## Blocking finding: post-launch exceptions can bypass owned-child cleanup

In the original `run_actual_gpu_child.py:23`, `Popen` starts the solver in its own session. Lines 24-26 open its pidfd, inspect `/proc`, check identity and save the start receipt, without a surrounding `try/finally`. The signal forwarding handler is installed only at lines 27-31. The remaining monitoring, library scanning/hashing, case scans and exit-receipt construction at lines 33-50 also lack a guaranteed cleanup/reap path.

A concrete failure such as inability to save `actual_solver_start.json` at line 26 raises after a solver is live and before its identity receipt is published. The wrapper then exits without terminating or waiting for that owned solver. In the original `run_gpu_profile.py:23-34`, timeout cleanup finds the actual solver only through that missing file; lines 38-40 terminate the profiler itself. The solver's separate session is not covered by that termination. This violates the proposal's bounded owned-process cleanup contract.

The narrow correction is unconditional cleanup and waiting for the exact direct child on every post-Popen failure, including failures before pidfd acquisition or identity/start-receipt publication. The original unreaped `Popen` child is safely owned even before the audit identity exists; do not substitute broad process-name/group termination. Preserve the actual waited return status and distinguish wrapper/monitoring errors from a successful solver exit. Outer exceptional/signal paths must likewise not bypass cleanup. No numerical, source, case or profiler-proof change is needed to resolve this finding.

## Other reviewed semantics

No additional blocking issue was identified in the original static proof design:

- Approval binds protocol/helpers, fresh receipt, shared startup and the external F14-to-CPU strict gate. The helpers do not issue a receipt or enable case permission.
- Outer original admission precedes profiler injection; the child rechecks byte/mtime records and receipt freshness, while preserving inherited `LD_PRELOAD` and allowing only pinned Nsight loader additions. This is a permitted profiler overlay, not a claim of identical uninstrumented loading.
- Direct-child UID, PID birth ticks, cwd, executable, nice level, actual wait status and sampled declared-library hashes remain separate from profiler/export statuses.
- The validator binds the NVTX first-step `globalTid` to the actual solver main PID/TID and a matching PROCESSES row. It requires non-null successful launch/sync returns, launches plus a successful subsequent device/context synchronization in the full step, assembly, predictor and each of two pressure-corrector windows. Missing schema/evidence fails closed. It does not claim distinct-kernel counts, GPU timeline proof, timing, or numerical acceptance.
- The first-range stop policy allows the remaining four steps to finish after collection ends. NVIDIA documents this behavior, the unregistered-name setting and environment-collection flag in its [Nsight Systems User Guide](https://docs.nvidia.com/nsight-systems/UserGuide/). The [Analysis Guide](https://docs.nvidia.com/nsight-systems/AnalysisGuide/) documents the PID/TID decoding formula used by the validator.

The external F14-to-CPU analysis file was hash-checked as `9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e`. Root reports that its numerical gate passed. Re-evaluating that gate and adopting a CFD/GPU backend are outside this helper review. Full GPU five-step numerical comparison and actual captured evidence remain outstanding.
