# C29 native hybrid application — source-only candidate v2

**Not compiled, linked, run, numerically validated, timed or approved for execution.** Root must review this candidate and coordinate native library readiness before any build or case restoration. No native/SPUMA/SDK/study/Git files were changed. The 84 CPU study results are unaffected.

The separate executable is `c29NativeHybridFoam`, derived from the exact native OpenCFD icoFoam snapshot in `upstream/`. Original GPL headers are preserved; `COPYING`, actual file hashes and a unified patch accompany it. The extracted tree has no local Git checkout: build-owner archive/pin, patches, compiler flags, loaded libraries and binary hashes must enter the **new method identity**. Do not reuse the Foundation14 be7 signature.

The exact reviewed v1 is preserved in sibling `candidate_v1_snapshot/` with its original d8e40e… manifest; the independent review is preserved separately as `candidate_review_v1.md/json`. This v2 responds to C1–C3. It is an author correction, not independent approval or a passed experiment.

## Source contract

- C29 body/includes are unchanged bytes (ff02e46… / c51376…). The host wrapper supplies mesh(), eqn and local Foundation DP epsilon/great, not native SMALL/GREAT. Lazy geometry is materialized without calling/priming C29.
- Full laminar momentum uses `-laplacian(nuFace,U)+Su(div(devTauCorrFlux),U)`, with `devTauCorrFlux=-nuFace*dotInterpolate(Sf,dev2(T(grad(U))))`. This is the reviewed Foundation14 divc identity for **!fluxRequired(U)**, rather than bare ico diffusion or a cell-tensor shortcut.
- A fresh zero temporary matrix receives C29; **UEqn subtracts it**, giving air force opposite craft thrust. No additional fvModels/fvOptions source is instantiated. The preserved controller/geometry/loss/work law samples pre-predictor U once per time index, including its original warm reset.
- Momentum explicitly solves a temporary pressure-added predictor with **UFinal**, preserving the original UEqn for pressure correction. PISO has two pressure and zero nonorthogonal corrections; p/pFinal selections remain explicit. No relaxation is applied, relaxationFactors are rejected, and `relax(1)` is not substituted.
- The restricted Euler correction uses local Foundation DP epsilon and all-noncoupled patch masking. Current pressureInletOutletVelocity is fixed-value-like in both branches, so the current boundary mask agrees. TotalPressure/zero tangential input and its anchored gauge are retained; no forced reference.
- NVTX covers overall/individual time loops, momentum assembly/predictor, each pressure correction and the verbatim source. These are annotations, **not proof of GPU work or performance**.

`C29Restrictions.H` rejects unsupported inputs: the initial protocol is serial, 922576 cells, static mesh, constant nu = 1.5e-5 m²/s, kinematic p/volumetric phi, the pinned farfield types, five fixed steps from .600 to .6005, the original schemes/criteria, no MRF/options/constraints/function objects/runtime edits/relaxation/U flux storage. More flexibility requires another review and signature; this is not a general module replacement.

## Host source and managed memory

C29's main loops remain serial host work; native Field/matrix helpers may offload. Checked CUDA synchronization covers source entry/zero-fill, exit, assembly/pressure temporary lifetimes and host audit access. GPU mode checks device managed-memory capability and that C/V/U/source/points data are CUDA-managed; this first candidate rejects other pointer modes instead of inferring safety.

**Boundary fences cannot prove completion inside every unchanged Field/List helper.** The custom controls now require false-by-default permission to conduct an **unvalidated experiment**, not booleans claiming prior memory validation. `allowUnvalidatedBackendExperiment` and the selected phase permission must be explicitly enabled after root reviews the proposed experiment. Initial-field-only mode requires `allowInitialFieldsOnlyExperiment` and skips unused C29 helper/geometry prerequisites; five-step mode requires `allowFiveStepSourceExperiment`. Admission and its external receipt are checked before mesh/field construction. All pointer checks/fences remain. CUDA errors are fatal; there is no silent CPU fallback. Actual managed/helper legality remains an acceptance question, particularly when concurrentManagedAccess = 0.

C29_USE_CUDA selects audit/fences; it does **not** select or prove the library backend. A CPU companion requires independently verified CPU libraries/compiler policy. GPU mode must use real matching libcudart, not link stubs. Actual paths/flags/library hashes must enter provenance. Strict managed-only checks may reject an otherwise usable unified-memory setup: support must be added explicitly after evidence, not bypassed silently.

## Wrapper source observations and proposed preregistration

Neither verbatim fragment changes. Immediately around the single call, wrapper-only diagnostics check exact source dimensions, fresh zero source/implicit/boundary coefficients, unchanged zero implicit coefficients and one call/update per consecutive index. They report per-rotor volume/flux/w, previous/current thrust, dt and index without duplicating or testing the unchanged controller law; original TILT samples must be compared across references. The diagnostic repeats existing quadrature on the **same unchanged pre-predictor U** immediately after the include; it is cache accounting, not a later sample or independent geometry experiment.

Positive temporary-source integration must give craft force and work **−Pair**. The actually applied matrix delta must give opposite air force and work **+Pair**. Both are observed/asserted, including density and volume accounting. `C29_ROTOR_AUDIT`, `C29_SOURCE_AUDIT` and `C29_APPLIED_AIR_AUDIT` make those checks reviewable. Extra full-array scans/snapshots are validation overhead; this is not a tuned timing path.

`validation_thresholds.json` freezes proposed precision identities, source-accounting tolerances, practical five-step Foundation14→native CPU and native CPU→GPU field/force/work criteria, residual/continuity/Courant checks and metric definitions **before candidate runtime**. Root must review/approve its hash before testing. Exact startup identities are distinct from cross-branch tolerances; no failing sample is averaged away. These proposals are not uncertainty bounds, successful results or a convergence/physical-model claim. The source accounting constants in C29ValidationThresholds.H match that proposal.

## Deferred build recipe — not executed

Root must first coordinate native finiteVolume/meshTools/library readiness and review the source/patch manifest. The source-only audit is:

```
python3 audit_candidate.py
```

For a later approved wmake, set C29_APPBIN to a new private output directory, C29_CUDA_INCLUDE/C29_CUDA_LIBDIR to reviewed real CUDA runtime paths, and C29_NVTX_INCLUDE to the NVTX3 include root. Missing paths are errors. Use the native owner's reviewed environment/backend compiler flags; this candidate changes no SDK/rules and invents no GPU linear-solver options. C29_USE_CUDA = 1 and C29_USE_NVTX = 1 are defaults. All API/link support remains untested. Record actual flags, loaded libraries and binary hashes.

## Planned fresh five-step comparison — no cases created

`validation_recipe.json` pins shared_seed.zip SHA 89c281… (62,823,211 bytes), reproduction manifest e75dea… and original cpu_serial override manifest 5194b4…. Use the published `outputs/tello_refinement/gpu_feasibility/amgx/recipes/restore_pilots.py` safe extraction/pin logic as a reference; do not edit the published bundle or restore into existing roots. A new root-selected private destination must refuse existing paths, symlinks and study/vendor roots. Do not execute the old Allrun/benchmark scripts or treat old manifests as new execution authorization.

The **actual seed is flat N8 square, nearest 10 cm, box 27.62 cm, D = 7.62 cm, h = 12 mm, inferred battery input 19.2923 W**. It is not the best tested 7.5° design simply because the generic C29 reference dictionary was collected there. RotorParameters SHA is 228b2bb…; 0.6/U is 40c9eb… and 0.6/p is 0f802d…. Exact vectors are in `reference_seed_geometry.json`; all unchanged mesh/parameter/field hashes are in the recipe.

After authorization, prepare two new controls:

1. **Foundation14 control:** frozen shared seed + cpu_serial physical/numerical overrides, original C29 model/PIMPLE/viscosity/BCs. Change only fresh time/output controls to fixed dt = 1e-4, .600→.6005, exactly five steps, no runtime edits/functions and matched write cadence/precision. Archive the fresh changed dictionaries. This differs from the published adaptive five-step AmgX/Ginkgo pilots; none of their trajectory/acceptance results proves this new protocol.
2. **Native candidate:** same mesh/U/p/geometry/parameters/schemes, native transportProperties syntax/PISO adapter, original linear solver criteria, renamed app and guarded c29PortControls. Original fvModels remains byte-identical provenance but is not instantiated as another source. Never load Foundation dynamicCode or pressure-adapter libraries into this app. The text templates are recipe fragments, **not a case**.

The unchanged C29 warm reset occurs in a fresh process at its first .6001 source call. Do not transfer controller history, prime it at .600, or interpret this as continuation of the original controller state. The new protocol is a short functional check, not another converged lift experiment.

## Exact startup phi gate and optional Foundation14 fallback

The seed has **no phi**. Initially both branches may compute linear initial flux from the pinned U. Native `-initialFieldsOnly` writes separate c29_initialU/P/Phi audit objects and exits before C29 or any timestep; U/p/phi inputs are not overwritten. Root must obtain the matching Foundation initialization audit independently and require exact initialized numerical U,p,phi agreement before accepting a five-step trajectory. Do not equate byte-pinned U/p with automatically identical computed phi.

If computed phi differs, **stop** or use the included source-only `foundation14_phi/c29FoundationInitialPhi.C` fallback:

1. After separate build approval, build it with the original Foundation14 environment and a new C29_PHI_APPBIN. Its Make/options rejects other WM_PROJECT_VERSION values. It is not the native GPU application.
2. Restore a **third fresh seed-only mesh/U clone**, verified against the pinned hashes; require the c29InitialPhiControls marker, start .600, writePrecision ≥ 17, serial 922576-cell static mesh and no phi. No existing case may be used.
3. The utility reproduces the original Foundation14 `incompressibleFluid` phi constructor: `READ_IF_PRESENT` (absent here) with `linearInterpolate(U)&mesh.Sf()`. It does no U BC correction, source call, pressure solve or timestep. Only this fresh clone's phi is written.
4. Record the utility/build identity and SHA of that one output. Copy **identical bytes** into both fresh five-step controls, declare `initialPhiPolicy sharedPinnedPhi`, and record this explicit policy change/new input hash. Preserve all U/p/mesh/parameter bytes. Run the initial-field audit again and compare parsed values exactly. Never accept branch-specific initialization silently.

The fallback has not been compiled or executed and creates no cases by itself; it requires an explicit new marker so it cannot operate on unchanged production cases. Its original constructor source hash/reference is in candidate_manifest.json. Root still owns safe restoration and approval.

## Input-to-launch receipt — no generic runner

After actual inputs, experimental permissions and a unique experimentId/receipt path are fixed, `audit_candidate.py --case ABS_CASE --private-root ABS_NEW_PRIVATE_ROOT --backend cpu|gpu --phase initial_fields_only|five_fixed_steps` checks the existing fresh inputs. A common phi additionally needs `--shared-phi-sha256 APPROVED_SHA`. Absolute paths, containment and nonsymlink ancestors are required. Plain/gzip/broken-link variants are rejected consistently; new dictionaries may not introduce unhashed code/include directives or expansions. The reader does not restore a case.

For a later explicitly approved experiment, add `--binary ABS_BINARY --library-identity ABS_IDENTITY_JSON --write-launch-receipt ABS_NEW_RECEIPT.json`. The identity JSON must declare backend and `files:[{"path":"ABS_CANONICAL_REAL_LIBRARY","sha256":"ACTUAL_SHA"},...]`. The script verifies declared library bytes but does not run ldd or prove actual loaded paths; root must supply/check loader evidence. Output stays outside the audited case and refuses overwrite. The predeclared experimentReceiptFile must name its `.foam` companion. Both bind the input snapshot, candidate/threshold hashes, binary/library identity, selected phase/backend, environment and exact **manual argv**. `runtime_validated` is always false. Initial-phi fallback uses phase `foundation_initial_phi`, the CPU utility and its marker, with pinned U/mesh inputs.

Immediately before root manually uses that exact argv, run `audit_candidate.py --verify-launch-receipt ABS_RECEIPT.json`. It rechecks hashes/mtimes, variants, environment, expiry and companion bindings. Default lifetime is 300 seconds, at most 900. C++ requires a matching receipt ID/phase/backend and logs its bindings with `C29_EXPERIMENTAL_UNVALIDATED`; it does not rehash files. Thus root must freeze inputs/environment across the recheck and manual launch. No script here invokes a process, and a receipt is **input admission only**, not scientific acceptance. Use a new ID/receipt and re-audit if phase or custom controls change. All original source/package hashes and mtimes must remain unchanged.

## Remaining acceptance gates

Prerecord thresholds. Check source sign/dimensions, rotor volumes/flux/controller/TILT, all five times, actual UFinal/p/pFinal selections, residuals, each continuity correction and U/p/phi. Verify complete finiteVolume/application linking, actual GPU launches inside momentum/pressure ranges and managed-memory correctness; core arithmetic/startup-only kernels are insufficient.

Native global constants outside the helpers, geometry/Field/ldu implementations, limiter/interpolation/reduction order, BC serialization and GAMG/coarsening defaults can differ. GPU support for the exact requested scheme/smoother/direct-coarsest controls remains unverified. **Fail the parity candidate if unsupported; do not silently replace them.** Keep Foundation14→native CPU branch validation separate from same-native-application CPU→GPU validation.

Only after functional accuracy may root approve representative end-to-end timing including host source, synchronization, setup/cache policy and the best valid CPU control. This candidate makes **no equivalence, speedup or production-adoption claim**.
