// Exact-arithmetic managed-memory stdpar installation smoke test.
// No aerodynamic quantities or performance conclusions are produced.
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cuda_runtime_api.h>
#include <execution>
#include <iomanip>
#include <iostream>
#include <numeric>
#include <vector>

int main()
{
    int count = 0;
    if (cudaGetDeviceCount(&count) != cudaSuccess || count < 1) return 10;
    cudaDeviceProp prop{};
    if (cudaGetDeviceProperties(&prop, 0) != cudaSuccess) return 11;
    int runtimeVersion = 0, driverVersion = 0;
    if (cudaRuntimeGetVersion(&runtimeVersion) != cudaSuccess
        || cudaDriverGetVersion(&driverVersion) != cudaSuccess) return 15;

    constexpr std::size_t n = 1u << 20;
    constexpr int iterations = 128;
    std::vector<double> values(n, 1.0);
    cudaPointerAttributes attr{};
    if (cudaPointerGetAttributes(&attr, values.data()) != cudaSuccess) return 12;
    if (attr.type != cudaMemoryTypeManaged) return 13;

    const auto started = std::chrono::steady_clock::now();
    for (int k = 0; k < iterations; ++k)
    {
        std::for_each
        (
            std::execution::par_unseq,
            values.begin(), values.end(),
            [](double& value) { value += 1.0; }
        );
    }
    const double sum = std::reduce
    (
        std::execution::par_unseq,
        values.begin(), values.end(), 0.0
    );
    const auto sync = cudaDeviceSynchronize();
    const auto error = cudaGetLastError();
    if (sync != cudaSuccess || error != cudaSuccess) return 16;
    const double expected = double(n) * double(iterations + 1);
    const bool allCorrect = std::all_of
    (
        values.begin(), values.end(),
        [](double value) { return value == double(iterations + 1); }
    );
    const auto elapsed = std::chrono::duration<double>
    (
        std::chrono::steady_clock::now() - started
    ).count();
    std::cout << std::setprecision(17)
        << "{\"kind\":\"managed stdpar installation smoke\","
        << "\"device\":\"" << prop.name << "\","
        << "\"device_count\":" << count << ","
        << "\"compute_major\":" << prop.major << ","
        << "\"compute_minor\":" << prop.minor << ","
        << "\"cuda_runtime_version\":" << runtimeVersion << ","
        << "\"cuda_driver_version\":" << driverVersion << ","
        << "\"pointer_memory_type\":" << int(attr.type) << ","
        << "\"elements\":" << n << ","
        << "\"iterations\":" << iterations << ","
        << "\"sum\":" << sum << ","
        << "\"expected_sum\":" << expected << ","
        << "\"exact_element_check\":" << (allCorrect ? "true" : "false") << ","
        << "\"cuda_synchronize_status\":" << int(sync) << ","
        << "\"cuda_last_error\":" << int(error) << ","
        << "\"elapsed_s\":" << elapsed
        << "}\n";
    return allCorrect && sum == expected && sync == cudaSuccess
        && error == cudaSuccess ? 0 : 14;
}
