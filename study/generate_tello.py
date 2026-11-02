"""Generate reproducible Foundation 14 Tello-sized tilted actuator cases.

All dimensions are SI except --distances (centimetres) and --angles (degrees).
Positive tilt points craft thrust up/out; negative tilt raises the outer edge.
No OpenFOAM utilities or solvers are launched by this generator.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import shutil
import subprocess
import sys


REFERENCE_POWER_W = 4.18 / (13.0 / 60.0)
LEVELS = {
    'coarse': (42, 9, 28, 21, 20),
    'medium': (56, 9, 34, 28, 26),
    'fine': (70, 11, 42, 35, 32),
}
LOSS_MODEL = dict(auxiliary_W=.5, esc_efficiency=.95, idle_W_per_motor=.10,
                  motor_conversion=.60, axial_fraction=.50)
CODE = r'''rotors {type coded;cellZone all;field U;
codeInclude
#{
#include "PstreamReduceOps.H"
#include "IOdictionary.H"
#include "DynamicList.H"
#};
codeAddSup
#{
const fvMesh& m=mesh();const vectorField& C=m.C();const scalarField& V=m.V();
const volVectorField& vel=m.lookupObject<volVectorField>("U");vectorField& S=eqn.source();
static const IOdictionary prm(IOobject("rotorParameters",m.time().constant(),m,IOobject::MUST_READ,IOobject::NO_WRITE));
static const List<vector> ctr(prm.lookup("centres")),axis(prm.lookup("normals")),radial(prm.lookup("radials"));
static const scalar sn=readScalar(prm.lookup("tiltSin")),cs=readScalar(prm.lookup("tiltCos"));
static const scalar radius=readScalar(prm.lookup("radius")),halfThickness=readScalar(prm.lookup("halfThickness"));
static const scalar radiusSqr=sqr(radius),maskHalfWidth=max(scalar(.065),radius+halfThickness);
static const scalar pe=readScalar(prm.lookup("batteryPower")),aux=readScalar(prm.lookup("auxiliaryPower")),etaEsc=readScalar(prm.lookup("etaEsc")),idle=readScalar(prm.lookup("idlePower")),etaMotor=readScalar(prm.lookup("etaMotor")),etaAxial=readScalar(prm.lookup("etaAxial"));
static const scalar shaftTarget=etaMotor*(etaEsc*(pe-aux)-ctr.size()*idle),airTarget=etaAxial*shaftTarget;
static List<labelList> ids(ctr.size());static List<scalarField> weights(ctr.size());
static scalarList volumes(ctr.size(),0.0),thrust(ctr.size(),0.0);static bool initialized=false;
if(!initialized){
 const labelListList& cp=m.cellPoints();const pointField& pts=m.points();
 forAll(ctr,r){
  DynamicList<label> selected;DynamicList<scalar> frac;
  forAll(C,i){
   if(mag(C[i].z()-ctr[r].z())>maskHalfWidth || mag(C[i].x()-ctr[r].x())>maskHalfWidth || mag(C[i].y()-ctr[r].y())>maskHalfWidth)continue;
   vector lo(great,great,great),hi(-great,-great,-great);
   forAll(cp[i],j){const point& q=pts[cp[i][j]];for(label k=0;k<3;++k){lo[k]=min(lo[k],q[k]);hi[k]=max(hi[k],q[k]);}}
   scalar fraction=0;
   for(label ix=0;ix<16;++ix)for(label iy=0;iy<16;++iy){
    const scalar x=lo.x()+(ix+.5)*(hi.x()-lo.x())/16.0-ctr[r].x(),y=lo.y()+(iy+.5)*(hi.y()-lo.y())/16.0-ctr[r].y();
    const scalar aa=x*radial[r].x()+y*radial[r].y(),bb=-x*radial[r].y()+y*radial[r].x();
    scalar zlo=lo.z()-ctr[r].z(),zhi=hi.z()-ctr[r].z();
    if(mag(sn)<1e-12){if(aa*aa+bb*bb>radiusSqr)continue;zlo=max(zlo,-halfThickness);zhi=min(zhi,halfThickness);}
    else{
     if(bb*bb>radiusSqr)continue;
     const scalar rr=sqrt(max(0.0,radiusSqr-bb*bb));
     const scalar z1=(cs*aa-rr)/sn,z2=(cs*aa+rr)/sn;
     zlo=max(zlo,max((-halfThickness-sn*aa)/cs,min(z1,z2)));
     zhi=min(zhi,min((halfThickness-sn*aa)/cs,max(z1,z2)));
    }
    fraction+=max(0.0,zhi-zlo)/(hi.z()-lo.z());
   }
   const scalar w=fraction/256.0;if(w>0){selected.append(i);frac.append(w);volumes[r]+=w*V[i];}
  }
  ids[r]=selected;weights[r]=frac;reduce(volumes[r],sumOp<scalar>());
  if(volumes[r]<=small)FatalErrorInFunction<<"Empty tilted actuator"<<exit(FatalError);
  Info<<"DISK_VOLUME "<<r<<" "<<volumes[r]<<endl;
 }
 Info<<"POWER_BUDGET battery="<<pe<<" shaft="<<shaftTarget<<" axial="<<airTarget<<endl;initialized=true;
}
static label last=-1;const bool update=(last!=m.time().timeIndex());scalar totalT=0,totalP=0;vector craftForce(vector::zero);
forAll(ctr,r){
 scalar flux=0;forAll(ids[r],j){label i=ids[r][j];flux+=-(vel[i]&axis[r])*weights[r][j]*V[i];}reduce(flux,sumOp<scalar>());
 const scalar w=flux/volumes[r];
 if(update){const scalar target=min(.50,(airTarget/ctr.size())/max(w,1.0));const scalar alpha=min(1.0,m.time().deltaTValue()/.03);if(last<0 && m.time().value()>.01)thrust[r]=target;thrust[r]+=(target-thrust[r])*alpha;}
 // fvMatrix RHS convention: positive S produces negative force on air.
 forAll(ids[r],j){label i=ids[r][j];S[i]+=thrust[r]*axis[r]*weights[r][j]*V[i]/(1.225*volumes[r]);}
 totalT+=thrust[r];craftForce+=thrust[r]*axis[r];totalP+=thrust[r]*w;
}
if(update){const scalar shaft=totalP/etaAxial,electrical=aux+(shaft/etaMotor+ctr.size()*idle)/etaEsc;Info<<"TILT "<<m.time().value()<<" "<<craftForce.z()<<" "<<totalP<<" "<<shaft<<" "<<electrical<<" "<<totalT<<" "<<craftForce.x()<<" "<<craftForce.y()<<endl;last=m.time().timeIndex();}
#};
}
'''
FV_MODELS = 'FoamFile {format ascii;class dictionary;object fvModels;}\n' + CODE
SOURCE_SHA256 = hashlib.sha256(FV_MODELS.encode('utf-8')).hexdigest()


def vectors(values):
    return '(' + ' '.join('(' + ' '.join(f'{x:.12g}' for x in v) + ')' for v in values) + ')'


def study_metadata():
    return dict(
        study='Tello-sized synchronized tilted actuator spacing refinement',
        official_sources=[
            dict(url='https://www.ryzerobotics.com/tello/specs',
                 claims=dict(approximate_mass_with_battery_and_propellers_g=80,
                             propeller_diameter_inches=3, battery_capacity_mAh=1100,
                             nominal_battery_voltage_V=3.8, maximum_flight_time_min=13)),
            dict(url='https://dl-cdn.ryzerobotics.com/downloads/Tello/20180404/Tello_User_Manual_V1.2_EN.pdf',
                 page=21, claims=dict(mass_including_propeller_guards_g=87,
                                      battery_energy_Wh=4.18, battery_capacity_mAh=1100,
                                      nominal_battery_voltage_V=3.8,
                                      maximum_flight_time_min=13,
                                      endurance_test_forward_speed_kmh=15,
                                      endurance_test_wind='windless')),
        ],
        estimated_power=dict(
            formula='rated battery energy Wh / (maximum endurance minutes / 60)',
            rated_energy_Wh=4.18, endurance_minutes=13,
            estimated_reference_battery_power_W=REFERENCE_POWER_W,
            lower_power_sensitivity_usable_energy_fraction=.8,
            lower_power_sensitivity_W=.8 * REFERENCE_POWER_W,
            status='Inference from rated energy and forward-flight endurance; not a measured hover, peak, motor or shaft power. Usable energy during the published test is unspecified.'),
        loss_model=LOSS_MODEL,
        loss_model_formula='shaft_W = motor_conversion * (esc_efficiency * (battery_W - auxiliary_W) - rotors * idle_W_per_motor); axial_W = axial_fraction * shaft_W',
        loss_model_status='Explicit assumptions retained from the earlier study; no efficiencies were fitted to Tello mass, endurance or thrust.',
        aircraft_mass_assumption=dict(mass_kg=.080,
            status='Hypothetical identical 80 g total mass for both layouts: no added motor, propeller, frame or synchronizer mass. Guarded 87 g reference is reported separately.'),
        geometry_status='Default diameter is exactly 0.0762 m, the published 3-inch size. Geometry is a finite actuator cylinder, not stock Tello blade, frame, guard or fuselage CAD; no stock Tello motor calibration.',
        geometry_model='Four square corners; eight adds the four side midpoints. d is original-to-added neighboring center spacing; square side is 2*d. All centers lie at z=0.',
        tilt_convention='Positive points craft thrust up/out and forces air down/in; negative raises outer blade edges and spreads downwash outward.',
        synchronization_assumption='Blade contact is assumed avoided by synchronization; no explicit blades or phase-resolved blade passage are modeled.',
        fluid=dict(density_kg_m3=1.225, kinematic_viscosity_m2_s=1.5e-5, flow_model='laminar incompressible transient'),
        default_geometry=dict(diameter_m=.0762, radius_m=.0381, thickness_m=.012),
        default_time_window=dict(end_s=.8, averaging_start_s=.4, averaging_stop_s=.8,
                                 averaging_duration_s=.4),
        default_mesh_levels={name: dict(inner_xy=counts[0], outer_xy_each_side=counts[1],
            below=counts[2], z_core=counts[3], above=counts[4],
            cells=(counts[0]+2*counts[1])**2*sum(counts[2:]))
            for name, counts in LEVELS.items()},
        quadrature_subcells=16, quadrature_subcells_xy=16, quadrature_subcells_per_cell=256,
        source_sha256=SOURCE_SHA256,
        averaging='Arithmetic time integration and convergence checks must use the per-case averaging_start_s and averaging_stop_s; no results are generated here.',
        limitations=['Actuator-only reaction thrust; forces on frames, guards and fuselage are not modeled.',
                     'Electrical conversion and unresolved blade-loss factors are assumed, not measured.',
                     'The actuator model resolves shared flow interaction, not synchronized blade timing.'])


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--rotors', type=int, choices=[4, 8], default=8)
    parser.add_argument('--powers', nargs='+', type=float, default=[REFERENCE_POWER_W])
    parser.add_argument('--distances', nargs='+', type=float, default=[7.5, 8, 9, 10])
    parser.add_argument('--angles', nargs='+', type=float, default=[0, -2.5, -5, -7.5, -10, -12.5])
    parser.add_argument('--level', choices=list(LEVELS), default='coarse')
    parser.add_argument('--diameter', type=float, default=.0762)
    parser.add_argument('--thickness', type=float, default=.012)
    parser.add_argument('--domain-xy', type=float, default=.36)
    parser.add_argument('--end', type=float, default=.8)
    parser.add_argument('--average-duration', type=float, default=.4)
    parser.add_argument('--tag', default='')
    parser.add_argument('--study-role', choices=['screening', 'validation', 'sensitivity'])
    return parser.parse_args()


def generate(a):
    if not all(math.isfinite(x) for x in [a.diameter, a.thickness, a.domain_xy, a.end,
                                         a.average_duration, *a.powers, *a.distances, *a.angles]):
        raise ValueError('All geometric, operating and time values must be finite')
    if a.diameter <= 0 or a.thickness <= 0 or a.domain_xy <= .168:
        raise ValueError('Positive diameter/thickness and domain halfwidth greater than .168 m required')
    if not 0 < a.average_duration < a.end:
        raise ValueError('Averaging duration must be positive and shorter than end time')
    if any(not 0 <= cm <= 10 for cm in a.distances):
        raise ValueError('Distance outside 0-10 cm')
    if any(abs(angle) > 45 for angle in a.angles):
        raise ValueError('Tilt outside -45 to 45 degrees')
    inner, reference_outer, below, core, above = LEVELS[a.level]
    outer = max(1, round(reference_outer * (a.domain_xy - .168) / (.36 - .168)))
    nx = inner + 2 * outer
    nz = below + core + above
    radius, half_thickness = a.diameter / 2, a.thickness / 2
    root = Path(a.root)
    root.mkdir(parents=True, exist_ok=True)
    template = root / ('_template_' + a.level)
    subprocess.run([sys.executable, str(Path(__file__).with_name('base_generator.py')),
                    '--root', str(template), '--scale', '.75', '--end', str(a.end)], check=True)
    (Path(__file__).parent / 'study_metadata.json').write_text(json.dumps(study_metadata(), indent=2) + '\n', encoding='utf-8')
    for power in a.powers:
        shaft = LOSS_MODEL['motor_conversion'] * (LOSS_MODEL['esc_efficiency'] * (power - LOSS_MODEL['auxiliary_W']) - a.rotors * LOSS_MODEL['idle_W_per_motor'])
        air = LOSS_MODEL['axial_fraction'] * shaft
        if air <= 0:
            raise ValueError('Insufficient battery budget')
        for cm in a.distances:
            for angle in a.angles:
                signed = ('p' if angle > 0 else 'm' if angle < 0 else 'z') + f'{round(abs(angle)*100):04d}'
                case = root / f'{a.level}{a.tag}_n{a.rotors}_e{power:g}_d{round(cm*100):04d}_a{signed}'
                if case.exists():
                    raise FileExistsError(case)
                case.mkdir()
                for name in ('0', 'constant', 'system'):
                    shutil.copytree(template / 'rotors8' / name, case / name)
                for name in ('Allrun', 'case.foam'):
                    shutil.copy2(template / 'rotors8' / name, case / name)
                d = cm / 100
                ids = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
                if a.rotors == 8:
                    ids.extend([(0, -1), (1, 0), (0, 1), (-1, 0)])
                centres = [(d*x, d*y, 0) for x, y in ids]
                radials = [(x/math.hypot(x, y), y/math.hypot(x, y), 0) for x, y in ids]
                sn, cs = math.sin(math.radians(angle)), math.cos(math.radians(angle))
                normals = [(sn*x, sn*y, cs) for x, y, _ in radials]
                extents = [(radius*math.sqrt(1-n[0]**2), radius*math.sqrt(1-n[1]**2)) for n in normals]
                projected_widths = [max(v[k]+e[k] for v, e in zip(centres, extents))-min(v[k]-e[k] for v, e in zip(centres, extents)) for k in (0, 1)]
                forcing_widths = [max(v[k]+e[k]+half_thickness*abs(n[k]) for v, e, n in zip(centres, extents, normals))-min(v[k]-e[k]-half_thickness*abs(n[k]) for v, e, n in zip(centres, extents, normals)) for k in (0, 1)]
                forcing_z = max(radius*math.sqrt(1-n[2]**2)+half_thickness*abs(n[2]) for n in normals)
                if any(width >= 2*a.domain_xy for width in forcing_widths) or forcing_z >= .36:
                    raise ValueError('Actuator support extends outside the domain')
                geom = dict(rotors=a.rotors, battery_power_W=power, distance_cm=cm,
                    tilt_deg=angle, level=a.level, tag=a.tag, diameter_m=a.diameter,
                    radius_m=radius, thickness_m=a.thickness, half_thickness_m=half_thickness,
                    centers=centres, normals=normals, radials=radials,
                    footprint_side_m=max(projected_widths), projected_footprint_m=max(projected_widths),
                    footprint_m=max(projected_widths), projected_footprint_xy_m=projected_widths,
                    forcing_footprint_side_m=max(forcing_widths), forcing_footprint_xy_m=forcing_widths,
                    forcing_z_extent_m=[-forcing_z, forcing_z], flat_footprint_side_m=a.diameter+.02*cm,
                    geometric_volume_per_rotor_m3=math.pi*radius*radius*a.thickness,
                    sum_geometric_actuator_volumes_m3=a.rotors*math.pi*radius*radius*a.thickness,
                    mesh_cells=nx*nx*nz, mesh_cells_xyz=[nx, nx, nz],
                    mesh_inner_xy_cells=inner, mesh_outer_xy_cells_each_side=outer,
                    mesh_z_cells=[below, core, above], domain_xy_m=a.domain_xy,
                    domain_z_m=[-.6, .36], fine_core_halfwidth_m=.168, z_core_halfwidth_m=.042,
                    inner_xy_cell_width_m=.336/inner, inner_z_cell_width_m=.084/core,
                    loss_model=LOSS_MODEL, target_shaft_power_W=shaft, target_air_power_W=air,
                    quadrature_subcells=16, quadrature_subcells_xy=16, quadrature_subcells_per_cell=256,
                    source_sha256=SOURCE_SHA256, averaging_duration_s=a.average_duration,
                    averaging_start_s=a.end-a.average_duration, averaging_stop_s=a.end,
                    study_role=(a.study_role or ('validation' if a.level != 'coarse' or 'validation' in a.tag else 'screening')),
                    configured_end_time_s=a.end,
                    aircraft_mass_assumption_kg=.080, aircraft_weight_reference_N=.080*9.80665,
                    no_added_mass_assumption=True)
                (case / 'geometry.json').write_text(json.dumps(geom, indent=2) + '\n', encoding='utf-8')
                b = a.domain_xy / .2
                zgrade = f'((2.79 {below} .15) (.42 {core} 1) (1.59 {above} 5))'
                grading = f'((({b-.84:.12g} {outer} .25) (1.68 {inner} 1) ({b-.84:.12g} {outer} 4)) (({b-.84:.12g} {outer} .25) (1.68 {inner} 1) ({b-.84:.12g} {outer} 4)) {zgrade})'
                (case / 'system/blockMeshDict').write_text('FoamFile {format ascii;class dictionary;object blockMeshDict;}\n' + f'''convertToMeters .2;
vertices (({-b} {-b} -3) ({b} {-b} -3) ({b} {b} -3) ({-b} {b} -3) ({-b} {-b} 1.8) ({b} {-b} 1.8) ({b} {b} 1.8) ({-b} {b} 1.8));
blocks (hex (0 1 2 3 4 5 6 7) ({nx} {nx} {nz}) simpleGrading {grading});
edges (); boundary (farfield {{type patch;faces ((0 3 2 1) (4 5 6 7) (0 1 5 4) (1 2 6 5) (2 3 7 6) (3 0 4 7));}});
''', encoding='utf-8')
                (case / 'constant/fvModels').write_text(FV_MODELS, encoding='utf-8', newline='\n')
                parameters = ('FoamFile {format ascii;class dictionary;object rotorParameters;}\n'
                              'centres ' + vectors(centres) + ';\nnormals ' + vectors(normals) +
                              ';\nradials ' + vectors(radials) + ';\n')
                parameters += f'radius {radius:.12g};halfThickness {half_thickness:.12g};tiltSin {sn:.12g};tiltCos {cs:.12g};batteryPower {power:.15g};auxiliaryPower .5;etaEsc .95;idlePower .10;etaMotor .60;etaAxial .50;\n'
                (case / 'constant/rotorParameters').write_text(parameters, encoding='utf-8')
                control = case / 'system/controlDict'
                control.write_text(control.read_text().replace('deltaT .001;', 'deltaT .0001;').replace('maxDeltaT .004;', 'maxDeltaT .0008;').replace('writeInterval .25;', 'writeInterval .1;'), encoding='utf-8')
                print(case)


if __name__ == '__main__':
    generate(parse_args())
