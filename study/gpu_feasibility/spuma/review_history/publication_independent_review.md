# Independent SPUMA publication review

Reviewed 2 November 2026. **No publication blocker found** in candidate manifest `4e05d46beb20b8ac83019610b99cd315f7cd676eeccdb2994225453630041e94`. This review reads completed evidence and source; it does not authorize publication or claim a new CFD run.

All **183 indexed files** match their size/hash records: 4,922,279 indexed bytes, **184 files / 4,953,742 bytes including the outer manifest**. The nested 178-file evidence inventory also matches exactly. Root-level gate aliases agree with the nested records. There are no symlinks, ELF/PE binaries, compiled-library/object/archive/SDK payloads, full raw SQLite/report files or targeted credential-pattern hits. The only SQLite payload is the deliberately restricted review subset. Inspection of the text/recipe scope and its two exported strings identified no credential payload.

## CUDA trace and process evidence

The subset passes SQLite integrity checking and contains only the runtime API table, NVTX_EVENTS, PROCESSES, StringIds and one subset-provenance row. Its data are exactly **4,890 API rows, one NVTX range, one actual icoFoam process and two StringIds** (`cudaLaunchKernel_v7000` and `cudaDeviceSynchronize_v3020`). It contains no environment/unrelated metadata tables.

Independent queries reproduce **2,445 successful launches and 2,445 successful device synchronizations**, no failures, all inside the complete first-step range and on globalTid **287645200915614**. Its documented decoding gives PID **367774**, agreeing with PROCESSES and the actual child receipt. The final launch ends at **54309567157 ns**; a same-thread successful device synchronization begins at **54309569990 ns** and ends at **54315889361 ns**, before the range ends. This is stronger than merely comparing aggregate API counts.

The retained private full SQLite matches its recorded SHA. Using read-only connections, I compared the exported API/NVTX/process/string rows against the exact allowed source predicates, including other possible launch/sync API tables. They match losslessly as row multisets. I did not read/export unrelated StringIds or environment metadata and did not modify the private reports or candidate. API events are not unique kernels, kernel activity or complete device-residence proof; the documents preserve those limits.

## Numerical/provenance consistency

The original fixture remains explicitly failed and intentionally stopped: 12 completed steps, actual child **−15**, observed all-corrector continuity **0.000255613348367**, and no completed 0.5 s horizon. Its connector status is correctly distinguished from the actual child receipt.

The fresh strict fixture is separately identified and preregistered. Protocol/validator hashes match their frozen records, including the freeze before the actual child start. All recorded strict inputs match. Start/completion binary/core/FV/observer/environment identities agree; actual child and Allrun receipts are both zero without timeout. The saved/logged five times are .005 through .025, and all ten logged local-continuity observations match the gate, with maximum **8.770776844746355e−9**. The code for saved-field/closed-wall/independent-flux checks is included and consistent with the reported result. This review did not rerun a solver or substitute its own new numerical acceptance protocol.

The README keeps tighter pressure relTol and shorter horizon explicit. It claims a bounded installation/coverage result, not a replacement pass for the failed original, CPU accuracy equivalence, a rotor result or speedup.

## Recipes and practical limits

The inspected source/build/environment/link-fix/case/profile/subset recipes use task-specific private roots and known owned children. There is no Git push or external-publication path, global driver/profile installation or broad recursive deletion. The only raw-report unlink operation removes checked copies inside the candidate after matching private originals. The generated-stub GCC filter changes only the diagnosed private linkstub -fpic argument; recorded object hashes/timestamps and failure/retry logs retain the build history. Solver patches add NVTX ranges without equation changes.

These are historical, guarded workstation recipes, **not a turnkey portable installer**. Their hard-coded paths, UID, dependency records, concurrency-stage guards and existing-evidence refusal need inspection/adaptation in a fresh private tree, as the README says. The shared NVHPC/CUDA SDK, full upstream tree and binaries are deliberately absent. No fresh-host rebuild was tested here. The unsupported-CUDA-C++ vendor warning is retained.

The accepted evidence covers a 400-cell, five-step cavity and first-step CUDA API activity plus the separate device-only executor marker. It does not validate an actuator port, long-time behavior, every GPU operator, production throughput or rotor-study rankings. No compiler, CFD, delivery-output, Git, vendor or case mutation was performed by this review. Root still owns the publication decision and final copied-byte checks.
