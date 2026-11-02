# Original execution prerequisites

The observed software versions and OpenFOAM help/build output are in [reference.json](reference.json). This is an environment record, not a container image or an export of the WSL filesystem.

The study ran on Linux ARM64 with Foundation OpenFOAM 14, package revision `20261008`, using double precision and 32-bit labels (`linuxArm64GccDPInt32Opt`), GCC 13.3.0 and Open MPI 4.1.6. Analysis used Python 3.12.3, NumPy 1.26.4 and Matplotlib 3.6.3. Other compatible installations require their own mesh/frozen-input checks; exact results across different compilers or numerical backends are not assumed.

The Foundation provides [OpenFOAM 14 source installation instructions](https://openfoam.org/download/14-source/) and [compilation instructions](https://openfoam.org/download/source/). Its [patch-release documentation](https://openfoam.org/news/v14-patch/) explains source tags corresponding to package revisions; use revision `20261008` when matching this installation. Installed OpenFOAM sources, SDKs and build directories are external dependencies rather than repository payload.

After installing the prerequisites, source that installation's `etc/bashrc` and follow the repository's reproduction commands. Run cases in a fresh directory as a non-root account. The provided `Allrun` runners and preparation verification establish each case's actual initialization and numerical settings; do not substitute an OpenCFD release or GPU backend without a separate compatibility/numerical review.
