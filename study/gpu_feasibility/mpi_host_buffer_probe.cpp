// Non-CFD lifecycle/API test: no mesh, case dictionaries or fluid solver.
#include "OGL/CommunicationPattern.hpp"
#include "UPstream.H"
#include <iostream>
#include <string>

int main(int argc, char** argv)
{
    Foam::UPstream::init(argc, argv, false);
    int global_error = 0;
    {
        auto exec = gko::ReferenceExecutor::create();
        auto comm = std::make_shared<gko::experimental::mpi::communicator>(
            MPI_COMM_WORLD, true);
        const int rank = comm->rank();
        Foam::DeviceIdHandler ids(2);
        const bool test_cuda = argc > 1 && std::string(argv[1]) == "--cuda-staging";
        int sum = rank + 1;
        comm->all_reduce(exec, &sum, 1, MPI_SUM);
        AllToAllPattern pattern{{1, 1}, {0, 1, 2}, {1, 1}, {0, 1, 2}};
        Foam::scalar send[2] = {10.0 * rank, 10.0 * rank + 1.0};
        Foam::scalar received[2] = {-1.0, -1.0};
        communicate_values(exec, exec, comm, pattern, send, received, true);
        const bool owner = ids.is_owner();
        int error = (comm->size() != 2 || !Foam::Pstream::parRun() ||
            !comm->force_host_buffer() || sum != 3 ||
            ids.compute_device_id(1) != 0 || owner != (rank == 0) ||
            received[0] != rank || received[1] != 10 + rank);
        if (test_cuda) {
            std::shared_ptr<const gko::Executor> device = exec;
            if (ids.is_owner()) device = gko::CudaExecutor::create(0, exec);
            gko::array<Foam::scalar> values(device, ids.is_owner() ? 4 : 0);
            AllToAllPattern gather{{2, 0}, {0, 2, 2},
                ids.is_owner() ? std::vector<int>{2, 2} : std::vector<int>{0, 0},
                ids.is_owner() ? std::vector<int>{0, 2, 4} : std::vector<int>{0, 0, 0}};
            communicate_values(exec, device, comm, gather, send, values.get_data(), true);
            AllToAllPattern scatter{
                ids.is_owner() ? std::vector<int>{2, 2} : std::vector<int>{0, 0},
                ids.is_owner() ? std::vector<int>{0, 2, 4} : std::vector<int>{0, 0, 0},
                {2, 0}, {0, 2, 2}};
            Foam::scalar returned[2] = {-1, -1};
            communicate_values(device, exec, comm, scatter, values.get_const_data(), returned, true);
            error = error || returned[0] != send[0] || returned[1] != send[1];
        }
        comm->all_reduce(exec, &error, 1, MPI_MAX);
        global_error = error;
        std::cout << "{\"rank\":" << rank
                  << ",\"ranks\":" << comm->size()
                  << ",\"pstream_parallel\":" << std::boolalpha << Foam::Pstream::parRun()
                  << ",\"force_host_buffer\":" << comm->force_host_buffer()
                  << ",\"single_gpu_owner\":" << owner
                  << ",\"allreduce_sum\":" << sum
                  << ",\"exchange\":[" << received[0] << ',' << received[1]
                  << "],\"passed\":" << !error
                  << ",\"actual_gpu_buffers_tested\":" << test_cuda << "}" << std::endl;
    }
    Foam::UPstream::exit(global_error);
}
