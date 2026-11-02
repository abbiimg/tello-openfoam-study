# Final CPU scientific review

All **84 selected CPU experiments** are complete and the current final analysis uses the exact approved list, SHA256 `1b08141dc0929fd0adfaadbca62d97c611af8d7bb9f39d6137a1aa4cddf2c98d`. It has **zero selected skips**, `preliminary=false`, roles 22 screening/60 validation/2 sensitivity, and 48 validation optimizer-qualified records. The 99-case numerical audit has no errors; 15 unrun prepared inputs are separately deferred and no excluded case has terminal evidence. Every one of the 84 case rows is identical to the independently reviewed pre-final 84-row snapshot; current final statistics SHA256 is `5a74dbd5c3010ec20de93f657b6918343de4588bd01de73a2295e638cf635740`. All 84 primary source/input checks pass; 52 pass the separate absolute row late-window screen. CSV force, inferred power, shaft power and drift match the reviewed JSON.

This is a completed **CPU scientific review**, not completion of the user's separate GPU dependency/build/integration request.

## Maximum lift and the best-tested region

The largest tested fine-grid mean is **Square eight-rotor, actual nearest hubs 8 cm, outer edges raised 7.5°, 1.31113810536 N**, at inferred electrical input 19.29334457 W and shaft power 10.23220640 W. Source and absolute temporal screens pass (drift −0.035598%). It is also the largest completed fine mean in both adjacent late halves. Ideal supported mass is 133.699 g; headroom against 80/87 g reference masses is 53.699/46.699 g, under the no-added-mass assumption, not a measured payload rating.

The table keeps one target cohort: fine grid, validation 0.8–1.2 s, mapped initialization and verified native serial/direct method `be7fbf20…`. Each row passes primary source/input checks; the last column is a distinct absolute temporal screen.

| Layout | Nearest cm | Tilt | Vertical lift N | Inferred electrical W | Half-window drift | Row screen |
|---|---:|---|---:|---:|---:|---|
| Square | 8 | 7.5° raised | 1.31113811 | 19.293345 | -0.035598% | pass |
| Square | 8 | 10.0° raised | 1.31068246 | 19.293906 | -0.056835% | pass |
| Square | 8 | 12.5° raised | 1.30989025 | 19.294014 | -0.071561% | pass |
| Square | 7.5 | 12.5° raised | 1.30970628 | 19.291369 | +0.033145% | pass |
| Square | 8 | 5.0° raised | 1.30846932 | 19.292756 | -0.042551% | pass |
| Circle | 8 | 10.0° raised | 1.30817837 | 19.298474 | -0.176354% | pass |
| Square | 8.5 | 5.0° raised | 1.30807402 | 19.294934 | -0.081973% | pass |
| Circle | 8 | 12.5° raised | 1.30802492 | 19.296227 | -0.253235% | FAIL |

Maximum lift remains primary. Square 7.5° beats Square 10° by only **0.03476%**. Medium preferred 10°, while fine prefers 7.5°. Square 5° and 8.5 cm/5° are qualified but lower; they close the planned checks without moving the raw maximum. The evidence supports a **best-tested region near 8 cm and raised 7.5–12.5°**, with the quoted 7.5° raw maximum, rather than a uniquely resolved continuous angle or hardware optimum.

Square 7.5° exceeds the best Circle 10° primary mean by **0.22625%**. At the common fixed 10° probe, the Square/Circle mean gap is **0.19142%**. These small model differences do not establish inherent layout superiority: medium-to-fine changes, finite-window drift and upstream histories remain material. In particular, Square seeds came from legacy coarse MPI2/direct-off screens while Circle seeds came from serial/direct-on coarse runs; equal target signatures and settling intervals do not erase that difference.

Circle 10° is only **0.01173%** above Circle 12.5° in the primary mean. Circle 12.5° wins the first late half, while 10° wins the primary/last half. Its fine drift is **−0.2532351548%**, beyond the absolute 0.25% limit by 0.003235155 percentage points. It must remain **FAIL**, even if a short display rounds it to −0.25%. The medium 12.5° drift −0.274139% also fails. No extra extension or matrix is proposed.

## Paired tilt gains at identical hubs

The following gains are independently recomputed from cached actual primary and adjacent-half means. Protocol, hubs, source, input law, grid, role and averaging window are held for each pair; only tilt changes. Source qualification, paired input, both absolute row drifts and gain-change checks are separate.

| Layout | Tilt | Gain vs same-hub flat | First half | Last half | Full pair screen |
|---|---|---:|---:|---:|---|
| Circle | 12.5° raised | +1.24504% | +1.36711% | +1.12295% | FAIL |
| Circle | 10° raised | +1.25692% | +1.34009% | +1.17374% | pass |
| Square | 12.5° raised | +1.12933% | +1.18115% | +1.07752% | pass |
| Square | 10° raised | +1.19049% | +1.23489% | +1.14610% | pass |
| Square | 7.5° raised | +1.22567% | +1.25933% | +1.19201% | pass |
| Square | 5° raised | +1.01963% | +1.05674% | +0.98253% | pass |

Fine Square 5–12.5° gains retain positive signs and pass the finite-window pair screen; the largest same-hub gain is +1.22567% at 7.5°. Circle 10° has +1.25692% and passes. Circle 12.5° has +1.24504%: paired input passes and gain change −0.244161pp is within the 0.25pp gain criterion, **but its absolute row drift fails, so the full pair fails**. Passing one component cannot override another. These are positive gains in this interacting actuator CFD model, not proof of mesh independence, stationarity, synchronized-blade physics or real motor/propeller gain.

The gains decrease with refinement: Square 10° same-hub gain drops from +1.74949% medium to +1.19049% fine; Circle 10° drops from +1.72632% to +1.25692%. Late reaverages overlap the same histories and are sensitivity diagnostics, not independent repetitions or confidence intervals.

## Compact alternatives

Square nearest 7.5 cm/raised 12.5° gives **1.30970628478 N**, **99.89080%** of the raw fine maximum, with a passing row screen. Its projected box width is **22.53023 cm**, **4.4822%** narrower and **8.7636%** lower in box area than the 8 cm/7.5° leader. It is a useful compact alternative, not a replacement for the maximum-lift result.

The force/box-width sampled frontier also contains Square 8/12.5°, 8/10° and8/7.5°. It is metric-specific and based on means: no statistical/physical dominance or interpolated optimum is implied. Circle 10° has a larger box/hull but a slightly smaller maximum span than the 7.5 cm Square alternative, so an unqualified “smaller” claim would be wrong. The8 cm leader's nominal adjacent flat-disk gap is 3.8 mm for 7.62 cm diameter; the model allowed overlaps, but phase/collision timing was never resolved.

## Layout and rotor-count controls

The updated user-primary layout comparison holds **nearest spacing 8 cm**, allows Circle to grow, and must report actual box/span/hull. Its flat and fixed 10° fine pairs pass the finite temporal pair screen; the 12.5° layout pair does not because Circle 12.5° fails absolute drift. Target method/init match does not eliminate the upstream source-history confound.

The contextual **equal 23.62 cm flat box** comparison is a different question. Circle fine gives 1.24041148083 N versus Square 1.29526248630 N, a mean difference −4.23474%. Circle primary source checks pass, but drift is **+1.204484%**; paired gain changes from −4.79677% to −3.67289% (+1.12388pp), and the fine pair fails paired-input and temporal screens. Do not present this mean as a converged isolated layout deficit. Circle nearest 6.6274 cm versus Square 8 cm and their hull/span measures also differ.

For the cleanest completed **count benchmark**, use the separate legacy cold fine matching-method pair: four 1.06736942627 N versus eight 1.29253138242 N, **+21.095035%**, with full pair screening passing. Both have 27.62 cm projected boxes; actual nearest spacing is 20 cm for the quad and 10 cm for eight rotors. The quad is a wide comparison control outside its 0–10 cm optimization range, not a fully optimized same-range quad. No fine within-range quad optimization was performed, and a Circle-versus-quad comparison also moves hub positions.

Retain the mapped fine flat count mean **+21.860003%**, but its paired screen fails: both absolute rows pass while gain changes by −0.483356pp. The count chart already marks it † and the report table exposes the failure. The old cold pair and mapped pair must not be pooled or described as equally temporally supported. Neither implies doubled lift at equal electrical budget or accounts for added motor/frame mass. Equal electrical budget is not equal shaft power: the assumed loss map assigns 0.24 W less target shaft power to eight motors than four because of additional idle losses. This is the requested electrical comparison and must not be relabelled equal-shaft.

## Interpretation and presentation checks

For standalone use, the planform PNG also needs an explicit mapped-seed caveat. Its current “Matched ... initialization and numerical method” subtitle describes target runs, while Square/Circle upstream coarse seeds used MPI2/direct-off versus serial/direct-on. The temporal/input † footer addresses a different limitation. Recommended planform-only subtitle: “Matched projected box, power, grid and target initialization/numerics”; extra footer: “Mapped targets match; Square/Circle upstream coarse-seed protocols differ (MPI2/direct-off versus serial/direct-on).” This is a display clarification only; root has been notified and the reviewer made no active edit.

The applied mass-chart correction states source qualification and marks absolute temporal failures. Keep it and the existing count pair dagger. Show Circle 12.5° drift with enough digits to preserve the narrow fail. The active numerical metrics/rankings need no change from this review. Raw source-qualified rankings may include temporally failing means; those flags must stay visible.

The report should retain the assumed electrical loss map (not a measured hover input), lack of a motor/RPM/phase model, finite actuator thickness/quadrature, laminar stress, unverified domain independence, absent body/guards/added mass, and lack of a proven global/hardware optimum. No confidence interval is available. The current final report now links the separate ongoing GPU setup/validation status. That work does not accelerate or retroactively validate these CPU 84 cases; the old Ginkgo experiment is not native-stdpar validation. GPU dependency/build/integration completion remains outside this CPU review.

For flow presentation, retain the immutable nearest8 four-panel flat/fixed 10° figure under its existing labels. Add the newly rendered **Square 8/7.5° raw-best** snapshot separately; do not substitute it into a 10° panel. The native image has dark overlay labels, so use the established common crop `[200,150,900,750]` and a clean common 0–12 m/s viridis bar/caption if making a presentation derivative. Raw PNG/geometry/source/render provenance are already in `results/final_flow_sources`. Label **instantaneous t=1.2 s, z=−4 cm, view+z**, separately from the **0.8–1.2 s mean lift**. |U| snapshots visualize velocity magnitude, not averaged flow, thrust distribution or real blades/phase. No new CFD/rendering is required for this recommendation.

The final analysis already uses the explicit root-approved 84 scope and retains every completed row/flag, with 15 deferred inputs audited separately. Final archive/source/CRC/hash packaging remains root/packager work. No fixed stage manifest should change. **No scientific blocker was found for CPU publication with these qualifications preserved.** The separate GPU dependency/build/integration task remains active and must not be finalized on CPU completion alone.
