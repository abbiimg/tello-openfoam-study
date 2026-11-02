# SPUMA v2512 source and functional evidence

Published locally on 2 November 2026 after root approval and independent review.
The complete reviewed candidate payload is preserved byte-for-byte. This
publication adds only this status/index wrapper, PUBLICATION.json, an outer
manifest.json and review_history/. The original candidate_manifest.json and
historical summaries retain their original creation-time candidate wording;
the outer manifest is the inventory of this published directory.

SPUMA at commit `1ff2d45c002b7afb599b9dd8c4c6874666242349` passed a distinct,
preregistered 400-cell, five-step CUDA icoFoam cavity check through 0.025 s.
Actual solver-child and Allrun exit codes were zero. Every corrector passed
the unchanged continuity screen (peak local 8.770776844746355e-9), and the
independent final saved-flux calculation passed. The first complete step
contained 2,445 successful observed launch API calls and 2,445 successful
device synchronizations, with no failures and completion synchronization
after the final launch. These are API observations, not unique kernels or
a GPU activity timeline.

The original longer fixture failed its continuity screen and was deliberately
stopped after 12 completed steps (actual child -15). It remains a separate
failed record. The strict fixture uses tighter pressure relTol=0 and a shorter
horizon; its result does not replace the original or establish long-time
behavior, CPU numerical equivalence, actuator/rotor validity or speedup.
The separate device-only executor marker and fixed-pool checks are preserved.

- [Detailed functional summary](SPUMA_FUNCTIONAL_TEST.md)
- [Strict numerical gate](spuma_strict_v2_tutorial_gate.json)
- [First-step GPU API gate](spuma_strict_v2_first_step_gpu_gate.json)
- [Original failed attempt](spuma_original_attempt_diagnostic.json)
- [Reviewed evidence, recipes, source/rules, case inputs, saved fields and logs](spuma_evidence/README.md)
- [Independent review](review_history/publication_independent_review.md)
- [Publication provenance](PUBLICATION.json)

The recipes are guarded historical workstation recipes, requiring deliberate
path/dependency adaptation in a fresh private tree; no new-host rebuild is
claimed. The NVHPC CUDA-C++ support warning and scoped generated-linkstub PIC
workaround remain documented. SDKs, full upstream/build trees, compiled
binaries, credentials, raw .nsys-rep files and full trace SQLite are excluded.
Only the reviewed lossless API/NVTX/process subset is included, with two
required safe strings and no environment or unrelated metadata tables.
See [the overall GPU status](../GPU_SETUP.md) for other backend results and
remaining gates. This publication does not change CPU84 results, archives or
the production backend.
