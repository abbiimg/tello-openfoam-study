// GPU execution marker: managed heap indices write a cudaMalloc device-only output.
// The program has no sequential or CPU-fallback control that writes this pointer.
#include <algorithm>
#include <cstdint>
#include <cstdlib>
#include <cuda_runtime_api.h>
#include <execution>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

int main(int argc, char** argv)
{
    constexpr std::size_t n = 1u << 18;
    const std::uint32_t seed = argc > 1
        ? std::uint32_t(std::strtoul(argv[1], nullptr, 10)) : 324508639u;
    std::vector<std::uint32_t> indices(n);
    std::iota(indices.begin(), indices.end(), 0u);
    cudaPointerAttributes inputAttr{};
    if (cudaPointerGetAttributes(&inputAttr, indices.data()) != cudaSuccess
        || inputAttr.type != cudaMemoryTypeManaged) return 20;
    std::uint32_t* output = nullptr;
    if (cudaMalloc(reinterpret_cast<void**>(&output), n*sizeof(*output))
        != cudaSuccess) return 21;
    cudaPointerAttributes outputAttr{};
    if (cudaPointerGetAttributes(&outputAttr, output) != cudaSuccess
        || outputAttr.type != cudaMemoryTypeDevice
        || outputAttr.hostPointer != nullptr
        || outputAttr.devicePointer == nullptr) return 22;
    if (cudaMemset(output, 0, n*sizeof(*output)) != cudaSuccess) return 23;
    if (cudaDeviceSynchronize() != cudaSuccess) return 24;
    std::for_each
    (
        std::execution::par_unseq,
        indices.begin(), indices.end(),
        [output, seed](std::uint32_t i)
        {
            output[i] = ((i*1664525u + seed) ^ 0xa5a5f00du) | 1u;
        }
    );
    const auto synchronize = cudaDeviceSynchronize();
    const auto lastError = cudaGetLastError();
    if (synchronize != cudaSuccess || lastError != cudaSuccess) return 26;
    std::vector<std::uint32_t> actual(n, 0);
    const auto copy = cudaMemcpy
    (
        actual.data(), output, n*sizeof(*output), cudaMemcpyDefault
    );
    const auto copySynchronize = cudaDeviceSynchronize();
    if (copy != cudaSuccess || copySynchronize != cudaSuccess) return 27;
    std::size_t mismatches = 0;
    for (std::size_t i = 0; i < n; ++i)
    {
        const auto expected =
            ((std::uint32_t(i)*1664525u + seed) ^ 0xa5a5f00du) | 1u;
        mismatches += actual[i] != expected;
    }
    const auto release = cudaFree(output);
    const bool passed = synchronize == cudaSuccess && lastError == cudaSuccess
        && copy == cudaSuccess && copySynchronize == cudaSuccess
        && release == cudaSuccess && mismatches == 0;
    std::cout << std::setprecision(17)
        << "{\"kind\":\"stdpar device-only-output execution marker\","
        << "\"elements\":" << n << ","
        << "\"seed\":" << seed << ","
        << "\"input_memory_type\":" << int(inputAttr.type) << ","
        << "\"output_memory_type\":" << int(outputAttr.type) << ","
        << "\"output_device_pointer_valid\":"
        << (outputAttr.devicePointer != nullptr ? "true" : "false") << ","
        << "\"output_host_pointer_is_null\":"
        << (outputAttr.hostPointer == nullptr ? "true" : "false") << ","
        << "\"synchronize_status\":" << int(synchronize) << ","
        << "\"last_error\":" << int(lastError) << ","
        << "\"copy_status\":" << int(copy) << ","
        << "\"copy_synchronize_status\":" << int(copySynchronize) << ","
        << "\"release_status\":" << int(release) << ","
        << "\"mismatches\":" << mismatches << ","
        << "\"passed\":" << (passed ? "true" : "false") << "}\n";
    return passed ? 0 : 25;
}
