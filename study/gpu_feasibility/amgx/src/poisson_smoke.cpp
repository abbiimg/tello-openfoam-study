// Private installation verification, not a CFD or performance benchmark.
#include <amgx_c.h>
#include <cuda_runtime_api.h>
#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <iomanip>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

static void check(AMGX_RC rc, const char* expr)
{
    if (rc != AMGX_RC_OK)
    {
        char message[4096];
        AMGX_get_error_string(rc, message, sizeof(message));
        throw std::runtime_error(std::string(expr)+": "+message);
    }
}
static void cudaCheck(cudaError_t rc, const char* expr)
{
    if (rc != cudaSuccess) throw std::runtime_error(std::string(expr)+": "+cudaGetErrorString(rc));
}
#define A(call) check((call), #call)
#define C(call) cudaCheck((call), #call)

int main(int argc, char** argv)
{
    try
    {
        if (argc != 2) throw std::runtime_error("Expected a config JSON path");
        C(cudaSetDevice(0));
        cudaDeviceProp properties{};
        C(cudaGetDeviceProperties(&properties, 0));
        int managed = 0, concurrent = 0, pools = 0;
        C(cudaDeviceGetAttribute(&managed, cudaDevAttrManagedMemory, 0));
        C(cudaDeviceGetAttribute(&concurrent, cudaDevAttrConcurrentManagedAccess, 0));
        C(cudaDeviceGetAttribute(&pools, cudaDevAttrMemoryPoolsSupported, 0));
        constexpr int width = 32, n = width*width*width;
        std::vector<int> offsets(n+1), columns;
        std::vector<double> values, exact(n), rhs(n), solution(n, 0.0);
        columns.reserve(7*n); values.reserve(7*n);
        constexpr double pi = 3.14159265358979323846;
        for (int k=0; k<width; ++k) for (int j=0; j<width; ++j) for (int i=0; i<width; ++i)
        {
            const int row = i + width*(j+width*k);
            exact[row] = std::sin(pi*(i+1)/(width+1))*std::sin(pi*(j+1)/(width+1))*std::sin(pi*(k+1)/(width+1));
            offsets[row] = static_cast<int>(columns.size());
            std::vector<std::pair<int,double>> entries{{row, 6.0}};
            if (i) entries.emplace_back(row-1,-1.0);
            if (i+1<width) entries.emplace_back(row+1,-1.0);
            if (j) entries.emplace_back(row-width,-1.0);
            if (j+1<width) entries.emplace_back(row+width,-1.0);
            if (k) entries.emplace_back(row-width*width,-1.0);
            if (k+1<width) entries.emplace_back(row+width*width,-1.0);
            std::sort(entries.begin(), entries.end());
            for (auto entry: entries) {columns.push_back(entry.first); values.push_back(entry.second);}
        }
        offsets[n] = static_cast<int>(columns.size());
        for (int row=0; row<n; ++row)
            for (int entry=offsets[row]; entry<offsets[row+1]; ++entry)
                rhs[row] += values[entry]*exact[columns[entry]];

        A(AMGX_initialize());
        A(AMGX_initialize_plugins());
        AMGX_config_handle config;
        AMGX_resources_handle resources;
        AMGX_matrix_handle matrix;
        AMGX_vector_handle b, x;
        AMGX_solver_handle solver;
        A(AMGX_config_create_from_file(&config, argv[1]));
        int device = 0;
        A(AMGX_resources_create(&resources, config, nullptr, 1, &device));
        A(AMGX_matrix_create(&matrix, resources, AMGX_mode_dDDI));
        A(AMGX_vector_create(&b, resources, AMGX_mode_dDDI));
        A(AMGX_vector_create(&x, resources, AMGX_mode_dDDI));
        A(AMGX_solver_create(&solver, resources, AMGX_mode_dDDI, config));
        A(AMGX_matrix_upload_all(matrix, n, offsets[n], 1, 1, offsets.data(), columns.data(), values.data(), nullptr));
        A(AMGX_vector_bind(b, matrix));
        A(AMGX_vector_bind(x, matrix));
        A(AMGX_vector_upload(b, n, 1, rhs.data()));
        A(AMGX_vector_upload(x, n, 1, solution.data()));
        A(AMGX_solver_setup(solver, matrix));
        C(cudaDeviceSynchronize());
        using Reset = void (*)();
        using Count = unsigned long long (*)();
        auto reset = reinterpret_cast<Reset>(dlsym(RTLD_DEFAULT, "amgx_audit_reset"));
        auto count = reinterpret_cast<Count>(dlsym(RTLD_DEFAULT, "amgx_audit_launches"));
        if (reset) reset();
        A(AMGX_solver_solve(solver, b, x));
        C(cudaGetLastError());
        C(cudaDeviceSynchronize());
        const auto launches = count ? count() : 0ULL;
        int iterations = -1;
        AMGX_SOLVE_STATUS status;
        A(AMGX_solver_get_status(solver, &status));
        A(AMGX_solver_get_iterations_number(solver, &iterations));
        A(AMGX_vector_download(x, solution.data()));
        C(cudaDeviceSynchronize());
        double errorMax = 0, residualSquared = 0, rhsSquared = 0;
        for (int row=0; row<n; ++row)
        {
            double ax = 0;
            for (int entry=offsets[row]; entry<offsets[row+1]; ++entry)
                ax += values[entry]*solution[columns[entry]];
            const double residual = rhs[row]-ax;
            residualSquared += residual*residual;
            rhsSquared += rhs[row]*rhs[row];
            errorMax = std::max(errorMax,std::abs(solution[row]-exact[row]));
        }
        const double relativeResidual = std::sqrt(residualSquared/rhsSquared);
        const bool numericalPass = status==AMGX_SOLVE_SUCCESS && std::isfinite(relativeResidual)
            && relativeResidual<1e-8 && std::isfinite(errorMax) && errorMax<1e-6;
        std::cout << std::setprecision(17)
            << "AMGX_SMOKE_JSON {\"mode\":\"dDDI\",\"device\":\"" << properties.name
            << "\",\"compute_major\":" << properties.major << ",\"compute_minor\":" << properties.minor
            << ",\"managed_memory\":" << managed << ",\"concurrent_managed_access\":" << concurrent
            << ",\"async_memory_pools\":" << pools << ",\"rows\":" << n << ",\"nnz\":" << offsets[n]
            << ",\"iterations\":" << iterations << ",\"solve_status\":" << static_cast<int>(status)
            << ",\"relative_residual_l2\":" << relativeResidual << ",\"max_solution_error\":" << errorMax
            << ",\"rhs_norm_l2\":" << std::sqrt(rhsSquared)
            << ",\"cuda_kernel_launches_during_solve\":" << launches
            << ",\"launch_audit_loaded\":" << (count ? "true" : "false")
            << ",\"launch_count_semantics\":\"successful intercepted launch API calls, not unique kernels\""
            << ",\"numerical_pass\":" << (numericalPass ? "true" : "false") << "}\n";
        A(AMGX_solver_destroy(solver));
        A(AMGX_vector_destroy(x)); A(AMGX_vector_destroy(b)); A(AMGX_matrix_destroy(matrix));
        A(AMGX_resources_destroy(resources)); A(AMGX_config_destroy(config));
        A(AMGX_finalize_plugins()); A(AMGX_finalize());
        C(cudaDeviceSynchronize());
        return numericalPass ? 0 : 2;
    }
    catch (const std::exception& error)
    {
        std::cerr << "AMGX_SMOKE_ERROR " << error.what() << '\n';
        return 1;
    }
}
