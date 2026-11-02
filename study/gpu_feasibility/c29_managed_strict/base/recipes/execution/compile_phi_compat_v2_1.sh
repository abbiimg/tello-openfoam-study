#!/bin/bash
set -e
source /opt/openfoam14/etc/bashrc
set -u -o pipefail
task_prefix=/opt/openfoam-workspace/gpu-feasibility/native-c29-validation/f14_phi_compat_v2_1_20261102
export C29_PHI_APPBIN="$task_prefix/bin"
export WM_NCOMPPROCS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
cd "$task_prefix/source/foundation14_phi"
{
    date -u +%FT%TZ
    printf 'WM_PROJECT_VERSION=%s\nWM_OPTIONS=%s\nWM_NCOMPPROCS=%s\n' "$WM_PROJECT_VERSION" "$WM_OPTIONS" "$WM_NCOMPPROCS"
    g++ --version
    nice -n 15 wmake
    date -u +%FT%TZ
} >"$task_prefix/build.log" 2>&1
