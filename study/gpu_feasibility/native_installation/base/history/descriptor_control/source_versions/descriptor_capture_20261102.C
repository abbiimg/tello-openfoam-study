// Diagnostic only: identical data, reference-captured descriptor versus raw pointer.
#include "argList.H"
#include "Time.H"
#include "scalarField.H"
#include "autoPtr.H"
#include <cuda_runtime_api.h>
#include <execution>
#include <iostream>
#include <iomanip>
#include <cstdint>
#include <cstdlib>
using namespace Foam;
static void attributes(const char* name,const void* ptr)
{
    cudaPointerAttributes a{};
    const auto status=cudaPointerGetAttributes(&a,ptr);
    std::cout<<"DIAG_ATTR name="<<name<<" address="<<reinterpret_cast<std::uintptr_t>(ptr)
        <<" status="<<int(status)<<" type="<<(status==cudaSuccess?int(a.type):-1)
        <<" host="<<a.hostPointer<<" device="<<a.devicePointer<<std::endl;
    cudaGetLastError();
}
__attribute__((noinline)) static void referenceKernel(const scalarField& input,scalar* output,label n)
{
    labelRange indices(n);
    apply_policy(n,[&](auto policy)
    {
        std::for_each(policy,indices.begin(),indices.end(),[output,&input](label i)
        {
            output[i]=input[i]*scalar(2)+scalar(1);
        });
    });
}
__attribute__((noinline)) static void rawKernel(const scalar* input,scalar* output,label n)
{
    labelRange indices(n);
    apply_policy(n,[&](auto policy)
    {
        std::for_each(policy,indices.begin(),indices.end(),[input,output](label i)
        {
            output[i]=input[i]*scalar(2)+scalar(1);
        });
    });
}
int main(int argc,char* argv[])
{
    argList::addOption("mode","word","stack-ref, raw, or heap-ref");
    argList::addOption("n","label","diagnostic element count");
    #include "setRootCase.H"
    #include "createTime.H"
    const word mode=args.getOrDefault<word>("mode","raw");
    const label n=args.getOrDefault<label>("n",4096);
    if(n<=0 || (mode!="stack-ref" && mode!="raw" && mode!="heap-ref"))return64;
    scalarField stackInput(n),output(n,Zero);
    autoPtr<scalarField> heapInput(new scalarField(n));
    forAll(stackInput,i){stackInput[i]=scalar(i)/8;heapInput()[i]=scalar(i)/8;}
    const scalarField& selected=(mode=="heap-ref"?heapInput():stackInput);
    std::cout<<std::setprecision(17)<<"DIAG_BEGIN mode="<<mode<<" n="<<n
        <<" offload_selected="<<ListPolicy::use_offload(n)
        <<" descriptor_bytes="<<sizeof(scalarField)<<std::endl;
    attributes("stack_descriptor",&stackInput);
    attributes("heap_descriptor",&heapInput());
    attributes("selected_data",selected.cdata());
    attributes("output_data",output.cdata());
    try
    {
        if(mode=="raw")rawKernel(selected.cdata(),output.data(),n);
        else referenceKernel(selected,output.data(),n);
        const auto sync=cudaDeviceSynchronize();
        if(sync!=cudaSuccess){std::cout<<"DIAG_SYNC status="<<int(sync)<<std::endl;std::_Exit(42);}
        label mismatches=0;
        forAll(output,i)if(output[i]!=(scalar(i)/8)*2+1)++mismatches;
        std::cout<<"DIAG_RESULT mode="<<mode<<" mismatches="<<mismatches<<" sync="<<int(sync)<<std::endl;
        return mismatches?43:0;
    }
    catch(const std::exception& e)
    {
        std::cout<<"DIAG_EXCEPTION mode="<<mode<<" what="<<e.what()<<std::endl;
        // Diagnostic-only process exit: preserve fault without invoking CUDA
        // deallocators on the already-failed context. No device reset is called.
        std::_Exit(41);
    }
}
