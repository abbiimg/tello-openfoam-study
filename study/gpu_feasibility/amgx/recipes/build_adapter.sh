#!/bin/bash
set -e
source "${FOAM_BASHRC:-/opt/openfoam14/etc/bashrc}"
set -u -o pipefail
: "${AMGX_PREFIX:?Set the private prefix built by build_private.sh}"
: "${CUDA_ROOT:?Set the same CUDA 13 root}"
[[ "$WM_PROJECT_VERSION" = 14 ]]
RECIPE_DIR=$(cd -- "$(dirname -- "$0")" && pwd)
BUNDLE=$(cd -- "$RECIPE_DIR/.." && pwd)
[[ ! -e "$AMGX_PREFIX/adapter" ]]
mkdir -p "$AMGX_PREFIX/adapter/Make"
cp "$BUNDLE/src/AmgXPressure.C" "$AMGX_PREFIX/adapter/AmgXPressure.C"
cat > "$AMGX_PREFIX/adapter/Make/files" <<'EOF'
AmgXPressure.C

LIB = $(FOAM_USER_LIBBIN)/libAmgXPressure
EOF
cat > "$AMGX_PREFIX/adapter/Make/options" <<EOF
EXE_INC = -std=c++17 -I$AMGX_PREFIX/install/include -I$CUDA_ROOT/include

LIB_LIBS = -lOpenFOAM -L$AMGX_PREFIX/install/lib -lamgxsh -L$CUDA_ROOT/lib -L$CUDA_ROOT/lib64 -lcudart -ldl -Wl,-rpath,$AMGX_PREFIX/install/lib:$CUDA_ROOT/lib:$CUDA_ROOT/lib64:/usr/lib/wsl/lib
EOF
export FOAM_USER_LIBBIN="$AMGX_PREFIX/install/lib" FOAM_USER_APPBIN="$AMGX_PREFIX/install/bin"
export WM_NCOMPPROCS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export LD_LIBRARY_PATH="$AMGX_PREFIX/install/lib:$CUDA_ROOT/lib:$CUDA_ROOT/lib64:/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
cd "$AMGX_PREFIX/adapter"
exec nice -n 15 wmake -j1 libso
