#!/bin/bash
source /opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_cpu_managed_strict_v2_3_20261102/build_environment.sh
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
exec python3 /mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/execution/launch_strict_cpu_five_once.py --role cpu
