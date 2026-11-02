#!/bin/bash
set -euo pipefail
: "${AMGX_PREFIX:?Set the private prefix}"
: "${CUDA_ROOT:?Set the same CUDA 13 root}"
RECIPE_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
BUNDLE=$(cd -- "$RECIPE_DIR/.." && pwd)
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export LD_LIBRARY_PATH="$AMGX_PREFIX/install/lib:$CUDA_ROOT/lib:$CUDA_ROOT/lib64:/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
export LD_PRELOAD="$AMGX_PREFIX/install/lib/libamgxLaunchAudit.so"
exec nice -n 15 "$AMGX_PREFIX/install/bin/amgx_poisson_smoke" "$BUNDLE/src/poisson_config.json"
