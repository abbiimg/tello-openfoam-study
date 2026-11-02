# Native archive refresh recipe

The final chosen recipe is refresh_compact_native_v3.py, with PLAN_V3.txt and its independent source review. V1 and V2, both reviews/plans and exact diffs remain historical. V2 preserves two explicit empty SPUMA markers bound to the component manifest; V3 uses Windows extended paths for long source folders without changing Windows settings. The earlier V2 attempt stopped during inventory before a new archive was created; the original archive and verified backup remained intact.

The recipe preserves verified compressed CPU case records and refreshes study files. All member SHA256 values, CRCs, protected CPU84 hashes, source membership, permissions and metadata are checked. It runs no CFD or Git command and does not rebuild the full case archive.

Exact historical workstation/interpreter/old-archive guards require deliberate adaptation on another host or snapshot. The default prints a plan; execution requires explicit closed-writer acknowledgement. The ordinary readonly backup flag is not immutable storage. Post-publication failures need manual review.

Actual closed receipts and final archive checksums are stored outside the archive to avoid circular self-hashes. Frozen source-only wording records the recipe's state when reviewed.
