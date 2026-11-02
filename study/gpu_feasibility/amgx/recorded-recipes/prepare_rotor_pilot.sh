#!/bin/bash
set -e
source /opt/openfoam14/etc/bashrc
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 WM_NCOMPPROCS=1
exec nice -n 15 python3 "$(dirname "$0")/prepare_rotor_pilot.py"
