# Private ARM64 managed-stdpar OpenFOAM installation

Status at 2026-11-02 09:27 UTC: NVIDIA HPC SDK26.9, CUDA13.3, CUDA-enabled Umpire and the native OpenCFD core are installed. Managed stdpar arithmetic and actual native `Foam::Field` GPU arithmetic have passed. The remaining OpenFOAM mesh/finite-volume libraries and the isolated `icoFoam` cavity tutorial are still building. **No native CFD result or speedup has been measured yet.**

The prefix is `/opt/openfoam-workspace/gpu-feasibility/native-stdpar`. It does not replace Foundation14, the existing CUDA13.0/Ginkgo route, system compiler, driver, shell startup files or the study's cases. These scripts contain this computer's absolute WSL paths; they are an exact local procedure, not a portable package manager.

## Observed gates

| Gate | Actual result | Scope |
|---|---|---|
| Managed stdpar heap arithmetic |1,048,576 doubles, exact element and sum checks; managed pointer type3; successful synchronization |Compiler/runtime smoke |
| Device-only-output marker |262,144 exact nonuniform values written through `cudaMalloc` device-only output; device pointer type2 and null host pointer checked |Independent GPU-execution proof for the stdpar marker |
| Native Foam managed allocator and algebra |32,768 scalar/vector elements, zero mismatches, exact sums134,246,400 and9,894,214; managed pool verified |Actual OpenFOAM core integration |
| GPU API audit of the native algebra NVTX range |8 successful launch API calls;0 failed launches or synchronizations |GPU arithmetic in the named native algebra window |
| Native transient cavity |Pending build/run |Required before claiming native GPU CFD works |
| Rotor model / performance |Not ported or measured |Separate later acceptance gate |

Nsight Systems captures CUDA APIs here, but its exported databases currently contain no CUDA GPU kernel-activity records. API counts are not counts of distinct kernels and do not provide a GPU kernel timeline. Functional tests performed while other builds run must not be used as timing benchmarks.

## Versions and source provenance

* OpenCFD core/develop SHA `b239fea6e48922730477e218c44e8b6a8ab17ade`, API2609; source folder retains the upstream `OpenFOAM-v2606` label. The GPU merge commit is `68a81857c3af06fceb9f0ea2001446df34962d01`.
* ThirdParty SHA `b70425b2611c23f26f24bdb97a5e6b48b99ffe0d`.
* Umpire2025.03.0, with the two CUDA13 API compatibility source files described below.
* Official NVIDIA HPC SDK26.9 ARM64 CUDA13.3 archive: [download](https://developer.download.nvidia.com/hpc-sdk/26.9/nvhpc_2026_269_Linux_aarch64_cuda_13.3.tar.gz),6,904,150,881 bytes. Its MD5 matches NVIDIA's [official checksum list](https://developer.download.nvidia.com/hpc-sdk/26.9/md5sum.txt): `592aa5ca14cbb27012de983acd8d6b62`. Computed SHA256: `acf0d8ea9fc1b5457b16481b1067c742e6610989865e18be93e383d9ded37e2a`.
* Compiler `nvc++26.9-0`, SDK `nvcc13.3.73`; system GCC/G++13.3; existing private CMake3.31.7; private Bison3.8.2 extracted from the official Ubuntu ARM64 package without a system package installation.

The recorded `source_archives.json`, `nvhpc_archive.json`, private configuration and patch manifests in the prefix's `provenance/` directory carry exact URLs, source pins, archive sizes and SHA256 hashes. SDK archives, compilers, object files and library binaries are deliberately outside the Git export.

## Machine-specific compatibility changes

1. RTX Spark N1X reports compute capability12.1, managed memory1, concurrent managed access0 and pageable access0. The private ARM64 build rule uses `-stdpar=gpu -gpu=cc121,mem:managed -DFOAM_OFFLOAD`, replacing the source's GH200 `cc90`/unified-memory default. Host reads in the explicit smoke tests follow a checked device synchronization. Managed-mode functionality has actually passed here; the missing full-unified attributes do not make managed mode impossible.
2. The SDK26.9 installer forwards the optional `NVHPC_STDPAR_CUDACC` setting to a removed `makelocalrc -stdpar` option. The corrected procedure omits that installer variable and invokes the official private `makelocalrc` helper with CUDA13.3. The architecture stays explicit in compiler flags. No SDK compiler binary is patched.
3. Umpire2025.03.0 predates CUDA13's changed advice/prefetch signatures. `backport_umpire_cuda13.py` copies only `CudaAdviseOperation.cpp` and `CudaMemPrefetchOperation.cpp` from official LLNL commit `03c43d88537e4932b9d6dac8591abcd8c25a61ae`. Original/patched hashes and the diff are retained. Umpire is built with CUDA on, architecture121, PIC static libraries, and MPI/OpenMP/tests/examples/docs/tools off.
4. The native core's final shared-library link initially overflowed AArch64's small GOT in NVHPC's generated registration stub. All628 core objects were preserved. A link-only diagnostic showed that the generated `linkstub.c` was compiled by GCC with lowercase `-fpic`, even though the nvc++ command already used `-fPIC`. The narrowly filtered private GCC trampoline changes only that generated SDK26.9 registration compilation to genuine GNU `-fPIC`; other GCC invocations are forwarded unchanged. The link then passed, and readelf confirmed large-GOT relocations. This is an observed local workaround, not a documented NVIDIA fix. Neither global GCC configuration nor shared-library symbol visibility was changed.

The wrapper is installed at `tools/stub-gcc-wrapper/gcc` inside the private prefix and applies only when a command sources this prefix's `env.sh`. Each matching invocation logs original/forwarded arguments and retains generated registration source. Diagnostics and the wrapper install manifest remain in `provenance/`.

## Reproduction order

Run the Python helpers as WSL user `openfoam` with the task prefix already owned/writable by that user. Existing prerequisites are Ubuntu24.04 ARM64, the working Windows/WSL NVIDIA driver, GCC/G++/GFortran13.3, Flex2.6.4, M4, zlib headers, Python3.12, and private CMake3.31.7 at the path in `build_minimal_native_stack.py`. The Foundation14 installation and its private CUDA13.0 remain prerequisites only for the optional earlier CUDA coherence test, not for compiling native stdpar.

1. `download_nvhpc.py` verifies the complete SDK archive against NVIDIA's checksum; `finish_nvhpc_ranges.py` is the recorded ranged-resume alternative used for this download. Use one downloader at a time.
2. `fetch_pinned_sources.py`, then `install_private_bison.py`.
3. `configure_private_tree.py`, then `install_stub_pic_wrapper.py`.
4. `install_sdk_and_probe.py` installs only inside the private prefix, repairs local compiler configuration, and runs the managed heap stdpar check.
5. `run_device_marker.py`, then `profile_stdpar_marker.py`.
6. `backport_umpire_cuda13.py`, then `instrument_ico_time_loop.py`. The latter adds only an NVTX include and push/pop around the private upstream icoFoam time loop; it changes no equation or case setting.
7. `build_minimal_native_stack.py`. It builds Umpire, wmake/core/base, the upstream standard-execution test, finiteVolume and required mesh libraries, blockMesh and icoFoam, then runs a separately copied standard400-cell cavity to time0.5. The upstream standard-execution app remains compiled but unexecuted: it is a ten-million-cell timing benchmark with1000 sequential and1000 parallel repeats, and its reference capture produced NVHPC's `no_device_stack` warning. No runtime failure is claimed. The bounded deterministic native Field check replaces it as the arithmetic acceptance gate.
8. `early_native_field_gate.py` and `audit_native_field_trace.py` provide the independent framework arithmetic check. The helper coordinates its single compile slot with the main budget; the one-time borrowed SPUMA slot was explicitly coordinated and has been returned.
9. `profile_native_cfd_loop.py` waits for the actual tutorial gate and then audits successful CUDA launch APIs contained within the annotated CFD time-loop window. This is a required execution gate, distinct from compiler flags and startup activity.

The helper scripts source only the private `env.sh`. Builds use nice15, at most4 native compilation jobs, and check for20GiB available memory before stages. During the coordinated build SPUMA has a separate2-job allowance, for a combined6; the single early Field compile briefly borrowed its unused second slot while SPUMA was pinned to1. No production CFD run or input was paused or changed.

Worker persistence was corrected after the original foreground tool sessions and PIDs disappeared at a stage boundary. The cause was not proven. The resumed main worker uses separate file descriptors and a new session; its active process and exact descendant tree were then adopted into a private transient systemd supervisor service without restarting compilers. The idle profile watcher runs directly as a second transient service. Both use `User=openfoam`, `Nice=15`, fixed private paths/logs and auto-collection on exit. Adoption requires `Delegate=yes` at creation on this installed systemd; the setting applies only to that task unit. `systemd_workers.json` records units/PIDs; `check_native_worker_survival.py` independently records liveness and cgroup membership after launch commands exit. The original completed build journal is retained on resume.

Pilot cases are under `/opt/openfoam-workspace/cases/native_stdpar_gpu_pilots_20261102/`, separate from the Tello study. The main helper refuses to overlay an existing cavity case. A repeat should use a new recorded pilot case rather than silently replacing prior fields.

## Completion evidence still required

The intended remaining gates are an actual native cavity completion at time0.5 with finite fields and peak local continuity below1e-5, and successful GPU launch APIs inside its NVTX time-loop window. The planned evidence files are `native_openfoam_tutorial_gate.json` and `native_cfd_time_loop_gpu_gate.json`; their existence and contents must be checked before updating this status.

An actuator port must subsequently preserve force sign, finite-cylinder normalization, overlap accumulation, work/power integration, controller state and the original momentum stress term. A successful cavity does not validate that port or establish a speedup. The production study remains the completed Foundation14 CPU result set.
