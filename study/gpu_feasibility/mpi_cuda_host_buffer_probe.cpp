// Non-CFD CUDA lifecycle/staging/reduction test. No mesh or case is opened.
#include "OGL/CommunicationPattern.hpp"
#include "UPstream.H"
#include <cmath>
#include <iostream>
#include <iomanip>

int main(int argc, char** argv)
{
    Foam::UPstream::init(argc, argv, false);
    int global_error = 0;
    {
        using scalar = Foam::scalar;
        using dense = gko::matrix::Dense<scalar>;
        using vector = gko::experimental::distributed::Vector<scalar>;
        auto host_exec = gko::ReferenceExecutor::create();
        auto comm = std::make_shared<gko::experimental::mpi::communicator>(MPI_COMM_WORLD, true);
        const int rank = comm->rank();
        Foam::DeviceIdHandler ids(2);
        const bool owner = ids.is_owner();
        std::shared_ptr<const gko::Executor> device = host_exec;
        if (owner) device = gko::CudaExecutor::create(0, host_exec);
        const gko::size_type local_rows = owner ? 4 : 0;
        scalar send[2] = {10.0*rank, 10.0*rank+1.0};
        gko::array<scalar> values(device, local_rows);
        AllToAllPattern gather{{2, 0}, {0, 2, 2},
            owner ? std::vector<int>{2, 2} : std::vector<int>{0, 0},
            owner ? std::vector<int>{0, 2, 4} : std::vector<int>{0, 0, 0}};
        communicate_values(host_exec, device, comm, gather, send, values.get_data(), true);
        AllToAllPattern scatter{
            owner ? std::vector<int>{2, 2} : std::vector<int>{0, 0},
            owner ? std::vector<int>{0, 2, 4} : std::vector<int>{0, 0, 0},
            {2, 0}, {0, 2, 2}};
        scalar returned[2] = {-1, -1};
        communicate_values(device, host_exec, comm, scatter, values.get_const_data(), returned, true);
        int error = comm->size()!=2 || !Foam::Pstream::parRun() ||
            !comm->force_host_buffer() || owner!=(rank==0) || ids.compute_device_id(1)!=0 ||
            returned[0]!=send[0] || returned[1]!=send[1];

        // Exercise actual Ginkgo CUDA reduction kernels and its distributed
        // host-buffer collectives, with the other real MPI rank owning no rows.
        auto local = dense::create(device, gko::dim<2>{local_rows, 1},
            gko::make_array_view(device, local_rows, values.get_data()), 1);
        auto x = vector::create(device, *comm, gko::dim<2>{4,1}, std::move(local));
        auto result = dense::create(device, gko::dim<2>{1,1});
        auto host_result = dense::create(host_exec, gko::dim<2>{1,1});
        x->compute_norm1(result);
        host_result->copy_from(result);
        const scalar norm1 = host_result->at(0,0);
        x->compute_norm2(result);
        host_result->copy_from(result);
        const scalar norm2 = host_result->at(0,0);
        x->compute_mean(result);
        host_result->copy_from(result);
        const scalar mean = host_result->at(0,0);
        error = error || std::abs(norm1-22.0)>1e-12 ||
            std::abs(norm2-std::sqrt(222.0))>1e-12 || std::abs(mean-5.5)>1e-12;
        comm->all_reduce(host_exec, &error, 1, MPI_MAX);
        global_error = error;
        std::cout << "{\"rank\":" << rank << ",\"ranks\":" << comm->size()
            << ",\"pstream_parallel\":" << std::boolalpha << Foam::Pstream::parRun()
            << ",\"force_host_buffer\":" << comm->force_host_buffer()
            << ",\"single_gpu_owner\":" << owner << ",\"passed\":" << !error
            << ",\"executor_description\":" << std::quoted(device->get_description())
            << ",\"actual_gpu_buffers_tested\":true,\"actual_cuda_reduction_kernels_tested\":true"
            << ",\"global_norm1\":" << norm1 << ",\"global_norm2\":" << norm2
            << ",\"global_mean\":" << mean << "}" << std::endl;
    }
    Foam::UPstream::exit(global_error);
}
