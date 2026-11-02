#!/bin/bash
# Opt-in source build only. Requires an existing CUDA 13 SDK; installs no driver.
set -euo pipefail
: "${AMGX_PREFIX:?Set a fresh private absolute install/build prefix}"
: "${CUDA_ROOT:?Set the existing CUDA 13 toolkit root with cuSOLVER, cuBLAS, cuSPARSE and CCCL}"
[[ "$AMGX_PREFIX" = /* && "$CUDA_ROOT" = /* ]]
[[ ! -e "$AMGX_PREFIX" ]]
RECIPE_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
BUNDLE=$(cd -- "$RECIPE_DIR/.." && pwd)
PIN=cc1cebdbb32b14d33762d4ddabcb2e23c1669f47
CMAKE=${CMAKE:-cmake}
CXX=${CXX:-g++}
CUDA_ARCH=${CUDA_ARCH:-121}
mkdir -p "$AMGX_PREFIX/logs" "$AMGX_PREFIX/cache/cuda" "$AMGX_PREFIX/tmp"
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CMAKE_BUILD_PARALLEL_LEVEL=1
export CUDA_CACHE_PATH="$AMGX_PREFIX/cache/cuda" TMPDIR="$AMGX_PREFIX/tmp"
export LD_LIBRARY_PATH="$CUDA_ROOT/lib:$CUDA_ROOT/lib64:/usr/lib/wsl/lib:${LD_LIBRARY_PATH:-}"
git clone --no-checkout https://github.com/NVIDIA/AMGX.git "$AMGX_PREFIX/AMGX"
git -C "$AMGX_PREFIX/AMGX" checkout --detach "$PIN"
[[ $(git -C "$AMGX_PREFIX/AMGX" rev-parse HEAD) = "$PIN" ]]
CCCL_FLAG=
[[ ! -d "$CUDA_ROOT/include/cccl" ]] || CCCL_FLAG="-I$CUDA_ROOT/include/cccl"
nice -n 15 "$CMAKE" -S "$AMGX_PREFIX/AMGX" -B "$AMGX_PREFIX/build" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX="$AMGX_PREFIX/install" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON -DCMAKE_POSITION_INDEPENDENT_CODE=ON \
  -DCMAKE_CUDA_COMPILER="$CUDA_ROOT/bin/nvcc" -DCUDAToolkit_ROOT="$CUDA_ROOT" \
  -DCMAKE_CUDA_ARCHITECTURES="$CUDA_ARCH" -DCMAKE_CUDA_STANDARD=17 -DCMAKE_CXX_STANDARD=17 \
  -DCMAKE_CUDA_RUNTIME_LIBRARY=Shared -DCMAKE_CUDA_FLAGS="$CCCL_FLAG --threads=1" \
  -DCMAKE_NO_MPI=ON \
  -DCMAKE_BUILD_RPATH="$CUDA_ROOT/lib;$CUDA_ROOT/lib64;/usr/lib/wsl/lib" \
  -DCMAKE_INSTALL_RPATH="$AMGX_PREFIX/install/lib;$CUDA_ROOT/lib;$CUDA_ROOT/lib64;/usr/lib/wsl/lib" \
  2>&1 | tee "$AMGX_PREFIX/logs/configure.log"
nice -n 15 "$CMAKE" --build "$AMGX_PREFIX/build" --target amgxsh amgx amgx_capi --parallel 1 \
  2>&1 | tee "$AMGX_PREFIX/logs/build.log"
"$CMAKE" --install "$AMGX_PREFIX/build" 2>&1 | tee "$AMGX_PREFIX/logs/install.log"
# Audit is CUDA-13-specific. Check the internal entry-point signature against
# the installed header before using it with another toolkit release.
grep -q '__cudaLaunchKernel' "$CUDA_ROOT/include/crt/device_functions.h"
nice -n 15 "$CXX" -std=c++17 -O2 -shared -fPIC -I"$CUDA_ROOT/include" \
  "$BUNDLE/src/cuda_launch_audit.cpp" -ldl -o "$AMGX_PREFIX/install/lib/libamgxLaunchAudit.so"
nice -n 15 "$CXX" -std=c++17 -O2 -I"$AMGX_PREFIX/install/include" -I"$CUDA_ROOT/include" \
  "$BUNDLE/src/poisson_smoke.cpp" -L"$AMGX_PREFIX/install/lib" -lamgxsh \
  -L"$CUDA_ROOT/lib" -L"$CUDA_ROOT/lib64" -lcudart -ldl \
  -Wl,-rpath,"$AMGX_PREFIX/install/lib:$CUDA_ROOT/lib:$CUDA_ROOT/lib64:/usr/lib/wsl/lib" \
  -o "$AMGX_PREFIX/install/bin/amgx_poisson_smoke"
echo 'Source build completed. Run the explicit Poisson check before building/using the OpenFOAM adapter.'
