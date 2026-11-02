# Read-only C29 CPU evidence map

Completed 2026-11-02. No case or private-prefix files, live GPU transient log/receipt/trace contents, build trees, binaries, archives, or environment dumps were read. No source, case, delivery, Git, build, simulation, or runtime mutation was performed. The only new files are this map and its companion JSON.

## Confirmed immutable gates

All five supplied principal pins match their actual workspace bytes:

- strict report `strict_runs/f14_to_cpu_analysis.json`: `9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e`.
- Root external gate: `9d1a7729b4368eba60bb7f298836c5f1866dde3dd6e9ab31e4221359edd9cfa2`.
- Root input audit: `5d28b04d822be3c3513e885e985970223da48329f688ab70408639c7ef55b926`.
- strict protocol: `946e8c2a0e566cbfb5e494af2da1cf94ba3f3102567c8db36135fd1a758de8fd`.
- Root authorization: `8ea985fb7143d34fecfa2e6b7277b971466fbe9426a5013db98f4ebdfd259b56`.

The report contains exactly **499 checks, all true**, 15 field comparisons and 5 source samples. The five saved times are 0.6001 through 0.6005. F14 actual PID390944 and native CPU PID391146 each returned0, printed End, passed actual identity, retained original inputs and loaded expected libraries. These are recorded claims cross-bound by Root; this mapping did not rehash external executables/libraries or reopen the cases.

Across all internal/boundary blocks and five steps, maximum normalized RMS/max errors are U3.5706690971909314e-7/7.899263823049269e-7, p1.033469833775196e-6/5.405231464379313e-6, and phi1.7135986943370432e-7/1.4337817807435926e-6. These transient fields are threshold-equivalent, not bitwise identical.

Initial computed startup is a preserved **FAIL**, SHA81c826eb089d6eb0aa52aa9ee8405944b202e8407853c023cbcc59b59a541489: GPU phi maximum internal difference3.1742559698354905e-19, boundary5.421010862427522e-20. `candidate/validation_recipe.json` line86 explicitly allowed STOP or separately authorize/pin one F14 common phi copied to BOTH fresh controls; this fallback was declared before runtime. `strict_initial_shared_fallback.json` records canonical phi SHA `f5bb13f6e8d90b181bb6e711d09b80d251e4598f63651f8b3cddc26b238b342c`. Repeated shared startup report SHA `6da117692c579c345bcddafab1d1f9a9f92858bbbd63c61f96bd1f56e382a3d7` records zero difference for every stored U/p/phi internal and boundary value block for both backends.

The legacy relTol.05 report `f14_to_native_cpu_validation_v3.json` SHA `9ac760b08a489047db94a3b98ff9733f1569f86f9efaa250999a45f7b3ca61e3` remains failed: 499 checks, exactly4 global-continuity failures, first pressure correctors of steps1/2 in both F14 and nativeCPU. Keep it separate from the new strict pass; no failure waiver is supported.

## Exact evidence selection

The JSON companion lists size/hash records for36 execution sources/evidence files and all30 saved field hash references. Copy explicitly selected terminal evidence, not the whole mutable `strict_runs` directory:

- `strict_runs/{f14_control,native_cpu}_five_{execution,prelaunch}.json` and corresponding stdout logs; strict report, external gate, input audit/binding, resolved queries, launcher review, phase edits/archive and `previous_controls`.
- `strict_initial_runs` terminal CPU/F14/GPU initial-only receipts/prelaunch/stdout and failed comparison.
- `strict_initial_shared_runs` terminal CPU/GPU initial-only receipts/prelaunch/stdout and exact comparison, plus fallback record.
- Complete frozen strict proposal, ownership `_b`, managed/strict combined source groups and their review histories. The active GPU five-step files are excluded until Root supplies terminal outcome.

## Dependency closure and aliases

`analyze_five_steps.py` needs exact sibling `compare_initial_cpu.py` SHA071202fdd5e9fa623f98701054e48ebea39d271be78171ce228a665b9292850c, sibling-parent `geometry_reference/reference_axial_speed.py` SHAc223006e824d1d40cc5dcd5d42e8ebc0e3a9a151d5a25f8a3e40ea93faa9699f, `candidate/validation_thresholds.json` SHAd6001e84a626ea18d806859c18600f69ab703c03660817545e97d7a367e0be9b, strict admission module/audit, logs and saved fields. The axial helper hardcodes an external geometry cache requiring `quadrature.csv` SHA5d786c48c11b80b1f4d45c989f8873d22314c9ea2118fda3bfbdaf3b44930db1 and `rotors.csv` SHA41fe936fc5ad3eb63c3756c808ce9b22c67ed0c5abad17e03c130c0ac3bc75ff. Include those small CSVs or document their pinned reconstruction and alias; hashes alone do not make the helper runnable.

`prepare_strict_pressure_cases.py` imports sibling `prepare_native_c29_cases.py` SHAd7064bde61a40764965436b4c1935d1a3cd63e54f5a2cf694fae898014c7135c, and needs complete `candidate` manifest/recipe/templates/sources, strict protocol/auth, existing benchmark reproduction override/catalogue, AmgX cache evidence and external cached F14 library pin402b112e09f36444ac13d19a3a04f3aca24344a632eb7a258fd11fc3a33392ce. Do not deliver that ELF; supply existing source/rebuild procedure and explain original execution reused the exact cache without rebuilding.

The strict initial/shared and CPU launcher sources also require `candidate/{audit_candidate.py,admission_audit.py,validation_recipe.json,validation_thresholds.json}`, combined-source manifest7e4492d4d644e3b03211315f0a0c692db5b6652edb063cf2779a6ff1db9cbaf5, corresponding per-backend library identity JSONs, actual unique launch receipts and pinned controls. Those external receipt JSONs may need explicit later curation; execution records bind them by hash but do not embed their contents.

Keep immutable historical scripts byte-identical and expose their exact historical layout/path aliases. They contain hardcoded workspace/private/case paths and one-shot/exclusive-output guards; do not describe them as a turnkey new-host installer. Full parent-relative topology is safer than collecting flattened scripts. A reference map must distinguish package-relative sources, external pinned prerequisites and historical case/runtime paths.

## Field and mesh policy

Reuse the existing CPU84 `benchmark_reproduction/shared_seed.zip` SHA89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb/62823211B and corresponding overrides to restore identical mesh/U/p. Do not duplicate that seed or full unchanged mesh in this addendum.

Independent numerical reevaluation requires all30 saved U/p/phi output fields for both F14/nativeCPU at allfive steps, or an explicitly verified lossless numerical representation retaining original file hashes. The 499-check report alone and field hashes are evidence, but cannot reproduce comparisons without values. The canonical common initial phi is new relative to the seed: preserve it once or include exact F14 utility source/reproduction recipe and its canonical byte hash. If storing fields, deduplicate by SHA and map role/time/field names to immutable blobs; no case source bytes need modification. The JSON lists every exact field path/hash for this purpose. No actual field files or private cache were opened here, so their sizes/content-copy verification remain the curator's task.

This gate establishes only strict shared-phi F14-to-nativeCPU five-fixed-step compatibility. No GPU transient qualification, speedup, production default, settled lift, equal-power optimization or fresh-host rebuild result follows. Keep live GPU evidence pending.
