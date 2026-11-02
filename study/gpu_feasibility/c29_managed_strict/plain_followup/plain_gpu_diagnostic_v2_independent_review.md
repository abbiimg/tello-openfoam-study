# Independent plain GPU diagnostic helper review: V2

Reviewed 2026-11-02 by `stdpar_memory_review`. **No remaining blocking static finding. Plain V2 is acceptable for a separately Root-approved single diagnostic after all prerequisite gates pass.** This review does not authorize a run, attest completion of the curator's integrity gate, or establish GPU/numerical/performance qualification.

## Frozen identity and source checks

- Proposal: `plain_gpu_diagnostic_proposal_v2/`.
- Helper manifest SHA256: `ed3bd4f82fe29b361cae7a1da5fedbabfb3394e5021a55ae2ed0007dbad0ee8f`.
- Unchanged protocol SHA256: `e6e58d9e37514f0dc3b3f76bfaaf6a839612faef2fde095f3c38ebf3d24c6395`.
- V1-to-V2 correction patch SHA256: `ce7edc057ff20f7f56cada491422fad4cbd46c5cdbbfcf12ddf65e10fd2cc836`.
- Run helper SHA256: `38e3690aa2b7c766f24700f3f097024b1a06a8c1893e506c2c4eedbda6ac57ba`.
- Exact binary remains `7056d5f5bcffb88119881752361f09d40459126af065fd37cdc45288c00d9185`; library identity remains `c3e61de12b03e5406d5c1155d932b2de5b27c7198dd99e29c1228ccd18deadff`.

All six V2 manifest entries match the current files. All six external protocol file records match their current files: binary, library identity, linked identity, source manifest, native environment and receipt verifier. These checks bind identity files; each actual declared library must still be observed and hash-checked during the run. The original plain V1 manifest/files and its diff from reviewed V3 were also verified. The narrow V2 correction patch was independently regenerated and matches byte for byte. Only `run_plain_gpu_once.py` changes relative to V1. All three Python files parse as ASTs; none of the proposed helpers was imported or executed.

## Admission, environment and process ownership

`plain_common.py:18-37` requires an explicit Root decision bound to this protocol/helper manifest and a fresh launch receipt. Root approval must also bind fresh-clone preparation and three passing prerequisite attestations: the external F14-to-CPU strict gate, exact shared startup, and native-Windows 31-field integrity gate. This review checks the contract, not the not-yet-supplied attestations or field copies. Root must complete and verify the 31 native/Windows double hashes before approving execution.

The helper accepts only the new diagnostic case/private root, the exact original binary/argv/library/phi pins, five-step phase and unique diagnostic ID. It rejects the failed original case. Fresh physical inputs and unchanged strict dictionaries are Root's separately bound preparation responsibility; no clone or receipt is created by this proposal. Original admission, source audit, receipt-bound bytes/mtime, receipt freshness and the native GPU environment are rechecked before launch.

No Nsight, debugger, observer or additional execution wrapper is launched. The runner inherits its environment without an environment override. `plain_common.py:34-35` rejects LD_PRELOAD, CUDA/NVTX injection paths and a Nsight loader overlay. Post-run observed Nsight/CUPTI libraries prevent a process-gate pass. Existing NVTX annotations inside the unchanged application are not a new profiling launch.

The exact reviewed V3 `owned_cleanup.py` is reused (SHA256 `c50601d01b0513cfe94892578e2a00b4d2f3fba58b7c312cbeeb81b778b67203`). The timer begins just before Popen (`run_plain_gpu_once.py:29-30`) and triggers cleanup at 180 seconds. Every subsequent identity/start-save/monitoring operation is inside try/finally (`31-55`). Signals request cancellation; cleanup targets only the direct owned pidfd or its unreaped Popen fallback, then TERM/grace/KILL/wait. Identity evidence includes PID, birth ticks, UID999, cwd, executable and nice level. Actual waited status is saved before log close/postprocessing and remains separate from wrapper errors. No automatic retry or unrelated-process cleanup exists. Final OS reaping can outlast normal timers if the OS has not made a killed process terminal; unresolved status cannot pass.

## One V1 gate defect corrected

In V1, the process-pass boolean was computed before the final exit-receipt save; a failure of that save appended a wrapper error but could leave the final return path using the stale true boolean. V2 clears the gate in that exception (`run_plain_gpu_once.py:68`) and rechecks errors, cleanup errors and actual waiting in the final return guard (`72`). The persisted initial receipt or fallback still preserves the true solver status. Thus a successful solver exit cannot waive a subsequent evidence-save failure. No source, case, binary, environment or numerical change accompanies this correction.

## Meaning of the future result

The helper retains partial/full stdout, actual child status, input and observed-library integrity, added files, all saved field hashes, time headers and source/controller counts. A plain process pass requires child exit0, no timeout/cancellation/errors, completed postprocessing, unchanged inputs/declared libraries, five time/source/controller observations, finite log, End, and fifteen recognized saved step fields. The unchanged application also guards its exact clock sequence; the separate strict analyzer remains responsible for numerical acceptance and every expected field block.

An unprofiled pass or failure can narrow the profiling-overlay confound but cannot by itself prove what caused the prior SIGSEGV. Missing CUPTI tables in the partial failed profile do not establish zero GPU execution. Exit0, actual GPU-library loading and this process gate do not supply accepted CUDA execution proof, CPU/GPU numerical parity, lift results or speedup. The 2.4 ownership proposal remains an unbuilt, unproven remedy; GDB remains optional and separately reviewed if later needed.

Only independent review artifacts were written. No case/receipt/approval was created, no proposal/application/vendor/build/SDK/permission was changed, and no helper, debugger, profiler, build or CFD application was run by this reviewer.
