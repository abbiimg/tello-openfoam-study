// Process-local CUDA launch observation; no global tracing/settings changes.
#include <cuda_runtime_api.h>
#include <atomic>
#include <cstdio>
#include <dlfcn.h>
static std::atomic<unsigned long long> successfulLaunches{0};
extern "C" void amgx_audit_reset() { successfulLaunches.store(0); }
extern "C" unsigned long long amgx_audit_launches() { return successfulLaunches.load(); }

extern "C" cudaError_t cudaLaunchKernel(const void* function, dim3 grid, dim3 block,
    void** arguments, size_t sharedBytes, cudaStream_t stream)
{
    using Function = cudaError_t (*)(const void*,dim3,dim3,void**,size_t,cudaStream_t);
    static auto original = reinterpret_cast<Function>(dlsym(RTLD_NEXT,"cudaLaunchKernel"));
    if (!original) { std::fprintf(stderr,"AMGX_AUDIT missing cudaLaunchKernel\n"); return cudaErrorUnknown; }
    const auto result = original(function,grid,block,arguments,sharedBytes,stream);
    if (result==cudaSuccess) successfulLaunches.fetch_add(1);
    return result;
}
extern "C" cudaError_t cudaLaunchKernelExC(const cudaLaunchConfig_t* config,
    const void* function, void** arguments)
{
    using Function = cudaError_t (*)(const cudaLaunchConfig_t*,const void*,void**);
    static auto original = reinterpret_cast<Function>(dlsym(RTLD_NEXT,"cudaLaunchKernelExC"));
    if (!original) { std::fprintf(stderr,"AMGX_AUDIT missing cudaLaunchKernelExC\n"); return cudaErrorUnknown; }
    const auto result = original(config,function,arguments);
    if (result==cudaSuccess) successfulLaunches.fetch_add(1);
    return result;
}

// CUDA13-generated host stubs use this kernel-handle entry point. Signature is
// verified against this private SDK's include/crt/device_functions.h:2932.
extern "C" cudaError_t __cudaLaunchKernel(cudaKernel_t kernel, dim3 grid, dim3 block,
    void** arguments, size_t sharedBytes, cudaStream_t stream)
{
    using Function = cudaError_t (*)(cudaKernel_t,dim3,dim3,void**,size_t,cudaStream_t);
    static auto original = reinterpret_cast<Function>(dlsym(RTLD_NEXT,"__cudaLaunchKernel"));
    if (!original) { std::fprintf(stderr,"AMGX_AUDIT missing __cudaLaunchKernel\n"); return cudaErrorUnknown; }
    const auto result = original(kernel,grid,block,arguments,sharedBytes,stream);
    if (result==cudaSuccess) successfulLaunches.fetch_add(1);
    return result;
}
