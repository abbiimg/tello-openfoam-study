# Publication review fixes, v2

This separate unpublished candidate preserves the original4ec8be72… candidate.
Only four originally indexed paths changed: README.md, REPRODUCTION.md and the
two newly authored offline adapters. All fields, recorded logs/receipts, d600
limits, historical analyzers/helpers and application/model source are unchanged.
The507 original indexed payloads were compared with their frozen v1 manifest;
503 retain their original current-path bytes. All495 original source/alias payload
bytes remain available:493 at their original paths, plus the two old generated
adapter versions copied exactly into review_history/v1_original. Original
CONTENT_CHECKS/curation provenance describe v1; REVIEW_V2_CHECKS supplies the
explicit current-path exceptions and v2 validation. No recorded evidence was
rewritten to fit a new path guard.

The restore destination must be canonically disjoint from both the package and
seed directory, rejecting ancestors, descendants and equality. Both adapters
reject symlink, junction and other reparse ancestors before canonical resolution.
Replay validates explicit input/code paths and output containment before included
code imports, and repeats output checks before exclusive writing. New input/data
paths do not bypass those checks by silently resolving linked ancestors.

The README propeller diameter is7.62cm (radius0.0381m), as recorded in the actual
frozen geometry. This is a descriptive correction; no geometry or input changed.
Distances explicitly labelled rotor spacing are separate measurements.

The exact original scripts/docs/manifest are in review_history/v1_original.
Two hash-bound fixture receipts and their exact source are in
review_history/v2_path_fixtures. Windows22 fixtures passed, including two real
NTFS junctions and a FILE_ATTRIBUTE_REPARSE_POINT fallback check. Windows native
symlink creation was unavailable; Linux26 fixtures passed with real symlink,
dangling-link, output/base/package and linked-field-input attacks. Fixtures only
called path-validation functions against inert private files. No restore, main,
analyze, numerical replay, compiler, CFD, profiler or GPU action was invoked.
Private fixture directories were retained; no recursive cleanup was performed.

The source/doc diff is held privately as work/c29_managed_v2_source_doc.patch;
its hash is recorded in REVIEW_V2_CHECKS.json. Original installation/prerequisite
and source-only limitations remain in README.md and REPRODUCTION.md.
