"""Prepare a fresh generic medium/fine mapped validation design; never run CFD.

The completed COARSE source supplies the geometry and exact 0.6 s U,p. There
are deliberately no independent target spacing/angle switches: first complete
the chosen same-geometry coarse design. Output must be a separate input root,
not the live source study root or an existing case. Native CPU serial/direct
numerics, unchanged actuator C, mapped start 0.6 and average 0.8–1.2 are fixed.

Examples AFTER the named coarse source has completed and saved 0.6/U,p:
  python3 generate_mapped_design.py --source COARSE_CIRCLE --root FRESH_INPUTS \
      --level medium --tag circle_validation
  python3 generate_mapped_design.py --source COARSE_CIRCLE --root FRESH_INPUTS \
      --level fine --tag circle_validation
  python3 generate_mapped_design.py --source COARSE_SQUARE --root FRESH_INPUTS \
      --level fine --search-root EXISTING_STUDY

Existing exact mapped protocols are reported for reuse rather than copied or
restarted. Search defaults include the source study and output root. Old mapped
square controls can therefore be reused. Load Foundation14; blockMesh,
checkMesh and mapFields are the ONLY simulation utilities executed here.
Run as the non-root OpenFOAM user, or use --owner USER:GROUP when preparing as
root. No Allrun, foamRun, mpirun, queue, or actual study matrix is launched.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
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
from generate_design_case import generate as generate_cold
from layout_geometry import physical_fingerprint,geometry
from prepare_mapped import (SOURCE_SHA,INVARIANT_KEYS,CONTROLLER_POLICY,
    SUPPORTED_CELLS,digest,record,invariant_equal,solver_configuration,verify)

EXPECTED_NUMERICS='be7fbf20fcedfaed74b459ac012046232b251d3767586d9d981b729523832eb8'
PHYSICAL_FILES=('fvModels','rotorParameters','physicalProperties','momentumTransport')
SOURCE_FILES=('geometry.json','0.6/U','0.6/p')+tuple('constant/'+p for p in PHYSICAL_FILES)+tuple(
    'constant/polyMesh/'+p for p in ('points','faces','owner','neighbour','boundary'))
SHAPE_FIELDS=('layout','requested_layout','distance_parameter_definition','nearest_spacing_m',
    'requested_nearest_spacing_m','center_ring_radius_m','hub_circumradius_m','projected_footprint_width_m',
    'projected_footprint_depth_m','projected_footprint_xy_m','footprint_side_m',
    'projected_footprint_m','footprint_m','flat_footprint_side_m','flat_projected_footprint_xy_m','projected_bounds_xy_m',
    'forcing_bounds_xy_m','forcing_footprint_side_m','forcing_footprint_xy_m',
    'forcing_z_extent_m','comparison_footprint_width_m','comparison_footprint_depth_m',
    'comparison_box','input_mode','spacing_above_optimizer_limit_is_matched_control',
    'uniform_source_core_contains_forcing','uniform_source_core_xy_halfwidth_m','uniform_source_core_z_halfwidth_m',
    'physical_geometry_sha256','four_rotor_layout_equivalence','footprint_definition','max_span_m')


def snapshot(source):
    return {name:record(source/name) for name in SOURCE_FILES}


def safe_root(root,source):
    root=Path(root).resolve()
    if root==source.parent or root==source or root in source.parents or source in root.parents:
        raise ValueError('Use a separate input-generation root, outside the source case/study root')
    if any((parent/'geometry.json').exists() for parent in (root,*root.parents)):
        raise ValueError('Output root is inside an existing case; no case overwrite is allowed')
    return root


def source_shape(g):
    n=int(g['rotors']);layout=g.get('layout','square_perimeter')
    centers=g['centers']
    nearest=min(math.dist(a[:2],b[:2]) for i,a in enumerate(centers) for b in centers[i+1:])
    expected=geometry(n,layout,nearest,float(g['tilt_deg']),float(g['diameter_m']),float(g['thickness_m']))
    test=dict(expected,battery_power_W=g['battery_power_W'],loss_model=g['loss_model'],source_sha256=g['source_sha256'])
    if physical_fingerprint(test,include_operating=True)!=physical_fingerprint(g,include_operating=True):
        raise ValueError('Source is not a supported generic square/circle design with the declared tilt')
    return expected


def reusable(case,sg,source_before,level):
    """Read-only exact-protocol reuse; missing evidence is never an equivalence."""
    try:
        g=json.loads((case/'geometry.json').read_text())
        manifest=json.loads((case/'initialization.json').read_text())
        if not (g.get('level')==level and g.get('mesh_cells')==SUPPORTED_CELLS[level]
            and g.get('study_role')=='validation' and g.get('initialization_family')=='mapped'
            and g.get('initialization_method')=='mapped_coarse_fields'
            and g.get('initialization_controller_state_policy')==CONTROLLER_POLICY
            and manifest.get('status')=='mapped_ready_no_solver_run'
            and g.get('solver_configuration_sha256')==EXPECTED_NUMERICS
            and all(math.isclose(float(g[k]),value,rel_tol=0,abs_tol=1e-9) for k,value in
                (('initialization_start_time_s',.6),('initialization_source_time_s',.6),
                 ('averaging_start_s',.8),('averaging_stop_s',1.2),('configured_end_time_s',1.2)))
            and all(invariant_equal(g.get(k),sg.get(k)) for k in INVARIANT_KEYS)):
            return False
        old_source=manifest['source_case_files_before']
        if any(old_source.get(k,{}).get('sha256')!=source_before[k]['sha256']
               for k in SOURCE_FILES if k!='geometry.json'):
            return False
        if any(digest(case/'constant'/name)!=source_before['constant/'+name]['sha256'] for name in PHYSICAL_FILES):
            return False
        _,signature,direct=solver_configuration(case)
        if signature!=EXPECTED_NUMERICS or direct!=dict(p=True,pFinal=True):
            return False
        with contextlib.redirect_stdout(io.StringIO()):
            verify(case)
        if (case/'cold_preparation.json').exists():
            return False
        return True
    except (OSError,ValueError,KeyError,TypeError,subprocess.SubprocessError):
        return False


def _run(arguments,log):
    with log.open('x') as stream:
        proc=subprocess.run([str(v) for v in arguments],stdout=stream,stderr=subprocess.STDOUT,
            env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1'))
    if proc.returncode:
        raise RuntimeError('Preparation utility/helper failed; preserved scratch log '+str(log))


def prepare(args):
    here=Path(__file__).resolve().parent
    source=Path(args.source).resolve(strict=True)
    root=safe_root(args.root,source)
    level='medium' if args.level=='med' else args.level
    if args.owner and os.geteuid()!=0:
        raise PermissionError('--owner requires root and affects only the fresh target')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',args.tag):
        raise ValueError('Tag must contain 1–32 letters, digits, underscores or hyphens')
    for utility in ('foamDictionary','blockMesh','checkMesh','mapFields'):
        if not shutil.which(utility):
            raise RuntimeError('Load Foundation14; missing '+utility)
    sg=json.loads((source/'geometry.json').read_text())
    if sg.get('level')!='coarse' or sg.get('mesh_cells')!=SUPPORTED_CELLS['coarse']:
        raise ValueError('Require the exact same-geometry supported coarse source')
    status=json.loads((source/'run_status.json').read_text())
    if status.get('state')!='succeeded' or status.get('returncode')!=0 or status.get('validated') is not True:
        raise ValueError('Source must already be successfully completed and validated')
    with (source/'log.foamRun').open('rb') as stream:
        stream.seek(max(0,(source/'log.foamRun').stat().st_size-65536))
        ending=stream.read().decode(errors='replace')
    if not re.search(r'^\s*(?:\[\d+\]\s*)?End\s*$',ending,re.M):
        raise ValueError('Completed source has no terminal End marker')
    shape=source_shape(sg)
    if sg['source_sha256']!=SOURCE_SHA or digest(source/'constant/fvModels')!=SOURCE_SHA:
        raise ValueError('Require unchanged approved actuator source C')
    # Check all exact source inputs before making a root or any fresh case.
    source_before=snapshot(source)
    search_roots=list(dict.fromkeys([source.parent,root]+[Path(v).resolve() for v in args.search_root]))
    for search in search_roots:
        if not search.is_dir():
            continue
        for existing in sorted(search.iterdir()):
            if existing.is_dir() and (existing/'geometry.json').is_file() and reusable(existing,sg,source_before,level):
                if snapshot(source)!=source_before:
                    raise RuntimeError('Source changed during reuse verification')
                result=dict(case=str(existing),reused_existing_mapped_case=True,
                    prepared=False,solver_launched=False,mesh_or_mapping_launched=False,
                    source_unchanged=True,solver_configuration_sha256=EXPECTED_NUMERICS)
                print(json.dumps(result,indent=2));return result
    identity=dict(source_physics=physical_fingerprint(sg,include_operating=True),
        source_fields={k:source_before[k]['sha256'] for k in ('0.6/U','0.6/p')},
        source_mesh={k:source_before[k]['sha256'] for k in SOURCE_FILES if k.startswith('constant/polyMesh/')},
        level=level,role='validation',window=[.8,1.2],start=.6,end=1.2,
        method=EXPECTED_NUMERICS,controller_policy=CONTROLLER_POLICY)
    identifier=hashlib.sha256(json.dumps(identity,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    name=f'{level}{args.tag}_{shape["layout"]}_n{sg["rotors"]}_mapped_{identifier[:12]}'
    root.mkdir(parents=True,exist_ok=True)
    target=root/name
    if target.exists() or target.is_symlink() or target.resolve().parent!=root:
        raise FileExistsError('Refusing existing/out-of-root target; inspect/reuse '+str(target))
    claim=root/('.mapped-design-claim-'+identifier)
    with claim.open('x') as stream:
        json.dump(dict(pid=os.getpid(),target=str(target)),stream)
    stage=root/('_mapped_design_'+uuid.uuid4().hex)
    published=False
    try:
        stage.mkdir();build=stage/'build'
        # Safe generic cold generation is only a reversible precursor. It is
        # never used as a mapped manifest or passed to a solver.
        spacing=shape['nearest_spacing_m']
        box_mode=(spacing>.10 or (sg.get('comparison_footprint_width_m') is not None
                                  and sg.get('comparison_footprint_depth_m') is not None))
        width=float(sg.get('comparison_footprint_width_m') or shape['projected_footprint_width_m'])
        cold_args=argparse.Namespace(root=build,rotors=int(sg['rotors']),layout=shape['layout'],
            nearest_spacing_cm=None if box_mode else 100*spacing,
            projected_box_width_cm=100*width if box_mode else None,
            tilt_deg=float(sg['tilt_deg']),diameter_m=float(sg['diameter_m']),
            thickness_m=float(sg['thickness_m']),power_w=float(sg['battery_power_W']),
            level=level,end_s=1.2,average_start_s=.8,study_role='validation',tag=args.tag,owner=None)
        with contextlib.redirect_stdout(io.StringIO()):
            generated=generate_cold(cold_args)
        fresh=Path(generated['case'])
        if fresh.resolve().parent!=build.resolve():
            raise ValueError('Cold precursor escaped the private build root')
        renamed=build/name
        if renamed.exists() or renamed.is_symlink():
            raise FileExistsError('Fresh mapped rename already exists')
        fresh.rename(renamed);fresh=renamed
        history=fresh/'preparation_history';history.mkdir()
        cold_record=fresh/'cold_preparation.json'
        cold_record.rename(history/'cold_preparation.json')
        cold_geometry=json.loads((fresh/'geometry.json').read_text())
        (history/'cold_geometry.json').write_text(json.dumps(cold_geometry,indent=2)+'\n')
        g=dict(cold_geometry)
        for key in INVARIANT_KEYS:
            g[key]=sg[key]
        for key in SHAPE_FIELDS:
            if key in sg:
                g[key]=sg[key]
        if 'distance_parameter_definition' not in sg:
            g['distance_parameter_definition']=('Legacy square half-side d; nearest original-to-added spacing d for eight rotors, nearest hub spacing 2d for four.'
                if shape['layout']=='square_perimeter' else 'nearest horizontal rotor-center distance')
        # Remove contradictory active cold initialization/execution fields;
        # genuine mapped metadata will be created by prepare_mapped itself.
        for key in list(g):
            if key.startswith('initialization_') or key in ('execution','solver_configuration','solver_configuration_sha256','pressure_direct_solve_coarsest'):
                g.pop(key)
        g.update(mapped_design_input_schema='tello-generic-mapped-input-v1',mapped_case_input_id=identifier,
            mapped_design_generator='generate_mapped_design.py',mapped_design_generator_sha256=digest(Path(__file__)),
            design_physics_sha256=physical_fingerprint(sg,include_operating=True),
            preparation_history={name:dict(path='preparation_history/'+name,sha256=digest(history/name))
                                 for name in ('cold_preparation.json','cold_geometry.json')})
        # Canonical source order and literal rotorParameters are retained, not
        # reconstructed approximately from a rounded spacing label.
        for name in PHYSICAL_FILES:
            shutil.copyfile(source/'constant'/name,fresh/'constant'/name)
        (fresh/'geometry.json').write_text(json.dumps(g,indent=2)+'\n')
        shutil.copyfile(Path(__file__),fresh/'generate_mapped_design.py')
        _run([sys.executable,here/'prepare_mapped.py','--case',fresh,'--source',source,
              '--ranks','1','--direct-coarsest'],fresh/'log.mapped_design_preparation')
        mapped=json.loads((fresh/'geometry.json').read_text())
        if mapped['solver_configuration_sha256']!=EXPECTED_NUMERICS or (fresh/'cold_preparation.json').exists():
            raise ValueError('Mapped result has conflicting cold provenance or wrong serial/direct method')
        if any(not invariant_equal(mapped.get(k),sg.get(k)) for k in INVARIANT_KEYS):
            raise ValueError('Final mapped geometry/operating identity changed')
        if snapshot(source)!=source_before:
            raise RuntimeError('Source hashes/mtimes changed during fresh preparation')
        manifest=json.loads((fresh/'initialization.json').read_text())
        # Preserve the cold precursor and frozen wrapper in initialized reruns,
        # using the existing manifest's general relative-input copy mechanism.
        extra=('preparation_history/cold_preparation.json','preparation_history/cold_geometry.json','generate_mapped_design.py')
        for group in ('target_inputs_before_preparation','target_inputs_after_preparation'):
            manifest[group].update({p:record(fresh/p) for p in extra})
        manifest['generic_mapped_design']=dict(wrapper_sha256=digest(Path(__file__)),
            precursor_history_preserved=True,source_unchanged_verified_by_wrapper=True,
            planned_published_case=str(target),preparation_case_absolute_historical=str(fresh))
        (fresh/'initialization.json').write_text(json.dumps(manifest,indent=2)+'\n')
        with contextlib.redirect_stdout(io.StringIO()):
            verify(fresh)
        if target.exists() or target.is_symlink() or target.resolve().parent!=root:
            raise FileExistsError('Target appeared during preparation; refusing overwrite')
        fresh.rename(target)
        published=True
        if args.owner:
            subprocess.run(['chown','-R',args.owner,str(target)],check=True)
        result=dict(case=str(target),prepared=True,reused_existing_mapped_case=False,
            source=str(source),source_time_s=.6,start_s=.6,average_s=[.8,1.2],end_s=1.2,
            solver_configuration_sha256=EXPECTED_NUMERICS,source_sha256=SOURCE_SHA,
            source_unchanged=True,cold_history_archived=True,active_cold_record=False,
            mesh_mapping_utilities_only=True,solver_launched=False)
        print(json.dumps(result,indent=2));return result
    except BaseException:
        print('Failed fresh staging preserved for review: '+str(stage),file=sys.stderr)
        raise
    finally:
        claim.unlink(missing_ok=True)
        if published and stage.exists():
            if stage.resolve().parent!=root or not stage.name.startswith('_mapped_design_'):
                raise ValueError('Refusing cleanup outside task-owned mapped staging')
            shutil.rmtree(stage)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--root',required=True,type=Path)
    parser.add_argument('--level',required=True,choices=('medium','med','fine'))
    parser.add_argument('--tag',default='mapped_design')
    parser.add_argument('--search-root',action='append',default=[],type=Path)
    parser.add_argument('--owner')
    prepare(parser.parse_args())
