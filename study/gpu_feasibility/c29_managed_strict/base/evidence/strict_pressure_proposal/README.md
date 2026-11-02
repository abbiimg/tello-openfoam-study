# Strict pressure five-step proposal

This is SOURCE ONLY, prepared after both original five-step runs failed the unchanged continuity criterion. It is not authorization to compile, restore, initialize or run. Original code, cases, v2/v3 reports, the approved candidate and `d6001e84…` threshold file stay intact.

The only changed linear-solve setting is **first `p` relTol 0.05 → 0**, at the same absolute tolerance `1e-7`. `pFinal` stays at relTol 0. `U` stays at 0.05 and `UFinal` at 0. Two pressure correctors, all other solver/scheme settings, five fixed `1e-4 s` steps, initial `.600` state, stress/source/flux operators, boundaries and pressure gauge stay fixed. Stronger pressure solves are not a guarantee that the continuity screen passes.

`C29Restrictions_strict_pressure.patch` is for a NEW versioned private clone of the compiled native v2.2 source. It changes only the exact admitted protocol ID and expected pressure relTol. Apply it to neither the frozen candidate nor an existing build. A later approved clone needs a separately named output executable, new source/binary/library identity, and fresh input/launch receipts. Neither verbatim fragment is copied or edited here.

Root would prepare a separate fresh case root with the same three role names, from the original pinned seed/CPU override. Never continue from `.6005` or copy an advanced controller state. Change only first `p` relTol to zero in each fresh `fvSolution`; retain original Foundation14 PIMPLE/model and native PISO adapter. Set the new exact native control protocol `c29-native-five-fixed-steps-strict-pressure-v1`; fresh custom permissions start false, with unique external receipt paths. Reuse the independently pinned original C29 library only for the fresh Foundation control, without rebuilding it. Use the same cached F14 geometry accounting. Repeat exact initialized U/p/phi comparison before timesteps; do not assume the prior startup gate covers new cases/binaries.

The separate analyzer candidate requires `--pressure-protocol` explicitly. `legacy-v1` keeps 0.05. `strict-pressure-v1` uses **configured first-pressure relTol 0**, with the original formula `max(1e-7, configuredRelTol * initialResidual) + 1e-12`. Every other d600 criterion and all field/source metrics remain unchanged. No old run is retroactively qualified. Stage two remains blocked until Foundation14 → native CPU passes; GPU startup/framework/memory gates remain separate and are currently unresolved for the large case.

Strict mode also requires a separate root authorization and input-audit JSON, with exact case paths, `fvSolution` hashes, audited `{U,UFinal,p,pFinal}` criteria, and native `c29PortControls` hashes/new protocol. The helper binds root's dictionary audit to current bytes; it is not another OpenFOAM parser and does not prove solver execution. Root must still bind these inputs and the new executable to immediate-before-launch receipts and actual loader evidence. A CLI flag alone cannot qualify legacy data.

After review and separately authorized fresh runs, the intended analysis invocation is:

```
python strict_pressure_proposal/analyze_five_steps_strict_candidate.py \
  --pressure-protocol strict-pressure-v1 \
  --protocol-audit ROOT_ISSUED_STRICT_INPUT_AUDIT.json \
  --base /opt/openfoam-workspace/cases/ROOT_CHOOSE_NEW_STRICT_ROOT \
  --log-dir ROOT_CHOOSE_NEW_STRICT_LOG_DIRECTORY \
  --stage f14-to-cpu --out ROOT_CHOOSE_NEW_REPORT.json
```

The prospective input-audit schema is `c29-strict-pressure-input-audit-v1`, with `protocol`, `protocol_sha256`, `validation_thresholds_sha256`, `inputs_audited: true`, `root_authorization: {path, sha256}`, and `cases` keyed by `f14`, `cpu`, optionally `gpu`. Each case has `case`, `fvSolution: {path, sha256}`, `audited_solver_criteria` exactly matching the four settings above, and native cases also `c29PortControls: {path, sha256}`. The separate authorization must identify the same protocol/hash and decision `APPROVED_FOR_UNVALIDATED_FIVE_STEPS`. No such authorization or input audit is issued by this proposal.

All local/global continuity observations, including the first corrector, retain their original limits. Source indices, full saved fields and every sample must pass; no averaging or widened limits. Even a future short-test pass would not establish long-time equivalence, production GPU suitability or speed.
