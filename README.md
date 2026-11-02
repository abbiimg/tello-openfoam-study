# Tello-sized quadcopter and eight-rotor OpenFOAM study

Actual transient OpenFOAM actuator-model experiments comparing square and circular layouts, four and eight rotors, and inward/outward tilt with different horizontal rotor-center spacings.

**Work in progress:** this initial export contains the 84 planned experiment inputs and a preliminary analysis snapshot while the final CFD runs continue. `selection/provisional_cases.json` records the planned scope; it is not final completion approval. A later snapshot will include the final approved scope and results.

The reference propeller diameter is 7.62 cm, with a modeled total electrical input near 19.2923 W and an 80 g aircraft reference. Electrical/shaft/air-power conversion, motor idle losses and actuator behavior are assumptions documented in [the study notes](study/README.txt). These are interacting finite-volume actuator sources in a shared flow field. Blade geometry, synchronization phases, blade collisions and physical motor curves are not resolved. Results describe this model and do not establish a validated hardware optimum.

## What is included

- `cases/`: selected compact case inputs, source code, meshing dictionaries, actual frozen mapped initial fields and their verification records.
- `study/`: geometry/generation/reproduction/analysis tools, numerical audits, CSV/JSON data, plots, flow images and provenance.
- `environment/`: observed versions of the original Linux ARM64 execution environment and rebuild guidance.
- `export_manifest.json`: SHA-256 hashes of copied files and the export scope.

The WSL operating-system filesystem, home directories, credentials, installed SDKs and compiled build trees are not exported. The full reconstructed/transient flow fields remain in the separately delivered local `cases.zip`; that multi-gigabyte archive is not tracked in this repository. Meshes are rebuilt from the supplied dictionaries. The duplicate compact delivery ZIP is also omitted because its contents are represented directly here.

`.gitattributes` disables line-ending conversion so Windows and Linux checkouts preserve the SHA-256-checked input bytes. The compact inputs fit ordinary Git's individual-file limits; this export does not configure Git LFS or purchase storage.

## Reproduce on Linux

Install/load **OpenFOAM Foundation 14**, Open MPI, a C++ compiler and Python with NumPy/Matplotlib. The original package was `openfoam14` ARM64 version `20261008`; see [the environment record](environment/reference.json). Use a non-root OpenFOAM account and keep the repository's input cases unchanged.

```bash
source /opt/openfoam14/etc/bashrc
python3 study/reproduce_cases.py --inputs cases --root fresh_cases
python3 study/run_cases.py --root fresh_cases --jobs 8
python3 study/collect_numerics.py --root fresh_cases --out fresh_numerical_configurations.json
python3 study/analyze_refinement.py --root fresh_cases --out new_results \
  --numerics fresh_numerical_configurations.json \
  --case-list selection/provisional_cases.json --circle-max-spacing-cm 8
```

Adjust the installation path and concurrency for the machine. `reproduce_cases.py` rebuilds omitted meshes and checks the frozen mapped inputs/mesh hashes before a solver run. The original source files and frozen initial fields remain available for inspection. The 15 deferred, unrun preparations are documented in the study's audit scope and are not included as default runnable cases.

Clone/download the repository and open [the HTML report](study/results/report.html) locally to view its embedded figures. The completed initial [square/circle layout-stage report](study/layout_stage/nearest8_v2/report.html) has its own fixed scope and interpretation.

## GPU status

The lift matrix uses CPU OpenFOAM. A separate pressure-only CUDA adapter was built and benchmarked; its measured timing and continuity review flag are retained in `study/gpu_feasibility/`. The newer official full-flow stdpar GPU implementation was researched but not built or benchmarked here. See [the native GPU assessment](study/gpu_feasibility/native_stdpar/README.md) before interpreting either route's performance.

Upstream source snapshots retain their own licenses. No license is granted here for proprietary SDKs, which are not included.
