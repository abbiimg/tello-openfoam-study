#!/bin/bash
# The first wrapper issued its receipt/approval but argparse refused its wrong
# execution flag before any evidence directory or solver child was created.
# Reuse that still-fresh, reverified approval once; do not issue another receipt.
source /opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102/build_environment.sh
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
root_work=/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/gpu_actuator_port/execution
test ! -e /opt/openfoam-workspace/gpu-feasibility/native-c29-validation/native_gpu_managed_strict_v2_3_20261102/plain_unprofiled_diagnostic_v1_20261102
exec python3 -B "$root_work/strict_runs/plain_gpu_diagnostic_proposal_v2/run_plain_gpu_once.py" --approval "$root_work/strict_runs/root_plain_gpu_approval.json" --receipt /opt/openfoam-workspace/cases/native_c29_gpu_diagnostics_20261102/receipts/c29_plain_unprofiled_2_3_20261102_a.json --execute-approved-diagnostic
