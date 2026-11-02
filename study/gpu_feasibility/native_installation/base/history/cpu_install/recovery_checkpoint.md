# CPU control recovery checkpoint

Observed 2026-11-02T10:36:03.172141+00:00 after the launch command fully exited.

Worker PID 331683, parent PID 1; service native-cpu-control-20261102T103411Z.service; User=openfoam, Nice=15, active and in its expected systemd cgroup. No tool exec session is needed.

Current stage: openfoam_base, up to 4 jobs. Objects: 184. Available memory: 49.99 GiB. Compile errors observed: 0.

Prefix: /opt/openfoam-workspace/gpu-feasibility/native-cpu-control. Monitor build_progress.json, provenance/build_journal.json and service.json. Source pins and isolated environment are in provenance/source_and_environment.json. Budget is work/native_cpu_control/build_budget.json: CPU4 plus GPU4 plus SPUMA2, combined maximum10, Nice15,20GiB reserve with2GiB allowance per new CPU job.

Queued: remaining base, finiteVolume and required mesh libraries/apps, followed by only the isolated400-cell cavity to0.5. The final manifest will be provenance/native_cpu_cavity_gate.json. No C29 candidate or speed benchmark has been built/run. GPU source/SDK/cases and global defaults remain untouched.

Root will monitor and reactivate this agent for failure or a completed gate. Workers continue when this agent returns; reviewed publication is root-owned.
