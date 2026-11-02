# Native GPU and same-source CPU OpenFOAM installation

Reviewed local source/evidence publication, 2 November 2026. The [frozen base bundle](base/README.md) is copied byte-for-byte, including its dated review-candidate README. This wrapper records its subsequent local publication. The [independent review](review_history/native_install_publication_independent_review.md) found no blocking finding.

The installed GPU stack uses the exact OpenCFD develop/API2609 source pin, NVHPC26.9/CUDA13.3, SM121 managed memory and CUDA-enabled Umpire. A separate GCC13.3 CPU build uses the same upstream source pin. Compiler, device-only, native Field and strict short-cavity checks passed within the limits documented in the base bundle. Original failures, the current/historical core distinction and the small-cavity CPU-interpolation limit remain visible.

See the [prerequisites](base/EXTERNAL_PREREQUISITES.json) and [reproduction map](base/REPRODUCTION_REFERENCES.md) for source pins, checksums, recipes and scoped patches. SDKs, full upstream archives, binaries, raw traces and environment metadata are excluded. Historical guarded workstation recipes need deliberate fresh-tree adaptation; a fresh-host rebuild was not tested. The restricted trace exporter is used only in a validated fresh owned nonsymlink destination tree.

The newer managed-ownership/strict-pressure C29 rotor variant and its runtime outcomes belong to a separate addendum. This base publication does not establish rotor validity, a speedup or a production-default change. The 84-case Foundation14 CPU lift study is unchanged.
