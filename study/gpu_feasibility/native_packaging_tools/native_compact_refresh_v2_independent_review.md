# Native compact refresher v2 — bounded incremental source review

Verdict: **no concrete source blockers**. The narrow change repairs the SPUMA component's two manifest-required hidden markers. The v1 operational limitations still apply: root must close all writers before execution, and postpublication failures require manual review of the retained backup. This review does not execute or authorize packaging.

| Input | SHA256 |
|---|---|
| `refresh_compact_native_v2.py` | `8d715ae0cf688f4397a385a575528ae0ee78b3a066ad88931f0116e3428a24d0` |
| `PLAN_V2.txt` | `a7a09ed0edc1f1a8d2a1a5242fb11566a9cb9fa90d59dad894f2bd8dfa885d1b` |
| `refresh_compact_native_v1_to_v2.diff` | `4348a3626048784c52c1d060c49913a1233f2eb73aa44f602b0d70f884160bd2` |
| Unchanged v1 helper | `ed37cfd7b79417b6dc33395ee560419f51c5317912fbbd3e2bc06fab3175507b` |
| Unchanged v1 PLAN | `36dccbd3c37592987a204b28bc43e6bbc44482f0eb6d7ec7f548c7f01754e47f` |

Independent source parsing under the installed native CPython 3.13.13 passed. Reconstructing the unified diff from the two actual source texts exactly reproduced the supplied diff. Imports and 25 existing functions are identical; only `source_files`, `inventory` and `main` changed, with new `reviewed_spuma_files` and `require_spuma_inventory` validators. The diff leaves raw record copying, case ZipInfo/mode checks, CPU84 pins/membership, native backup, source stability, full entry hashes/CRC, atomic replacement and failure handling unchanged. The `main` delta only adds version/manifest/exception metadata to plan and success receipts.

The only dotfile exceptions are:

- `gpu_feasibility/spuma/spuma_evidence/original_failed/.spuma-smoke-started`
- `gpu_feasibility/spuma/spuma_evidence/strict_v2/.strict-v2-started`

Before traversal, `reviewed_spuma_files` requires the outer manifest's exact SHA `4824419c7cb30822ddb51230c6976e0739028901d795a1365e331001319b4edd`, rechecks it after parsing, validates canonical member names and records, requires both exact marker records to be zero bytes with SHA `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and reads both actual markers through the unchanged regular-file, single-hardlink, ancestor-reparse/symlink guards. A directory, link, changed marker or altered manifest fails before either exception becomes eligible.

The walker includes those two literal keys and retains all other original hidden, pycache, pyc and compressed-file filters. `require_spuma_inventory` requires the selected SPUMA key set to equal all outer-manifest file keys plus the outer manifest itself. The full source inventory also checks every selected SPUMA file's size/SHA against that mapping. Thus no manifested file or nested manifest can silently be filtered out, and no unbound hidden file is admitted. Historical nested manifests are retained as exact hash-checked bytes rather than incorrectly interpreted as new live-root inventories. The unchanged per-source and archive checks then carry those two marker bytes into their exact `study/**` paths and verify them before and after replacement.

Additional read-only observations: the current published outer manifest has the expected hash, and both current marker files report zero size, the expected empty-file SHA and no leaf link/reparse attributes. These observations are not a completed archive-validation result.

The helper was not imported or executed. No archives were opened, created or modified, no output/case/source was edited, and no CFD, GPU, compiler or Git operation ran. The only writes were this independent review and its JSON record outside the proposal. Source success checks remain proposed until root separately executes the reviewed helper after all writers close.
