# Native compact refresher v3 — namespace-only source review

Verdict: **no concrete source blockers** for the bounded v3 change. Root's closed-writer execution condition and the v1/v2 operational limitations remain applicable. No archive success is inferred from source review or path fixtures.

| Input | SHA256 |
|---|---|
| `refresh_compact_native_v3.py` | `d0dd7c34c70fb9bdf63aa46286b396fa584bb2b52b6b446687e77e7c8ad913f0` |
| `PLAN_V3.txt` | `9b8a868be144b3627aec365f3f48f6125659ab73f05e166e84363235b7173b53` |
| `refresh_compact_native_v2_to_v3.diff` | `4fb90d057f825e31831446fec27b01ddfa597717a3c981339647f9d03b584ff0` |
| `long_path_readonly_proof.json` | `6bf53d5beb6a0a5952451018686e2da6fd181a28a2fb2025ae1dff84080f16a4` |
| `v3_inert_long_path_check.json` | `fe55338719ac6ac4d3abd253261f53daf1e92944d3dad108f7810d98bf3257c2` |

Independent native CPython 3.13.13 AST parsing passed, and the exact supplied diff was independently reconstructed from actual v2/v3 source texts. All imports and 26 existing functions are identical. The sole changed module assignment is `WORKSPACE`; only `lexical`, `safe_path`, `check_runtime` and `main` differ. V1 remains `ed37cfd7…5507b` and v2 remains `8d715ae0…8a24d0`. The v3 source hash was rechecked after review and remained unchanged.

The fixed workspace now uses the Windows extended local-drive prefix, so the derived output, work, backup, candidate and compact paths all use the same namespace. `lexical` applies absolute and lexical normalization before adding the prefix to ordinary local-drive spellings. An already extended drive is not prefixed twice. `inside` therefore compares ordinary and extended aliases with one normalized spelling. `safe_path` still requires fixed-root containment before checking the namespace; it then requires the fixed extended drive and checks every existing ancestor using `lstat`, symlink type and reparse attributes. Network UNC and other device drives do not match this root/drive. Existing regular-file/single-hardlink checks remain unchanged. No resolve call follows an unchecked link, and no registry or global Windows setting changes.

The runtime identity check now canonicalizes both the actual interpreter and the expected Blender interpreter before comparison, avoiding an ordinary/extended spelling mismatch. Archive member names continue to come only from paths relative to the identically prefixed output root and `as_posix()`; filesystem namespace prefixes are not introduced into ZIP keys. `ZipInfo.from_file` still receives an explicit relative archive name. The `main` delta only updates helper-version and namespace metadata in plan/success receipts.

All SPUMA manifest/empty-marker admission and complete inventory checks are unchanged from reviewed v2. Study selection, CPU84 protected hashes and membership, raw case-record copying, case ZipInfo/Unix mode equality, native backup, every source/member SHA, full CRC, same-directory atomic replacement and failure handling are textually unchanged in the actual diff and structurally unchanged in the independent AST comparison.

The actual v2 failure receipt reports WinError 3 during source membership enumeration, before candidate creation or publication (`target_already_published=false`). The author supplied and this reviewer read the proof/fixture source plus the hash-bound receipts. The read-only proof records the same device/inode for the 258-character ordinary directory and its extended alias, with ordinary enumeration failing and extended enumeration listing the actual child. The inert fixture receipt records a 423-character work file, ordinary-alias canonicalization, native runtime/ancestor checks, relative POSIX keys and 1,852 read-only source selections including both SPUMA markers. These records support the reason for the namespace correction; they do not demonstrate backup/ZIP creation or final publication.

This reviewer ran only independent AST/diff/hash checks and read the existing proof/fixture records. The helper and fixture modules were not imported or executed, no archives were opened or changed, and no output/case/source, CFD, GPU, compiler, registry or Git action occurred. The only writes were the independent review records outside the proposal. Actual v3 packaging remains root's separate action after all writers close.
