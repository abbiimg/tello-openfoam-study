# C29 managed-ownership and strict-pressure 2.3 addendum

Unpublished source/evidence candidate, 2 November 2026. This is a separate, dated experiment using the native GPU and same-pin CPU installation. It does not alter the 84-case Foundation14 CPU lift study or select a production GPU default.

The application combines the reviewed app-local managed-heap ownership change with a separately authorized strict-pressure protocol. Both native backends use source-tree SHA256 `ad01489971b0b65d86eaf5f88fb51347ed9337bd1afeb570a6fc8c003c49f99b`. The whole original C29 fvModels input, verbatim source body and includes remain pinned. The C29 actuator/controller source remains host code; this is a hybrid application with eligible native core operations offloaded. The strict protocol changes first-pressure `relTol .05` to `0`, keeping absolute tolerance `1e-7` and the original d600 validation limits. The original failed experiments remain separately labelled.

The representative case has 922,576 cells and 2,739,208 internal faces: eight flat 8 cm rotors on the square layout with 10 cm nearest-center spacing. It starts from the frozen t=0.6 s field and uses five fixed 0.0001 s steps. The reset controller makes this a short compatibility experiment. Its changing transient electrical power is not a settled equal-power lift result.

## What actually happened

- Initial managed2.3 CPU and GPU initialization returned 0. Computed GPU initial phi differed from Foundation14 by at most `3.1742559698354905e-19`, so the exact-startup gate **failed**. The predeclared fallback copied the identical Foundation14 phi into both native backends. Repeated startup then matched every stored U/p/phi internal and boundary value block exactly, with zero difference.
- New strict Foundation14 and native CPU runs each actually completed all five steps, source updates and End with child exit 0, unchanged inputs and recorded loaded-library identity checks. The frozen mechanical analysis has **499 passing checks and zero failures**. The fields are equivalent within the original limits; they are not byte-identical transient solutions. The Root external gate binds the analysis, startup, input audit and true execution receipts.
- The managed2.3 GPU transient attempt **failed**. Actual solver PID392599 was waited and returned **−11 (SIGSEGV)**; profiler exit was 139 and the outer helper refused qualification with exit 1. It printed only Time 0.6001 and completed no source call, controller update or End. Original input bytes and declared loaded-library hashes remained unchanged; no case files were added. Wrapper and cleanup error lists are empty. The failure occurred before a Courant line, momentum/source evidence and a complete first step. Its exact faulting instruction and cause remain unproven. The incomplete capture grants no GPU launch/subrange qualification or numerical pass.
- The older relTol .05 five-step comparison remains a **failure** with four global-continuity checks failing. The original2.2 initialization failure and descriptor controls remain historical evidence in the separately published native installation base. The later2.4 diagnostic proposal is outside this2.3 bundle.

There is no speedup, settled-lift, production-default, full device-residence or fresh-host rebuild claim here.

## Contents and reproduction

See [REPRODUCTION.md](REPRODUCTION.md), [DEPENDENCY_MAP.json](DEPENDENCY_MAP.json) and [HISTORICAL_REFERENCES.md](HISTORICAL_REFERENCES.md). The source groups, build records, review histories, startup/terminal receipts and original logs are copied byte-for-byte. Historical source-only/pending wording inside originals describes their state when written; this wrapper supplies the later outcome.

All **30 original ASCII saved U/p/phi files** from the completed Foundation14/nativeCPU pair are included, with a per-file hash catalogue. Canonical initial phi is included once. Initial U/p and the unchanged mesh come from the already published 62.8 MB seed with SHA256 `89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb`, plus its pinned CPU override catalogue. This addendum does not duplicate that seed or mesh. The two small repeated-geometry cache CSVs are included for the saved-field axial-speed calculation.

The optional [offline restoration helper](recipes/restore_completed_evidence.py) verifies those dependencies and can create a fresh evidence tree without CFD. It does not build an application, run a solver, issue launch authorization or recover a compiled cache. Historical installation/build/launcher sources use guarded workstation paths and one-shot receipts. They require deliberate fresh-tree adaptation and review; a fresh-host rebuild was not tested.

SDKs, full upstream trees/archives, ELF executables/libraries/objects, raw profiler reports, full trace SQLite databases, full environment dumps and credentials are excluded. Native installation prerequisites and scoped compiler/Umpire adaptations are in the separate native installation publication.
