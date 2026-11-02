# Actual offline completed-evidence reproduction

**PASS**, completed 2 November 2026 at 15:15:49 UTC. This is one actual fresh evidence restoration and one offline numerical replay, not a CFD simulation, new science result, GPU qualification or new-host build.

The independently reviewed frozen v2 package manifest remains **6b2994a2aae47fdad8dcb57b36add85b48e21d16f8f4be62ea34a408d3cdf884**. Its complete 518-file inventory and all hashes, sizes and original mtimes match before and after. The seed89c…, reproduction cataloguee75… and every used CPU override dependency also match before and after.

The unchanged `recipes/restore_completed_evidence.py` ran once as dedicated UID 999 into the fresh canonical directory `/opt/openfoam-workspace/cases/c29_offline_completed_replay_20261102`, outside package and seed sources with no linked ancestors. Actual waited Python child **PID 1777135 returned 0**. Independent catalogue reconstruction verified **all 91 restored files exact**, with no missing or extra files: published shared seed, CPU overrides, strict role overlays, canonical initial phi, all 30 saved fields, and two correctly relocated offline audit receipts. Allrun remains inert; it was never executed.

The unchanged `recipes/replay_completed_cpu_analysis.py` ran once with system **NumPy 1.26.4**. Actual waited Python child **PID 1777156 returned 0**. The new report `work/c29_completed_offline_replay_analysis.json` has **499 checks, zero failures**, and all 499 check records are exactly equal to the original strict CPU report9514…. Its SHA256 is **c82065bd31fc53affb4df68d9559f3e7d93c0b09b05ee7ff93330954a4360087**. Runtime admission remains false. The restored file tree, including hashes, sizes and mtimes, is unchanged after analysis.

Exactly **one restore command and one replay command** were issued; no retry, overwrite or cleanup was performed. The harness itself ended 0. No Allrun, OpenFOAM solver, compiler, profiler, GPU command, Git or delivery-output publication ran. Frozen candidate bytes were never edited. The completed fresh tree and all receipts remain available for review.

## Command and provenance records

- `work/c29_completed_offline_started.json`: harness/review/manifest pins, UID, Python/NumPy identity, intended scope.
- `work/c29_completed_offline_before_inputs.json` and `after_inputs.json`: complete package/seed snapshots and restored-tree immutability.
- `work/c29_completed_offline_restore_child_start.json` and `restore_child_exit.json`: exact command, PID/UID/birth tick/nice, true wait status, log hash.
- `work/c29_completed_offline_replay_child_start.json` and `replay_child_exit.json`: equivalent actual replay evidence.
- `work/c29_completed_offline_restore.log` and `replay.log`: preserved original command stdout/stderr.
- `work/c29_completed_offline_restored_catalogue_before.json`: exact91-file restored hashes/sizes/mtimes; corresponding after catalogue is in `after_inputs.json`.
- `work/c29_completed_offline_result.json`: terminal aggregate, no retries/failure, both immutability gates true.
- `work/run_c29_offline_reproduction_once.py`: exact once-only harness; independent source audit is `work/c29_offline_harness_independent_review.md/json`.

All receipts are outside the frozen candidate. Root owns later publication and coherent ZIP refresh. The failed managed2.3 GPU transient remains unqualified; successful offline replay does not change that result.
