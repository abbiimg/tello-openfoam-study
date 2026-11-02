// SPDX-License-Identifier: GPL-3.0-or-later
// Actual SPUMA-managed input and a CUDA DEVICE-only output; not a speed test.
#include "argList.H"
#include "MemoryPoolBase.H"
#include "executors.H"
#include "IOstreams.H"
#include <cuda_runtime.h>
#include <cstdlib>
#include <iostream>
#include <type_traits>
#include <vector>
using namespace Foam;
#ifndef have_cuda
#error This device-only-output marker must never be compiled for CPU fallback
#endif
static_assert(std::is_same<Foam::foamExecutor,Foam::cudaExecutor>::value,"Require actual SPUMA CUDA executor");

int main(int argc, char** argv)
{
    Foam::argList::noParallel();
    #include "addMemoryPoolOptions.H"
    #include "addInitDeviceOptions.H"
    Foam::argList args(argc, argv);
    #include "initDevice.H"
    #include "createMemoryPool.H"
    auto* memoryPool = Foam::Spuma::MemoryPool::getInstance();
    constexpr unsigned count=65536;
    const char* text=std::getenv("SPUMA_PROBE_SEED");
    const unsigned seed=text ? static_cast<unsigned>(std::strtoul(text,nullptr,10)) : 324508639u;
    auto* input=static_cast<unsigned*>(memoryPool->allocate(count*sizeof(unsigned)));
    for (unsigned i=0;i<count;++i) input[i]=i^(seed+17u);
    cudaPointerAttributes inAttr{},outAttr{};
    int status=cudaPointerGetAttributes(&inAttr,input);
    unsigned* output=nullptr;
    status|=cudaMalloc(reinterpret_cast<void**>(&output),count*sizeof(unsigned));
    status|=cudaPointerGetAttributes(&outAttr,output);
    status|=cudaMemset(output,0xA5,count*sizeof(unsigned));
    status|=cudaDeviceSynchronize();
    cudaDeviceProp device{};status|=cudaGetDeviceProperties(&device,0);
    auto operation=[=] FOAM_DEVICE (const Foam::label i)
    {
        output[i]=(input[i]*1664525u+seed)^((static_cast<unsigned>(i)+1u)*1013904223u);
    };
    Foam::foamExecutor execution;
    execution.parallelFor(operation,static_cast<Foam::label>(count));
    double reduced=0;
    auto reductionOperation=[] FOAM_DEVICE (const Foam::label i) -> double
    {
        return static_cast<double>(i)+0.25;
    };
    execution.reductionSum(reductionOperation,&reduced,static_cast<Foam::label>(count));
    const double expectedReduction=static_cast<double>(count)*(count-1u)/2.0+static_cast<double>(count)*0.25;
    const int launch=cudaGetLastError();const int sync=cudaDeviceSynchronize();
    std::vector<unsigned> observed(count);
    status|=cudaMemcpy(observed.data(),output,count*sizeof(unsigned),cudaMemcpyDeviceToHost);
    unsigned mismatches=0,changed=0;
    for(unsigned i=0;i<count;++i)
    {
        const unsigned expected=(input[i]*1664525u+seed)^((i+1u)*1013904223u);
        mismatches += observed[i]!=expected;
        changed += observed[i]!=0xA5A5A5A5u;
    }
    const bool passed=!status && !launch && !sync && !mismatches && changed>count/2 && reduced==expectedReduction
        && pool==Foam::word("fixedSizeMemoryPool")
        && inAttr.type==cudaMemoryTypeManaged && outAttr.type==cudaMemoryTypeDevice
        && outAttr.hostPointer==nullptr && outAttr.devicePointer!=nullptr;
    std::cout << "{\"kind\":\"actual_SPUMA_pool_executor_and_device_only_output\",\"executor\":\"Foam::foamExecutor::parallelFor\",\"device\":\"" << device.name
        << "\",\"count\":" << count << ",\"runtime_seed\":" << seed
        << ",\"compute_capability\":" << device.major*10+device.minor
        << ",\"pool_size_bytes\":" << memoryPool->size()
        << ",\"double_reduction_exact\":" << (reduced==expectedReduction?"true":"false")
        << ",\"pool_input_memory_type\":" << static_cast<int>(inAttr.type)
        << ",\"output_memory_type\":" << static_cast<int>(outAttr.type)
        << ",\"output_host_pointer_null\":" << (outAttr.hostPointer==nullptr?"true":"false")
        << ",\"mismatches\":" << mismatches << ",\"cuda_status\":" << status
        << ",\"changed_from_sentinel\":" << changed
        << ",\"launch_status\":" << launch << ",\"synchronize_status\":" << sync
        << ",\"passed\":" << (passed?"true":"false") << "}" << std::endl;
    cudaFree(output);memoryPool->free(input);
    return passed ? 0 : 1;
}
