// SPDX-License-Identifier: GPL-3.0-or-later
// Application-local annotations/fences; no vendor-library or SDK changes.
#ifndef C29BackendAudit_H
#define C29BackendAudit_H
#include "fvCFD.H"
#ifndef C29_USE_CUDA
#define C29_USE_CUDA 0
#endif
#ifndef C29_USE_NVTX
#define C29_USE_NVTX 1
#endif
#if C29_USE_NVTX
#include <nvtx3/nvToolsExt.h>
#endif
#if C29_USE_CUDA
#include <cuda_runtime_api.h>
#endif
namespace C29
{
class Range
{
public:
    explicit Range(const char* name)
    {
#if C29_USE_NVTX
        nvtxRangePushA(name);
#else
        (void)name;
#endif
    }
    ~Range()
    {
#if C29_USE_NVTX
        nvtxRangePop();
#endif
    }
    Range(const Range&) = delete;
    void operator=(const Range&) = delete;
};
#if C29_USE_CUDA
inline void checked(const cudaError_t result, const char* operation)
{
    if (result != cudaSuccess)
        FatalErrorInFunction << operation << ": "
            << cudaGetErrorString(result) << Foam::exit(Foam::FatalError);
}
#endif
inline void sync(const char* operation)
{
#if C29_USE_CUDA
    checked(cudaDeviceSynchronize(), operation);
#else
    (void)operation;
#endif
}
inline void managedPointer(const void* p, const Foam::label count, const char* name)
{
#if C29_USE_CUDA
    if (!count) return;
    cudaPointerAttributes attributes{};
    checked(cudaPointerGetAttributes(&attributes, p), name);
    if (attributes.type != cudaMemoryTypeManaged)
        FatalErrorInFunction << name
            << " must be CUDA-managed in this initial candidate. Unregistered,"
            << " mapped-host and inferred unified-memory modes are unsupported."
            << Foam::exit(Foam::FatalError);
#else
    (void)p; (void)count; (void)name;
#endif
}
inline void auditDevice()
{
#if C29_USE_CUDA
    int device = -1, managed = 0, concurrent = 0;
    checked(cudaGetDevice(&device), "cudaGetDevice");
    checked(cudaDeviceGetAttribute(&managed,cudaDevAttrManagedMemory,device),
        "cudaDevAttrManagedMemory");
    checked(cudaDeviceGetAttribute(&concurrent,cudaDevAttrConcurrentManagedAccess,device),
        "cudaDevAttrConcurrentManagedAccess");
    if (!managed)
        FatalErrorInFunction << "Managed memory unavailable"
            << Foam::exit(Foam::FatalError);
    Foam::Info<< "C29_DEVICE device=" << device << " managed=" << managed
        << " concurrentManagedAccess=" << concurrent << Foam::endl;
#else
    Foam::Info<< "C29_DEVICE CPU companion: no CUDA fences. Only valid with"
        << " independently verified CPU libraries/compiler policy." << Foam::endl;
#endif
}
}
#endif
