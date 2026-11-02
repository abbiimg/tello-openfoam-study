# Historical references and path aliases

Every copied original is byte-identical. Absolute workstation paths in old scripts,
receipts and manifests describe the recorded experiment. They are not links that
will work on another host. `HISTORICAL_SOURCE_ALIASES.json` maps every copied
original source pathname to its package-relative aliases. No original was patched
to hide those paths.

| Historical group | Bundled source/evidence or explicit dependency |
|---|---|
| work/gpu_actuator_port/candidate | source/legacy_candidate_v2_2 and exact recipes/candidate alias |
| ownership_candidate_v2_3_source_only_b | source/reviewed_ownership_b |
| managed_strict_combined_v2_3/source | source/managed_strict_v2_3 |
| managed_strict_combined_v2_3 build records | evidence/build |
| execution/strict_pressure_proposal | evidence/strict_pressure_proposal and recipes/execution/strict_pressure_proposal |
| execution/strict_initial_runs and strict_initial_shared_runs | evidence directories with identical names |
| execution/strict_runs completed CPU receipts/logs/audits | evidence/strict_runs |
| strict_runs GPU V1/intermediate/V2/V3 proposal freezes | recipes/profiling_history; reviews/diffs in evidence/strict_runs |
| closed managed2.3 functional_profile_v1_20261102 | evidence/gpu_transient_failure, named safe receipts/logs only |
| case receipts, historical controls | evidence/launch_receipts and evidence/strict_runs/previous_controls |
| exact Foundation14 phi utility private source | source/foundation14_phi_actual_v2_2, evidence/foundation14_phi_build |
| recorded Foundation14 codedFvModel source/Make | source/foundation14_recorded_dynamicCode; compiled ELF/object excluded |
| completed strict case inputs/output fields | case_inputs, saved_fields, shared_initial/phi, their catalogues |
| f14_geometry_reference_20261102/cache | geometry_cache/quadrature.csv and rotors.csv; helper location adapted only by offline replay wrapper |
| benchmark_reproduction | external existing peer, complete in CPU84 setup, pinned in DEPENDENCY_MAP.json |
| native-stdpar and native-cpu-control env/source/SDK/toolchain | external published native_installation base plus separately downloaded pinned prerequisites |
| application/core/system/driver binary paths in identity records | historical hash identity only; rebuild/host prerequisite, binaries excluded |
| .nsys-rep/fullSQLite/private profiler temp paths | deliberately private and absent; no incomplete-capture GPU API qualification |
| old native_c29_validation_20261102 relTol.05 | separately labelled evidence/legacy_relTol005; failure never promoted to strict pass |

The original host-specific restorer refuses an existing hardcoded root and requires
the exact historical cached Foundation14 library. Its portable-source dependency
does not imply that the ELF is bundled. Rebuild in a fresh environment when doing
future CFD. The optional offline restoration helper uses only the pinned seed,
portable case overlays and exact saved fields, and grants no runtime permission.

New offline wrappers are clearly separate from all historical sources. They adapt
only package paths and preserve original formulas, acceptance limits and hashes.
They have not established any fresh-host CFD result or GPU support.
