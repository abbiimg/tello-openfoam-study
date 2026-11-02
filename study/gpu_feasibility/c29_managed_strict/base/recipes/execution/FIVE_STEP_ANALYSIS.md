# Read-only mechanical five-step analyzer

`analyze_five_steps.py` is prepared source, not a process runner. It invokes no solver, initializer or external program and changes no case/source/threshold. Default stage is Foundation14→native CPU. CPU→GPU is blocked until that first mechanical gate passes; root's failed GPU initial-only process is not qualified by this analyzer.

The exact threshold SHA is `d6001e84…`. The code pins and imports root's `compare_initial_cpu.py` complete ASCII reader and `reference_axial_speed.py` frozen-cache measurement without invoking either main. No controller law is reconstructed. Every source sample uses the matching prior-step F14 U: .600 for .6001, then .6001… .6004. The cache check is repeated accounting, not independent geometry validation.

All five saved times and all U/p/phi internal and boundary value blocks must pass. Each boundary value block is checked separately, with uniform broadcasting where needed. For vector U, error/reference RMS is based on vector magnitude; maximum is maximum vector magnitude. Denominators are max(reference RMS or maximum, the approved physical floor). Scalar p/phi use absolute scalar magnitudes. Pressure mean is never subtracted and no volume weighting or sample averaging is introduced. Boundary blocks are aligned by the same ordered complete reader used for the exact startup gate; shape/key/inventory differences fail.

The logs must contain five consecutive times/TILT samples, eight initial volumes, all velocity components, two p solves/continuity correctors per step, finite diagnostics and ordinary End. Every final residual uses the unchanged configured criterion plus the approved1e-12 reporting allowance. Every Courant and continuity observation is checked, including first pressure correctors. Foundation reports Co before increment; native reports it after Time, so coverage is assigned accordingly without dropping startup observations.

Parser-only v2 accepts Foundation time labels with an optional `s` suffix. Local/global continuity is required on all ten correctors; actual cumulative values are required on every final correction and checked wherever printed, without fabricating an intermediate cumulative value. V3 also exempts the exact normal native startup `trapFpe: Floating point exception trapping enabled (FOAM_SIGFPE).` banner, alongside the exact Foundation `sigFpe : Floating point exception trapping - not supported on this platform` banner; actual fatal FPE/other failures remain failures. It labels log checks by role. Frozen v1 f95aec1… and v2 1310a87… are preserved. These are structural format corrections reported by root, not numerical criterion changes.

Native logs additionally require explicit UFinal/p/pFinal ordering, five source and applied-air audits, all40 rotor observations and consecutive once-per-index updates. Source dimensions/zero coefficients, craft/positive-source force, negative applied air force and signed work are checked against the approved accounting tolerances. Previous/current thrust is telemetry only; no expected-thrust mirror test exists.

Original Foundation stdout does not print UFinal/pFinal alias names. Its residual/order tests use the reviewed original one-outer PIMPLE protocol; exact selected aliases/unchanged input and loader identity remain separate source/protocol receipt gates. The analyzer states this limitation rather than claiming direct log observation. Likewise End is not a substitute for root's process exit/terminal receipt.

Example after root has completed the required runs:

```
python analyze_five_steps.py --stage f14-to-cpu --out NEW_REPORT.json
```

Planned stdout names are `f14_control_five_stdout.log`, `native_cpu_five_stdout.log`, and `native_gpu_five_stdout.log` in this directory; `--log-dir` can select another read-only log location. Output must be a new file outside the cases. Missing/partial data remains failed or incomplete, never filled with estimates. Terminal/input/loader/framework/startup receipts and overall backend adoption are explicitly outside the mechanical pass result. No timings or performance claim are computed.

The authorized v3 reanalysis of the original completed Foundation14/native CPU runs remains a mechanical FAIL: first-corrector global continuity at steps 1 and 2 fails in each role, with the unchanged `1e-7` limit. All other checks pass. The previous v2 failed report remains unchanged. V3 ran with NumPy 1.26.4, whereas the root v2 report used 2.5.4; reference file hashes agree, repeated summary reductions differ only at last bits, and numerical classifications agree. `five_step_parser_v3_reanalysis_record.json` records those differences without changing any acceptance criterion.

The separate `strict_pressure_proposal/` contains an unapproved SOURCE-ONLY prospective protocol for fresh cases. It is not applied to this analyzer or to original cases, and cannot retroactively qualify the failed experiment.
