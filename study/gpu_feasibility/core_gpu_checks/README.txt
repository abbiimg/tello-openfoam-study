Completed core GPU checks — 2 November 2026

These immutable evidence/source excerpts document actual framework arithmetic,
not CFD solver completion or performance. Native OpenCFD uses the pinned
b239fea6e48922730477e218c44e8b6a8ab17ade core, NVHPC26.9/CUDA13.3 and
CUDA-enabled Umpire managed memory. Its actual32768-element Foam scalar/vector
algebra passed all element/sum checks and eight successful launch API calls
inside the named NVTX algebra range. No kernel-activity timeline was available.

SPUMA v2512 SHA1ff2d45c002b7afb599b9dd8c4c6874666242349 used its own
Foam::foamExecutor::parallelFor with a1GiB fixed managed pool. All65536
runtime-seeded values written into verified DEVICE-only output matched,
along with an exact double reduction. Its original NVHPC CUDA-C++ support
warning remains explicit in the gate. The preparation record predates the
successful run; the final core-executor gate records the actual completion.

Probe source bytes are unchanged from their recorded builds. Gate files carry
binary/library hashes and original local evidence paths; binaries, SDKs and
profiler databases are not redistributed here. This directory is a small
completed-check snapshot, not a complete standalone installation recipe.
Full solver build/tutorial and actuator/performance gates remain pending;
see ../GPU_SETUP.md for current status. The84CPU lift results are unchanged.
