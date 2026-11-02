"""Prepare ONE fresh serial/cold OpenFOAM 14 design input; never run CFD.

Examples (lengths explicitly labelled):
  python3 generate_design_case.py --root FRESH --rotors 8 --layout circular_ring \
      --projected-box-width-cm 23.62 --tilt-deg -10 --level coarse
  python3 generate_design_case.py --root FRESH --rotors 4 --layout square_perimeter \
      --projected-box-width-cm 23.62 --tilt-deg 0

Nearest-spacing mode accepts 0–10 cm. Fixed-box mode may create a wider-spaced
matched control, provided the entire finite forcing support stays in the
uniform source core. Four circular hubs canonicalize to the same square quad.
No mesh utility, mapping utility, flow solver, queue or actual study matrix is
launched or selected. Load the Foundation 14 environment for foamDictionary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

sys.dont_write_bytecode=True
from layout_geometry import (LAYOUTS, OPTIMIZER_MAX_SPACING_M, geometry,
                             for_box_width, physical_fingerprint)

SOURCE_SHA='29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
REFERENCE_POWER_W=4.18/(13/60)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command):
    result=subprocess.run([str(v) for v in command],text=True,capture_output=True,
        env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
    if result.returncode:
        raise RuntimeError('Input preparation failed (no solver was launched): '+
                           result.stdout+'\n'+result.stderr)
    return result.stdout+result.stderr


def _safe_cleanup(stage,root):
    if stage.resolve().parent!=root.resolve() or not stage.name.startswith('_design_inputs_'):
        raise ValueError('Refusing cleanup outside the task-owned fresh staging directory')
    shutil.rmtree(stage)


def _write_rotor_parameters(case,g):
    def number(value):
        return '0' if float(value)==0. else f'{float(value):.12g}'
    def vectors(values):
        return '('+' '.join('('+' '.join(number(v) for v in row)+')' for row in values)+')'
    loss=g['loss_model']
    text='FoamFile {format ascii;class dictionary;object rotorParameters;}\n'
    text+=f'centres {vectors(g["centers"])};\nnormals {vectors(g["normals"])};\nradials {vectors(g["radials"])};\n'
    text+=(f'radius {number(g["radius_m"])};halfThickness {number(g["half_thickness_m"])};'
        f'tiltSin {number(math.sin(math.radians(g["tilt_deg"])))};'
        f'tiltCos {number(math.cos(math.radians(g["tilt_deg"])))};'
        f'batteryPower {g["battery_power_W"]:.15g};'
        f'auxiliaryPower {number(loss["auxiliary_W"])};etaEsc {number(loss["esc_efficiency"])};'
        f'idlePower {number(loss["idle_W_per_motor"])};etaMotor {number(loss["motor_conversion"])};'
        f'etaAxial {number(loss["axial_fraction"])};\n')
    (case/'constant/rotorParameters').write_text(text,encoding='utf-8')


def _duplicate(root,g,ignore,desired_case):
    """Match geometry AND a verified grid/initialization/role/time/method protocol."""
    from prepare_mapped import solver_configuration
    protocol_files=('system/blockMeshDict','0/U','0/p',
                    'constant/physicalProperties','constant/momentumTransport')
    for case in root.iterdir():
        if case==ignore or not case.is_dir() or not (case/'geometry.json').is_file():
            continue
        try:
            old=json.loads((case/'geometry.json').read_text())
            same=(old.get('level')==g['level'] and old.get('initialization_family')=='cold'
                and old.get('initialization_start_time_s')==0
                and old.get('study_role')==g['study_role']
                and old.get('solver_configuration_sha256')==g['solver_configuration_sha256']
                and all(math.isclose(float(old[k]),float(g[k]),rel_tol=0,abs_tol=1e-10)
                        for k in ('averaging_start_s','averaging_stop_s'))
                and math.isclose(float(old.get('configured_end_time_s',old['averaging_stop_s'])),
                                 float(g['configured_end_time_s']),rel_tol=0,abs_tol=1e-10)
                and physical_fingerprint(old,include_operating=True)==g['design_physics_sha256'])
            if same:
                same=all(digest(case/relative)==digest(desired_case/relative) for relative in protocol_files)
            if same:
                _,verified_signature,_=solver_configuration(case)
                same=(verified_signature==old['solver_configuration_sha256']
                      and digest(case/'constant/fvModels')==g['source_sha256'])
        except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
            continue
        if same:
            return case
    return None


def generate(args):
    here=Path(__file__).resolve().parent
    root=Path(args.root).resolve()
    level='medium' if args.level=='med' else args.level
    if args.owner and os.geteuid()!=0:
        raise PermissionError('--owner requires root and applies only to the fresh case')
    if not shutil.which('foamDictionary'):
        raise RuntimeError('Load the OpenFOAM Foundation 14 environment; foamDictionary is required for cold serial preparation')
    if not re.fullmatch(r'[A-Za-z0-9_-]{0,40}',args.tag):
        raise ValueError('Tag must contain at most 40 letters, digits, underscores or hyphens')
    power=float(args.power_w)
    if not math.isfinite(power) or .95*(power-.5)-args.rotors*.1<=0:
        raise ValueError('Power is insufficient for the unchanged assumed electronics/motor losses')
    end,start=float(args.end_s),float(args.average_start_s)
    if not math.isfinite(end) or not math.isfinite(start) or not 0<=start<end:
        raise ValueError('Require a finite 0 ≤ averaging start < end time')
    if args.nearest_spacing_cm is not None:
        spacing=float(args.nearest_spacing_cm)/100
        if not math.isfinite(spacing) or not 0<=spacing<=OPTIMIZER_MAX_SPACING_M:
            raise ValueError('Optimizer nearest spacing must lie in 0–10 cm; wider matched controls require projected-box-width mode')
        shape=geometry(args.rotors,args.layout,spacing,args.tilt_deg,args.diameter_m,args.thickness_m)
        mode='nearest_spacing'
        shape.update(comparison_footprint_width_m=None,comparison_footprint_depth_m=None)
    else:
        shape=for_box_width(args.rotors,args.layout,float(args.projected_box_width_cm)/100,
                            args.tilt_deg,args.diameter_m,args.thickness_m)
        mode='projected_box_width'
    shape['comparison_box']=dict(mode='fixed_projected_box' if mode=='projected_box_width' else 'free_actual_box',
        width_m=shape['projected_footprint_width_m'],depth_m=shape['projected_footprint_depth_m'],
        fixed_control_target=mode=='projected_box_width')
    shape['input_mode']=mode
    shape['spacing_above_optimizer_limit_is_matched_control']=bool(shape['nearest_spacing_m']>OPTIMIZER_MAX_SPACING_M+1e-12)
    shape['requested_input']=dict(rotors=args.rotors,layout=args.layout,
        nearest_spacing_cm=args.nearest_spacing_cm,projected_box_width_cm=args.projected_box_width_cm,
        tilt_deg=args.tilt_deg,diameter_m=args.diameter_m,thickness_m=args.thickness_m,
        battery_power_W=power,level=level,end_s=end,averaging_start_s=start)
    shape['requested_input']['study_role']=args.study_role
    physics_seed=dict(shape,battery_power_W=power,source_sha256=SOURCE_SHA,
        loss_model=dict(auxiliary_W=.5,esc_efficiency=.95,idle_W_per_motor=.1,motor_conversion=.6,axial_fraction=.5))
    physical_id=physical_fingerprint(physics_seed,include_operating=True)
    identity=dict(physical_design=physical_id,level=level,study_role=args.study_role,end_s=format(end,'.12g'),
        average_start_s=format(start,'.12g'),initialization='cold serial; pressure direct-coarsest on')
    case_id=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    theta=float(args.tilt_deg)
    sign='m' if theta<0 else 'p' if theta>0 else 'z'
    name=(f'{level}{args.tag}_{shape["layout"]}_n{args.rotors}_e{power:g}_'
          f'd{round(shape["distance_cm"]*100):04d}_a{sign}{round(abs(theta)*100):04d}_{case_id[:12]}')
    root.mkdir(parents=True,exist_ok=True)
    target=root/name
    if target.resolve().parent!=root or target.exists() or target.is_symlink():
        raise FileExistsError('Refusing an existing/out-of-root case: '+str(target))
    claim=root/('.design-claim-'+case_id)
    with claim.open('x') as stream:
        json.dump(dict(pid=os.getpid(),case=name),stream)
    stage=root/('_design_inputs_'+uuid.uuid4().hex)
    try:
        stage.mkdir()
        tools=stage/'tools';tools.mkdir()
        for filename in ('generate_tello.py','base_generator.py'):
            shutil.copy2(here/filename,tools/filename)
        build=stage/'build'
        duration=round(end-start,12)
        generation_log=run([sys.executable,tools/'generate_tello.py','--root',build,
            '--rotors',args.rotors,'--powers',power,'--distances',8,'--angles',theta,
            '--level',level,'--diameter',args.diameter_m,'--thickness',args.thickness_m,
            '--end',end,'--average-duration',duration,'--study-role',args.study_role,'--tag','designbase'])
        cases=[p for p in build.iterdir() if p.is_dir() and (p/'geometry.json').is_file()]
        if len(cases)!=1:
            raise ValueError('Legacy generator did not produce exactly one fresh case')
        fresh=cases[0]
        if fresh.resolve().parent!=build.resolve() or not fresh.resolve().is_relative_to(stage.resolve()):
            raise ValueError('Fresh base case escaped the private staging root')
        renamed=build/name
        if renamed.exists() or renamed.is_symlink() or renamed.resolve().parent!=build.resolve():
            raise FileExistsError('Refusing a pre-existing/out-of-root fresh rename')
        fresh.rename(renamed);fresh=renamed
        g=json.loads((fresh/'geometry.json').read_text())
        if g['source_sha256']!=SOURCE_SHA or digest(fresh/'constant/fvModels')!=SOURCE_SHA:
            raise ValueError('Unchanged model C source SHA256 does not match the approved study source')
        g.update(shape)
        g.update(tag=args.tag,purpose='layout_comparison',experiment_stage='angle_spacing',
            study_role=args.study_role,design_input_schema='tello-generic-layout-input-v1',
            design_physics_sha256=physical_id,case_input_id=case_id,
            generated_base_square_parameter_cm=8.,
            input_generator='generate_design_case.py',
            input_generator_sha256=digest(Path(__file__)),
            geometry_helper_sha256=digest(here/'layout_geometry.py'),
            private_generator_sha256=digest(tools/'generate_tello.py'),
            private_base_generator_sha256=digest(tools/'base_generator.py'))
        (fresh/'geometry.json').write_text(json.dumps(g,indent=2)+'\n',encoding='utf-8')
        _write_rotor_parameters(fresh,g)
        command=[sys.executable,here/'prepare_serial_cold.py','--case',fresh]
        if args.owner:
            command+=['--owner',args.owner]
        generation_log+=run(command)
        g=json.loads((fresh/'geometry.json').read_text())
        duplicate=_duplicate(root,g,stage,fresh)
        if duplicate is not None:
            raise FileExistsError('Identical geometry and grid/initialization/role/averaging/numerical protocol already exists; reuse '+str(duplicate))
        if target.exists() or target.is_symlink() or target.resolve().parent!=root or not fresh.resolve().is_relative_to(stage.resolve()):
            raise FileExistsError('Target changed or fresh rename escaped its approved root')
        (fresh/'log.design_input_generation').write_text(generation_log,encoding='utf-8')
        fresh.rename(target)
        result=dict(case=str(target),prepared=True,no_solver_launched=True,no_mesh_utility_launched=True,
            requested_layout=args.layout,layout=g['layout'],nearest_spacing_cm=100*g['nearest_spacing_m'],
            projected_box_cm=[100*v for v in g['projected_footprint_xy_m']],
            forcing_box_cm=[100*v for v in g['forcing_footprint_xy_m']],
            uniform_core_contains_forcing=g['uniform_source_core_contains_forcing'],
            numerical_signature=g['solver_configuration_sha256'],source_sha256=g['source_sha256'])
        print(json.dumps(result,indent=2))
        return result
    finally:
        if stage.exists():
            _safe_cleanup(stage,root)
        claim.unlink(missing_ok=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',required=True)
    parser.add_argument('--rotors',type=int,choices=(4,8),required=True)
    parser.add_argument('--layout',choices=LAYOUTS,default='square_perimeter')
    group=parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--nearest-spacing-cm','--actual-nearest-spacing-cm',dest='nearest_spacing_cm',type=float)
    group.add_argument('--projected-box-width-cm','--box-width-cm',dest='projected_box_width_cm',type=float)
    parser.add_argument('--tilt-deg','--tilt',type=float,default=0.)
    parser.add_argument('--diameter-m',type=float,default=.0762)
    parser.add_argument('--thickness-m',type=float,default=.012)
    parser.add_argument('--power-w',type=float,default=REFERENCE_POWER_W)
    parser.add_argument('--level',choices=('coarse','medium','med','fine'),default='coarse')
    parser.add_argument('--end-s',type=float,default=1.2)
    parser.add_argument('--average-start-s',type=float,default=.8)
    parser.add_argument('--study-role',choices=('validation','sensitivity'),default='validation')
    parser.add_argument('--tag',default='angle_spacing')
    parser.add_argument('--owner')
    generate(parser.parse_args())
