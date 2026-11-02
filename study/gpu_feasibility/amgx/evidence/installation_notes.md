# Private AmgX 2.5 installation

AmgX and a bounded Foundation 14 adapter are installed and have passed actual GPU, cavity and C29 rotor functional tests. No controlled speed comparison has been run with this adapter. The existing Ginkgo installation, production inputs, live MCP configuration, and system NVIDIA drivers were not changed.

## Installed stack

- Official NVIDIA AmgX 2.5.0, pinned to `cc1cebdbb32b14d33762d4ddabcb2e23c1669f47`; upstream tree remains clean.
- Private prefix: `/opt/openfoam-workspace/gpu-feasibility/amgx-cuda`.
- Shared library: `install/lib/libamgxsh.so`, SHA256 `28385b730dccb1f9aabbd9b0caf37ecd478720889398d0df8c65e5d24ce7ef58`.
- Foundation 14 adapter: `install/lib/libAmgXPressure.so`, SHA256 `dce4bb6ca9e9d6b1060c10636ebec99f5623194c19e11277b57c90fabaa5fc3c`.
- CUDA 13.0.88 compiler, SM121, GCC 13.3 and CMake 3.31.7. Existing private CUDA components are reused through a separate overlay. Only missing cuSOLVER 12.0.4.66 was downloaded, verified against NVIDIA's redistribution manifest. No drivers were installed.
- Build is explicitly non-MPI. Final linkage uses shared cudart, allowing process-local observation of the actual CUDA 13 launch entry point.

The initial full build used two nice 15 jobs and took 1552.6 seconds. A later shared-runtime relink reused all 163 compiled objects. Subsequent work was capped at one nice 15 compilation job. These build durations are not solver performance results.

## Actual validation

`smoke.json`: manufactured 32³ Poisson system, 32,768 rows and 223,232 nonzeros; AmgX device-double mode `dDDI`, 26 iterations, independently computed relative L2 residual `7.2647e-11`, maximum solution error `5.8634e-12`. The runtime identified the N1X compute 12.1 GPU. Successful CUDA launch API calls were observed inside the solve interval, followed by checked device synchronization and host residual verification. The counter reports intercepted launch calls, not unique kernels or a GPU timeline.

`adapter_smoke.json`: native GAMG and AmgX pilots both completed 20 steps to 0.1 seconds on the same 400-cell laminar lid-driven cavity. All 40 AmgX pressure solves launched observed GPU work; their maximum native normalized residual was `8.0448e-13`, below `1e-11`. Maximum differences from GAMG were `2.4442e-12 m/s` for U and `1.8968e-10 m²/s²` for p. Shared mesh/initial/physics input hashes remained identical.

Tested cases and complete fields/logs are under `/opt/openfoam-workspace/cases/amgx_gpu_pilots_20261102/{cavity-native,cavity-amgx}`. They ran through the existing allowed-root MCP server. An earlier temporary stdio helper is closed and was used only for tutorial copying/schema discovery; its note and unused clone are retained for provenance. `private_mcp_call.py` is a historical diagnostic, not the supported launch route.

`rotor_smoke.json`: fresh 922,576-cell C29 rotor pilots copied the exact frozen `0.6` U/p seed and actuator source/library. Serial GAMG and AmgX each completed five matching adaptive steps to `0.60086186 s`, with successful return codes and `End`. All ten AmgX pressure systems independently met the native stopping criterion and launched observed GPU work (16,310 successful intercepted launch calls). Maximum final-corrector native pressure residual was `5.9732e-9`, below `1e-7`. Final relative L2 differences were `8.3395e-6` for volume-weighted U, `8.3767e-4` for volume-weighted p, and `1.2300e-5` for internal-face phi. Mean lift differed by `2.9124e-7` relative and inferred electrical input by `-1.7504e-5` relative. No continuity deterioration flags remained. All frozen originals, seed and private library hashes were unchanged, and the actuator required no rebuild. These five steps establish bounded compatibility, not stationary aerodynamic accuracy or performance. The short controller-reset transient has mean inferred input near 19.13 W despite the unchanged 19.2923 W target; it is not an equal-power lift optimization result.

Complete rotor pilot fields/logs remain under the same allowed-root directory in `{rotor-native,rotor-amgx}`. The portable publication candidate includes source, recipes, small cavity inputs, rotor dictionaries and raw logs/evidence. The large frozen mesh/warm fields are referenced by their SHA256-verified shared seed package rather than duplicated. No SDK or build binary is in the candidate.

## Adapter scope and use

The adapter enforces serial execution, symmetric matrices, no coupled interfaces and `minIter 0`. It uses GPU 0, device-double PCG/aggregation AMG with Jacobi smoothing. Every solve rebuilds its matrix, resources and preconditioner. Backend stopping includes an extra tenfold safety margin, and the adapter independently rejects a result that fails the native OpenFOAM normalized stopping test. This conservative, uncached prototype is not a tuned performance implementation.

For a fresh case copy, load the absolute adapter library in `system/controlDict`, select `solver AmgXPressure` for both p and pFinal, and retain explicit OpenFOAM tolerances/maxIter. The tested pilot's `AllrunPilot` supplies its private library paths and process-local launch audit; the ordinary MCP runner sources Foundation 14 and executes that script at nice 15 with one solver thread. No global PATH, bashrc or FOAM changes are needed. The audit is optional for later use; a future controlled benchmark must state whether it is enabled, together with setup caching and tolerance policy.

## Reproduction and evidence

The scripts here perform source/dependency fetch, configure, capped build, installation/GPU smoke, adapter build and field verification. They run under the dedicated WSL user `openfoam`; only `provision_prefix.py` requires root to create that exact private prefix. Current `build.py` defaults to one job. `source_pin.json`, `dependencies.json`, `configure.json`, `build.json`, `smoke.json`, `adapter_build.json`, `pilot_manifest.json` and `adapter_smoke.json` retain exact commands, checksums and checks. Earlier audit attempts are explicitly labelled.

Raw scalar L2 semantics were verified in pinned `src/norm.cu` and `src/blas.cu`: square root of the sum of squared magnitudes, with no RMS division. `src/convergence/absolute.cu` compares that norm directly with tolerance. The adapter therefore uses the sufficient bound `||r||1 <= sqrt(n)||r||2`, transformed consistently with the uniform scaling of A and b, then applies its additional factor 0.1. Native final-residual verification remains the deciding check.

[Official release](https://github.com/NVIDIA/AMGX/releases/tag/v2.5.0) · [Pinned source](https://github.com/NVIDIA/AMGX/tree/cc1cebdbb32b14d33762d4ddabcb2e23c1669f47)
