# Independent current-Nsight publication review

Reviewed 2026-11-02 by `stdpar_memory_review`. **No blocking privacy, byte-integrity, subset-fidelity or scope finding. The frozen candidate is acceptable for Root's publication decision.** This review did not publish, run included code, change an archive, or execute GPU/CFD work.

## Frozen bytes

- Candidate: `work/current_nsight_publication_candidate/`.
- Manifest SHA256: `a4a01612725c3596547add66005cdce60dfe45878b6eb9257b42620f40dae77d`.
- Total: 85 files, 370426 bytes; 84 manifest-bound files plus the manifest. No unlisted files were found.
- All 84 entries matched in WSL and in two independent native-Windows hash passes. The separate existing native-Windows verification also records two matching 84-file passes against this manifest.
- All 73 provenance-declared copies match both their recorded source/destination hashes and the original source bytes. All 22 included Python sources parse as ASTs; none was imported or run.

## SQLite selection is lossless and restricted

The included subset SHA256 is `5602699ee2bbe13bb003480e3e14d3031120c3779b0b33d326e0d985d2945f87`. It has exactly six tables, passes integrity_check and has zero freelist pages. Independently selected original rows have identical schemas, complete columns and row multisets, including duplicate multiplicities. Every recorded multiset hash matches.

| Table | Rows | Columns |
| --- | ---: | ---: |
| PROCESSES | 1 | 3 |
| NVTX_EVENTS | 1 | 21 |
| CUPTI_ACTIVITY_KIND_RUNTIME | 17 | 8 |
| CUPTI_ACTIVITY_KIND_KERNEL | 8 | 40 |
| DIAGNOSTIC_EVENT | 4 | 6 |
| StringIds | 18 | 2 |

The one process and complete named range match the actual probe PID1778006, globalTid311304969199958 and globalPid311304967421952. All 17 API rows belong to that thread and range and have successful returns: eight launches and nine synchronizations. One device synchronization begins after the final launch and completes inside the range. All eight kernel rows have the target globalPid and lie inside the same range; their correlation-ID multiset equals the launch correlation-ID multiset.

The 18 StringIds are exactly those referenced by selected rows. Their inspected values are allowlisted API/kernel/range names without paths or newlines. No unrelated process, string, environment table, view or extra payload table is present. The exporter creates a fresh database from selected schemas and rows; it does not delete rows from a full raw copy. No raw database content is hidden in freelist pages.

## Safe gate is explicit, not an altered original

Private originals remain unchanged:

- Full SQLite: `9b42e088184eca91acad3fc86a479417d7cc16653187c95965afbf6a32dd36e0`.
- Raw report: `6140a06f276c9b037bc64f3c075cbad8e8ef02a1e41a600f83a9ed6621795a7f`.
- Original gate: `8497e7bef6ba44436cac1bda9affd02c79cb756568518453632b9430a214c846`.

The review-safe gate is `e73065404ef366fea0e08cb6bcdd770b729806abd5f9428735cc90338b15e4fc`. Its keys and every non-diagnostic value exactly equal the original gate. Only diagnostic_events changes, using the documented exact target/global-PID and four-text allowlist. Original and safe hashes and the transformation are recorded. The safe view is not represented as byte-identical to the original; the full original gate is not copied into the candidate.

The diagnostic list changes from 24 to 4 rows. Of the 20 excluded rows, 11 are target/global Info records and nine are non-target records (five Info, four Warning). **No target/global Warning or unsupported-driver warning was omitted.** The four retained original rows include incomplete CUDA/NVTX collection warnings, disabled Unified Memory tracing, and the CUDA event count. Candidate wording correctly says unrelated/non-allowlisted diagnostics; publication wording should retain that precision rather than say that all removed rows were unrelated.

## Privacy and package provenance

No included file has ELF, PE, archive or compressed-package magic or a prohibited binary/archive/raw-report extension. No full raw SQLite/report/original-gate hash appears as a candidate file payload. Reviewed text produced no private-key, GitHub-token, AWS-key, authorization-value or credential-URL matches. This scan supplements the targeted source/data review; it is not a universal secret-detection claim.

The bundle deliberately includes a fixed task environment setup script, linked-library identities and the recorded Nsight injection path. The script's 18 unique export names exactly match its documented allowlist and contain fixed task paths/flags or unexpanded references to future inherited paths. These are reproducibility inputs, not a captured environment dump. No environment table or unrelated environment StringIds are included. Exact local file paths remain visible as documented provenance.

The locally retained official Debian download was independently hashed: 208229554 bytes, SHA256 `087c08b5ddf3ed6f913748f8206d6bbdc225f2aa275ff33af4c487e8b319c8ab`. Reading its control metadata in memory, without extraction or execution, confirms Package `nsight-systems-cli-2026.5.1`, Version `2026.5.1.161-265138896106v0`, Architecture arm64 and Depends `libc6, libglib2.0-0`. This matches the copied installation receipt and actual installed --version proof. The documented checksum is explicitly locally calculated, not a separately supplied vendor checksum.

The official [download page](https://developer.nvidia.com/nsight-systems/get-started) lists the 2026.5.1 Arm CLI, and [release notes](https://docs.nvidia.com/nsight-systems/ReleaseNotes/) state CUDA13.4 support. The candidate records the exact official HTTPS download URL and actual v0 metadata. The package, SDK, ELF files, build trees and full profiling reports are excluded.

## Claims and historical evidence

The original V2 audit's metadata-label failure is preserved, together with all three frozen harness revisions, limited diffs, independent reviews, approvals and commands. The exact Linux comm alternative and V3 audit-only correction are explicit. No raw row rewrite or second GPU execution is implied by the passing V3 gate.

The documentation accurately limits success to the existing 32768-element Field probe. It retains incomplete NVTX/CUDA collection and disabled Unified Memory tracing, and does not claim whole-process event completeness. Observed API/kernel records demonstrate this named algebra range; they do not establish complete device residency or a speedup. The failed profiled/plain large C29 transient remains unqualified, 2.4 remains unbuilt, and no rotor lift or timing result is claimed. This review does not re-evaluate the 84 production CPU CFD cases; the new-tool package makes no change to them.

Only this independent review and its JSON companion were written outside the candidate. Candidate bytes, private originals, case/source/build state, Git and ZIP outputs were not changed. Root retains publication and final archive decisions.
