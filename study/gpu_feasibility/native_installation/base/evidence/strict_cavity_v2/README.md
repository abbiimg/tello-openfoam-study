# Proposed strict cavity v2

No new solver or mesh run has been started. `protocol.json` is proposed and `prepare_fixture.py` refuses to prepare a case until root changes its status to `ROOT_APPROVED`. The completed CPU stock run retains its original failed-screen status.

The proposed fixture uses the same pinned400-cell cavity, identical initial/boundary/transport inputs, and one CPU-generated mesh copied byte for byte to both backends. It changes the first pressure solver's `relTol` from0.05 to0 while retaining absolute tolerance1e-6 and the existing final pressure settings. It runs five fixed0.005s steps to0.025s, writing every step as17-digit ASCII. Velocity tolerance remains1e-5; two PISO correctors and no nonorthogonal correction remain unchanged. This is a bounded backend functionality test.

Acceptance requires the actual solver child to exit0, exactly five time steps and ten pressure/continuity records, End, finite residuals/fields, every pressure final residual<=1e-6, every velocity final residual<=1e-5, and **every corrector's local continuity<=1e-5**. No first-corrector exception is introduced.

`check_cavity_flux.py` independently reconstructs cell volumes from oriented mesh-face triangle tetrahedra and sums signed written phi for each cell. For every written step, dimensionless local flux continuity must be<=1e-5, absolute global continuity<=1e-10, and agreement with that step's own final logged corrector must be within max(1e-12,0.001*abs(logged)). The exact formulas and proposed cross-backend U/p gates are in the JSON for root review before data collection.

The flux parser was exercised read-only against the existing CPU stock output at0.5s. It reconstructed0.1x0.1x0.01m and total volume1e-4m3. Its local flux measure was2.3888e-7, with global-7.32e-19. That field was written at six digits; its printed phi cannot reproduce the in-memory final logged9.66354e-9 tightly. The new17-digit fixture avoids using such truncation as a conservation diagnostic. This audit does not change the original failed all-corrector screen, whose peak was4.66513e-4.

For native GPU capture, the proposal uses a separately named `icoFoamStrictV2` copied from the pristine pinned icoFoam application, with only NVTX push/pop around the complete first loop body, including field writing and ExecutionTime. Compile just that application after native libraries finish; leave vendor source and SDK intact. The root may instead approve a validated observer before freezing the protocol, but the selected method must be recorded before the new run.

Use the exact capture flags in the JSON: named NVTX capture, `--capture-range-end=stop`, `--kill=none`, `--cuda-trace-scope=process-tree`, `--wait=all`. Set `NSYS_NVTX_PROFILER_REGISTER_ONLY=0` only in that runner's child environment so the `nvtxRangePushA` string can trigger named capture. Preserve any inherited LD_PRELOAD. Verify the complete first-step range actually triggered and contains successful CUDA launch API calls with no failed launches/synchronizations. Stop collection at the range end and let the remaining four solver steps finish unprofiled.

The direct-child wrapper must retain PID/birth identity, binary SHA256, exact command and true return code, written atomically only after wait/cleanup. Profiler or outer-shell status is a separate field. A signal exit remains a failure. No timing conclusion is allowed while builds run.

The original native stock run must first end normally or fail its original gate; its waiting watcher must be handled only after that outcome. No replay of completed build stages is needed. These helpers do not include C29.
