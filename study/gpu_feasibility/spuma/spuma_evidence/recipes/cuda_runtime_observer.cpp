// Process-local launch/allocation evidence. It does not establish full coverage.
#include <cuda_runtime_api.h>
#include <atomic>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <unistd.h>
#include <sys/resource.h>
static std::atomic<unsigned long long> launches{0},failed{0},managed{0},managedBytes{0};
static std::atomic<unsigned long long> synchronizations{0},failedSync{0};
static std::atomic<int> lastSync{-1};
static std::atomic<unsigned> described{0};
static void note(const char* entry,const void* function,cudaError_t result)
{
    if(result==cudaSuccess)launches.fetch_add(1);else failed.fetch_add(1);
    if(described.fetch_add(1)<12)
    {
        Dl_info info{};dladdr(function,&info);
        std::fprintf(stderr,"SPUMA_CUDA_LAUNCH entry=%s status=%d library=%s symbol=%s\n",entry,int(result),
            info.dli_fname?info.dli_fname:"unknown",info.dli_sname?info.dli_sname:"unavailable");
    }
}
extern "C" cudaError_t cudaLaunchKernel(const void* f,dim3 grid,dim3 block,void** a,size_t bytes,cudaStream_t stream)
{
    using F=cudaError_t(*)(const void*,dim3,dim3,void**,size_t,cudaStream_t);
    static auto real=reinterpret_cast<F>(dlsym(RTLD_NEXT,"cudaLaunchKernel"));
    if(!real)return cudaErrorUnknown;
    const auto result=real(f,grid,block,a,bytes,stream);note("cudaLaunchKernel",f,result);return result;
}
extern "C" cudaError_t cudaLaunchKernelExC(const cudaLaunchConfig_t* c,const void* f,void** a)
{
    using F=cudaError_t(*)(const cudaLaunchConfig_t*,const void*,void**);
    static auto real=reinterpret_cast<F>(dlsym(RTLD_NEXT,"cudaLaunchKernelExC"));
    if(!real)return cudaErrorUnknown;
    const auto result=real(c,f,a);note("cudaLaunchKernelExC",f,result);return result;
}
extern "C" cudaError_t __cudaLaunchKernel(cudaKernel_t f,dim3 grid,dim3 block,void** a,size_t bytes,cudaStream_t stream)
{
    using F=cudaError_t(*)(cudaKernel_t,dim3,dim3,void**,size_t,cudaStream_t);
    static auto real=reinterpret_cast<F>(dlsym(RTLD_NEXT,"__cudaLaunchKernel"));
    if(!real)return cudaErrorUnknown;
    const auto result=real(f,grid,block,a,bytes,stream);note("__cudaLaunchKernel",nullptr,result);return result;
}
extern "C" cudaError_t cudaMallocManaged(void** p,size_t bytes,unsigned flags)
{
    using F=cudaError_t(*)(void**,size_t,unsigned);
    static auto real=reinterpret_cast<F>(dlsym(RTLD_NEXT,"cudaMallocManaged"));
    if(!real)return cudaErrorUnknown;
    const auto result=real(p,bytes,flags);
    if(result==cudaSuccess){managed.fetch_add(1);managedBytes.fetch_add(bytes);}
    return result;
}
extern "C" cudaError_t cudaDeviceSynchronize()
{
    using F=cudaError_t(*)();
    static auto real=reinterpret_cast<F>(dlsym(RTLD_NEXT,"cudaDeviceSynchronize"));
    if(!real)return cudaErrorUnknown;
    const auto result=real();
    if(result==cudaSuccess)synchronizations.fetch_add(1);else failedSync.fetch_add(1);
    lastSync.store(int(result));return result;
}
__attribute__((destructor)) static void summary()
{
    const char* omp=std::getenv("OMP_NUM_THREADS");
    const char* blas=std::getenv("OPENBLAS_NUM_THREADS");
    std::fprintf(stderr,"SPUMA_CUDA_SUMMARY {\"pid\":%d,\"nice\":%d,\"OMP_NUM_THREADS\":\"%s\",\"OPENBLAS_NUM_THREADS\":\"%s\",\"successful_kernel_launch_apis\":%llu,\"failed_kernel_launch_apis\":%llu,\"successful_managed_allocations\":%llu,\"managed_allocated_bytes\":%llu,\"successful_device_synchronizations\":%llu,\"failed_device_synchronizations\":%llu,\"last_device_synchronize_status\":%d,\"profiler_kernel_activity_proof\":false}\n",
        int(getpid()),getpriority(PRIO_PROCESS,0),omp?omp:"unset",blas?blas:"unset",
        launches.load(),failed.load(),managed.load(),managedBytes.load(),
        synchronizations.load(),failedSync.load(),lastSync.load());
}
