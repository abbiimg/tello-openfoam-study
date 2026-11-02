"""Standalone prespecified layout-stage view; never edits master analysis/cases.

Freeze inputs before consuming outcomes:
  python3 generate_layout_stage_report.py --root CASES --freeze-only
Preview pending cells (not a completed scientific stage):
  python3 generate_layout_stage_report.py --root CASES --allow-incomplete \
      --out layout_stage/preview
Final data view, after all ten master rows exist:
  python3 generate_layout_stage_report.py --root CASES
User-revised nearest-8-cm stage (eight required cases; separate manifest/output):
  python3 generate_layout_stage_report.py --root CASES --scope nearest8_v2 \
      --manifest layout_stage/stage_manifest_nearest8_v2.json --freeze-only
  python3 generate_layout_stage_report.py --root CASES --scope nearest8_v2 \
      --manifest layout_stage/stage_manifest_nearest8_v2.json
  Optional: --interpretation-text ROOT_REVIEWED_TEXT.txt

Default outputs are beside results/ in layout_stage/. The stage never filters
the master, chooses winners, runs a solver, changes scope, or fits a model.
"""
from __future__ import annotations

import argparse
import base64
import copy
import csv
from datetime import datetime,timezone
import hashlib
import html
import json
import math
import os
from pathlib import Path
import sys
import time

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
SCHEMA='tello-prespecified-layout-stage-v1'
SOURCE_C29='29df3e9ea621551c51f5576e9dfac9a17d31fb3d26e2aac0c0be118914d4fdbd'
METHOD_BE7='be7fbf20fcedfaed74b459ac012046232b251d3767586d9d981b729523832eb8'
CASE_SPECS=(
    ('square_flat_medium','mediummapped_n8_e19.2923_d0800_az0000','square8','medium',0.),
    ('square_inward_medium','mediummapped_n8_e19.2923_d0800_am1000','square8','medium',-10.),
    ('square_flat_fine','finemapped_n8_e19.2923_d0800_az0000','square8','fine',0.),
    ('square_inward_fine','finemapped_n8_e19.2923_d0800_am1000','square8','fine',-10.),
    ('circle_flat_medium','mediumcircle_flat_candidate_circular_ring_n8_mapped_f2153d152c4f','circle8','medium',0.),
    ('circle_inward_medium','mediumcircle_inward_candidate_circular_ring_n8_mapped_7d72dfd9877c','circle8','medium',-10.),
    ('circle_flat_fine','finecircle_flat_candidate_circular_ring_n8_mapped_689ac2e20f88','circle8','fine',0.),
    ('circle_inward_fine','finecircle_inward_candidate_circular_ring_n8_mapped_8846f63e5424','circle8','fine',-10.),
    ('circle_equalbox_medium','mediumcircle_equalbox_flat_circular_ring_n8_mapped_a515ece04b18','circle_equalbox','medium',0.),
    ('circle_equalbox_fine','finecircle_equalbox_flat_circular_ring_n8_mapped_8e6feb26c611','circle_equalbox','fine',0.))
INPUTS=('geometry.json','initialization.json','Allrun','prepare_mapped.py','0/U','0/p',
    'constant/fvModels','constant/rotorParameters','constant/physicalProperties','constant/momentumTransport',
    'system/blockMeshDict','system/controlDict','system/fvSchemes','system/fvSolution','system/decomposeParDict')
PRESPECIFIED=[dict(key=k,case=n,group=g,level=level,tilt_deg=angle) for k,n,g,level,angle in CASE_SPECS]
NEAREST8_PRESPECIFIED=[entry for entry in PRESPECIFIED if entry['group']!='circle_equalbox']
NEAREST8_SCHEMA='tello-prespecified-layout-stage-nearest8-v2'
V1_MANIFEST_SHA256='20a85e808bb640b9e9dd867ebd2d48c94dab6b7b7984871f2a0bef9386cceabe'

def scope_cases(args):return NEAREST8_PRESPECIFIED if args.scope=='nearest8_v2' else PRESPECIFIED
def scope_schema(args):return NEAREST8_SCHEMA if args.scope=='nearest8_v2' else SCHEMA

def now():return datetime.now(timezone.utc).isoformat()
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical_digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()).hexdigest()
def load_json(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def file_record(path):return dict(sha256=digest(path),size_bytes=path.stat().st_size,mtime_ns=path.stat().st_mtime_ns)

def guard_artifact_location(directory,root,master_parent):
    directory=Path(directory).resolve();root=Path(root).resolve();master_parent=Path(master_parent).resolve()
    if directory==root or root in directory.parents or directory==master_parent or master_parent in directory.parents:
        raise ValueError('Stage artifacts may not be written in the CFD case tree or master results')
    if any((parent/'geometry.json').is_file() for parent in (directory,*directory.parents)):
        raise ValueError('Stage artifacts may not be written inside an existing case')

def geometry_metadata(case,g,audit):
    from analysis_helpers import projected_footprint,read_initialization
    from geometry_metrics import swept_disk_envelope_metrics
    from collect_numerics import case_numerics
    width,depth=projected_footprint(g,int(g['rotors']),float(g['radius_m']),float(g['tilt_deg']))
    centers=g['centers']
    nearest=min(math.dist(a[:2],b[:2]) for i,a in enumerate(centers) for b in centers[i+1:])
    keys=('rotors','diameter_m','radius_m','thickness_m','battery_power_W','tilt_deg','level','mesh_cells',
        'loss_model','domain_xy_m','domain_z_m','quadrature_subcells_xy','source_sha256','study_role',
        'averaging_start_s','averaging_stop_s','configured_end_time_s','centers','normals','radials')
    result={key:g.get(key) for key in keys}
    result.update(layout=g.get('layout','square_perimeter'),nearest_spacing_cm=100*nearest,
        projected_width_m=width,projected_depth_m=depth,projected_box_area_m2=width*depth,
        **swept_disk_envelope_metrics(g['centers'],g['normals'],g['radius_m']))
    result.update(read_initialization(case,g)['row'])
    result.update(case_numerics(case,g,audit))
    result['declared_method_sha256']=g.get('solver_configuration_sha256')
    result['declared_configuration_digest_consistent']=(canonical_digest(g.get('solver_configuration',{}))==g.get('solver_configuration_sha256'))
    return result

def upstream_metadata(root,target,manifest,audit):
    from collect_numerics import case_numerics
    name=manifest.get('source_case_logical') or Path(manifest['source_case']).name
    if not isinstance(name,str) or Path(name).name!=name or '/' in name or '\\' in name:
        raise ValueError('Invalid upstream coarse case name')
    source=root/name;g=load_json(source/'geometry.json')
    numerics=case_numerics(source,g,audit)
    recorded=manifest.get('source_case_files_before',{}).get('geometry.json',{}).get('sha256')
    return dict(source_case=name,source_time_s=float(manifest['source_time_directory']),
        geometry_sha256=digest(source/'geometry.json'),historical_geometry_sha256=recorded,
        historical_geometry_hash_matches_current=recorded==digest(source/'geometry.json'),
        source_field_hashes={key:value.get('sha256') for key,value in manifest.get('source_case_files_before',{}).items() if key in ('0.6/U','0.6/p')},
        initial_fields_rehashed_by_this_report=False,level=g.get('level'),mesh_cells=g.get('mesh_cells'),
        source_sha256=g.get('source_sha256'),
        numerical_method_signature=numerics.get('numerical_method_signature'),
        numerical_audit_valid=numerics.get('numerical_audit_valid'),
        numerical_audit_status=numerics.get('numerical_audit_status'),
        rank_count=numerics.get('numerical_rank_count'),
        pressure_direct_coarsest=numerics.get('numerical_direct_coarsest_p'))


def validate_prespecified_geometry(spec,g):
    expected_layout='square_perimeter' if spec['group']=='square8' else 'circular_ring'
    expected_nearest=6.627416997969514 if spec['group']=='circle_equalbox' else 8.
    numeric=dict(rotors=8,diameter_m=.0762,thickness_m=.012,battery_power_W=4.18/(13/60),
        tilt_deg=spec['tilt_deg'],nearest_spacing_cm=expected_nearest,
        averaging_start_s=.8,averaging_stop_s=1.2,configured_end_time_s=1.2,
        initialization_start_time_s=.6,initialization_source_time_s=.6)
    if any(g.get(key) is None or not math.isclose(float(g[key]),value,rel_tol=0,abs_tol=1e-8) for key,value in numeric.items()):
        raise ValueError('Frozen geometry/operating protocol differs from prespecification: '+spec['case'])
    if (g['layout']!=expected_layout or g['level']!=spec['level'] or g['study_role']!='validation'
        or g['initialization_method']!='mapped_coarse_fields' or g['source_sha256']!=SOURCE_C29):
        raise ValueError('Frozen layout/role/initialization/source differs: '+spec['case'])
    if spec['group']=='circle_equalbox' and any(abs(g[key]-.2362)>1e-10 for key in ('projected_width_m','projected_depth_m')):
        raise ValueError('Equal-box baseline is not 23.62 cm square')

def freeze_manifest(args):
    from collect_numerics import load_audit
    root=Path(args.root).resolve();path=Path(args.manifest)
    guard_artifact_location(path.parent,root,args.master.parent)
    prescribed=scope_cases(args);schema=scope_schema(args)
    if path.exists():
        existing=load_json(path)
        if existing.get('schema')!=schema or existing.get('prespecified_cases')!=prescribed:
            raise ValueError('Existing stage manifest differs; never overwrite or select another scope')
        return existing
    audit=load_audit(args.numerics)
    entries=[]
    for spec in prescribed:
        case=root/spec['case']
        if case.resolve().parent!=root or case.is_symlink():raise ValueError('Escaping/aliased case')
        g=load_json(case/'geometry.json');initialization=load_json(case/'initialization.json')
        records={relative:file_record(case/relative) for relative in INPUTS}
        if records['constant/fvModels']['sha256']!=SOURCE_C29:raise ValueError('Unexpected source C hash')
        metadata=geometry_metadata(case,g,audit)
        validate_prespecified_geometry(spec,metadata)
        if metadata['declared_method_sha256']!=METHOD_BE7 or not metadata['declared_configuration_digest_consistent']:
            raise ValueError('Unexpected target numerical configuration')
        entries.append(dict(**spec,input_files=records,geometry=metadata,
            upstream=upstream_metadata(root,case,initialization,audit)))
    manifest=dict(schema=schema,frozen_utc=now(),prespecified_cases=prescribed,
        prespecified_case_ids_sha256=canonical_digest(prescribed),required_case_count=len(prescribed),
        root_absolute_at_freeze=str(root),input_cases=entries,
        questions=[dict(id='equal_box_flat',definition='Flat, 23.62×23.62 cm projected box, Square8 versus Circle6.62741699797, medium and fine'),
            dict(id='equal_nearest_spacing',definition='Nearest hubs 8 cm, Square8 versus Circle8, flat and inward10, medium and fine; actual box/span/hull differ')],
        no_outcome_file_read_by_freeze=True,no_case_chosen_by_outcome=True,
        generator_sha256_at_freeze=digest(Path(__file__)),
        numerical_audit_path=str(Path(args.numerics).resolve()) if args.numerics else None,
        numerical_audit_sha256_at_freeze=digest(Path(args.numerics)) if args.numerics else None,
        master_remains_complete=True,stage_is_not_a_master_case_filter=True,
        interpretation_policy='No automated winner declaration; optional root-reviewed interpretation text is separate.',
        scope_limit='Flat plus one fixed inward10 probe; no narrow angle optimization or global optimum claim.')
    if args.scope=='nearest8_v2':
        prior=HERE/'layout_stage/stage_manifest.json'
        if digest(prior)!=V1_MANIFEST_SHA256:raise ValueError('Historical ten-case manifest changed')
        manifest.update(scope='nearest8_v2',supersedes_primary_comparison_constraint_only=True,
            previous_ten_case_manifest_path=str(prior),previous_ten_case_manifest_sha256=V1_MANIFEST_SHA256,
            excluded_equalbox_reference_cases=[entry for entry in PRESPECIFIED if entry['group']=='circle_equalbox'],
            rationale='Explicit user constraint change: compare Square and Circle at nearest hub spacing 8 cm; Circle may grow as large as needed. Equal projected box is no longer the primary layout constraint. This scope change is user-driven, not selected by outcomes.',
            timing_statement='Frozen at the recorded UTC after the user clarification and before Circle fine-grid outcomes were known, as directed by root. Prior Square and Circle medium results were already available; this is not blind whole-study preregistration.',
            optimization_scope='For later Circle design optimization, requested maximum nearest-center spacing is 8 cm. Older 8.659/10 cm explorations remain in master but are outside this updated limit; master rankings are not edited here.',
            questions=[dict(id='equal_nearest_spacing',definition='Eight rotors, nearest hub spacing 8 cm, Square versus Circle, flat and outer edges raised 10 degrees, medium/fine. Circle may be larger; no equal-width goal.'),
                       dict(id='fixed_hub_tilt',definition='Within each layout/grid, raised10 versus flat at unchanged hubs; same actual nearest spacing 8 cm.')])
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return manifest


def input_integrity(root,entry):
    changed,mtime_changed,missing=[],[],[]
    for name,expected in entry['input_files'].items():
        path=root/entry['case']/name
        try:
            current=file_record(path)
        except OSError:
            missing.append(name);continue
        if current['sha256']!=expected['sha256'] or current['size_bytes']!=expected['size_bytes']:
            changed.append(name)
        if current['mtime_ns']!=expected['mtime_ns']:mtime_changed.append(name)
    return dict(frozen_input_bytes_match=not changed and not missing,
        frozen_input_mtimes_match=not mtime_changed and not missing,
        changed_input_files=changed,mtime_changed_input_files=mtime_changed,missing_input_files=missing)


def close(a,b,tol=1e-9):
    return a is not None and b is not None and math.isclose(float(a),float(b),rel_tol=0,abs_tol=tol)


def row_metadata_issues(row,entry,integrity):
    if row is None:return []
    g=entry['geometry'];issues=[]
    expected=dict(rotors=8,diameter_m=.0762,thickness_m=.012,battery_power_W=4.18/(13/60),
        tilt_deg=entry['tilt_deg'],mesh_cells=g['mesh_cells'],start_s=.8,stop_s=1.2,
        initialization_start_time_s=.6,initialization_source_time_s=.6)
    for key,value in expected.items():
        if not close(row.get(key),value):issues.append('Mismatch: '+key)
    for key,value in (('level',entry['level']),('layout',g['layout']),('study_role','validation'),
        ('initialization_method','mapped_coarse_fields'),('physical_source_sha256',SOURCE_C29),
        ('numerical_method_signature',METHOD_BE7),
        ('initialization_controller_state_policy',g['initialization_controller_state_policy'])):
        if row.get(key)!=value:issues.append('Mismatch: '+key)
    for key in ('loss_model','domain_xy_m','domain_z_m','quadrature_subcells_xy'):
        if row.get(key)!=g.get(key):issues.append('Mismatch: '+key)
    for key in ('numerical_audit_valid','role_window_consistent','initialization_provenance_consistent','layout_geometry_metadata_consistent'):
        if row.get(key) is not True:issues.append('Not verified: '+key)
    for key in ('nearest_spacing_cm','projected_width_m','projected_depth_m'):
        if not close(row.get(key),g.get(key),1e-8):issues.append('Geometry differs from frozen inputs: '+key)
    if not integrity['frozen_input_bytes_match']:issues.append('Frozen input hash mismatch/missing')
    return issues


def build_rows(master,manifest,root):
    by_name={}
    for row in master.get('cases',[]):
        if row['case'] in by_name:raise ValueError('Duplicate master case row: '+row['case'])
        by_name[row['case']]=row
    skipped={Path(item['case']).name:item.get('reason') for item in master.get('skipped_cases',[])}
    rows=[]
    for entry in manifest['input_cases']:
        row=copy.deepcopy(by_name.get(entry['case']))
        integrity=input_integrity(root,entry);issues=row_metadata_issues(row,entry,integrity)
        g=entry['geometry'];upstream=entry['upstream']
        value=dict(key=entry['key'],case=entry['case'],group=entry['group'],level=entry['level'],
            tilt_deg=entry['tilt_deg'],angle_label='Flat' if entry['tilt_deg']==0 else 'Outer edges raised 10°',
            layout=g['layout'],stage_status='completed_master_row' if row is not None else 'pending_or_unavailable_in_master',
            source_master_row_sha256=canonical_digest(row) if row is not None else None,
            master_unavailable_reason=skipped.get(entry['case']) if row is None else None,
            metadata_checks_passed=not issues if row is not None else None,metadata_issues=issues,
            nearest_spacing_cm=g['nearest_spacing_cm'],box_width_cm=100*g['projected_width_m'],
            box_depth_cm=100*g['projected_depth_m'],projected_max_span_cm=100*g['projected_max_span_m'],
            projected_convex_hull_area_cm2=1e4*g['projected_convex_hull_area_m2'],
            hub_center_max_span_cm=100*max(math.dist(a[:2],b[:2]) for i,a in enumerate(g['centers']) for b in g['centers'][i+1:]),
            geometry_metric_method=g.get('projected_geometry_metric_method'),
            geometry_metric_reliable=g.get('projected_geometry_metric_reliable'),
            geometry_angular_samples_per_disk=g.get('projected_geometry_angular_samples_per_disk'),
            geometry_span_bound_width_m=g.get('projected_max_span_bound_width_m'),
            geometry_hull_area_bound_width_m2=g.get('projected_convex_hull_area_bound_width_m2'),
            diameter_cm=100*g['diameter_m'],thickness_mm=1000*g['thickness_m'],
            battery_budget_W=g['battery_power_W'],role=g['study_role'],start_s=.8,stop_s=1.2,
            upstream_case=upstream['source_case'],upstream_method_sha256=upstream['numerical_method_signature'],
            upstream_method_verified=upstream['numerical_audit_valid'],upstream_MPI_ranks=upstream['rank_count'],
            upstream_pressure_direct_coarsest=upstream['pressure_direct_coarsest'],
            upstream_geometry_hash_matches_historical=upstream['historical_geometry_hash_matches_current'],
            **integrity)
        for key in ('mean_lift_N','mean_equivalent_battery_input_W','mean_shaft_power_W','mean_air_power_W',
            'supported_mass_g','power_error_percent','qualified_for_comparison','power_within_0_5_percent',
            'loss_diagnostic_consistent','force_projection_diagnostic_consistent','actuator_volume_check_passed',
            'half_window_drift_percent','late_power_agreement_passed','late_window_stability_screen_passed',
            'numerical_method_signature','numerical_audit_valid'):
            value[key]=row.get(key) if row is not None else None
        value['source_master_row']=row
        rows.append(value)
    return rows


def pair_definitions():
    pairs=[]
    for level in ('medium','fine'):
        pairs.append(dict(question='equal_box_flat',kind='layout',level=level,angle='Flat',
            left='square_flat_'+level,right='circle_equalbox_'+level,
            description='Circle − Square at the same 23.62 cm box'))
        for angle in ('flat','inward'):
            pairs.append(dict(question='equal_nearest_spacing',kind='layout',level=level,
                angle='Flat' if angle=='flat' else 'Outer edges raised 10°',
                left='square_'+angle+'_'+level,right='circle_'+angle+'_'+level,
                description='Circle − Square at nearest hubs 8 cm; footprint differs'))
        for layout in ('square','circle'):
            pairs.append(dict(question='equal_nearest_spacing',kind='fixed_hub_tilt',level=level,
                angle='Outer edges raised 10° versus flat',left=layout+'_flat_'+level,
                right=layout+'_inward_'+level,description=layout.title()+' inward10 − flat at unchanged hubs'))
    return pairs


def paired_diagnostics(master,rows,manifest_entries):
    """Reuse stored master pairs, or the master cached window metrics only."""
    by_key={row['key']:row for row in rows};output=[]
    geometry_by_key={entry['key']:entry['geometry'] for entry in manifest_entries}
    for spec in pair_definitions():
        if spec['left'] not in by_key or spec['right'] not in by_key:continue
        left,right=by_key[spec['left']],by_key[spec['right']]
        available=all(row['source_master_row'] is not None for row in (left,right))
        p=dict(**spec,left_case=left['case'],right_case=right['case'],both_completed=available,
            comparison_metadata_checks_passed=bool(available and left['metadata_checks_passed'] and right['metadata_checks_passed']),
            left_lift_N=left['mean_lift_N'],right_lift_N=right['mean_lift_N'],primary_gain_percent=None,
            left_box_width_cm=left['box_width_cm'],right_box_width_cm=right['box_width_cm'],
            left_span_cm=left['projected_max_span_cm'],right_span_cm=right['projected_max_span_cm'],
            left_hull_area_cm2=left['projected_convex_hull_area_cm2'],right_hull_area_cm2=right['projected_convex_hull_area_cm2'],
            left_upstream_case=left['upstream_case'],right_upstream_case=right['upstream_case'])
        verified=all(r['upstream_method_verified'] and r['upstream_method_sha256'] for r in (left,right))
        same_upstream=bool(verified and left['upstream_method_sha256']==right['upstream_method_sha256'])
        p['upstream_initialization_profile_status']='same_verified_profile' if same_upstream else 'different_verified_profiles' if verified else 'unresolved_profile'
        p['upstream_initialization_confound_or_uncertainty']=not same_upstream
        p['isolated_layout_effect_claim']=False
        if available and left['mean_lift_N']:
            p['primary_gain_percent']=100*(right['mean_lift_N']/left['mean_lift_N']-1)
        stored=None;origin=None
        for collection,lkey,rkey in (('matched_planform_comparisons','square_case','circle_case'),
                                     ('same_hub_tilt_comparisons','flat_case','candidate_case')):
            stored=next((r for r in master.get(collection,[]) if r.get(lkey)==left['case'] and r.get(rkey)==right['case']),None)
            if stored is not None:origin='master.'+collection;break
        if stored is None and available:
            from analyze_refinement import annotate_matched_pair_stability
            temporary=dict(matched_planform_comparisons=[dict(square_case=left['case'],circle_case=right['case'])])
            try:
                annotate_matched_pair_stability(temporary,master['cases'],master['late_window_diagnostics'],
                    master['late_window_stability_diagnostics']['lift_drift_tolerance_percent'])
                stored=temporary['matched_planform_comparisons'][0]
                origin='Derived with existing master pair helper from cached master primary/half-window row metrics; no histories rerun'
            except (KeyError,TypeError,ValueError,ZeroDivisionError):
                stored=None
        p['diagnostics_origin']=origin or 'Unavailable until both cases and cached diagnostics exist'
        p['diagnostics_available']=stored is not None
        p['master_pair_record']=copy.deepcopy(stored)
        for key in ('source_qualified_all_three_intervals','first_late_half_gain_percent','last_late_half_gain_percent',
            'gain_half_change_percentage_points','paired_power_agreement_passed','maximum_paired_input_difference_percent_of_budget',
            'both_lift_drift_screens_passed','gain_stable_within_tolerance','temporal_screen_passed',
            'left_half_window_drift_percent','right_half_window_drift_percent'):
            p[key]=stored.get(key) if stored is not None else None
        if spec['question']=='equal_box_flat':
            p['fixed_geometry_control_check']=all(close(r[k],23.62,1e-8) for r in (left,right) for k in ('box_width_cm','box_depth_cm'))
        else:
            p['fixed_geometry_control_check']=all(close(r['nearest_spacing_cm'],8.,1e-8) for r in (left,right))
        if available:
            from analysis_helpers import initialization_key,centers_only_hash
            a,b=left['source_master_row'],right['source_master_row']
            held=('rotors','diameter_m','thickness_m','battery_power_W','level','mesh_cells','study_role',
                  'loss_model','domain_xy_m','domain_z_m','quadrature_subcells_xy','physical_source_sha256',
                  'start_s','stop_s','numerical_method_signature')
            numeric_held=('diameter_m','thickness_m','battery_power_W','start_s','stop_s')
            held_ok=all(close(a.get(k),b.get(k)) if k in numeric_held else a.get(k)==b.get(k) for k in held)
            held_ok=held_ok and initialization_key(a)==initialization_key(b)
            if spec['kind']=='layout':held_ok=held_ok and close(a.get('tilt_deg'),b.get('tilt_deg'))
            else:
                held_ok=held_ok and centers_only_hash(geometry_by_key[spec['left']]['centers'])==centers_only_hash(geometry_by_key[spec['right']]['centers'])
            p['comparison_metadata_checks_passed']=bool(p['comparison_metadata_checks_passed'] and held_ok and p['fixed_geometry_control_check'])
        output.append(p)
    return output


def csv_write(path,rows,omit=()):
    columns=list(dict.fromkeys(key for row in rows for key in row if key not in omit))
    with path.open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns or ['case'],extrasaction='ignore');writer.writeheader()
        for row in rows:
            writer.writerow({key:json.dumps(value,sort_keys=True) if isinstance(value,(dict,list)) else value
                             for key,value in row.items() if key not in omit})


def figure(path,grid,labels_x,labels_y,title,preview,geometry_note='',*,
           value_key='mean_lift_N',value_format='.5f',value_suffix='',
           colorbar_label='Time-averaged gross vertical lift [N]',legend=None):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    values=np.full((len(grid),len(grid[0])),np.nan)
    for y,line in enumerate(grid):
        for x,row in enumerate(line):
            if row[value_key] is not None:values[y,x]=row[value_key]
    available=values[np.isfinite(values)]
    fig,ax=plt.subplots(figsize=(9.5,4.8 if len(grid)==2 else 6.5),layout='constrained')
    cmap=plt.get_cmap('viridis').copy();cmap.set_bad('#e5e7eb')
    lower=float(available.min()) if len(available) else 0.
    upper=max(float(available.max()),lower+1e-6) if len(available) else 1.
    im=ax.imshow(np.ma.masked_invalid(values),cmap=cmap,interpolation='nearest',aspect='auto',vmin=lower,vmax=upper)
    for y,line in enumerate(grid):
        for x,row in enumerate(line):
            if row[value_key] is None:continue
            marker='' if row['late_window_stability_screen_passed'] is True else '†'
            if 'paired_gain_stability_screen_passed' in row and row['paired_gain_stability_screen_passed'] is not True:marker+='‡'
            color='white' if (row[value_key]-lower)/(upper-lower)<.55 else 'black'
            ax.text(x,y,format(row[value_key],value_format)+value_suffix+marker,ha='center',va='center',fontsize=15,color=color)
            if row['qualified_for_comparison'] is not True:ax.text(x-.40,y-.30,'×',color='crimson',fontsize=22,weight='bold')
            if row['metadata_checks_passed'] is not True:ax.text(x+.40,y-.30,'!',color='crimson',fontsize=16,weight='bold')
    ax.set(xticks=range(len(labels_x)),xticklabels=labels_x,yticks=range(len(labels_y)),yticklabels=labels_y)
    if len(available):fig.colorbar(im,ax=ax,label=colorbar_label,shrink=.8)
    fig.suptitle(('PRELIMINARY PREVIEW — ' if preview else '')+title+
        '\n7.62 cm actuator disks · 19.29 W modeled electrical budget · no interpolation',fontsize=12)
    ax.set_xlabel((legend or 'Gray blank = pending/unavailable; × = input/source check fails; † = row late-window screen fails/unavailable; ! = metadata issue')+
                  ('\n'+geometry_note if geometry_note else '')+
                  '\nUpstream coarse-source initialization numerics differ between layouts; values do not isolate a layout effect.',fontsize=9)
    fig.savefig(path,dpi=180,bbox_inches='tight',pad_inches=.15);plt.close(fig)


def html_table(rows,fields):
    if not rows:return '<p>Not available.</p>'
    def value(row,key,fmt):
        val=row.get(key)
        if val is None:return '—'
        if isinstance(val,(dict,list)):return html.escape(json.dumps(val,sort_keys=True))
        return html.escape(format(val,fmt) if fmt else str(val))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(label)+'</th>' for key,label,fmt in fields)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+value(row,key,fmt)+'</td>' for key,label,fmt in fields)+'</tr>' for row in rows)+'</tbody></table></div>'


def embedded(path):return '<img alt="'+html.escape(path.stem)+'" src="data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode()+'">'


def render(args):
    if not args.manifest.is_file():raise ValueError('Freeze the prespecified input manifest with --freeze-only before consuming outcomes')
    manifest=load_json(args.manifest)
    prescribed=scope_cases(args);schema=scope_schema(args);nearest8=args.scope=='nearest8_v2'
    if manifest.get('schema')!=schema or manifest.get('prespecified_cases')!=prescribed or manifest.get('prespecified_case_ids_sha256')!=canonical_digest(prescribed):
        raise ValueError('Prespecified manifest/scope mismatch; no automatic replacement')
    for entry in manifest['input_cases']:validate_prespecified_geometry(entry,entry['geometry'])
    master_raw=None
    for i in range(10):
        try:master_raw=args.master.read_bytes();master=json.loads(master_raw.decode('utf-8-sig'));break
        except OSError:
            if i==9:raise
            time.sleep(.1)
    rows=build_rows(master,manifest,Path(args.root).resolve())
    missing=[row['case'] for row in rows if row['source_master_row'] is None]
    if missing and not args.allow_incomplete:
        raise ValueError('Stage incomplete: required master rows missing; use --allow-incomplete only for a marked preview: '+', '.join(missing))
    out=args.out.resolve();master_parent=args.master.resolve().parent
    guard_artifact_location(out,args.root,master_parent)
    if (out/'layout_stage_metrics.json').is_file() and load_json(out/'layout_stage_metrics.json').get('schema')!=schema:
        raise ValueError('Output belongs to a different historical scope; choose a separate output directory')
    out.mkdir(parents=True,exist_ok=True)
    pairs=paired_diagnostics(master,rows,manifest['input_cases'])
    by_key={row['key']:row for row in rows}
    q1=[] if nearest8 else [by_key[key] for level in ('medium','fine') for key in ('square_flat_'+level,'circle_equalbox_'+level)]
    q2=[by_key[key] for level in ('medium','fine') for group in ('square','circle') for key in (group+'_flat_'+level,group+'_inward_'+level)]
    preview=bool(args.allow_incomplete or missing)
    fig1=out/'equal_box_flat.png';fig2=out/'equal_nearest_spacing.png';fig_tilt=out/'fixed_hub_tilt_gains.png'
    if not nearest8:
        sq,ci=by_key['square_flat_medium'],by_key['circle_equalbox_medium']
        note1=(f'Known geometry: Square span {sq["projected_max_span_cm"]:.3f} cm / hull {sq["projected_convex_hull_area_cm2"]:.2f} cm²; '
               f'Circle span {ci["projected_max_span_cm"]:.3f} cm / hull {ci["projected_convex_hull_area_cm2"]:.2f} cm².\n'
               'Equal projected box does not mean equal span or convex-hull area; hull area is not disk-union area.')
    notes2=[]
    for group,label in (('square','Square'),('circle','Circle')):
        a,b=by_key[group+'_flat_medium'],by_key[group+'_inward_medium']
        notes2.append(f'{label} geometry (flat → raised10): box {a["box_width_cm"]:.3f}→{b["box_width_cm"]:.3f} cm; '
            f'span {a["projected_max_span_cm"]:.3f}→{b["projected_max_span_cm"]:.3f} cm; '
            f'hull {a["projected_convex_hull_area_cm2"]:.2f}→{b["projected_convex_hull_area_cm2"]:.2f} cm².')
    if not nearest8:
        figure(fig1,[[by_key['square_flat_'+level],by_key['circle_equalbox_'+level]] for level in ('medium','fine')],
            ['Square flat\nnearest hubs 8 cm','Circle flat\nnearest hubs 6.6274 cm'],['Medium','Fine'],
            '1. Eight-rotor flat layouts at the same 23.62 × 23.62 cm projected box',preview,note1)
    figure(fig2,[[by_key[group+'_flat_'+level],by_key[group+'_inward_'+level]] for level in ('medium','fine') for group in ('square','circle')],
        ['Flat','Outer edges raised 10°'],['Square · medium','Circle · medium','Square · fine','Circle · fine'],
        ('1.' if nearest8 else '2.')+' Eight-rotor layouts at nearest hub spacing 8 cm; Circle may be larger',preview,'\n'.join(notes2))
    tilt_pairs=[p for p in pairs if p['kind']=='fixed_hub_tilt']
    if nearest8:
        gain_grid=[]
        for level in ('medium','fine'):
            line=[]
            for layout in ('square','circle'):
                p=next(p for p in tilt_pairs if p['level']==level and p['left'].startswith(layout+'_'))
                line.append(dict(primary_gain_percent=p['primary_gain_percent'],
                    late_window_stability_screen_passed=p['both_lift_drift_screens_passed'],
                    paired_gain_stability_screen_passed=p['temporal_screen_passed'],
                    qualified_for_comparison=p['source_qualified_all_three_intervals'],
                    metadata_checks_passed=p['comparison_metadata_checks_passed']))
            gain_grid.append(line)
        figure(fig_tilt,gain_grid,['Square','Circle'],['Medium','Fine'],
            '2. Eight-rotor fixed-hub tilt change at nearest hubs 8 cm',preview,
            'Derived from actual CFD primary means: 100 × (raised10 / flat − 1); unchanged hubs within each layout.\nFinite late-window screens are not confidence intervals or proof of stationarity.',
            value_key='primary_gain_percent',value_format='+.3f',value_suffix='%',
            colorbar_label='Raised10 versus flat gross vertical lift change [%]',
            legend='Gray blank = pending; × = source/input failure; † = either row late screen fails/unavailable; ‡ = pair screen fails/unavailable; ! = metadata issue')
        csv_write(out/'fixed_hub_tilt_gains.csv',tilt_pairs,('master_pair_record',))
    else:csv_write(out/'equal_box_flat.csv',q1,('source_master_row',))
    csv_write(out/'equal_nearest_spacing.csv',q2,('source_master_row',))
    csv_write(out/'layout_stage_cases.csv',rows,('source_master_row',))
    csv_write(out/'paired_diagnostics.csv',pairs,('master_pair_record',))
    interpretation=None
    if args.interpretation_text:
        interpretation=dict(path=str(args.interpretation_text.resolve()),sha256=digest(args.interpretation_text),
                            text=args.interpretation_text.read_text(encoding='utf-8-sig'))
    result=dict(schema=schema,scope=args.scope,rendered_utc=now(),preliminary_preview=preview,data_complete=not missing,
        required_case_count=len(prescribed),completed_required_case_count=len(rows)-len(missing),missing_cases=missing,
        manifest_path=str(args.manifest.resolve()),manifest_sha256=digest(args.manifest),
        master_path=str(args.master.resolve()),master_sha256=hashlib.sha256(master_raw).hexdigest(),
        master_completed_case_count=len(master.get('cases',[])),master_was_not_filtered_or_modified=True,
        prespecification_scope=(manifest.get('timing_statement') if nearest8 else 'Root supplied the ten required IDs before this generator consumed stage outcomes. Prior coarse screening and already completed Square data informed the research design; this is not a blind preregistration of the entire study.'),
        user_constraint_change_rationale=manifest.get('rationale'),
        excluded_equalbox_reference_cases=manifest.get('excluded_equalbox_reference_cases',[]),
        generator_sha256=digest(Path(__file__)),generator_sha256_at_manifest_freeze=manifest['generator_sha256_at_freeze'],
        cases=rows,pairs=pairs,interpretation=interpretation,
        result_kind='Actual completed-row metrics copied from a frozen master snapshot; geometry metadata from frozen inputs; pending values are absent, never estimated.',
        limits='No automated winner, confidence interval, stationarity, isolated layout effect or global optimum claim. Upstream coarse initialization methods differ across layout families.')
    flow_section=''
    flow_image=out/'flow_comparison.png';flow_record=out/'flow_provenance.json'
    if flow_image.is_file():
        flow=load_json(flow_record)
        expected_fine={entry['case'] for entry in prescribed if entry['level']=='fine' and entry['group'] in ('square8','circle8')}
        if (flow.get('snapshot_not_time_average') is not True or flow.get('snapshot_time_s')!=1.2
            or {panel['case'] for panel in flow.get('panels',[])}!=expected_fine
            or flow.get('assembled_image_sha256')!=digest(flow_image)):
            raise ValueError('Optional flow image scope/hash/snapshot provenance mismatch')
        result['flow_visualization']=dict(image=flow_image.name,image_sha256=digest(flow_image),
            provenance=flow_record.name,provenance_sha256=digest(flow_record),snapshot_time_s=1.2,snapshot_not_time_average=True)
        flow_section='<h2>Fine-grid instantaneous velocity snapshots</h2><p>Actual native ParaView slices at t = 1.2 s, z = −4 cm, viewed along +z, with identical camera, crop and 0–12 m/s scale. These are instantaneous CFD velocity fields, not time-averaged flow or geometry drawings. The force labels separately use the 0.8–1.2 s means. Actuator forcing does not resolve blades, phase or synchronization; upstream coarse initialization numerics differ across layouts. Native PNGs, geometry and source/copy/display hashes are delivered in flow_sources/ and flow_provenance.json.</p>'+embedded(flow_image)
    (out/'layout_stage_metrics.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    master_link=os.path.relpath(args.master.with_name('report.html').resolve(),out).replace(os.sep,'/')
    geometry_fields=[('case','Case',None),('level','Grid',None),('angle_label','Angle',None),('nearest_spacing_cm','Nearest hubs cm','.4f'),
        ('box_width_cm','Box width cm','.4f'),('box_depth_cm','Box depth cm','.4f'),('projected_max_span_cm','Maximum span cm','.4f'),
        ('hub_center_max_span_cm','Maximum hub-center span cm','.4f'),('projected_convex_hull_area_cm2','Convex-hull area cm²','.4f')]
    metric_fields=[('case','Case',None),('stage_status','Status',None),('mean_lift_N','Gross vertical lift N','.5f'),
        ('mean_equivalent_battery_input_W','Inferred electrical W','.5f'),('qualified_for_comparison','Source/input checks',None),
        ('half_window_drift_percent','Half-window lift drift %','+.3f'),('late_window_stability_screen_passed','Row late screen',None),
        ('metadata_checks_passed','Protocol metadata',None),('metadata_issues','Metadata issues',None)]
    pair_fields=[('kind','Pair type',None),('level','Grid',None),('left_case','Reference',None),('right_case','Candidate',None),
        ('primary_gain_percent','Signed change %','+.3f'),('first_late_half_gain_percent','First-half change %','+.3f'),
        ('last_late_half_gain_percent','Last-half change %','+.3f'),('gain_half_change_percentage_points','Gain change pp','+.3f'),
        ('paired_power_agreement_passed','Paired input check',None),('both_lift_drift_screens_passed','Both absolute drift checks',None),
        ('temporal_screen_passed','Pair finite-window screen',None),('comparison_metadata_checks_passed','Target protocol match',None),
        ('upstream_initialization_profile_status','Upstream coarse profiles',None),('diagnostics_origin','Diagnostics source',None)]
    upstream=[dict(case=row['case'],upstream_case=row['upstream_case'],ranks=row['upstream_MPI_ranks'],
        direct=row['upstream_pressure_direct_coarsest'],verified=row['upstream_method_verified']) for row in rows]
    review_text=('<h2>Root-reviewed interpretation</h2><p>'+html.escape(interpretation['text']).replace('\n','<br>')+'</p>' if interpretation else
        '<p>No interpretation text has been supplied. This is a stage data view for root review, with no automated winner narrative.</p>')
    banner=('<div class="banner"><strong>PRELIMINARY PREVIEW</strong> — '+str(len(missing))+' of '+str(len(prescribed))+' required master rows are missing. Gray cells are blank; no Circle result is inferred. This is not a completed layout stage.</div>'
        if preview else '<div class="banner">All '+str(len(prescribed))+' required master rows are present. Source, temporal and metadata flags remain visible; completion does not establish a scientific winner.</div>')
    if nearest8:
        historical_link=os.path.relpath(HERE/'layout_stage/preview/report.html',out).replace(os.sep,'/')
        flat_circle=by_key['circle_flat_medium']
        scope_heading='Layout stage v2: nearest hub spacing 8 cm'
        scope_intro=f'''<p><strong>Updated user constraint:</strong> Circle may grow as large as needed to use 8 cm nearest-center spacing. Equal projected width is not a goal for this primary layout decision. The new eight-case manifest excludes two equal-box references from the required set because of that explicit user instruction, not a data-driven selection. The unchanged historical ten-case manifest and its <a href="{html.escape(historical_link)}">old equal-box/nearest-spacing preview</a> remain available; completed equal-box results remain in master and do not block this stage.</p>
<p>The flat Circle at 8 cm nearest hubs has projected box width {flat_circle['box_width_cm']:.4f} cm, projected maximum disk span {flat_circle['projected_max_span_cm']:.4f} cm and maximum hub-center diameter {flat_circle['hub_center_max_span_cm']:.4f} cm. These are different geometric measures; a larger box does not imply every size measure is larger. Tables retain the actual flat/tilted size metrics.</p>
<p>The scope was frozen at {html.escape(manifest['frozen_utc'])}, before Circle fine-grid outcomes were known as directed by root. Earlier Square and Circle medium data were available, so this is not blind whole-study preregistration. Later Circle optimization respects the updated maximum nearest-center spacing of 8 cm; older 8.659/10 cm exploratory cases remain in master, outside this updated limit. This standalone view does not edit master rankings.</p>'''
        questions_html='''<h2>1. Eight-rotor layouts at 8 cm nearest hubs: flat and one raised10 probe</h2>
<p>Medium and fine grids remain separate. Circle may have a larger projected box. Within each layout, flat and tilted cases share exactly the same hub positions. This fixed tilt probe does not establish an optimized angle.</p>'''+embedded(fig2)+html_table(q2,metric_fields)+html_table(q2,geometry_fields)+html_table([p for p in pairs if p['kind']=='layout'],pair_fields)+'''
<h2>2. Fixed-hub tilt changes, separately within each layout and grid</h2>
<p>Signed changes are computed from the actual primary force means as 100 × (raised10 / flat − 1). Pending pairs stay blank. † flags either absolute row late-window screen failing or unavailable; ‡ flags the separate paired finite-window screen failing or unavailable. These checks are not uncertainty intervals or proof of stationarity.</p>'''+embedded(fig_tilt)+html_table(tilt_pairs,pair_fields)
        trace_files='equal_nearest_spacing.csv, fixed_hub_tilt_gains.csv, layout_stage_cases.csv, paired_diagnostics.csv, layout_stage_metrics.json and the two embedded scientific PNGs.'
    else:
        scope_heading='Layout stage: two prespecified questions'
        scope_intro='''<p>The frozen ten-case manifest separates equal projected box size from equal nearest hub spacing. Medium and fine grids stay separate. The original user constraint and ten-case scope are retained in this historical view.</p>
<p>Prespecification refers to this fixed ten-case stage view, supplied by root before this generator consumed outcomes. Earlier coarse screening and known Square results informed the research design; this is not a blind preregistration of the whole study.</p>'''
        questions_html='''<h2>1. Flat layouts at the same 23.62 × 23.62 cm projected box</h2>
<p>Square flat at 8 cm nearest hubs versus Circle flat at 6.627417 cm. The axis-aligned projected width/depth are held equal; maximum span and convex-hull area are not. Convex-hull area encloses the disk union and is not disk-union area.</p>'''+embedded(fig1)+html_table(q1,metric_fields)+html_table(q1,geometry_fields)+html_table([p for p in pairs if p['question']=='equal_box_flat'],pair_fields)+'''
<h2>2. Equal nearest spacing 8 cm: flat and one inward10 probe</h2>
<p>This asks a different question: both layouts use 8 cm nearest hubs, so their actual box widths, maximum spans and convex-hull areas differ. It does not supply an equal-footprint verdict. The two tilt states use the same hub positions within each layout.</p>'''+embedded(fig2)+html_table(q2,metric_fields)+html_table(q2,geometry_fields)+html_table([p for p in pairs if p['question']=='equal_nearest_spacing'],pair_fields)
        trace_files='equal_box_flat.csv, equal_nearest_spacing.csv, layout_stage_cases.csv, paired_diagnostics.csv, layout_stage_metrics.json and the embedded scientific PNGs.'
    page='''<!doctype html><html><head><meta charset="utf-8"><title>Prespecified layout-stage comparison</title>
<style>body{font:16px/1.55 system-ui,sans-serif;max-width:1250px;margin:32px auto;padding:0 20px;color:#1e293b}img{width:100%;height:auto}.banner{padding:16px;background:#fff3d5}.scroll{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border-bottom:1px solid #cbd5e1;padding:8px;text-align:left}code{overflow-wrap:anywhere}h1{line-height:1.2}</style></head><body>
<h1>'''+scope_heading+'</h1>'+banner+scope_intro+f'''
<p>This stage contains flat models and one fixed 10° inward-thrust probe (outer edges raised); narrow angle optimization comes later. It is not a master case filter: all {result['master_completed_case_count']} completed master rows remain in the <a href="{html.escape(master_link)}">master report</a>, including other completed tests, controls and unqualified measured rows.</p>
<p>7.62 cm finite actuator disks, 12 mm forcing thickness, modeled total electrical budget 19.29230769 W. Native CPU Foundation14 GAMG serial/direct profile be7 and unchanged C29 forcing are required. Electrical/shaft powers are inferred through the assumed loss map, not measured motor or battery power. Blade phase, common RPM, synchronized blade passage, stock fuselage/guards and a calibrated motor map are unresolved.</p>
'''+questions_html+flow_section+'''
<p>Flat span/hull metrics are analytic. Tilted projected-ellipse hulls use converged angular sampling with conservative geometry bounds, recorded in the frozen manifest and CSV/JSON. These geometry-discretization bounds are not CFD uncertainty estimates.</p>
<h2>Protocol and upstream initialization limitations</h2>
<p>Target comparison checks hold rotor count, D/h, electrical budget/loss law, validation role, native numerical signature, mapped initialization regime, 0.6 s start/source time, and 0.8–1.2 s primary window. Frozen input hashes and completed master geometry/metadata are checked. Input failures and measured values remain visible instead of being removed.</p>
<p><strong>Upstream coarse initialization is confounded across layout families.</strong> The Square mapped fields came from legacy coarse MPI2/direct-coarsest-off sources, while Circle sources used serial/direct-coarsest-on. These verified profile differences are retained below. Equal target methods and finite settling time do not eliminate the difference in initialization history; this report makes no isolated layout-effect claim. Unknown upstream evidence also cannot establish a match.</p>'''+html_table(upstream,[('case','Target case',None),('upstream_case','Coarse 0.6 source',None),('ranks','Source ranks',None),('direct','Source pressure direct coarsest',None),('verified','Source profile audited',None)])+'''
<p>† denotes the existing absolute row late-window lift/input screen failing or unavailable. It is distinct from paired gain stability. The row screen uses the master tolerance (normally 0.25% mean-lift half drift), independently qualified primary/half windows and inferred-input agreement. Pair flags are copied from stored master diagnostics when present; otherwise the existing master pair helper uses cached master half-window metrics, without rerunning histories. Their provenance is listed in CSV/JSON. None is a confidence interval or proof of stationarity, mesh independence, physical gain or a global optimum.</p>
<p>The unchanged assumed loss map reserves 0.5 W electronics, 95% ESC efficiency, 0.10 W idle loss per motor, 60% motor conversion and 50% axial forcing fraction: Pshaft=0.60·[0.95·(Pe−0.5)−0.10N], Pair=0.50Pshaft, shared equally among rotors. The 19.29 W reference comes from nominal 4.18 Wh divided by advertised 13 min forward-flight endurance; it is not measured hover or maximum power, and reproducing 13 min by division is not validation. No efficiency was fitted to mass.</p>'''+review_text+f'''
<h2>Traceability</h2><p>Manifest SHA256: <code>{result['manifest_sha256']}</code><br>Master snapshot SHA256: <code>{result['master_sha256']}</code><br>Rendered UTC: {result['rendered_utc']}</p>
<p>Files: {trace_files} CSV rows retain source/input, temporal, metadata and pending status; full copied master rows are retained in layout_stage_metrics.json. The immutable selected manifest is <code>{html.escape(args.manifest.name)}</code>; the original ten-case manifest is preserved. Optional final interpretation is a separately hashed root-reviewed text file, never generated from a ranking.</p></body></html>'''
    (out/'report.html').write_text(page,encoding='utf-8')
    print(json.dumps(dict(report=str(out/'report.html'),required_cases=len(prescribed),completed_required_cases=result['completed_required_case_count'],
        missing_case_count=len(missing),preliminary_preview=preview,manifest_sha256=result['manifest_sha256'],master_unchanged=True),indent=2))

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',default='/opt/openfoam-workspace/cases/tello_refinement')
    parser.add_argument('--master',type=Path,default=HERE/'results/statistics.json')
    parser.add_argument('--numerics',type=Path,default=HERE/'numerical_configurations.json')
    parser.add_argument('--scope',choices=('legacy10','nearest8_v2'),default='legacy10')
    parser.add_argument('--manifest',type=Path)
    parser.add_argument('--out',type=Path)
    parser.add_argument('--freeze-only',action='store_true')
    parser.add_argument('--allow-incomplete',action='store_true')
    parser.add_argument('--interpretation-text',type=Path)
    args=parser.parse_args()
    if args.manifest is None:args.manifest=HERE/('layout_stage/stage_manifest_nearest8_v2.json' if args.scope=='nearest8_v2' else 'layout_stage/stage_manifest.json')
    if args.out is None:args.out=HERE/('layout_stage/nearest8_v2' if args.scope=='nearest8_v2' else 'layout_stage')
    if args.freeze_only:
        manifest=freeze_manifest(args)
        print(json.dumps(dict(manifest=str(args.manifest),required_cases=manifest['required_case_count'],
            manifest_sha256=digest(args.manifest),outcomes_read=False),indent=2));return
    render(args)

if __name__=='__main__':main()
