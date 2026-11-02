# Independent review of C29 native candidate v2 corrections

Reviewed 2 November 2026. This is a bounded **source-only** review of the C1–C3 corrections, not compilation, launch approval or numerical acceptance. No candidate, vendor, SDK, study, output or Git files were changed; no cases were created and no application or CFD was run. Only this review and its JSON companion were written.

The stable reviewed manifest is `562ff512bf2d5da044226bbc88a6fa8a1f4373395e12d93dbb364f3b4ff3cfe7`. All **35** inventoried files match. Main source is `47a113b8221d829c101dfcb2f1fecfebb2cbf942a0e494af30f3a22b9eab479c`; thresholds are `d6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b`; v1→v2 patch is `90e3b2d1b9e085e96693e737c5b359bef26add34c975260660b1b2863cc08fd5`. The preserved v1 manifest remains `d8e40e2bbe72d2be2df0018a2f3aa6334aa437bd3c25fbf51df85d342b6525bf`, and all its 30 inventoried files match.

**No blocking source correction remains from C1–C3.** The candidate is suitable for root to consider building and testing as an explicitly unvalidated experiment when its library prerequisites are ready. I found no definite new force-sign, unit or source-accounting error. This does not establish compiler/API compatibility, legal completion of every host/helper operation, exact initialization or CFD parity.

## C1: honest, phase-specific experimental admission

The three proof-like review flags are removed and explicitly rejected. False-default unvalidated-backend permission and separate initial-field/five-step permissions are required. Receipt ID, actual case path, phase and compiled backend must agree; the receipt must say input audit only and runtime validation false. The native main reads admission before constructing mesh/fields, logs the unvalidated status, retains device/pointer/fence checks, and skips C29 geometry preparation and source calls in initial-field-only mode. Nothing now requires pretending that the pending helper/memory gate has already passed.

## C2: unchanged source with useful accounting

The verbatim body `ff02e46f3857af75dfff6f69533c97a7baf2cff2478c2b7e7193d0e8aaaf64a7` and includes `c51376a789cb9b1b52cff384235ea73522c765d457bdb2af5c330ca9d158da83` match. The original fvModels was independently hashed at its recorded source path and remains `29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd`.

The wrapper checks integrated kinematic momentum dimensions, exactly zero fresh source/allocated coefficients, unchanged zero implicit coefficients, one call per consecutive index and at most five calls. It observes the actual fragment's update/index and cached per-rotor volume, signed flux/w, previous/current thrust and dt on the same pre-predictor U. It neither makes a second C29 call nor duplicates the controller law as an acceptance assertion. The repeated volume quadrature is correctly described as cache accounting, not an independent geometry test.

The temporary source satisfies `rho*sum(S)=craftForce` and work `-Pair`. The measured change after `UEqn-=source` is checked against opposite force and work `+Pair`; density and integrated volume factors are consistent with the preserved fragment. Finite force/work errors use the declared absolute-plus-relative criteria. The C++ accounting constants agree with the JSON proposal.

I inspected the pinned native declarations for hasDiag/hasUpper/hasLower and coefficient accessors. This pin stores boundary coefficients in flat Field<vector> containers. The observer's nested component traversal remains legal because VectorSpace provides size/cdata, and exact-zero/finite checks still cover every component. It does perform a CUDA pointer-attribute query per coefficient vector; that is validation overhead, not an optimized timing implementation. A later reviewed observer simplification could scan each flat Field directly once.

## C3: input audit and launch binding

The Python reader rejects plain/gzip conflicts, broken symlinks, symlink/junction ancestors, unsuitable roots, missing pinned bytes and unsupported directives/expansions in fresh dictionaries. The no-phi and optional common-phi rules now match the runtime's compressed-file awareness. Foundation fallback admits only a pinned mesh/U clone, requires absent phi and its explicit marker, and treats failed phi writing as fatal.

The optional external receipt binds input hashes/sizes/mtimes, candidate and threshold hashes, binary and declared real-library hashes, backend/phase, relevant environment and exact manual argv. It refuses existing receipts and places them outside the audited case. The separate recheck checks byte/mtime identities, expiry, environment, variants and the companion's bindings. The script contains no process launcher. C++ checks/logs the receipt bindings and honestly does not claim to rehash files or prove actual library loading.

## Preregistered thresholds and remaining limits

The proposals distinguish exact startup identities and tight accounting identities from practical five-step field/force/power tolerances. They separately compare Foundation14→native CPU and the same native application CPU→GPU, specify internal/boundary field normalization and floors, retain absolute anchored pressure, and require individual residual/continuity/Courant checks. Failures cannot be averaged away or thresholds silently relaxed after seeing results. No runtime result was inspected to select them. Root must approve their hash before the experiment; these are short functional-test criteria, not convergence, ranking uncertainty or hardware-validation bounds.

Actual safe restoration, frozen inputs between recheck and manual launch, actual loaded-library evidence, exact initialized U/p/phi, all five source/TILT observations and ten pressure corrections, full field comparisons and loop-scoped GPU execution remain root's execution responsibilities. The Foundation reference must supply the proposed comparison observations independently; candidate diagnostics alone cannot pass cross-branch gates. The original v1 scientific/API review remains bounded source evidence. No pass, speedup or production-adoption claim follows from this review.
