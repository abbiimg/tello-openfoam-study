// SPDX-License-Identifier: GPL-3.0-or-later
// Private Foundation14 integration: serial, symmetric, noncoupled pressure systems.
// Native residual normalization follows OpenFOAM Foundation's GPL PCG interface.
#include "lduMatrix.H"
#include "lduInterfaceField.H"
#include "Pstream.H"
#include "scalarField.H"
#include "solverPerformance.H"
#include <amgx_c.h>
#include <cuda_runtime_api.h>
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <dlfcn.h>
#include <iomanip>
#include <limits>
#include <sstream>
#include <vector>

namespace Foam
{
namespace
{
void amgxCheck(const AMGX_RC result, const char* expression)
{
    if (result != AMGX_RC_OK)
    {
        char text[4096];
        AMGX_get_error_string(result, text, sizeof(text));
        FatalErrorInFunction << expression << ": " << text << exit(FatalError);
    }
}
void cudaCheck(const cudaError_t result)
{
    if (result != cudaSuccess)
        FatalErrorInFunction << cudaGetErrorString(result) << exit(FatalError);
}
struct AmgXRuntime
{
    AmgXRuntime()
    {
        cudaCheck(cudaSetDevice(0));
        cudaDeviceProp properties{};
        cudaCheck(cudaGetDeviceProperties(&properties, 0));
        amgxCheck(AMGX_initialize(), "AMGX_initialize");
        amgxCheck(AMGX_initialize_plugins(), "AMGX_initialize_plugins");
        Info<< "AmgXPressure: private serial mode dDDI, GPU0 " << properties.name
            << ", compute " << properties.major << '.' << properties.minor << nl;
    }
    ~AmgXRuntime()
    {
        AMGX_finalize_plugins();
        AMGX_finalize();
    }
};
void initializeRuntime() { static AmgXRuntime runtime; }
}

class AmgXPressure : public lduMatrix::solver
{
public:
    TypeName("AmgXPressure");
    AmgXPressure(const word& fieldName, const lduMatrix& matrix,
        const FieldField<Field,scalar>& boundaryCoefficients,
        const FieldField<Field,scalar>& internalCoefficients,
        const lduInterfaceFieldPtrsList& interfaces, const dictionary& controls)
    : lduMatrix::solver(fieldName,matrix,boundaryCoefficients,internalCoefficients,interfaces,controls) {}

    virtual solverPerformance solve(scalarField& psi, const scalarField& source,
                                     const direction cmpt=0) const override
    {
        static_assert(sizeof(scalar)==sizeof(double), "Requires Foundation DP scalar");
        if (Pstream::parRun())
            FatalErrorInFunction << "Private AmgXPressure is serial only" << exit(FatalError);
        if (!matrix_.symmetric())
            FatalErrorInFunction << "Only symmetric matrices are supported" << exit(FatalError);
        forAll(interfaces_, patchi)
            if (interfaces_.operator()(patchi))
                FatalErrorInFunction << "Coupled interfaces are not supported" << exit(FatalError);
        if (minIter_ != 0 || maxIter_ < 1)
            FatalErrorInFunction << "Requires minIter0 and positive maxIter" << exit(FatalError);

        solverPerformance performance(typeName, fieldName_);
        const label n = psi.size();
        scalarField product(n), scratch(n);
        matrix_.Amul(product,psi,interfaceBouCoeffs_,interfaces_,cmpt);
        scalarField residual(source-product);
        const scalar normalization = this->normFactor(psi,source,product,scratch);
        if (!(normalization>0) || !std::isfinite(normalization))
            FatalErrorInFunction << "Non-finite or nonpositive native normalization" << exit(FatalError);
        performance.initialResidual() = gSumMag(residual,matrix_.mesh().comm())/normalization;
        if (!std::isfinite(performance.initialResidual()))
            FatalErrorInFunction << "Non-finite initial residual" << exit(FatalError);
        performance.finalResidual() = performance.initialResidual();
        if (performance.checkConvergence(tolerance_,relTol_)) return performance;
        if (n < 1) return performance;

        const labelUList& owners = matrix_.lduAddr().lowerAddr();
        const labelUList& neighbours = matrix_.lduAddr().upperAddr();
        const scalarField& diagonal = matrix_.diag();
        const scalarField& upper = matrix_.upper();
        const scalarField& lower = matrix_.lower();
        if (static_cast<long long>(n)+2LL*owners.size()>std::numeric_limits<int>::max())
            FatalErrorInFunction << "CSR32 matrix is too large" << exit(FatalError);
        double scale = 0;
        forAll(diagonal,i) scale = std::max(scale,std::abs(diagonal[i]));
        if (!(scale>0) || !std::isfinite(scale))
            FatalErrorInFunction << "Invalid diagonal scale" << exit(FatalError);
        const double sign = diagonal[0]<0 ? -1.0 : 1.0;
        forAll(diagonal,i)
            if (!(sign*diagonal[i]>0))
                FatalErrorInFunction << "Diagonal signs are inconsistent" << exit(FatalError);
        std::vector<int> offsets(n+1,0);
        for (label i=0;i<n;++i) offsets[i+1] = 1;
        forAll(owners,f) {++offsets[owners[f]+1]; ++offsets[neighbours[f]+1];}
        for (label i=0;i<n;++i) offsets[i+1] += offsets[i];
        std::vector<int> columns(offsets[n]), next(offsets);
        std::vector<double> values(offsets[n]), rhs(n), solution(n);
        auto insert = [&](int row,int col,double coefficient)
        {
            const int entry = next[row]++;
            columns[entry] = col;
            values[entry] = sign*coefficient/scale;
        };
        for (label i=0;i<n;++i)
        {
            insert(i,i,diagonal[i]);
            rhs[i] = sign*source[i]/scale;
            solution[i] = psi[i];
        }
        // Foundation Amul uses upper for owner<-neighbour and lower for neighbour<-owner.
        forAll(owners,f)
        {
            insert(owners[f],neighbours[f],upper[f]);
            insert(neighbours[f],owners[f],lower[f]);
        }
        for (label row=0;row<n;++row)
            for (int entry=offsets[row]+1;entry<offsets[row+1];++entry)
            {
                int j=entry;
                while (j>offsets[row] && columns[j]<columns[j-1])
                {
                    std::swap(columns[j],columns[j-1]);
                    std::swap(values[j],values[j-1]);
                    --j;
                }
            }
        const double threshold = std::max(tolerance_,relTol_*performance.initialResidual());
        if (!(threshold>0) || !std::isfinite(threshold))
            FatalErrorInFunction << "A positive stopping threshold is required" << exit(FatalError);
        // ||r||1 <= sqrt(n)||r||2, with matrix/rhs both scaled by sign/scale.
        // Factor0.1 is an additional tenfold safety margin, not part of that bound.
        const double backendTolerance = std::max(1e-300,
            0.1*threshold*normalization/(scale*std::sqrt(static_cast<double>(n))));
        if (!(backendTolerance>0) || !std::isfinite(backendTolerance))
            FatalErrorInFunction << "Invalid backend tolerance" << exit(FatalError);
        std::ostringstream options;
        options << std::setprecision(17)
            << "{\"config_version\":2,\"solver\":{\"solver\":\"PCG\",\"max_iters\":" << maxIter_
            << ",\"tolerance\":" << backendTolerance
            << ",\"norm\":\"L2\",\"convergence\":\"ABSOLUTE\",\"monitor_residual\":1,\"print_solve_stats\":0,"
            << "\"preconditioner\":{\"solver\":\"AMG\",\"algorithm\":\"AGGREGATION\",\"selector\":\"SIZE_2\","
            << "\"cycle\":\"V\",\"presweeps\":1,\"postsweeps\":1,\"max_iters\":1,\"max_levels\":100,"
            << "\"coarse_solver\":\"DENSE_LU_SOLVER\",\"smoother\":{\"solver\":\"BLOCK_JACOBI\"}}}}";
        initializeRuntime();
        AMGX_config_handle config;
        AMGX_resources_handle resources;
        AMGX_matrix_handle matrix;
        AMGX_vector_handle b,x;
        AMGX_solver_handle solver;
        auto checked = [](AMGX_RC rc) {amgxCheck(rc,"AmgXPressure C API");};
        checked(AMGX_config_create(&config,options.str().c_str()));
        int device=0;
        checked(AMGX_resources_create(&resources,config,nullptr,1,&device));
        checked(AMGX_matrix_create(&matrix,resources,AMGX_mode_dDDI));
        checked(AMGX_vector_create(&b,resources,AMGX_mode_dDDI));
        checked(AMGX_vector_create(&x,resources,AMGX_mode_dDDI));
        checked(AMGX_solver_create(&solver,resources,AMGX_mode_dDDI,config));
        checked(AMGX_matrix_upload_all(matrix,n,offsets[n],1,1,offsets.data(),columns.data(),values.data(),nullptr));
        checked(AMGX_vector_bind(b,matrix)); checked(AMGX_vector_bind(x,matrix));
        checked(AMGX_vector_upload(b,n,1,rhs.data()));
        checked(AMGX_vector_upload(x,n,1,solution.data()));
        checked(AMGX_solver_setup(solver,matrix));
        cudaCheck(cudaDeviceSynchronize());
        auto reset = reinterpret_cast<void(*)()>(dlsym(RTLD_DEFAULT,"amgx_audit_reset"));
        auto count = reinterpret_cast<unsigned long long(*)()>(dlsym(RTLD_DEFAULT,"amgx_audit_launches"));
        if (reset) reset();
        checked(AMGX_solver_solve(solver,b,x));
        cudaCheck(cudaGetLastError()); cudaCheck(cudaDeviceSynchronize());
        const auto launches = count ? count() : 0ULL;
        int iterations=0;
        AMGX_SOLVE_STATUS status;
        checked(AMGX_solver_get_status(solver,&status));
        checked(AMGX_solver_get_iterations_number(solver,&iterations));
        checked(AMGX_vector_download(x,solution.data()));
        cudaCheck(cudaDeviceSynchronize());
        for (label i=0;i<n;++i) psi[i] = solution[i];
        matrix_.Amul(product,psi,interfaceBouCoeffs_,interfaces_,cmpt);
        residual = source-product;
        performance.finalResidual() = gSumMag(residual,matrix_.mesh().comm())/normalization;
        performance.nIterations() = iterations;
        const bool converged = performance.checkConvergence(tolerance_,relTol_);
        Info<< "AMGX_PRESSURE_SOLVE rows=" << n << " nnz=" << offsets[n]
            << " iterations=" << iterations << " kernels=" << static_cast<std::uint64_t>(launches)
            << " initial=" << performance.initialResidual() << " final=" << performance.finalResidual()
            << " converged=" << converged << nl;
        checked(AMGX_solver_destroy(solver)); checked(AMGX_vector_destroy(x));
        checked(AMGX_vector_destroy(b)); checked(AMGX_matrix_destroy(matrix));
        checked(AMGX_resources_destroy(resources)); checked(AMGX_config_destroy(config));
        if (status!=AMGX_SOLVE_SUCCESS || !std::isfinite(performance.finalResidual()) || !converged)
            FatalErrorInFunction << "AmgX did not meet the native OpenFOAM stopping criterion" << exit(FatalError);
        return performance;
    }
};
defineTypeNameAndDebug(AmgXPressure,0);
lduMatrix::solver::addsymMatrixConstructorToTable<AmgXPressure> addAmgXPressureToTable;
}
