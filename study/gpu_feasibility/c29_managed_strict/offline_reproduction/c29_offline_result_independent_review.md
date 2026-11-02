# Independent completed offline C29 replay review

PASS. No remaining blocker found in the closed external receipts and numerical report. This review read only the specified closed work JSONs and frozen original report. No restored target, case, source/seed payload, runtime log, archive or process was reopened; no helper or experiment was run.

The actual once-only restoration Python child PID1777135 and replay child PID1777156 have matching start/exit commands and PIDs, parent PID1776945, UID999, nice15, actual-child-waited true, return0 and no cleanup actions. Recorded durations were162.7118s and46.5447s. These are offline Python task durations, not CFD/GPU timings. The final receipt records one restore, one replay, retry false and failure null.

All **91 restored files** match across the before/after catalogues, including SHA256, byte size and mtime. The source snapshots independently reconcile **518 package files and8 seed dependencies**, with no name, hash, size or mtime mismatch. Both snapshots bind frozen manifest `6b2994a2aae47fdad8dcb57b36add85b48e21d16f8f4be62ea34a408d3cdf884` and the62,823,211-byte seed `89c281267262bab336e3421ace9ccf41e4ec3fbdf1a42612e50dbdbd92bc62eb`. This review compared the recorded snapshots; it did not rehash their external payload files.

The replay report actual SHA256 is `c82065bd31fc53affb4df68d9559f3e7d93c0b09b05ee7ff93330954a4360087`, matching the terminal receipt. The frozen original report actual SHA256 remains `9514a88c2ac7fbfce110eae39cc7edc0c8d2614e7bc21c6d28150a294951190e`.

Independently parsed both reports: **499 checks, all true,0 failed**, with the complete check objects exactly equal. All5 source-sample objects also match exactly. All15 paired field-comparison rows retain identical time/field/reference-hash/candidate-hash bindings to the original. The replay remains strict-pressure-v1 under NumPy1.26.4, mechanical_passed true, runtime_admission false, compiler_or_CFD_run false and overall_acceptance_decided_here false.

This establishes actual fresh offline restoration and reproducible historical CPU mechanical analysis. It does not launch or qualify a new CFD run, GPU transient, speedup, default backend or lift result. The companion JSON records hashes of all8 closed receipt files used and the explicit scope limits. Publication remains Root's decision.
