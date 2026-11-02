TELLO REFERENCE: FINER ANGLE / SPACING STUDY

Open results/report.html for illustrated actual CFD results. During execution,
the report/manifest identify incomplete cases. Final accepted cases are frozen
in approved_cases.json before final archives are produced.

CURRENT OBJECTIVE AND STAGED ORDER
Maximum vertical lift at the common total electrical budget is the primary
objective. Smaller spacing/footprint is secondary for close or unresolved
results; four rotors, either planform, and zero tilt remain valid candidates.
The user requested layout first, rotor count second, angle/spacing third.
Three additional cold serial/direct pilots therefore compare flat N8 square
and circular layouts, then flat N4, all with23.62cm projected width/depth.
numerical_configurations.json records the audited preparation scope;
supervisor_state.json records current completion and scheduling counts.
Earlier unstarted optimization cases are deferred during the staged pilots;
prepared inputs are not counted as completed simulations. Running fine-grid
calculations can be OS-suspended in memory for pilot priority, then resumed
with their original solver/controller state. No physics input is changed.

REFERENCE PARAMETERS
Ryze publishes approximately 80 g with battery/propellers, 3-inch (76.2 mm)
propellers, a 3.8 V / 1100 mAh battery, and up to 13 minutes endurance. Its
manual lists 87 g including guards and 4.18 Wh rated battery energy. Sources:
 https://www.ryzerobotics.com/tello/specs
 https://dl-cdn.ryzerobotics.com/downloads/Tello/20180404/Tello_User_Manual_V1.2_EN.pdf

The nominal electrical budget is 4.18 Wh / (13/60 h) = 19.2923076923 W TOTAL
for either layout. This is inferred from rated energy and advertised forward
flight endurance (15 km/h, windless). It is not a published measured hover,
peak, motor or shaft power. The delivered CFD is still-air stationary forcing.
Using this chosen input to recover 13 minutes is not endurance validation.

Both layouts hypothetically retain the same 80 g total mass, under the user's
no-added-weight assumption. 87 g is a separate mass reference; guard geometry
is not simulated. Weight affects postprocessed lift margin, not this fixed
geometry/power flow solution. With g=9.80665 m/s2:
 80 g weighs 0.784532 N; 87 g weighs 0.85317855 N.
 Supported mass = vertical lift / g.
 Ideal headroom beyond the reference = supported mass minus reference mass.
Added motors, frame, synchronizer mass and airframe aerodynamic forces are
not predicted. This idealized layout is not a replica of the stock Tello CAD
or motor system. No efficiency has been fitted to make it support 80 g.

GEOMETRY AND POWER MODEL
Four original hubs are at (+/-d,+/-d,0). Eight rotors add hubs at (0,+/-d,0)
and (+/-d,0,0). For eight rotors, d is the nearest original-to-added center
spacing. Neighboring hubs of the four-rotor control are 2*d apart. Reported
width is the projected bounding box of thin swept disks, not center spacing.
Flat four/eight controls at the same d have exactly the same footprint.
Tilted comparisons report their actual projected extents.

Negative theta raises the outer disk edges, leans craft thrust inward, and
applies air force outward/downward. Positive theta reverses that inclination.
Actual wakes can bend and mix. Overlap/contact avoidance is assumed possible
through synchronization; blades and their azimuthal phase are not resolved.

Every rotor is a finite inclined cylindrical force region sharing one 3D
incompressible flow solution. Default diameter 76.2 mm, axial source thickness
12 mm, rho=1.225 kg/m3, nu=1.5e-5 m2/s, laminar stress. Geometry weights use
16x16 horizontal midpoints with exact vertical-line/cylinder intersections.
The same normalized weights apply force, sample velocity, and integrate work.
Opposing forces can cancel inside one cell; subcell counterflows are unresolved.

The assumed loss map reserves 0.5 W for electronics, takes motor-driver
efficiency .95, subtracts .10 W per motor, uses motor conversion .60 and
assigns .50 of shaft power to modeled axial work:
 Pshaft = .60 * [.95*(Pe-.5) - .10*N]; Pair = .50*Pshaft.
These remain assumptions, not measured Tello motor/propeller efficiencies.
Each rotor receives Pair/N, with thrust relaxing toward (Pair/N)/max(w,1m/s)
over .03 s and capped at .50 N. Motor RPM, pitch, voltage sag and real drive
power distribution are not solved. Electrical input is inferred from CFD air
work through this map; the primary input tolerance is +/-0.5% of budget.
Equal per-rotor axial power is an idealized independent-control assumption.
Synchronization is assumed to permit the geometry; common-RPM fixed-pitch
motor/propeller operating curves are not enforced by these actuator sources.

NUMERICAL REFINEMENT
Initial sweep: 24 eight-rotor combinations, d=7.5,8,9,10 cm and outer edges
raised 0,2.5,5,7.5,10,12.5 degrees; plus a flat four-rotor d=10 cm control.
Additional local points and mesh/sensitivity checks are recorded in the final
manifest and per-case geometry, not silently interpolated into results.
The earlier prepared square-study matrix has 62 cases: 29 coarse screens (including the
four-rotor control and four local spacing checks), four original cold-start
medium/fine flat controls, 27 mapped validation cases, and two cold serial
initialization checks. The mapped matrix covers all three grids for four
rotors flat at d=10 cm, eight flat at d=10 cm, and eight at d=8 cm with outer
edges raised 0,7.5,10,12.5 degrees. The final named approved list controls the
delivered matrix if subsequent evidence warrants further refinement.
The remaining mapped states check adjacent promising points on all three
grids: d7.5/raised12.5 degrees, d8.5/raised5 degrees, and d8/raised5 degrees.
Meshes: coarse 248400 cells (core 8 mm xy /4 mm z), medium 481888 (6/3 mm),
fine 922576 (4.8/2.4 mm). Domain xy +/-0.36 m, z=-0.60 to +0.36 m; uniform
source core xy +/-0.168 m and z +/-0.042 m. Open totalPressure / pressure-
InletOutletVelocity boundaries, no ground or solid vehicle surfaces.
Euler time, linearUpwind convection, GAMG/GaussSeidel pressure tolerance1e-7,
PIMPLE1 outer/2 pressure corrections; adaptive maxCo .9, maximum dt .0008 s.
Screening runs start at rest at t=0, end .8 s and average .4-.8 s. Their
adjacent .4-.6 and .6-.8 s means revealed appreciable baseline drift. Selected
validation cases therefore run to 1.2 s and average .8-1.2 s, with adjacent
.8-1.0 and 1.0-1.2 s checks. The four already-running medium/fine controls were
extended continuously well before .8 s, without restarting or changing source
or rotor parameters; control_changes.json records exact times and hashes.
Fresh coarse validation replicas keep the archived screening cases immutable.
All four original cold controls completed to 1.2 s; none was cancelled.
New validation cases initialize U and p from their OWN geometry's exact
coarse screening checkpoint at 0.6 s, then advance the actual Navier-Stokes
solution to 1.2 s. The existing source reinitializes its relaxed thrust from
mapped velocity; actuator controller history is not transferred. No phi is
mapped: the solver builds/projects flux. The interval 0.6-0.8 s is excluded
from primary averages. This is mapped/reinitialized validation, not a full
cold-start continuation or a scaling of a previous lift result.
The archived target 0.6 fields, mesh and initialization.json hashes permit
reruns without the historical source path. Source/mapped fields and physics
invariants were checked during preparation. Both absolute lift and paired
gain still need late-window stability checks; initialization alone proves
neither. Two additional medium cold-start checks use the SAME serial/direct
numerics as their mapped counterparts (flat d10 and raised10 degrees at d8).
Explicit study_role metadata separates screening, validation and model checks;
the first screening cases use documented legacy role inference.
Lift and paired-gain stability are screened at about .25% and .25 percentage
points respectively, independently of input/source checks. A longer endpoint
alone does not establish stationarity. Mesh pairs hold the physical averaging
interval fixed. This is coupled space/time refinement: Courant-limited time
steps also change with the mesh. No separate time-step convergence claim is
made. Three meshes, finite
windows and a finite parameter grid do not by themselves prove an optimum,
domain independence or hardware performance. Tagged model checks are separate.

CUDA BENCHMARK AND DEFAULT BACKEND
The production lift study uses native CPU OpenFOAM. A separate private
Foundation14/OGL/Ginkgo CUDA pressure-solver path was built and exercised
on the RTX Spark GPU, with actual logged CUDA executor use and 81% peak
GPU utilization. CUDA is available for that experimental configuration;
it has not become the production default.

A sequential, same-frozen-state, 922576-cell benchmark from 0.600 to0.620s
took237.579s with serial CPU,137.435s with two CPU ranks, and250.130s with
two ranks plus CUDA pressure offload. Full runner wall times include
decomposition/reconstruction where applicable and exclude the one-time
private build. The tested CUDA configuration took82.0% longer than CPU2,
so it failed the preregistered speed gate. Force/power and field differences
met their stated limits, but an intermediate continuity-envelope review
flag remains in the evidence. No GPU study result is mixed with the CPU
lift matrix. This benchmark does not rule out other GPU solvers or tuning.
See gpu_feasibility/benchmark_evidence_manifest.json and
gpu_feasibility/benchmark_reproduction/INSTRUCTIONS.txt for measurements,
source pins, compatibility patch and actual frozen benchmark inputs.

A separate official stdpar GPU implementation covers incompressible flow;
the pressure-only Ginkgo measurement above cannot establish its performance.
Current OpenCFD core/develop identifies a GPU-branch merge (68a81857/API2609).
This computer has no installed nvc++/NVHPC or ready stdpar OpenFOAM build.
Its basic managed-memory support leaves a possible managed-mode route, while
the GH200 unified-memory defaults cannot be assumed suitable. The Foundation
actuator would also need a verified target-branch port. No native stdpar
build, actuator run or speedup was measured here. The supplied published
4–5x example uses a much larger grid and different hardware. Primary sources,
the local inventory and the required validation gates are documented in
gpu_feasibility/native_stdpar/README.md and local_inventory.json beside it.

ACTUAL EXECUTION / REPRODUCTION
Use Linux, OpenFOAM Foundation14, Open MPI, a compiler, Python3.10+ and a
non-root OpenFOAM account. Analysis requires NumPy/Matplotlib. Original cold
screens/controls use two MPI ranks per case; new mapped cases and matched
cold initialization checks use one serial process. The scheduler limits the
sum to 16 solver processes, with one OMP/BLAS thread per process. Two-rank
runners decompose along x, copy rotorParameters to each rank, run foamRun,
then reconstruct root fields. Serial runners write root fields directly.
Mapped runners preserve the initial 0.6 fields and verify frozen hashes
before and after solving. MPI reconstruction excludes that initial time.

New serial cases enable GAMG directSolveCoarsest for both p and pFinal while
retaining all tolerances/schemes. Short isolated probes retained identical
initial fields, mesh and physics. The serial/direct probe's final force
differed from the two-rank/direct result by about0.000036%; U/p relative L2
differences were0.0031%/0.0209%. This supports its use with fewer CPU resources;
it is not a proof that long runs or every geometry are numerically identical.
Canonical method signatures distinguish the original and new configurations.
Pure initialization comparisons require matching verified method signatures;
comparisons that also change execution settings are identified separately.
ideal_disk_consistency.json separately labels an analytic internal check:
at the nominal assumed axial work, isolated ideal disks give1.07003N for
four rotors and1.32748N for eight. Completed original fine flat CFD gives
1.06737N and1.29253N. This checks gross force/work scaling; it does not
calibrate electrical losses, validate hardware, or bound every interacting
or canted configuration.

Completed archives contain logs and results and are protected against overwrite.
To reproduce the EXACT delivered matrix after extracting setup_results.zip:
 python3 study/reproduce_cases.py --inputs cases --root fresh_cases
 python3 study/run_cases.py --root fresh_cases --jobs 8
 python3 study/collect_numerics.py --root fresh_cases --out fresh_numerical_configurations.json
 python3 study/analyze_refinement.py --root fresh_cases --out new_results --numerics fresh_numerical_configurations.json --case-list study/approved_cases.json --circle-max-spacing-cm 8

Collect a fresh read-only numerical audit so matched comparisons use verified
settings from the reproduced inputs. The explicit accepted case list keeps
nested preparation templates separate from executed experiments. It includes
completed controls and unqualified measurements, rather than selecting only
favorable or qualified results. Deferred unrun inputs are documented separately.

The default delivered mode preserves each case's frozen inputs, runner,
numerical settings and actual initial fields. It never copies evolved fields,
old run markers or solver logs. A mapped case uses its archived 0.6/U,p and
target mesh, rebuilding the mesh if omitted; hash verification does not need
the historical source-case path. Do not run prepare_parallel.py over these
initialized copies. Serial cold copies also retain cold_preparation.json.
Use --mode parameters only for explicitly selected LEGACY square cold cases;
then install the cold runner with prepare_parallel.py. New circle/count pilots
define distance_cm as nearest hub spacing, including 16 cm for the quad, so
they must not be fed into the legacy square-d generator. Use delivered mode,
or regenerate the supplied flat 23.62 cm pilot family with:
 python3 generate_layout_pilots.py --root fresh_pilots --journal fresh_pilots_preparation.json --stage all
Use --stage layout or --stage rotor_count to prepare only the relevant stage.
No flow solver is launched by these reproduction or preparation steps.
Direct legacy generator use is shown below.

To generate only the initial sweep directly:
 python3 generate_tello.py --root fresh_cases
 python3 generate_tello.py --root fresh_cases --rotors 4 --distances 10 --angles 0
 python3 prepare_parallel.py --root fresh_cases
 python3 run_cases.py --root fresh_cases --jobs 8

run_manifest.json records the actual connector-managed jobs. The reproduction
driver writes local_run_manifest.json in the fresh root. Source histories are
retained as CSV; TILT columns are time,Lz,Pair,Pshaft,Pe,Tsum,Fx,Fy.
setup_results.zip contains inputs/scripts/logs/reports; cases.zip additionally
contains initial/final reconstructed fields and mesh. Duplicate processor
directories are excluded. Allrun refuses previously started cases by design.
The flow images are actual saved velocity snapshots at the stated time,
not time-averaged velocity fields. flow_provenance.json records source hashes,
native renderer requests and the common display crop/scale.

CIRCULAR LAYOUT QUESTION
circle_geometry.png is a geometry-only illustration. Separate actual CFD
layout pilot results are reported only after solver completion.
For flat D7.62cm disks and the current d8cm square arrangement, both
width/depth equal23.62cm. An evenly spaced eight-hub ring rotated22.5degrees
fits that same box with hub radius8.65914cm and nearest spacing6.62742cm.
Keeping nearest spacing8cm instead gives a26.93371cm box. The maximum span
also differs: current square30.24742cm; equal-box ring24.93828cm. Footprint
comparisons must name the chosen metric. Overlap remains allowed under the
synchronization assumption. The illustration itself predicts no lift/power.
New layout/count pilot distance_cm values explicitly mean nearest horizontal
hub separation, unlike the legacy square d parameter. The matched N4 pilot
has16cm nearest spacing and the same23.62cm box; N8 square has8cm and the
ring6.62742cm. distance_parameter_definition and independently derived values
prevent interpreting the N4 control as part of an0-10cm spacing sweep.

UPDATED CIRCLE SIZE ALLOWANCE
The circle may grow up to the size needed for 8 cm between neighboring hubs.
At that spacing the hub-circle diameter is 20.9050 cm, flat disk maximum span
is 28.5250 cm, and projected width/depth are 26.9337 cm. Equal width with the
square is no longer required for the primary layout decision. The completed
nearest8 layout stage is in layout_stage/nearest8_v2/report.html; its immutable
manifest records why it supersedes the earlier equal-box stage requirement.

Current analysis uses --circle-max-spacing-cm 8, as shown in the reproduction
command. This restricts circular eight-rotor optimization to nearest spacing
0–8 cm; square/quad search stays 0–10 cm. It changes only postprocessing
eligibility. Old wider Circle tests,
wide quad benchmarks, unqualified measurements and historical geometry input
declarations remain visible; no CFD input or computed result is changed.
