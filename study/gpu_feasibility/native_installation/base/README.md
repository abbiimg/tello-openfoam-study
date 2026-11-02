# Native managed-stdpar GPU and same-pin CPU installation — review candidate

This unpublished source/evidence candidate records the completed private OpenCFD installation and its bounded checks on Linux ARM64 / RTX Spark N1X. It contains no SDK, compiler, full source archive/tree, executable, shared/static library, object/build tree, raw profiler report, full trace SQLite, credentials or full target environment dump. Root review and publication remain separate.

Both builds use OpenCFD core `b239fea6e48922730477e218c44e8b6a8ab17ade` (API 2609; upstream directory label OpenFOAM-v2606) and ThirdParty `b70425b2611c23f26f24bdb97a5e6b48b99ffe0d`. The GPU route uses NVHPC 26.9/CUDA 13.3, SM 121, explicit managed memory and CUDA-enabled Umpire 2025.03.0 with an exact two-file official CUDA 13 API backport. The independent CPU tree uses GCC 13.3, DP/Int32/Opt and no offload flags. SDK/full upstream archives are [external pinned prerequisites](EXTERNAL_PREREQUISITES.json), rather than duplicated payloads.

## What passed

- Managed compiler test: 1,048,576 doubles with exact element/sum checks, managed pointer type 3 and successful checked synchronization.
- Device-only marker: 262,144 runtime-seeded nonuniform values, verified CUDA device-only output with null host pointer, zero mismatches and checked APIs. This supplies a separate execution marker beyond compiler flags.
- Actual native Field/Umpire arithmetic: 32,768 scalar/vector elements, zero mismatches and exact sums. **The current post-resume core/probe identities match the retained gate**, with eight successful CUDA launch API calls in its named algebra window. The earlier core identity/gate is retained as history; see [current identity check](CURRENT_IDENTITY_CHECK.json).
- Distinct preregistered 400-cell strict cavities: both CPU and GPU completed five steps through 0.025 s with actual waited child exit 0, finite complete saved U/p/phi, residual/continuity/independent flux and cross-backend field gates. Peak all-corrector continuity is about 1.078e-8 on both; maximum relative L2 differences are U 3.71e-15 and p 1.30e-13. The GPU complete first step contains 12 successful launch API calls and 13 successful synchronizations, including checked completion after the last launch. See [summary](evidence/strict_cavity_v2/completed_summary.json), [protocol](evidence/strict_cavity_v2/protocol.json), [closure](evidence/strict_cavity_v2/immutable_closure.json) and [copied-evidence review](CPU_STRICT_READONLY_REVIEW.json).

The original stock CPU and GPU cavities completed to 0.5 s with zero solver exits, but **failed** the original all-corrector continuity screen (peak 4.66513e-4 with loose first-pressure relTol 0.05). Their initial inputs, mesh, saved fields, logs and build-journal records remain under `cases/original_stock_failed_screen/` and the installation evidence. The strict fixtures tighten first-pressure relTol to 0 at the original absolute tolerance and use a shorter, preregistered horizon. They are separate experiments and do not replace those failures. No nonexistent final stock-pass gate is fabricated.

## Important coverage and interpretation limits

Native ListPolicy chooses offload only for lengths of at least 1,000. The 400-cell cavity has 760 internal faces, so its flux interpolation ran on CPU even though other operations produced genuine CUDA launches. A small cavity pass does not validate GPU interpolation on a rotor-sized mesh, all operators or complete device residence.

API counts are successful observed calls, not distinct kernels or a GPU kernel timeline. The [restricted trace subsets](trace_subsets/) retain only selected-thread launch/sync rows, one selected complete range when applicable, its actual process row and required safe names. They deliberately include selected-thread events outside the range where needed to assess absence after capture; window counts must be computed using the recorded range. The Field process record retains its exact known owned executable path. No environment tables or unreferenced strings are exported. Full originals remain private with hashes. Strict runtime library records are named `loaded_library_candidates_sha256` and derive from ldd; they must not be relabelled as complete /proc/maps observations.

The CPU compiler audit has **1,620 GCC/G++-prefixed log lines**, including 1,606 with `-c`; this is not 1,620 objects. No offload flags were found. An earlier 313-line snapshot is preserved and explicitly historical.

## Dated large-case diagnostic history

`history/original_c29_v2_2/` preserves the original 922,576-cell GPU initialization failure before source/controller/time stepping, plus the exact CPU startup comparison. `history/descriptor_control/` preserves the separate completed diagnostic: raw managed data and a managed-heap descriptor pass at 4096, a stack descriptor passes on the sequential 400 path, and the same binary's stack-reference 4096 offload aborts. The independent source/control audit supports this descriptor-storage failure class. It does **not** identify the full case's exact faulting instruction or prove a complete remedy.

`history/sanitizer_attempt_a/` records the actual tool failure: Compute Sanitizer reported CUDA initialized before the sanitizer, disabled itself and returned 86; the actual child aborted separately. This is not valid address/kernel attribution. Current ownership/combined-strict source, build/runtime progress and any later remedy acceptance are intentionally excluded and require a separate addendum. No GPU rotor result or fixed-runtime pass is claimed here.

## Reproduction and immutable records

See [reference and procedure map](REPRODUCTION_REFERENCES.md). These are exact guarded historical workstation recipes with fixed paths, UID assumptions, stage budgets and completed-evidence refusal. Inspect/adapt into fresh private trees; do not point them at the preserved completed cases. No fresh-host rebuild was tested. Selected source/rules, env scripts, full compiler/build/test receipts, original failure records, official Umpire backport files/diff and private generated-stub PIC workaround are included. SDK/full-source archives must be obtained separately and hash-verified. No global driver/profile/default-compiler change or production backend switch is part of these procedures.

`CURATION_PROVENANCE.json` records every copied source path/hash/size, and `manifest.json` inventories this candidate. Candidate curation only read original artifacts; it launched no compiler, CFD, benchmark or GPU test and changed no case/vendor/SDK/delivery/Git state. The completed 84-case Foundation14 CPU lift study is separate and unchanged. No speedup, long-time validation, rotor ranking or production adoption follows from this bundle.
