#!/bin/bash
source /opt/openfoam-workspace/gpu-feasibility/native-stdpar/env.sh
set -euo pipefail
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
root_work=/mnt/c/Users/abbii/Documents/Codex/2026-10-30/referenced-chatgpt-conversation-this-is-an/work/native_stdpar_install
exec python3 -B "$root_work/nsys_2026_5_positive_control_proposal_v3/audit_control.py" --approval "$root_work/nsys_2026_5_positive_control_audit_v3_approval.json"
