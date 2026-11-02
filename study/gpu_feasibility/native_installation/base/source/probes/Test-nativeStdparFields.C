// Deterministic native Foam::Field/managed-pool integration check, not CFD.
#include "argList.H"
#include "Time.H"
#include "scalarField.H"
#include "vectorField.H"
#include <cuda_runtime_api.h>
#include <nvtx3/nvToolsExt.h>
#include <iostream>
#include <iomanip>
using namespace Foam;
int main(int argc, char* argv[])
{
    #include "setRootCase.H"
    #include "createTime.H"
    const label n = 32768;
    scalarField a(n, scalar(0));
    vectorField v(n, vector::zero);
    forAll(a, i)
    {
        a[i] = scalar(i)/8;
        v[i] = vector(i%17, i%13, i%7);
    }
    nvtxRangePushA("NATIVE_STDPAR_FIELD_ALGEBRA");
    scalarField b(a*scalar(2) + scalar(1));
    vectorField w(v*scalar(2));
    scalarField q(v & w);
    const scalar actualSum = sum(b);
    const scalar actualDotSum = sum(q);
    const auto synchronize = cudaDeviceSynchronize();
    nvtxRangePop();
    if (synchronize != cudaSuccess) return 31;
    cudaPointerAttributes attr{};
    if (cudaPointerGetAttributes(&attr,b.begin()) != cudaSuccess) return 32;
    if (attr.type != cudaMemoryTypeManaged) return 33;
    label mismatches = 0;
    scalar expectedSum = 0, expectedDotSum = 0;
    forAll(b, i)
    {
        const scalar expected = scalar(i)/4 + 1;
        const scalar x=i%17, y=i%13, z=i%7;
        const scalar expectedDot = 2*(x*x+y*y+z*z);
        expectedSum += expected;
        expectedDotSum += expectedDot;
        if (b[i] != expected || q[i] != expectedDot
            || w[i].x()!=2*x || w[i].y()!=2*y || w[i].z()!=2*z)
            ++mismatches;
    }
    const bool passed = !mismatches && actualSum==expectedSum
        && actualDotSum==expectedDotSum;
    std::cout << std::setprecision(17)
        << "{\"kind\":\"native Foam Field arithmetic integration\","
        << "\"elements\":" << n << ",\"mismatches\":" << mismatches
        << ",\"actual_sum\":" << actualSum
        << ",\"expected_sum\":" << expectedSum
        << ",\"actual_dot_sum\":" << actualDotSum
        << ",\"expected_dot_sum\":" << expectedDotSum
        << ",\"pointer_memory_type\":" << int(attr.type)
        << ",\"synchronize_status\":" << int(synchronize)
        << ",\"passed\":" << (passed ? "true" : "false") << "}\n";
    return passed ? 0 : 34;
}
