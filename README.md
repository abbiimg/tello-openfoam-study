# Tello-sized quadcopter and eight-rotor OpenFOAM study

This repository contains the source, **84 completed transient CPU CFD results**, time histories, plots and reviewed GPU setup evidence. Large exact-replay dependencies are delivered in a separate, SHA-pinned offline archive. The lift study used OpenFOAM Foundation 14 in WSL on Linux ARM64. CPU remains the study's default backend.

The reference uses **7.62 cm propellers**, an **80 g** aircraft and approximately **19.2923 W total inferred battery input** for either rotor count. That power comes from rated battery energy divided by advertised flight duration; it is an operating assumption, not measured hover or peak motor power. The assumed electrical/shaft/air-power loss map is documented in [the study notes](study/README.txt).

The largest tested fine-grid mean is **1.311138 N** for eight rotors on the square perimeter, **8 cm nearest hub spacing**, with **outer edges raised 7.5°** and thrust leaning inward. Nearby 7.5–10° results are very close, and 12.5° is also close. The model supports a best-tested region rather than a unique continuous or physical optimum. Keep the report's source, temporal and paired-screen flags: Circle 12.5° narrowly fails its absolute temporal screen.

The clean count benchmark gives about **21.10% more modeled lift for eight versus four**, at equal inferred electrical budget and matched projected box. Its actual nearest spacing is **20 cm for the quad versus 10 cm for eight rotors**. That wide quad control is outside the 0–10 cm optimization range and is not an optimized quad within that range. Equal electrical budget is not equal shaft power under the assumed motor-loss map.

These are interacting finite-volume actuator sources in a shared flow field. Blades, synchronized phase, collisions, actual motor curves, body/guards and added frame/motor mass are not resolved. Synchronization is assumed feasible; the simulations do not validate that mechanism. Supported mass and payload headroom are idealized postprocessing, not measured payload ratings.

## Included files

- `cases/`: all 84 approved case definitions, source code, initial `0/` inputs, mesh dictionaries and verification records. Large mapped `0.6/U,p` fields are external dependencies.
- `study/`: geometry, generation, reproduction and analysis tools; numerical audits; all 84 CSV time histories; final CSV/JSON/HTML results; plots and flow provenance.
- `study/gpu_feasibility/`: reviewed native installation, C29, SPUMA, AmgX and profiler source/evidence. The full offline bundle also contains the 30 raw C29 CPU/reference validation fields, shared initial flux and source/seed archives intentionally omitted here.
- `review/`: CPU scientific review, exact scope freeze and figure/flow publication evidence.
- `environment/` and `export_manifest.json`: original environment versions and byte hashes for the repository snapshot.

The 15 prepared but unrun CPU cases remain explicitly deferred. The full WSL filesystem, home directories, credentials, SDKs, compiled build trees, runtime caches and raw profiler reports are excluded. Large meshes and reconstructed initial/final fields from the lift matrix remain in the separate local `cases.zip`. The complete setup/evidence archive is `setup_results.zip`; neither ZIP is tracked here.

Verified downloads are available from the [Hugging Face evidence dataset](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/tree/569c8e3ba7121eef5105cb5695a0271029d44c1b): [setup_results.zip](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/setup_results.zip), [full case fields](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/cases.zip), [checksums](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/SHA256SUMS) and the [external-input catalogue](https://huggingface.co/datasets/abmorsego/tello-openfoam-study-data/resolve/569c8e3ba7121eef5105cb5695a0271029d44c1b/external_inputs_manifest.json). These links are pinned to the verified dataset commit.

**Exact replay requires external inputs.** [EXTERNAL_INPUTS.md](EXTERNAL_INPUTS.md) and [external_inputs_manifest.json](external_inputs_manifest.json) map the 90 omitted files to the verified offline archive. Full component manifests and dated READMEs describe that complete archive; `export_manifest.json` describes this lightweight Git projection. `.gitattributes` preserves included bytes, and `.gitignore` prevents regenerated fields/caches from being added accidentally. No Git LFS or storage purchase is configured.

The initial commit already contained large warm-start and archive blobs. A normal new commit removes them from the current tree; full Git history still retains them. A source ZIP made from the current tree excludes that history. No force push or history rewrite is used. `.gitignore` controls untracked Git files and does not curate the standalone evidence ZIP.

## Exact delivered rerun

Use OpenFOAM **Foundation 14**, Open MPI, a C++ compiler, Python, NumPy and Matplotlib on Linux. The original ARM64 package was `openfoam14` version `20261008`; see [environment/reference.json](environment/reference.json). Use a non-root OpenFOAM account. First restore dependencies from the separately delivered `setup_results.zip` (SHA256 `18a7676858d22f2ab78e78cd2f8e35c9943938aa948d905fad4afc7a6a001100`):

```bash
source /opt/openfoam14/etc/bashrc
python3 tools/verify_export.py
python3 tools/restore_external_inputs.py --project-root "$PWD" --archive /path/to/setup_results.zip
python3 tools/restore_external_inputs.py --project-root "$PWD" --archive /path/to/setup_results.zip --restore
python3 study/reproduce_cases.py --inputs cases --root fresh_cases
python3 study/run_cases.py --root fresh_cases --jobs 8
python3 study/collect_numerics.py --root fresh_cases --out fresh_numerical_configurations.json
python3 study/analyze_refinement.py --root fresh_cases --out new_results \
  --numerics fresh_numerical_configurations.json \
  --case-list study/approved_cases.json --circle-max-spacing-cm 8
```

The first restore command is a dry run; the second verifies the whole archive and restores only the selected, checksum-verified dependencies. Adjust paths and concurrency. The reproducer rebuilds meshes and checks frozen mapped fields/mesh hashes before solving. It requires the external warm starts; source alone is not a bitwise replay of the delivered matrix. Open [the HTML report](study/results/report.html) locally for embedded figures. The earlier [layout-stage report](study/layout_stage/nearest8_v2/report.html) retains its fixed scope.

## Fresh source-only cases

New flat cold-start layout/count pilots can be generated without the large external fields:

```bash
python3 study/generate_layout_pilots.py --root fresh_pilots \
  --journal fresh_pilots_preparation.json --stage all
```

This generates cases and does not launch a solver. Treat subsequent runs as new experiments with a new initialization; a source-only regeneration of the complete warm-start matrix has not been validated. The reproducer's parameters mode accepts only selected legacy square cold cases, not all mapped/circular/count cases.

## GPU results and limits

[GPU_SETUP.md](study/gpu_feasibility/GPU_SETUP.md) records the exact builds, checks, failures and source pins. GPU dependencies are installed privately, with reviewed recipes and evidence included here. These separate experiments did not accelerate or change the 84-case CPU lift matrix.

- **Native OpenCFD stdpar:** framework arithmetic and strict small-cavity checks passed. A 922,576-cell C29 startup was repaired, and the short native CPU/reference comparison passed its numerical checks. Both profiled and plain GPU transient attempts then ended with SIGSEGV before the first completed step. The large rotor GPU path remains unqualified.
- **SPUMA:** its own device executor and a distinct five-step, 400-cell cavity passed. The original longer fixture failed its continuity screen and remains recorded. Rotor compatibility, longer behavior and representative performance remain untested.
- **AmgX:** Poisson, cavity and a five-step actual fine-grid rotor compatibility check passed through a private serial pressure adapter. There is no controlled speed result.
- **Earlier OGL/Ginkgo bridge:** its benchmark and continuity review flag are retained; the tested CUDA configuration failed its speed gate.
- **Current profiler:** a separate native Field control recorded eight attributable GPU kernels with correct arithmetic. That small-test proof does not repair or qualify the failed rotor time loop.

No new GPU path is claimed faster or adopted as the production default. Historical workstation recipes need deliberate path/dependency adaptation; a fresh-host rebuild was not tested. The C29 offline restore/replay validates delivered numerical-comparison data without rerunning CFD. Full raw profiler reports, full trace databases and environment dumps are excluded; only five reviewed small trace subsets are included.

Upstream source snapshots retain their own licenses. Proprietary SDKs are not redistributed.
