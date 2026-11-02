# Independent ownership candidate review

Reviewed 2026-11-02 by `stdpar_memory_review`. **Static result: acceptable for controlled compilation and the full-size initial-fields-only gate. No blocking source, API, or lifetime defect found.** This review does not establish successful compilation, managed allocation, full-size execution, numerical parity, or CFD validity.

## Frozen inputs and checks

- Candidate: `ownership_candidate_v2_3_source_only_b/`.
- Ownership proposal manifest SHA256: `689b261f3a91f280719ba575d48b4b56187cc442cf032728dd8f80ba63088203`.
- Ownership patch SHA256: `85439b77952af6e249af54bf3576c5517fb570a1e4d0324e5617585fe193dcb9`.
- Reference: `/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_compat_v2_2_20261102/source`; all 36 original-reference hashes match files read directly. The corresponding `native_cpu_compat_v2_2_20261102/source` has the same 36 files byte for byte.
- All 39 candidate files listed in the ownership manifest match their recorded hashes. The historical `candidate_manifest.json` is unchanged and is not the identity of this new ownership proposal.
- Independently regenerated the six-file unified diff from actual reference/vendor/candidate bytes; it equals `ownership_only.patch` byte for byte.
- Exactly four pre-existing reference files change: main application, `createC29Fields.H`, `C29Operators.H`, and `C29HostSource.H`. The new implementation headers are `C29ManagedOwnership.H` and `createC29ManagedPhi.H`.
- Each of the 16 declaration transformations occurs once. Reversing them and removing only the new ownership includes/address-audit calls reproduces all four original files exactly. Reversing the phi declaration reproduces pinned vendor `createPhi.H` exactly (SHA256 `3bffc7d3f5a4161e528183596a7e029ae7989b1583019db5b77dc2e82313d0cd`).

## Ownership and lifetime assessment

The earlier inventory is fully covered:

| Scope | Owners, with candidate declaration lines |
| --- | --- |
| Main field scope | `p` 25, `U` 44, `nuEff` 71 in `createC29Fields.H`; `phi` 38 in `createC29ManagedPhi.H` |
| Initial-copy block | `initialU` 75, `initialP` 82, `initialPhi` 89 in main |
| Momentum helper | `nuFace` 22, `devTauCorrFlux` 28 in `C29Operators.H` |
| Euler helper | `dPhi` 57, `coupling` 66 in `C29Operators.H` |
| Pressure-corrector scope | `rAU` 136, `HbyA` 142, `phiHbyA` 148 in main |
| Nonorthogonal-corrector scope | `pEqn` 163 in main |
| Host-source helper | `source` 113 in `C29HostSource.H` |

Each owner directly constructs the original type using the original constructor argument text. The original variable name becomes a reference to the owned object. No owner is transferred, reset, or escaped. Owner declarations retain the original lexical scope and ordering, so their pointee destructors run in the same reverse order as the original automatic objects. The new reference aliases own nothing. Exact IOobject arguments, registration flags, names and write options remain intact; object construction/destruction still performs registration/unregistration. The mesh and time outlive their fields.

Existing `tmp` owners for momentum result, `tUEqn`, predictor, and Euler result remain intact. New audit calls inspect these objects; they do not introduce new owners. All original checked synchronization fences remain, including before helper temporary destruction, predictor destruction, pressure-matrix destruction, and PISO field destruction. The source matrix survives through source evaluation, subtraction, synchronization, and accounting. No earlier `oldTime()` access is introduced; its existing expressions are byte unchanged.

## Address audit and pinned API assessment

`C29ManagedOwnership.H:10` requires CUDA memory type `cudaMemoryTypeManaged` for each nonempty inspected address. `managedArray` at line 27 checks both the descriptor and its separate data. `managedGeometricField` at line 33 checks the owning object, primitive Field descriptor/data, boundary container descriptor, and each patch Field descriptor/data. The U checks at `createC29Fields.H:59` occur before the phi initializer at `createC29ManagedPhi.H:49`, which still calls `fvc::flux(U)`.

`managedMatrix` at line 44 checks the matrix, inline source/internal/boundary coefficient descriptors and data, offsets, and already-present diagonal/upper/lower fields. The pinned APIs support these calls:

- `autoPtr.H:100` takes ownership of `T*`; its destructor at 140 deletes that pointer. `autoPtrI.H:140` returns the pointee by reference for `operator()`. No copy/move owner behavior is invoked by these declarations.
- `GeometricFieldI.H:43` and 52 return existing primitive/boundary const references. These audit calls do not invoke the mutable accessors that update event counters or store old times.
- `fvMatrix.H:490`, 497, 510 and 551 return existing const Field/list references. The coefficient fields are flat `Field<Type>` storage in this pin, so `cdata()`/`size()` are available.
- `lduMatrix.H:779` checks stored coefficient pointers without allocation. The const accessors in `lduMatrix.C:203`, 243 and 314 only return existing coefficient fields; the candidate guards each with the corresponding `has*()`. Nonconst allocating getters are not selected because `managedMatrix` takes a const matrix reference.
- `UListI.H:314` returns the existing data pointer. It does not allocate or copy storage.

This supports the source-level legality of the implementation. Only compilation and actual address logs can confirm NVHPC treatment of every allocation. The audit is a snapshot of explicitly inspected objects; it does not prove every library-internal descriptor, boundary pointer-list backing store, historical field or later reallocated buffer accessible. Those are limits of the audit, not demonstrated defects in this patch.

## Preserved scope and remaining gates

`C29_body_verbatim.inc`, `C29_includes_verbatim.inc`, restrictions, source accounting, experiment admission, validation thresholds, backend audit, Make files, recipes and reference geometry match the private reference hashes. All equations, operators, constants, controls, source calls, original fences and arithmetic remain exact after ownership/audit reversal. No strict-pressure adapter is included. No ListPolicy, vendor, SDK, library or case change is part of this patch.

Retain the existing validation sequence: build the same revised application source for CPU/GPU; run the full-size initial-only gate with actual exit status and type-3 descriptor/data evidence; compare all initialized U/p/phi values and boundary data; only then proceed through separately authorized PDE/source/continuity gates. The prior controlled raw/heap/stack test motivates this patch, but it does not attribute the exact full-case faulting instruction or prove this app-only change sufficient. A later combined strict-pressure/renamed-app source needs a new identity and review of that separate diff.

This reviewer read files and headers and computed comparisons/hashes only. No build, GPU diagnostic, CFD application, or candidate mutation was performed. The only written files are this review and its JSON companion.
