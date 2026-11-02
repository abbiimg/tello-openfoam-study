#!/bin/bash
source /opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102/build_environment.sh
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
root_work=/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/execution
python3 "$root_work/admit_strict_gpu_profile.py"
exec python3 -B "$root_work/strict_runs/gpu_profile_proposal_v3/run_gpu_profile.py" --approval "$root_work/strict_runs/root_gpu_profile_approval.json" --receipt /opt/openfoam-workspace/cases/native_c29_strict_pressure_20261102/receipts/c29_strict_shared_five_gpu_20261102_a.json --execute-approved-receipt
