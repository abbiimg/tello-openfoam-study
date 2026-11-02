# Task-private environment. Source only for the selected build/test command.
export NVCOMPILERS='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc'
export NVARCH=Linux_aarch64
export PATH='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/stub-gcc-wrapper:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/compilers/bin:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9/cuda/bin:/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/bison/usr/bin:/opt/openfoam-workspace/gpu-feasibility/pressure-offload/tools/cmake-3.31.7-linux-aarch64/bin:'"$PATH"
export BISON_PKGDATADIR='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tools/bison/usr/share/bison'
export LD_LIBRARY_PATH='/usr/lib/wsl/lib:'"$LD_LIBRARY_PATH"
export TMPDIR='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/tmp'
export XDG_CONFIG_HOME='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/runtime-config'
export CUDA_CACHE_PATH='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/runtime-config/CudaCache'
export FOAM_CONFIG_MODE=o
. '/opt/openfoam-workspace/gpu-feasibility/native-stdpar/source/OpenFOAM-v2606/etc/bashrc' WM_COMPILER=Nvidia-gpu WM_MPLIB=none
export WM_NCOMPPROCS=4
export OMP_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
export WM_PROJECT_USER_DIR='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/user'
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/runtime/jobControl'
export FOAM_RUN='/opt/openfoam-workspace/gpu-feasibility/native-stdpar/runs'
export FOAM_MEMORY_POOL='managed; size=64; incr=64'
export PATH="$FOAM_USER_APPBIN:$PATH"
