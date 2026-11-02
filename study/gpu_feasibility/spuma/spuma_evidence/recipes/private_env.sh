# Private SPUMA environment. Never source from global/user profiles.
export NVCOMPILERS=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc
export NVHPC_CUDA_HOME=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3
export CUDA_HOME=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3
export CUDA_PATH=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3
export PATH=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/compilers/bin:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3/bin:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/bison/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export BISON_PKGDATADIR=/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/bison/usr/share/bison
export LD_LIBRARY_PATH=/usr/lib/wsl/lib:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/compilers/lib:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/13.3/lib64
export TMPDIR=/opt/openfoam-workspace/gpu-feasibility/spuma/tmp
export XDG_CONFIG_HOME=/opt/openfoam-workspace/gpu-feasibility/spuma/runtime-config
export CUDA_CACHE_PATH=/opt/openfoam-workspace/gpu-feasibility/spuma/runtime-config/CudaCache
export FOAM_CONFIG_MODE=o
export have_cuda=true
export have_umpire=false
export NVARCH=121
. /opt/openfoam-workspace/gpu-feasibility/spuma/source/etc/bashrc WM_COMPILER=Nvidia WM_MPLIB=none FOAM_SIGFPE=false
export have_cuda=true
export have_umpire=false
export NVARCH=121
export FOAM_SIGFPE=false
export WM_NCOMPPROCS=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
export WM_PROJECT_USER_DIR=/opt/openfoam-workspace/gpu-feasibility/spuma/user
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR=/opt/openfoam-workspace/gpu-feasibility/spuma/runtime/jobControl
export FOAM_RUN=/opt/openfoam-workspace/gpu-feasibility/spuma/smoke
export PATH="$FOAM_USER_APPBIN:$PATH"

# Scoped CUDA registration-stub PIC fix; system compiler and SDK unchanged.
export PATH="/opt/openfoam-workspace/gpu-feasibility/spuma/tools/stub-gcc-wrapper:$PATH"
