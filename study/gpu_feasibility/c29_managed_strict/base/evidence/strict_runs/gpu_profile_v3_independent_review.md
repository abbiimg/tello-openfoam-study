# Independent GPU functional-profile helper review: V3

Reviewed 2026-11-02 by `stdpar_memory_review`. **No remaining blocking static finding. V3 is acceptable for a separately approved single five-step functional profile.** This is not launch authorization, runtime success, numerical acceptance, a speed measurement, or adoption of a GPU CFD backend.

## Reviewed freeze

- Directory: `gpu_profile_proposal_v3/`.
- Helper manifest SHA256: `467b014b9fefe74ac76f26e7efe7bb0206994792cbe7e32d85c362dbbca1c5cb`.
- Unchanged protocol SHA256: `ef302349a02d6fc507773e9a7ec70d8c7176db51fbf3046f424e7e8381148cf0`.
- V2-to-V3 diff SHA256: `a1020857615228dc039d5be91e8b10e398243d45ee56290a67bd68ab011d85ee`.
- V2 base manifest SHA256: `a488de2a74b25f50d8fcb4644344ee7de1dc91830af444280115750d328e1c13`.

All nine V3 manifest entries match the current files. All nine protocol records containing an absolute path and SHA256 match their current files: binary, library identity, linked identity, combined source manifest, native environment, receipt verifier, root input audit, strict-pressure protocol, and Nsight executable. This checks the identity files themselves; runtime verification of each declared loaded library remains mandatory.

The restored original V1 manifest (`fa8bc924e0e5de55457167c873f84d297a297c9679ced2e70316d313de455b93`) and all seven bound files were independently verified, as were the intermediate `784ab973ef7c6c783a3bad611934aa5408b6a3406823dc4ad907fdfc68a1df9f` snapshot and V2. Both correction patches were regenerated from actual file contents and matched byte for byte. V3 changes only README and the outer runner relative to V2. All five V3 Python sources parse as ASTs; none of the proposed helpers was imported or executed. A text-comparison check initially used an incorrect search indent; the corrected line-aligned comparison confirmed that the trace proof body from the capture-message check onward is unchanged from original V1.

## Cleanup findings resolved

The original V1 blocker is resolved by `run_actual_gpu_child.py:29-56` and `owned_cleanup.py:3-26`. Every operation immediately after the direct solver Popen is inside `try/finally`. Failure to publish spawn/start evidence, open a pidfd, inspect identity or monitor the process reaches exact-owned-child cleanup. The helper sends TERM, waits through the grace period, sends KILL if still needed, and waits for the actual return status. The fallback target when pidfd setup failed is only that direct unreaped Popen child. No name-based or whole-group termination is introduced.

The wrapper publishes its own identity before its final cancellation check and possible solver Popen (`run_actual_gpu_child.py:26-29`). Signals set cancellation state rather than interrupting cleanup. Actual waited status is recorded before log close and case/log/library postprocessing. Monitoring and postprocessing errors remain distinct from the child's return code; the validator requires successful child completion, no recorded wrapper/cleanup errors, completed postprocessing, and separate successful profiler/export statuses (`validate_gpu_profile.py:12-22`).

The V2 outer failure paths are resolved in `run_gpu_profile.py:71-86`. A nonzero profiler exit now requests owned-wrapper/solver cleanup even if the profiler already terminated. The runner independently waits for actual child-terminal/no-launch evidence. A profiler exit alone is not treated as solver completion.

The pre-wrapper timeout branch is handled by the invariant at `run_gpu_profile.py:37-43`: successful atomic cancellation-marker publication plus absence of a wrapper-start receipt means a later wrapper must fail its pre-spawn marker check. An already-passed check requires that the wrapper-start receipt was previously published. Thus the direct profiler can be stopped/reaped without abandoning an unrecorded live solver in this branch. Once a wrapper has started, unresolved terminal evidence stays supervised. Cross-process signals require matching birth ticks, UID, cwd, executable and, for the wrapper, its exact script argument (`run_gpu_profile.py:13-28`).

The normal solver/profiler timers are not an absolute bound on pathological OS cleanup. The final wait intentionally continues if an existing owner has not yet supplied terminal evidence or an owned hard-killed process has not become reapable. This limitation is stated in the proposal; it does not permit a success gate while status is unresolved.

## Execution proof and admission assessment

The reviewed protocol remains one full 922576-cell, five-step functional experiment, with tracing restricted to the first `C29_NATIVE_TIME_STEP`. The original admission check runs before Nsight injection; the child rechecks receipt-bound bytes/mtime and freshness immediately before launch. Approval must bind the V3 manifest, unchanged protocol, fresh receipt, exact shared-startup evidence and Root's external F14-to-CPU strict numerical gate. The helpers issue no receipt and enable no case permission.

Inherited Nsight `LD_PRELOAD` is passed unchanged. Original loader components must remain in order, and added loader paths must resolve within the pinned Nsight installation. NVIDIA documents that `--discard-environment=true` suppresses environment collection; it does not discard the inherited process environment. It also documents first-range stop behavior and `NSYS_NVTX_PROFILER_REGISTER_ONLY=0` for unregistered capture names. [Nsight Systems User Guide](https://docs.nvidia.com/nsight-systems/UserGuide/).

The trace validator decodes globalTid using NVIDIA's PID/TID formula, binds the actual solver main thread and PROCESSES row, and requires a single complete first-step range. It requires non-null successful launch/sync return values, successful launches inside the full step, assembly, predictor and both pressure-corrector windows, and a subsequent successful same-thread device/context synchronization after the last launch in each window. Missing schema, capture or completion evidence fails closed. [Nsight Systems Analysis Guide](https://docs.nvidia.com/nsight-systems/AnalysisGuide/).

Startup work cannot satisfy these nested timestep gates. API calls are not distinct-kernel counts or GPU timeline proof; capture and ownership auditing do not support a speed claim. The remaining four steps finish after capture ends, with exactly five time/source/controller updates, finite logs and End required. Full CPU/GPU field, force, power, rotor, residual and continuity acceptance still belongs to the separate unchanged strict analysis.

The external F14-to-CPU analysis hash was independently checked as `9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e`; Root reports that gate passed. Its numerical re-audit is outside this helper review. No GPU PDE run was performed by this reviewer.

Only the independent review artifacts were written. No proposal, application source, case, vendor tree, build, SDK or permission was changed by this reviewer.
