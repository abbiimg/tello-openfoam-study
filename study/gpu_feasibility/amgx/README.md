# AmgX 2.5 / Foundation 14 pressure integration

This source-and-evidence package records a working, bounded GPU pressure path. It is not a production default or speed result. It contains no CUDA SDK, driver, build tree, executable or shared library. This reviewed source-and-evidence bundle was published on 2 November 2026; publication provenance is in PUBLICATION.json.

## What actually ran

- Manufactured 32³ Poisson: device-double AmgX, relative L2 residual 7.2647e-11, 26 iterations, 1,316 successful observed CUDA launch API calls.
- 400-cell cavity: both GAMG and AmgX completed 20 steps. All 40 GPU pressure solves independently passed native stopping checks; 8,040 observed launch calls. U/p field comparison is in evidence/adapter_smoke.json.
- 922,576-cell C29 rotor: exact same frozen t=0.600 U,p and C29 actuator source/library; five matching adaptive steps to t=0.60086186. Both returned zero and End. All ten pressure solves passed native stopping, with 16,310 successful launch calls. Max final-corrector native residual was 5.9732e-9 against 1e-7. Relative L2 field differences were U 8.34e-6, p 8.38e-4, internal phi 1.23e-5; mean lift differed by +2.91e-7 relative and inferred electrical input by -1.75e-5. All continuity/input/seed/library checks passed.

The counter observes successful launch API calls, not distinct kernels or a GPU activity timeline. The adapter independently recomputes residuals using the native unscaled OpenFOAM matrix. These are compatibility checks; five rotor steps do not establish settled lift or a speedup. The unchanged 19.2923 W input target is converted through the assumed loss map; short reset-transient mean input is about 19.13 W, not measured battery data.

## Scope

Serial, DP, symmetric scalar pressure matrices with no coupled interfaces and minIter 0 only. Velocity, actuator and other flow operations stay on CPU. GPU 0 uses PCG/aggregation AMG with Jacobi. Matrix/resources/preconditioner setup is rebuilt every solve. The backend uses a deliberately extra factor 0.1 beyond the sufficient L1-to-L2 residual bound; this is not a tuned AmgX performance implementation. Unsupported conditions fail explicitly; there is no silent CPU fallback.

Actual install pins, commands, artifact hashes and raw logs are in evidence/ and logs/. The temporary MCP helper from early schema discovery is excluded and is not a supported launch route. Production, frozen studies, Ginkgo installation and live MCP configuration were not changed. Both pilots identically reset controller history from the warm fields; no complete controller-history continuation is claimed.

## Rebuild and use the portable recipes

The recipes require a Linux CUDA 13 development toolkit with cuBLAS, cuSPARSE, cuSOLVER and CCCL, CMake, a compatible C++ compiler, and Foundation 14. They install no driver and make no global environment changes. They use a fresh user-writable prefix, one nice-15 build job and process-local paths. The tested machine was ARM64/compute 12.1; another architecture is a new validation target.

1. Set CUDA_ROOT to an existing compatible toolkit and AMGX_PREFIX to a fresh absolute directory. Optionally set CMAKE, CXX and CUDA_ARCH (tested 121). Run `bash recipes/build_private.sh`. This fetches the exact pinned upstream SHA and builds AmgX plus the audit and Poisson verifier. Inspect CUDA 13's internal __cudaLaunchKernel signature before using this audit with a different toolkit.
2. Run `bash recipes/run_poisson.sh`; require numerical_pass, a loaded launch audit and positive successful launch counts with zero return status. This is explicit test execution, separate from installation.
3. Set FOAM_BASHRC if Foundation14 is elsewhere, then run `bash recipes/build_adapter.sh` and source that Foundation14 environment for restoration.
4. For cavity inputs, run `python3 recipes/restore_pilots.py --kind cavity --case-root /fresh/allowed/root --amgx-prefix "$AMGX_PREFIX" --cuda-root "$CUDA_ROOT"`.
5. For rotor inputs, additionally obtain the separate existing benchmark_reproduction package containing shared_seed.zip, reproduction_manifest.json and overrides/. Supply `--kind rotor --seed-dir /path/to/benchmark_reproduction`. The exact ZIP SHA256 and CPU benchmark-manifest SHA256 (`5194b4442563947edc79af4f273dc67bc1b486b39e08d740352627d40c607f80`) are enforced. External catalogue names and source/destination containment are checked before directory creation; absolute, traversal, backslash, drive/colon and symlink paths are rejected. `--verify-seed-only` validates the inputs without creating/running cases. The large seed is deliberately not duplicated here.
6. Review the generated AllrunPilot and use the existing allowed-root OpenFOAM MCP runner, or explicitly run `bash AllrunPilot` in each fresh pilot. Never run against an original frozen case. No server/root override is needed. The portable rotor recipe rebuilds the exact C29 coded source privately if necessary, one job; the actual recorded workstation pilot reused a checked library and did not compile it.

The generic portable recipes were syntax-checked, their real seed-verification gate was exercised, and focused external-path/symlink/manifest-pin fixtures passed. A new host rebuild or fresh portable case restoration is not claimed. The original local scripts in recorded-recipes/ are historical records and are not runnable in their curated locations: siblings moved to evidence/ or src/, and some full installation scripts, source-pin response and helper/log material are deliberately local-only. [The historical reference map](recorded-recipes/HISTORICAL_REFERENCES.md) identifies each moved or omitted reference without rewriting the original script bytes or archived installation note. Use recipes/ for supported portable entry points and evidence/pins.json for included pins. The recorded analyzers document the completed full-field checks, not a generic future-job launcher. Case inputs under case-inputs/ preserve actual settings and paths as evidence; restore_pilots.py relocates library paths when making new cases. Small final cavity fields are included; large rotor final fields remain at the recorded local case paths.

## Evidence integrity

manifest.json inventories every package member by byte count and SHA256. The reviewed candidate ZIP was CRC-tested; review_history/ preserves its original README/manifest and independent review. The publication manifest covers this directory. Timings in raw OpenFOAM logs are incidental functional-test counters; no relative performance conclusion is made under the concurrent build load.
