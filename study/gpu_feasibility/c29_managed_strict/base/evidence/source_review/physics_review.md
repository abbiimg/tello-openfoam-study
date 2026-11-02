# Static physics/API review: C29 host source with a native GPU finite-volume core

This is a **read-only source review**. No solver/application/vendor/SDK/case files were edited, no compiler or simulation was run, and no network or performance measurement was used. Root owns a separately named candidate after this review. Parent reports that native/SPUMA core arithmetic gates now pass; full finite-volume/solver and C29 application validation remain separate.

The plan is feasible as a **restricted, separately named laminar hybrid application**, not by inserting the force into otherwise bare `icoFoam`. Mandatory items are exact local epsilon aliases, the full face-based viscous correction, source-matrix subtraction, explicit `UFinal`, matching pressure/Euler/BC controls and fixed-step reference tests.

## Preserved source and wrapper contract

The actual original `constant/fvModels` hashes to `29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd`; its extracted body is `ff02e46f3857af75dfff6f69533c97a7baf2cff2478c2b7e7193d0e8aaaf64a7` and includes are `c51376a789cb9b1b52cff384235ea73522c765d457bdb2af5c330ca9d158da83`. Both existing `.inc` files match the original bytes. Do not rewrite them.

Include the preserved header fragment at translation-unit scope after ordinary FV headers. Supply a callable `mesh()` and nonconst matrix parameter `eqn` inside a host function. The following is a source-based outline, **not compiled implementation**:

```cpp
// Translation-unit scope: fvCFD/native FV headers, <limits>, <type_traits>,
// then #include "C29_includes_verbatim.inc".
static_assert(std::is_same<Foam::scalar, double>::value, "C29 reference is DP");
void addC29Host(const Foam::fvMesh& caseMesh, Foam::fvVectorMatrix& eqn)
{
    using namespace Foam;
    auto mesh = [&caseMesh]() -> const fvMesh& { return caseMesh; };
    constexpr scalar small = std::numeric_limits<scalar>::epsilon();
    constexpr scalar great = scalar(1)/small;
    #include "C29_body_verbatim.inc"
}
```

**Do not alias these names to native `SMALL/GREAT`.** Foundation14 DP `small` is epsilon = **2.220446049250313e−16** and `great` = **4503599627370496** (`doubleScalar.H:60–63`, `scalar.H:73–80`). Native `scalarFwd.H:70–75` uses **1e−15/1e15**. Even `COMPAT_OPENFOAM_ORG` maps lowercase names to those different native values. Function-local constants shadow safely without altering globals or body bytes. Global branch constants outside the wrapper remain a disclosed difference.

Static C29 lists/cache/controller state are shared across calls. Restrict this source lifetime to one unchanged mesh; do not parallelize host calls or reuse it across meshes. Keep the exact 16×16 geometry integration, `−U·axis` averaging, global volume reductions, density 1.225, cap 0.50 N, floor 1 m/s, `.03 s` time constant, signed work diagnostics and once-per-time-index update. The first warm call (`time>0.01`, `last<0`) resets thrust to instantaneous target; cold does not. **Do not pre-call at startup to “prime” caches**, call again in PISO, or resample the corrected velocity for the original TILT line.

## Correct momentum equation and source sign

For this constant-viscosity, incompressible, static/no-MRF case:

\[
\partial_t U+\nabla\cdot(UU)-\nabla\cdot\{\nu[\nabla U+(\nabla U)^T-\tfrac23 I\nabla\cdot U]\}
=-\nabla p-\sum_r T_r n_r W_r/(\rho V_r),\qquad\nabla\cdot U=0.
\]

Pressure is kinematic, viscosity is **1.5e−5 m²/s**, and the source already divides by **1.225 kg/m³**. Do not add another density factor or change pressure to Pa.

Foundation `momentumPredictor.C:36–43` assembles `LHS == fvModels().source(U)`. `fvModelsTemplates.C:40–48,89–95` creates a fresh zero matrix with integrated momentum dimensions; **both branches' matrix `operator==(A,B)` return `A-B`**. Thus:

```cpp
// Materialize the full momentum LHS first.
fvVectorMatrix c29Source(U, UEqn.dimensions());
// Complete previous device work/temporary zero-fill before host access.
addC29Host(mesh, c29Source);
// Ensure host modifications are visible under the chosen memory contract.
UEqn -= c29Source;
```

C29 puts positive craft-normal entries into its temporary source. **Subtracting** them gives air force opposite craft thrust. Adding those positive entries directly to `UEqn.source()` reverses force. Entries already include `Vcell/(rho*Vrotor)` and have integrated dimensions `[0 4 -2 0 0 0 0]`. Do not multiply by volume again. Keep a fresh zero temporary per momentum assembly; no accumulation across pressure correctors and no second active `fvModels/fvOptions` copy.

## Full laminar stress: exact face-flux route

The Foundation path is `divDevSigma(U)` → `divDevTau(U)` → `linearViscousStress::DivDevTau` → `momentumTransportModel::divDevTauCorr`.

- `linearViscousStress.C:98–113` builds `nu_f=interpolate(alpha*rho*nuEff)` and a face correction `q=-nu_f*dotInterpolate(Sf,dev2(T(grad(U))))`, then subtracts `fvm::laplacian(nu_f,U)`.
- Present incompressible `alpha/rho` model multipliers are one and laminar `nuEff=nu` (`Stokes.C:75–83`). They are **not** the actuator's dimensional 1.225 density.
- `momentumTransportModel.C:142–160` names the correction `devTauCorrFlux` and calls `fvm::divc`.
- `fvmDiv.C:102–122` proves **`divc(q,U)=fvm::Su(fvc::div(q),U)`**, with an extra stored face-flux correction only when U flux is required.

A faithful restricted native LHS therefore has the structure:

```cpp
q = -nuFace * fvc::dotInterpolate(mesh.Sf(), dev2(T(fvc::grad(U))));
viscousLHS = -fvm::laplacian(nuFace, U) + fvm::Su(fvc::div(q), U);
```

Native `surfaceInterpolate.H/.C` declares/implements `dotInterpolate`. Native `fvm::Su` has the same explicit-source sign. Only **p** is explicitly flux-required in the current case, so there is no U face-flux pointer to reproduce. If an input requests U flux, either port that pointer behavior or reject the unsupported mode.

Bare `-laplacian(nu,U)` drops this term. A casual replacement by the older cell-centered `div(nu*dev2(T(grad U)))` is not guaranteed to reproduce Foundation's face interpolation, gradient limiting or boundary treatment. A continuum divergence-free simplification does not justify dropping a nonzero discrete correction. Preserve `grad(U) cellLimited Gauss linear 1`, linear interpolation and corrected Laplacian. The existing old-style tensor `divSchemes` entry alone does not implement this face-flux route.

## Final solver selection and relaxation

The original has **one PIMPLE outer iteration, two pressure corrections, zero nonorthogonal corrections**. Foundation `pimpleSingleRegionControl.C:89–102`, `pisoControl.C:73–94` and `fvMatrixSolve.C:330–343` show the momentum solve is marked final **before** the first pressure correction. It uses **`UFinal`, relTol 0**, not U's `.05`.

Bare native ico/PISO does not set that same outer final flag. The least ambiguous restricted fix is an explicit predictor solve:

```cpp
auto predictor = (UEqn == -fvc::grad(p));
predictor.ref().solve(mesh.solverDict("UFinal"));
```

Keep the original `UEqn` for H/rAU/pressure correction. Do not overwrite it with the pressure-added predictor matrix. Native pressure already explicitly selects `p.select(piso.finalInnerIter())`: with 2 corrections and 0 nonorthogonal corrections, retain p `.05` then pFinal 0, both tolerance 1e−7. U/UFinal retain smoothSolver/symGaussSeidel and tolerance 1e−7.

If using native `pimpleControl` instead, configure exactly one outer loop and verify actual final flags/selected dictionaries. Do not assume a same-named PIMPLE implementation is numerically identical.

No relaxation factors are present. Foundation `fvMatrix.C:576–606` returns factor 0 and performs no relaxation. **Never replace that by `relax(1)`**: it can enforce diagonal dominance (`:710–748`) and change the source. `p.relax()` is also a no-op under the present dictionary; changed relaxation inputs require another explicit port decision.

## Euler pressure-flux helper and current boundary equivalence

The original fixed mesh has no MRF and does not construct Uf. Under these conditions `ddtCorr(U,phi,Uf)` uses the ordinary incompressible Euler phi correction:

\[
\delta\phi=\phi^{old}-\operatorname{dotInterpolate}(S_f,U^{old}),\quad
c=1-\min\{\lvert\delta\phi\rvert/(\lvert\phi^{old}\rvert+\epsilon_\phi),1\},\quad
\mathrm{corr}=c\delta\phi/\Delta t.
\]

Foundation zeroes c on all **noncoupled** U patches (`ddtScheme.C:169–188`). Native's `ddtPhiCoeff_` default is **−1**, so its standard interior limiter form agrees; do not claim its default is constant 1. It uses native SMALL and zeroes fixed-value/cyclicAMI patches instead. For the **current farfield**, `pressureInletOutletVelocity` inherits `directionMixed::fixesValue()==true` in both branches, so boundary zeroing agrees. This is not a present-case boundary-mask mismatch. The epsilon difference remains if native core `ddtCorr` is used unchanged.

A small application-local **source-based outline** for exact Foundation epsilon/mask behavior is:

```cpp
const dimensionedScalar rDeltaT = 1.0/runTime.deltaT();
surfaceScalarField dPhi
(
    "foundationDeltaPhi",
    phi.oldTime() - fvc::dotInterpolate(mesh.Sf(), U.oldTime())
);
surfaceScalarField coupling
(
    "foundationDdtCoupling",
    scalar(1) - min
    (
        mag(dPhi)/(mag(phi.oldTime()) + dimensionedScalar
        (
            "small", phi.dimensions(), std::numeric_limits<scalar>::epsilon()
        )),
        scalar(1)
    )
);
forAll(U.boundaryField(), patchi)
{
    if (!U.boundaryField()[patchi].coupled())
        coupling.boundaryFieldRef()[patchi] = 0;
}
// Use coupling*rDeltaT*dPhi instead of native ddtCorr in phiHbyA.
```

This is deliberately limited to static/no-MRF/null-Uf, constant-density Euler. It is not a moving-mesh/rho-weighted/other-time-scheme port. Preserve library oldTime registration and identical startup-phi policy; do not initialize oldTime fields after advancing the clock. The original mapped startup has no phi field, so Foundation computes it from interpolated U. A copied phi must be present identically in both fresh references, or absent in both; do not mix those choices.

Pressure correction must retain `HbyA=constrainHbyA(rAU*UEqn.H(),U,p)`, `phiHbyA=flux(HbyA)+interpolate(rAU)*corr`, `constrainPressure`, two pressure corrections, `phi=phiHbyA-pEqn.flux()`, each continuity diagnostic and `U=HbyA-rAU*grad(p)` followed by U BC correction. Present `consistent=false`, no MRF and no other constraints/mass sources are assertable restrictions; C29 adds no p source.

Both `adjustPhi` implementations already guard with `p.needReference()`, so the native unconditional call is not a current-case mismatch. `totalPressure p0=0` fixes pressure and `setReference` is inactive unless forced; **do not force a gauge or replace totalPressure with fixedValue0**. Compare absolute p here. Foundation's extra tangential-energy term vanishes with the current zero imposed tangential velocity; nonzero/function-valued tangential inputs would need a separate adapter.

## Minimal fresh-case dictionary and timing changes

1. Use a separate renamed application/private case. Do not load C29 a second time through fvOptions/fvModels. The original whole dictionary remains provenance, never a modified production input.
2. Native createFields reads `transportProperties`, so supply dimensioned `nu [0 2 -1 0 0 0 0] 1.5e−5`. This is a syntax adapter, not a viscosity/density change.
3. If retaining pisoControl/createFields, map the original PIMPLE pressure settings into `PISO {nCorrectors 2; nNonOrthogonalCorrectors 0; momentumPredictor yes;}` and use explicit UFinal above. Keep p/pFinal, U/UFinal solvers/tolerances/smoothers; native GAMG source recognizes `directSolveCoarsest`, but build/runtime/device support must still be verified.
4. Preserve Euler, limited grad(U), linearUpwind grad(U), linear interpolation, corrected Laplacian/snGrad, actual farfield BCs and kinematic dimensions. No “temporary” simpler scheme should be silently accepted as the same physics/numerics.
5. Start cross-branch checks from a **fresh shared warm seed** with matching mesh/U/p/geometry/rotorParameters hashes, clock/reset semantics and initial phi policy. Use the **same fixed step sequence** in a fresh Foundation14 reference and the native candidate (`adjustTimeStep false`, explicit deltaT, writes that do not adjust steps, no unrecorded function-object limiter). Original Foundation preSolve/adjustDeltaT occurs before clock increment; bare icoFoam does not implement that adaptive ordering. A fixed-step validation cannot be described as reproducing the archived adaptive history.

## Required gates and unresolved differences

- Check hashes/DP/label size and all supported-scope assertions; zero temporary implicit/boundary coefficients and correct dimensions; source applied once with air/craft force signs and integrated balance correct.
- Match per-rotor weighted volumes/fluxes, controller updates and TILT/work samples at identical times, including cold and warm first-call behavior. Do not substitute a later corrected U into the original diagnostic.
- Compare viscous face correction, momentum coefficients/H/rAU, Euler correction, pressure/flux corrections, actual UFinal/p/pFinal choices, gauge/BC values, U/p/phi and every continuity correction. Set acceptance criteria before examining discrepancies.
- Separate **Foundation14→ported native CPU** equation/branch validation from **same native application CPU→GPU** backend validation. Scalar constants elsewhere, limiters/interpolation/reductions, matrix/boundary layouts and solver/coarsening implementations remain branch differences; dictionary similarity cannot erase them or justify reusing the CPU be7 method signature.
- Full finiteVolume/application linking, parser/runtime-selection coverage, memory legality and GPU work inside actual momentum/pressure time loops remain required. Core arithmetic or startup-only kernels do not establish those gates. Source loops remain host work, so validate the managed/unified-memory completion/visibility contract before host U/C/V/mesh/S access and after source modification. Temporary GPU zero-fill and operations inside Field/List must satisfy host completion semantics; WSL core arithmetic alone cannot prove this.
- Bind the extracted native source archive/pin, all patches/flags/libraries/binary and new wrapper/helper hashes into a new method identity. The local extracted directory has no `.git`; this review records actual source file hashes rather than inventing a commit.
- Only after functional accuracy passes may root authorize representative end-to-end timing against the best valid CPU control with matched steps/accuracy and declared startup/cache/source work. This review makes **no compilation, CFD accuracy, GPU performance or production-adoption claim**.

The concrete mandatory corrections are narrow enough for a separate candidate. This static review does not implement or authorize that candidate; it leaves all original/source/vendor/SDK/case files and preserved fragments unchanged. Detailed file hashes, equations, input adapters and gates are in `physics_review.json`.
