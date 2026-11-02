# Native stdpar recovery checkpoint

Updated 2026-11-02T10:07:19.934744+00:00. Workers continue under transient systemd ownership.

* Main worker PID 311811; supervisor PID 325989; unit native-stdpar-main-20261102T095941Z.service. Stage: finiteVolume_build.
* Profile watcher PID 326002; unit native-stdpar-profile-20261102T095941Z.service. Stage: waiting_for_native_tutorial_gate.

No tool exec session is needed. Both units run as openfoam, Nice=15, with fixed private log files and auto-collection. The active main tree was adopted without restarting any compiler. Its independent liveness/cgroup check passed after the adoption command exited; evidence is provenance/post_return_survival_latest.json. A delayed one-shot systemd check is also being scheduled for after this agent returns.

Original foreground worker PIDs and sessions disappeared; exact cause was not established. Base and upstream test app had completed. Cached objects and original journal entries were retained on resume. The upstream ten-million-cell/1000-repeat timing benchmark remains compiled but unexecuted, with its managed-mode stack-reference warning recorded. No runtime failure is claimed.

Current counts: 1132 objects total, 108 finiteVolume objects. Available memory: 53.22 GiB. Native budget remains 4 compilation jobs; SPUMA 2 separately; Nice=15 and 20 GiB reserve. Borrowed Field slot is returned.

Still queued: finish FV and mesh libraries/apps, then the isolated 400-cell cavity to time0.5 and NVTX-isolated CUDA launch API audit. Required gate files are provenance/native_openfoam_tutorial_gate.json and provenance/native_cfd_time_loop_gpu_gate.json. No native CFD or speedup result yet.

Passed: managed stdpar, device-only marker, Umpire, exact native Foam scalar/vector arithmetic and 8 successful CUDA launch APIs in its algebra window. No kernel-activity timeline is available. No actuator source or production study input was changed.

Monitor build_progress.json, provenance/minimal_build_journal.json, native_cfd_profile_progress.json and systemd_workers.json under /opt/openfoam-workspace/gpu-feasibility/native-stdpar. Reactivate this agent on failure or the next completed tutorial/profile gate. Exact current paths, PIDs, units and queues are in recovery_checkpoint.json. Root owns reviewed publication; SDK/build trees stay outside Git.
