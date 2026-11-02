# Private same-pin CPU control; source only for this build/run command.
export PATH='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/tools/bison/usr/bin:/usr/bin:/bin'
export LD_LIBRARY_PATH=''
unset CPATH CPLUS_INCLUDE_PATH C_INCLUDE_PATH LIBRARY_PATH NVCOMPILERS NVARCH CUDA_HOME CUDA_PATH CUDA_ROOT NVHPC_CUDA_HOME FOAM_MEMORY_POOL
export BISON_PKGDATADIR='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/tools/bison/usr/share/bison'
export TMPDIR='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/tmp'
export XDG_CONFIG_HOME='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/runtime-config'
export FOAM_CONFIG_MODE=o
. '/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/source/OpenFOAM-v2606/etc/bashrc' WM_COMPILER=Gcc WM_COMPILER_TYPE=system WM_MPLIB=none WM_PRECISION_OPTION=DP WM_LABEL_SIZE=32 WM_COMPILE_OPTION=Opt
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export FOAM_MODULE_PREFIX=none
unset FOAM_MEMORY_POOL
export WM_PROJECT_USER_DIR='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/user'
export FOAM_USER_APPBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/bin"
export FOAM_USER_LIBBIN="$WM_PROJECT_USER_DIR/platforms/$WM_OPTIONS/lib"
export FOAM_JOB_DIR='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/runtime/jobControl'
export FOAM_RUN='/opt/openfoam-workspace/gpu-feasibility/native-cpu-control/runs'
export PATH="$FOAM_USER_APPBIN:$PATH"
