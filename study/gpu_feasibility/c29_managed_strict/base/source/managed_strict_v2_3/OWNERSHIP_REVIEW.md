This is a source-only managed-heap ownership proposal based on the actual native GPU2.2 source. It has not been compiled or run. The copied original candidate manifest and README are historical reference material, and do not authorize launching this changed source. Root and independent review must precede a new versioned build and fresh guarded cases.

The original 922,576-cell initialization failed while calculating phi, before any C29 source call or PDE time step. The 400-cell strict cavity passed, but its 760 internal faces fall below the pinned library's 1,000-item interpolation offload threshold. The separate descriptor control passed with raw managed pointers and with a managed-heap descriptor; the same reference-capture function failed with a stack descriptor at 4,096 items and passed at 400 items. This demonstrates the descriptor-storage mechanism in the control. Compute Sanitizer disabled itself because CUDA initialized before injection, so it did not identify the exact failing full-case kernel or address.

The proposal changes only the ownership and address checks of app-owned field/matrix descriptors. Each constructor argument is retained verbatim, with new + autoPtr and a stable reference bearing the original variable name. Objects remain in their original lexical scopes and retain their original relative destruction order. The autoPtr handles themselves can remain on the CPU stack. No vendor library, SDK, allocation policy, source fragment, actuator physics, operator order, boundary condition, time-step rule, pressure control or tolerance changes are included.

| Stage | Descriptors moved from stack to managed new |
| --- | --- |
| Initial fields | p, U, phi, nuEff |
| Initial audit copies | initialU, initialP, initialPhi |
| Momentum assembly | nuFace, devTauCorrFlux |
| Euler correction | dPhi, coupling |
| Pressure correction | rAU, HbyA, phiHbyA, pEqn |
| Host-source temporary | source fvVectorMatrix |

The existing tmp-owned momentum result, UEqn, predictor and Euler result retain their ownership. Their address checks are added without moving the existing synchronization fences. Host-only controls, dimensioned scalars, counters, SourceObservation and std::vector snapshots retain their storage.

C29ManagedOwnership.H checks the CUDA memory type of each descriptor, embedded primitive Field and data, boundary container, patch Field/data, matrix source/internal/boundary coefficients and offsets. Existing diagonal/upper/lower storage is checked only when present, through const accessors; the checker does not allocate absent coefficients or materialize oldTime fields. U checks occur before the unchanged fvc::flux(U) initializer, in the copied createPhi header. Empty arrays have no data-address check. The CPU companion uses the same heap ownership with CUDA checks disabled. Success logs record address and observed type rather than implying that flags alone prove accessibility.

The checks cover app-owned descriptors and their directly accessible storage. The boundary UPtrList backing pointer table has no const raw-data accessor in this pin, and is not separately inspected. The checks do not establish that every library-internal lambda, descriptor or temporary is safe under managed-memory mode. No generic raw-pointer change to dotInterpolate/Sfi is proposed; geometricOneField support remains untouched.

ownership_only.patch is the complete ownership/instrumentation diff. ownership_proposal_manifest.json binds the native2.2 reference, pinned vendor phi initializer, original fragments and proposal source files. ownership_declaration_reversal_map.json records each exact old/new declaration. mechanical_source_check.json checks that removing this ownership/check instrumentation recovers the original complete source text exactly. That check supplies no compilation or runtime evidence. ownership_review_bundle.json additionally binds these review documents, the declaration map and mechanical check.

After review, the required gates remain a separately versioned build, fresh full-size initialized U/p/phi comparison with the CPU reference, CPU/source parity and the preregistered GPU functional gate. Any separately reviewed strict-pressure adapter must remain a distinct patch. This proposal does not claim the large-case failure is fixed, and supplies no performance result.
