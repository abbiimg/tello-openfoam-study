"""Actual CFD analysis for an idealized Tello-based rotor refinement.

python3 analyze_refinement.py --root CASES --out RESULTS [--metadata JSON] [--numerics AUDIT]
python3 analyze_refinement.py --root CASES --out FINAL_RESULTS --numerics AUDIT \
    --case-list FROZEN_CASE_NAMES.json --circle-max-spacing-cm 8

Optional --circle-max-spacing-cm restricts only circular eight-rotor search
winners. Omit it to preserve the historical 0–10 cm policy for all layouts.
All completed rows and qualified comparison controls remain visible.

Optional --case-list accepts ["exact_case_name", ...] or {"cases": [...]}.
It does not select by results or qualification. Include all completed tests and
controls in a final scientific scope; intentionally deferred unrun inputs can
remain excluded, with their names audited. Default recursive discovery remains
unchanged. Missing/invalid selected geometry is reported, never silently dropped.

Keep analysis_helpers.py, geometry_metrics.py, initialization_diagnostics.py and collect_numerics.py beside this file. Diameter, input power and primary
averaging windows come from each case's metadata. No thrust is fitted to mass.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import itertools
import json
import math
import hashlib
from pathlib import Path
import sys

sys.dont_write_bytecode = True
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from analysis_helpers import (DEFAULT_LOSS, G0, HISTORY_HEADER, LEVEL_ORDER, ROLE_WINDOWS,
    calculate, config_id, config_key, config_label, initialization_key, primary,
    qualified, comparison_eligible, ranking_eligible, read_history, read_initialization, numerical_key,
    optimization_range_text, validate_circle_max_spacing_cm,
    numerical_signature, same_numerics, flat_geometry_candidates, same_projected_box)
from initialization_diagnostics import compare_initializations
from collect_numerics import case_numerics, load_audit


def _unique_json_object(pairs):
    value={}
    for key,item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON object key in case list: '+str(key))
        value[key]=item
    return value


def _excluded_run_state(case,root):
    """Small read-only provenance screen; never inspect lift or qualification."""
    row=dict(case=case.relative_to(root).as_posix(),terminal_run_evidence=False)
    if not case.resolve().is_relative_to(root.resolve()):
        row['audit_note']='Excluded case escapes root; no files inspected'
        return row
    status_path=case/'run_status.json'
    try:
        if status_path.exists():
            status=json.loads(status_path.read_text(encoding='utf-8-sig'))
            row.update(run_state=status.get('state'),returncode=status.get('returncode'),
                       validated=status.get('validated'))
    except (OSError,ValueError,AttributeError) as exc:
        row['status_read_error']=str(exc)
    log=case/'log.foamRun'
    try:
        if log.is_file():
            with log.open('rb') as stream:
                stream.seek(max(0,log.stat().st_size-16384))
                tail=stream.read().decode(errors='replace')
            import re
            row['solver_End_in_log_tail']=bool(re.search(r'^\s*(?:\[\d+\]\s*)?End\s*$',tail,re.M))
    except OSError as exc:
        row['log_read_error']=str(exc)
    terminal=str(row.get('run_state','')).lower() in (
        'succeeded','failed','completed','error','cancelled','aborted','validation_failed','invalid')
    row['terminal_run_evidence']=bool(terminal or row.get('solver_End_in_log_tail',False))
    return row


def case_scope(root,selection_path=None):
    """Return geometry paths and an explicit, result-independent selection audit."""
    root=Path(root)
    discovered=sorted(root.rglob('geometry.json'))
    geometry_names=sorted({gp.parent.relative_to(root).as_posix() for gp in discovered})
    discovered_names=sorted({gp.parent.name for gp in discovered if len(gp.relative_to(root).parts)==2})
    nested_names=[name for name in geometry_names if name not in discovered_names]
    discovery_audit=dict(discovered_geometry_parent_paths=geometry_names,
        discovered_geometry_file_count=len(discovered),discovered_nested_geometry_parent_paths=nested_names,
        prepared_name_definition='Direct-child case directories with geometry.json; nested template/geometry paths are recorded separately and default recursive processing is unchanged.')
    if selection_path is None:
        return discovered,dict(mode='default_recursive_discovery',selection_path=None,
            selection_sha256=None,selected_names=geometry_names,selected_count=len(geometry_names),
            discovered_prepared_names=discovered_names,discovered_prepared_count=len(discovered_names),
            excluded_prepared_names=[],excluded_prepared_count=0,excluded_run_states=[],
            excluded_terminal_case_names=[],root_absolute=str(root.resolve()),
            **discovery_audit,
            interpretation='Default discovery unchanged; no explicit case-name filter applied.')
    path=Path(selection_path)
    raw=path.read_bytes()
    payload=json.loads(raw.decode('utf-8-sig'),object_pairs_hook=_unique_json_object)
    if isinstance(payload,dict):
        if set(payload)!={'cases'}:
            raise ValueError('Case-list object must contain only a cases list')
        payload=payload['cases']
    if not isinstance(payload,list):
        raise ValueError('Case list must be a JSON list or an object containing only cases: [names]')
    names,paths=[],[]
    resolved_root=root.resolve()
    for name in payload:
        if (not isinstance(name,str) or not name or name.strip()!=name or name in ('.','..')
                or any(c in name for c in ('/','\\','\0',':'))):
            raise ValueError('Case list requires exact single-component case names: '+repr(name))
        if name in names:
            raise ValueError('Duplicate selected case name: '+name)
        case=root/name
        gp=case/'geometry.json'
        if case.is_symlink() or gp.is_symlink():
            raise ValueError('Selected case/geometry must not alias another path: '+name)
        resolved=case.resolve()
        if (resolved.parent!=resolved_root or resolved.name!=name
                or not gp.resolve().is_relative_to(resolved_root)):
            raise ValueError('Selected case/geometry escapes root or aliases another case: '+name)
        names.append(name);paths.append(gp)
    excluded=[name for name in discovered_names if name not in set(names)]
    excluded_paths=[name for name in geometry_names if name not in set(names)]
    states=[_excluded_run_state(root/name,root) for name in excluded]
    return paths,dict(mode='explicit_exact_case_names',selection_path=str(path.resolve()),
        selection_sha256=hashlib.sha256(raw).hexdigest(),selected_names=names,selected_count=len(names),
        discovered_prepared_names=discovered_names,discovered_prepared_count=len(discovered_names),
        excluded_prepared_names=excluded,excluded_prepared_count=len(excluded),excluded_run_states=states,
        excluded_geometry_parent_paths=excluded_paths,**discovery_audit,
        excluded_terminal_case_names=[r['case'] for r in states if r['terminal_run_evidence']],
        root_absolute=str(resolved_root),
        interpretation='Explicit names only; no selection by completion, lift or qualification. Missing/invalid selected cases remain skipped. Excluded terminal tests are flagged for scope review, not silently treated as deferred/unrun.')


def level_key(row):
    return LEVEL_ORDER.get(row["level"], -1), row["mesh_cells"]


def flat_reference(row, records, control_distance):
    pool = [r for r in records if primary(r) and r['study_role']==row['study_role']
        and r['role_window_consistent'] and r['initialization_provenance_consistent']
        and r.get('layout_geometry_metadata_consistent',True)
        and r['level']==row['level'] and initialization_key(r)==initialization_key(row)
        and same_numerics(r,row) and r['loss_model']==row['loss_model']
        and r.get('physical_source_sha256')==row.get('physical_source_sha256')
        and r.get('domain_xy_m')==row.get('domain_xy_m') and r.get('domain_z_m')==row.get('domain_z_m')]
    candidates=flat_geometry_candidates(row,pool,control_distance)
    return candidates[0] if len(candidates)==1 else None


def matched_settings(a,b, same_rotors=True, same_tilt=True):
    physical_keys=('battery_power_W','diameter_m','thickness_m')
    if same_tilt:
        physical_keys+=('tilt_deg',)
    return (a['level']==b['level'] and a['mesh_cells']==b['mesh_cells']
        and (not same_rotors or a['rotors']==b['rotors'])
        and all(math.isclose(a[k],b[k],abs_tol=1e-9,rel_tol=0)
                for k in physical_keys)
        and initialization_key(a)==initialization_key(b) and same_numerics(a,b)
        and a['loss_model']==b['loss_model']
        and all(a.get(k)==b.get(k) for k in ('domain_xy_m','domain_z_m','physical_source_sha256')))


def same_hub_tilt_settings(candidate,flat):
    """Change rotor tilt with the hub multiset and full protocol held fixed."""
    hub_hash=candidate.get('rotor_centers_sha256')
    return bool(abs(candidate['tilt_deg'])>1e-8 and abs(flat['tilt_deg'])<1e-8
        and hub_hash and hub_hash==flat.get('rotor_centers_sha256')
        and matched_settings(candidate,flat,same_tilt=False)
        and candidate['study_role']==flat['study_role']
        and all(math.isclose(candidate[k],flat[k],rel_tol=0,abs_tol=1e-10)
                for k in ('start_s','stop_s'))
        and all(candidate.get(k)==flat.get(k) for k in
            ('inner_xy_cell_width_m','inner_z_cell_width_m','quadrature_subcells_xy')))


def summarize(records, control_distance=10., study_role="validation"):
    """Rank within one study role; validation is the final primary scope."""
    # A matched-footprint reference can lie outside the optimization range.
    # Never truncate this pool when applying current per-layout search limits.
    comparison_rows = [r for r in records if comparison_eligible(r, study_role)]
    eligible = [r for r in comparison_rows if ranking_eligible(r, study_role)]
    best, grid_winners, comparisons = {}, [], []
    groups = {(config_key(r), initialization_key(r), numerical_key(r)) for r in eligible}
    for key, init, method in sorted(groups, key=repr):
        rows = [r for r in eligible if config_key(r) == key
                and initialization_key(r) == init and numerical_key(r) == method]
        controls = [r for r in comparison_rows if config_key(r) == key
                and initialization_key(r) == init and numerical_key(r) == method]
        levels = sorted({r["level"] for r in rows}, key=lambda v:
            max(level_key(r) for r in rows if r["level"] == v))
        winners = [max((r for r in rows if r["level"] == level), key=lambda r: r["mean_lift_N"])
                   for level in levels]
        grid_winners.extend(winners)
        winner = winners[-1]
        finest = [r for r in rows if r["level"] == winner["level"]]
        flat = flat_reference(winner,controls,control_distance)
        coarse = winners[0]
        coarse_checked = any(r['rotor_geometry_sha256']==coarse['rotor_geometry_sha256']
            and level_key(r) > level_key(coarse)
            and initialization_key(r) == initialization_key(coarse) for r in rows)
        scope_id = config_id(key) + '_init' + hashlib.sha256(repr(init).encode()).hexdigest()[:8]
        scope_id += '_method' + (method[:12] if numerical_signature(winner) else
                                 'unknown_' + hashlib.sha256(method.encode()).hexdigest()[:8])
        method_label = method[:12] if numerical_signature(winner) else 'UNKNOWN: ' + winner['case']
        best[scope_id] = dict(configuration=config_label(key) + ' · ' + str(init[0]) +
            ' · method ' + method_label, physical_configuration=config_label(key),
            numerical_method_signature=numerical_signature(winner),
            initialization_method=winner['initialization_method'], study_role=study_role,
            best_tested=winner,
            finest_grid=winner["level"], finest_qualified_samples=len(finest),
            nominal_flat_control=flat,
            gain_vs_nominal_flat_percent=(100 * (winner["mean_lift_N"] / flat["mean_lift_N"] - 1)
                                          if flat else None),
            coarsest_grid_best=coarse,
            coarsest_maximum_needs_finer_check=not coarse_checked,
            selection_rule=f'Largest qualified tested force inside actual nearest spacing 0–{100*winner["optimization_max_nearest_spacing_m"]:g} cm for this layout; no percentage near-band overrides a resolved lift gain.',
            smaller_close_alternative_within_0_25_percent=min(
                (r for r in finest if r['mean_lift_N']>=.9975*winner['mean_lift_N']),
                key=lambda r:r['projected_box_area_m2']))
    for row in comparison_rows:
        ref = flat_reference(row,comparison_rows,control_distance)
        if ref:
            comparisons.append(dict(case=row["case"], reference_case=ref["case"],
                    rotors=row["rotors"], battery_power_W=row["battery_power_W"],
                    diameter_m=row["diameter_m"], level=row["level"],
                    study_role=study_role,
                    initialization_method=row["initialization_method"],
                    numerical_method_signature=numerical_signature(row),
                    distance_cm=row["distance_cm"], tilt_deg=row["tilt_deg"],
                    layout=row['layout'],nearest_spacing_cm=row['nearest_spacing_cm'],
                    projected_width_m=row['projected_width_m'],
                    candidate_optimization_eligible=ranking_eligible(row,study_role),
                    reference_optimization_eligible=ranking_eligible(ref,study_role),
                    lift_N=row["mean_lift_N"], reference_lift_N=ref["mean_lift_N"],
                    gain_percent=100 * (row["mean_lift_N"] / ref["mean_lift_N"] - 1),
                    projected_width_ratio=row["projected_width_m"] / ref["projected_width_m"]))
    matched = []
    for row in comparison_rows:
        if row["rotors"] == 4:
            continue
        ref = next((r for r in comparison_rows if r['rotors']==4 and matched_settings(row,r,False)
                    and same_projected_box(row,r)),None)
        if ref:
            matched.append(dict(case=row["case"], four_rotor_case=ref["case"], level=row["level"],
                study_role=study_role,
                initialization_method=row["initialization_method"],
                numerical_method_signature=numerical_signature(row),
                distance_cm=row["distance_cm"], tilt_deg=row["tilt_deg"],
                layout=row['layout'],four_rotor_layout=ref['layout'],
                outer_edge_angle_label=row['outer_edge_angle_label'],
                nearest_spacing_cm=row['nearest_spacing_cm'],four_rotor_nearest_spacing_cm=ref['nearest_spacing_cm'],
                projected_width_m=row['projected_width_m'],
                eight_rotor_optimization_eligible=ranking_eligible(row,study_role),
                four_rotor_optimization_eligible=ranking_eligible(ref,study_role),
                eight_rotor_projected_max_span_m=row.get('projected_max_span_m'),
                four_rotor_projected_max_span_m=ref.get('projected_max_span_m'),
                eight_rotor_convex_hull_area_m2=row.get('projected_convex_hull_area_m2'),
                four_rotor_convex_hull_area_m2=ref.get('projected_convex_hull_area_m2'),
                battery_power_W=row["battery_power_W"], diameter_m=row["diameter_m"],
                lift_N=row["mean_lift_N"], four_rotor_lift_N=ref["mean_lift_N"],
                gain_percent=100 * (row["mean_lift_N"] / ref["mean_lift_N"] - 1)))
    planforms=[]
    for circle in (r for r in comparison_rows if r['rotors']==8 and r['layout']=='circular_ring'):
        for square in (r for r in comparison_rows if r['layout']=='square_perimeter'):
            if matched_settings(circle,square) and same_projected_box(circle,square):
                planforms.append(dict(circle_case=circle['case'],square_case=square['case'],
                    level=circle['level'],tilt_deg=circle['tilt_deg'],
                    outer_edge_angle_label=circle['outer_edge_angle_label'],
                    battery_power_W=circle['battery_power_W'],
                    circle_lift_N=circle['mean_lift_N'],square_lift_N=square['mean_lift_N'],
                    circle_gain_percent=100*(circle['mean_lift_N']/square['mean_lift_N']-1),
                    circle_nearest_spacing_cm=circle['nearest_spacing_cm'],
                    square_nearest_spacing_cm=square['nearest_spacing_cm'],
                    circle_projected_width_cm=100*circle['projected_width_m'],
                    square_projected_width_cm=100*square['projected_width_m'],
                    circle_projected_max_span_m=circle.get('projected_max_span_m'),
                    square_projected_max_span_m=square.get('projected_max_span_m'),
                    circle_convex_hull_area_m2=circle.get('projected_convex_hull_area_m2'),
                    square_convex_hull_area_m2=square.get('projected_convex_hull_area_m2'),
                    circle_optimization_eligible=ranking_eligible(circle,study_role),
                    square_optimization_eligible=ranking_eligible(square,study_role),
                    initialization_method=circle['initialization_method'],
                    numerical_method_signature=numerical_signature(circle),
                    same_projected_box_within_0_05_percent=True))
    maxspan_pairs=[]
    for circle in (r for r in comparison_rows if r['rotors']==8 and r['layout']=='circular_ring'):
        for square in (r for r in comparison_rows if r['layout']=='square_perimeter'):
            cs,ss=circle.get('projected_max_span_m'),square.get('projected_max_span_m')
            if (matched_settings(circle,square) and cs is not None and ss is not None
                    and math.isclose(cs,ss,rel_tol=5e-4,abs_tol=1e-7)):
                maxspan_pairs.append(dict(circle_case=circle['case'],square_case=square['case'],
                    level=circle['level'],study_role=study_role,
                    outer_edge_angle_label=circle['outer_edge_angle_label'],
                    circle_lift_N=circle['mean_lift_N'],square_lift_N=square['mean_lift_N'],
                    circle_gain_percent=100*(circle['mean_lift_N']/square['mean_lift_N']-1),
                    circle_projected_max_span_m=cs,square_projected_max_span_m=ss,
                    circle_box_width_m=circle['projected_width_m'],square_box_width_m=square['projected_width_m'],
                    initialization_method=circle['initialization_method'],
                    numerical_method_signature=numerical_signature(circle),
                    same_projected_max_span_within_0_05_percent=True))
    same_hub_tilts=[]
    for candidate in (r for r in comparison_rows if abs(r['tilt_deg'])>1e-8):
        for flat in (r for r in comparison_rows if abs(r['tilt_deg'])<1e-8):
            if not same_hub_tilt_settings(candidate,flat):
                continue
            same_hub_tilts.append(dict(candidate_case=candidate['case'],flat_case=flat['case'],
                study_role=study_role,level=candidate['level'],mesh_cells=candidate['mesh_cells'],
                rotors=candidate['rotors'],layout=candidate['layout'],flat_layout=flat['layout'],
                layout_label=candidate['layout_label'],diameter_m=candidate['diameter_m'],
                thickness_m=candidate['thickness_m'],battery_power_W=candidate['battery_power_W'],
                rotor_centers_sha256=candidate['rotor_centers_sha256'],
                same_unordered_centers_at_12_decimals=True,
                nearest_spacing_cm=candidate['nearest_spacing_cm'],
                tilt_deg=candidate['tilt_deg'],outer_edge_angle_label=candidate['outer_edge_angle_label'],
                start_s=candidate['start_s'],stop_s=candidate['stop_s'],
                initialization_method=candidate['initialization_method'],
                numerical_method_signature=numerical_signature(candidate),
                candidate_optimization_eligible=ranking_eligible(candidate,study_role),
                flat_optimization_eligible=ranking_eligible(flat,study_role),
                candidate_lift_N=candidate['mean_lift_N'],flat_lift_N=flat['mean_lift_N'],
                lift_difference_N=candidate['mean_lift_N']-flat['mean_lift_N'],
                gain_percent=100*(candidate['mean_lift_N']/flat['mean_lift_N']-1),
                candidate_projected_width_m=candidate['projected_width_m'],
                flat_projected_width_m=flat['projected_width_m'],
                comparison_kind='Tilt at fixed hub positions; projected footprint is allowed to change'))
    return dict(study_role=study_role,
                objective="Maximum gross vertical lift at the common electrical budget; smaller footprint is only a close-result tie-break",
                optimization_range=optimization_range_text(records),
                comparison_eligible_case_count=len(comparison_rows),optimization_eligible_case_count=len(eligible),
                out_of_range_comparison_control_cases=[r['case'] for r in comparison_rows
                    if not r.get('optimization_spacing_in_range',False)],
                ranking_basis="Separate planform, physical configuration, initialization regime and verified numerical method; unknown numerical settings are isolated per case",
                best_by_configuration=best, best_on_each_grid=grid_winners,
                gains_vs_nominal_flat_control=comparisons, matched_layout_comparisons=matched,
                matched_rotor_count_comparisons=matched, matched_planform_comparisons=planforms,
                matched_max_span_planform_comparisons=maxspan_pairs,
                same_hub_tilt_comparisons=same_hub_tilts)


def summarize_scopes(records, control_distance):
    return {role: summarize(records, control_distance, role) for role in ROLE_WINDOWS}


def footprint_tradeoffs(records):
    """Sampled force/box-width frontiers, without pooling numerical protocols.

    Benchmark controls are plotted but never participate in the search frontier.
    No percentage band converts a smaller, lower-lift sample into a winner.
    """
    groups = {}
    for row in records:
        if not comparison_eligible(row,row['study_role']):
            continue
        key = (row['study_role'],row['level'],row['mesh_cells'],
            row['battery_power_W'],row['diameter_m'],row['thickness_m'],
            row['start_s'],row['stop_s'],initialization_key(row),numerical_key(row),
            tuple(sorted(row['loss_model'].items())),str(row.get('domain_xy_m')),
            str(row.get('domain_z_m')),row.get('physical_source_sha256'))
        groups.setdefault(key,[]).append(row)
    output = []
    for key,rows in sorted(groups.items(),key=lambda item:repr(item[0])):
        eligible = [r for r in rows if ranking_eligible(r,r['study_role'])]
        frontier = [r for r in eligible if not any(
            other['projected_width_m'] <= r['projected_width_m']
            and other['mean_lift_N'] >= r['mean_lift_N']
            and (other['projected_width_m'] < r['projected_width_m']
                 or other['mean_lift_N'] > r['mean_lift_N'])
            for other in eligible)]
        output.append(dict(protocol_id=hashlib.sha256(repr(key).encode()).hexdigest()[:12],
            study_role=rows[0]['study_role'],level=rows[0]['level'],
            battery_power_W=rows[0]['battery_power_W'],diameter_m=rows[0]['diameter_m'],
            start_s=rows[0]['start_s'],stop_s=rows[0]['stop_s'],
            initialization_method=rows[0]['initialization_method'],
            numerical_method_signature=numerical_signature(rows[0]),
            cases=rows,optimization_frontier_cases=[r['case'] for r in sorted(frontier,
                key=lambda r:(r['projected_width_m'],r['mean_lift_N'],r['case']))],
            interpretation='Nondominated sampled means for smaller projected box width and greater lift within current per-layout search limits. '+optimization_range_text(records)+' No uncertainty or physical dominance is established. Benchmarks are displayed but excluded from this search frontier.'))
    return output


def reaverage(sample, start, stop):
    return calculate(sample["path"], sample["geometry"], sample["history"],
                     start, stop, sample["volumes"], sample.get("initialization"), sample.get("numerics"),
                     circle_max_spacing_cm=sample.get('circle_max_spacing_cm'))


def late_window_diagnostics(records, samples, control_distance):
    windows, all_rows = {}, []
    for name in ("first_late_half", "last_late_half"):
        rows, skipped = [], []
        for record in records:
            midpoint = (record["start_s"] + record["stop_s"]) / 2
            start, stop = ((record["start_s"], midpoint) if name == "first_late_half"
                           else (midpoint, record["stop_s"]))
            try:
                row = reaverage(samples[record["case"]], start, stop)
            except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                skipped.append(dict(case=record["case"], reason=str(exc))); continue
            row["window_id"] = name
            rows.append(row); all_rows.append(row)
        scopes = summarize_scopes(rows, control_distance)
        windows[name] = dict(cases=rows, skipped_cases=skipped, summaries_by_role=scopes,
                             **scopes["validation"])
    primary_scopes = summarize_scopes(records, control_distance)
    ranking = []
    for role in ROLE_WINDOWS:
        keys = set(primary_scopes[role]["best_by_configuration"])
        for group in windows.values():
            keys.update(group["summaries_by_role"][role]["best_by_configuration"])
        for key in sorted(keys):
            by_window = {}
            candidates = [("primary", primary_scopes[role])] + [
                (name, group["summaries_by_role"][role]) for name, group in windows.items()]
            for name, summary in candidates:
                entry = summary["best_by_configuration"].get(key)
                if entry:
                    row = entry["best_tested"]
                    by_window[name] = dict(case=row["case"], distance_cm=row["distance_cm"],
                        layout=row['layout'],nearest_spacing_cm=row['nearest_spacing_cm'],
                        projected_width_m=row['projected_width_m'],outer_edge_angle_label=row['outer_edge_angle_label'],
                        tilt_deg=row["tilt_deg"], lift_N=row["mean_lift_N"],
                        start_s=row["start_s"], stop_s=row["stop_s"],
                        gain_vs_nominal_flat_percent=entry["gain_vs_nominal_flat_percent"])
            ranking.append(dict(configuration=key, study_role=role, best_by_window=by_window,
                same_best_case_all_three=(len(by_window) == 3 and
                    len({r["case"] for r in by_window.values()}) == 1)))
    return dict(kind="Adjacent re-averages of the same completed CFD histories, not independent runs",
                windows=windows, ranking_sensitivity=ranking), all_rows


def stability_diagnostics(records, late, control_distance, tolerance=.25):
    """Assess both absolute lift drift and candidate/control gain drift.

    This finite-window screen is not a stationarity proof or confidence bound.
    Gain stability is measured in percentage points, lift drift in percent.
    """
    halves = [{r["case"]: r for r in late["windows"][name]["cases"]}
              for name in ("first_late_half", "last_late_half")]
    checks, pairs = {}, []
    for row in records:
        first, last = (group.get(row["case"]) for group in halves)
        if first is None or last is None:
            checks[row["case"]] = dict(case=row["case"], study_role=row["study_role"],
                stability_screen_passed=False, reason="one or both late halves unavailable")
            continue
        lift_ok = bool(abs(row["half_window_drift_percent"]) <= tolerance)
        power_delta = 100 * (last["mean_equivalent_battery_input_W"] -
                            first["mean_equivalent_battery_input_W"]) / row["battery_power_W"]
        source_ok = bool(all(qualified(r) for r in (row, first, last)))
        power_ok = bool(source_ok and abs(power_delta) <= .5)
        checks[row["case"]] = dict(case=row["case"], study_role=row["study_role"],
            initialization_method=row["initialization_method"],
            numerical_method_signature=numerical_signature(row),
            level=row["level"], start_s=row["start_s"], stop_s=row["stop_s"],
            mean_lift_half_change_percent=row["half_window_drift_percent"],
            lift_stable_within_tolerance=lift_ok,
            source_qualified_all_three_intervals=source_ok,
            late_input_change_percent_of_budget=power_delta,
            power_agreement_passed=power_ok,
            stability_screen_passed=bool(lift_ok and power_ok))
        row["late_lift_stability_passed"] = lift_ok
        row["late_power_agreement_passed"] = power_ok
        row["late_window_stability_screen_passed"] = bool(lift_ok and power_ok)
    for row in records:
        if not primary(row) or not row["role_window_consistent"]:
            continue
        ref=flat_reference(row,records,control_distance)
        if ref is None or ref['case']==row['case']:
            continue
        candidate_windows = [row] + [group.get(row["case"]) for group in halves]
        reference_windows = [ref] + [group.get(ref["case"]) for group in halves]
        if any(r is None for r in candidate_windows + reference_windows):
            continue
        same_intervals = all(np.allclose((c["start_s"], c["stop_s"]),
            (r["start_s"], r["stop_s"]), rtol=0, atol=1e-9)
            for c, r in zip(candidate_windows, reference_windows))
        source_ok = bool(same_intervals and all(qualified(r)
                         for r in candidate_windows + reference_windows))
        gains = [100 * (c["mean_lift_N"] / r["mean_lift_N"] - 1)
                 for c, r in zip(candidate_windows, reference_windows)]
        power_differences = [100 * (c["mean_equivalent_battery_input_W"] -
            r["mean_equivalent_battery_input_W"]) / row["battery_power_W"]
            for c, r in zip(candidate_windows, reference_windows)]
        power_ok = bool(source_ok and max(abs(p) for p in power_differences) <= .5
            and checks[row["case"]].get("power_agreement_passed", False)
            and checks[ref["case"]].get("power_agreement_passed", False))
        gain_change = gains[2] - gains[1]
        gain_ok = bool(source_ok and abs(gain_change) <= tolerance)
        lift_ok = bool(checks[row["case"]].get("lift_stable_within_tolerance", False)
                       and checks[ref["case"]].get("lift_stable_within_tolerance", False))
        pairs.append(dict(case=row["case"], reference_case=ref["case"],
            initialization_method=row["initialization_method"],
            numerical_method_signature=numerical_signature(row),
            study_role=row["study_role"], level=row["level"], distance_cm=row["distance_cm"],
            layout=row['layout'],nearest_spacing_cm=row['nearest_spacing_cm'],
            tilt_deg=row["tilt_deg"], start_s=row["start_s"], stop_s=row["stop_s"],
            source_qualified_all_intervals=source_ok,
            primary_gain_percent=gains[0] if source_ok else None,
            first_late_half_gain_percent=gains[1] if source_ok else None,
            last_late_half_gain_percent=gains[2] if source_ok else None,
            gain_half_change_percentage_points=gain_change if source_ok else None,
            gain_stable_within_tolerance=gain_ok,
            gain_sign_agrees_all_intervals=bool(source_ok and len(set(np.sign(gains))) == 1),
            maximum_paired_input_difference_percent_of_budget=max(abs(p) for p in power_differences),
            paired_power_agreement_passed=power_ok,
            candidate_and_control_lift_stable=lift_ok,
            stability_screen_passed=bool(source_ok and power_ok and lift_ok and gain_ok)))
    return dict(lift_drift_tolerance_percent=tolerance,
        gain_change_tolerance_percentage_points=tolerance,
        input_agreement_tolerance_percent_of_budget=.5,
        interpretation="Finite-window sensitivity checks, not proof of stationarity or independent experiments",
        cases=list(checks.values()), paired_gains_vs_flat_control=pairs)


def physical_geometry_signature(row, sample):
    g = sample["geometry"]
    vectors = tuple(round(float(v), 12) for key in ("centers", "normals")
                    for vector in g[key] for v in vector)
    domain = (str(g.get("domain_xy_m")), str(g.get("domain_z_m")))
    return (g.get("source_sha256"), config_key(row), row["thickness_m"], row["tilt_deg"],
            tuple(sorted(row["loss_model"].items())), domain, vectors)


def geometry_signature(row, sample):
    return (row["study_role"], row["primary_averaging_start_s"], row["primary_averaging_stop_s"],
            initialization_key(row), numerical_key(row), physical_geometry_signature(row, sample))


def mesh_diagnostics(records, samples, control_distance):
    groups, cache = {}, {}
    for row in records:
        if (primary(row) and row["role_window_consistent"]
                and row["initialization_provenance_consistent"] and numerical_signature(row)):
            groups.setdefault(geometry_signature(row, samples[row["case"]]), []).append(row)
    def at(row, start, stop):
        key = row["case"], start, stop
        if key not in cache:
            cache[key] = reaverage(samples[row["case"]], start, stop)
        return cache[key]
    comparisons, paired_gains, skipped = [], [], []
    for group in groups.values():
        ordered = sorted(group, key=level_key)
        for coarse, finer in itertools.combinations(ordered, 2):
            if level_key(coarse) == level_key(finer):
                continue
            start, stop = ROLE_WINDOWS[coarse["study_role"]]
            try:
                c, f = at(coarse, start, stop), at(finer, start, stop)
            except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                skipped.append(dict(coarse_case=coarse["case"], finer_case=finer["case"],
                                    reason=str(exc))); continue
            valid = bool(qualified(c) and qualified(f))
            comparisons.append(dict(coarse_case=c["case"], finer_case=f["case"],
                study_role=c["study_role"],
                initialization_method=c["initialization_method"],
                numerical_method_signature=numerical_signature(c),
                rotors=c["rotors"], battery_power_W=c["battery_power_W"], diameter_m=c["diameter_m"],
                distance_cm=c["distance_cm"], tilt_deg=c["tilt_deg"],
                layout=c['layout'],nearest_spacing_cm=c['nearest_spacing_cm'],
                coarse_level=c["level"], finer_level=f["level"], start_s=start, stop_s=stop,
                coarse_lift_N=c["mean_lift_N"], finer_lift_N=f["mean_lift_N"],
                coarse_qualified=bool(qualified(c)), finer_qualified=bool(qualified(f)),
                qualified_for_mesh_comparison=valid,
                lift_change_percent=100 * (f["mean_lift_N"] / c["mean_lift_N"] - 1) if valid else None))
            def flat_on_level(level):
                candidate=coarse if coarse['level']==level else finer
                return flat_reference(candidate,records,control_distance)
            cr, fr = flat_on_level(c["level"]), flat_on_level(f["level"])
            is_control = cr is not None and cr['case']==c['case']
            if valid and cr and fr and not is_control:
                try:
                    rc, rf = at(cr, start, stop), at(fr, start, stop)
                except (ValueError, KeyError, TypeError, ZeroDivisionError):
                    continue
                if qualified(rc) and qualified(rf):
                    cg = 100 * (c["mean_lift_N"] / rc["mean_lift_N"] - 1)
                    fg = 100 * (f["mean_lift_N"] / rf["mean_lift_N"] - 1)
                    paired_gains.append(dict(case_coarse=c["case"], case_finer=f["case"],
                        study_role=c["study_role"],
                        initialization_method=c["initialization_method"],
                        numerical_method_signature=numerical_signature(c),
                        reference_coarse=rc["case"], reference_finer=rf["case"],
                        start_s=start, stop_s=stop, coarse_gain_percent=cg, finer_gain_percent=fg,
                        gain_change_percentage_points=fg - cg,
                        sign_agrees=(int(cg > 0) - int(cg < 0) == int(fg > 0) - int(fg < 0))))
    return dict(basis="Study roles, initialization regimes and verified numerical methods never mix: validation uses 0.8–1.2 s on BOTH grids; screening uses 0.4–0.8 s. Unknown numerical methods cannot match. Each interval is independently requalified.",
                comparisons=comparisons, paired_gains_vs_flat_control=paired_gains,
                cases_without_verified_numerics=[r['case'] for r in records if not numerical_signature(r)],
                cases=list(cache.values()), skipped_pairs=skipped)


def write_csv(path, records):
    columns = list(dict.fromkeys(k for row in records for k in row if k != "loss_model")) if records else ["case"]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)


def annotate_matched_pair_stability(summary, records, late, tolerance):
    """Keep matched planform/count means distinct from temporal qualification."""
    full = {r['case']: r for r in records}
    halves = [{r['case']: r for r in late['windows'][name]['cases']}
              for name in ('first_late_half', 'last_late_half')]
    for key, left_case, right_case in (
        ('matched_planform_comparisons', 'square_case', 'circle_case'),
        ('matched_max_span_planform_comparisons', 'square_case', 'circle_case'),
        ('same_hub_tilt_comparisons', 'flat_case', 'candidate_case'),
        ('matched_rotor_count_comparisons', 'four_rotor_case', 'case')):
        for pair in summary.get(key, []):
            left, right = full[pair[left_case]], full[pair[right_case]]
            left_rows = [left] + [h.get(left['case']) for h in halves]
            right_rows = [right] + [h.get(right['case']) for h in halves]
            pair.update(left_half_window_drift_percent=left['half_window_drift_percent'],
                right_half_window_drift_percent=right['half_window_drift_percent'],
                left_lift_drift_screen_passed=bool(abs(left['half_window_drift_percent'])<=tolerance),
                right_lift_drift_screen_passed=bool(abs(right['half_window_drift_percent'])<=tolerance),
                left_equivalent_battery_input_W=left['mean_equivalent_battery_input_W'],
                right_equivalent_battery_input_W=right['mean_equivalent_battery_input_W'],
                temporal_screen_passed=False,
                temporal_screen_interpretation='Finite-window sensitivity, not a stationarity proof')
            if any(r is None for r in left_rows + right_rows):
                pair['temporal_screen_reason'] = 'Missing late-half records'
                continue
            interval_ok = all(np.allclose((l['start_s'], l['stop_s']),
                (r['start_s'], r['stop_s']), rtol=0, atol=1e-9)
                for l, r in zip(left_rows, right_rows))
            source_ok = bool(interval_ok and all(qualified(r) for r in left_rows + right_rows))
            gains = [100 * (r['mean_lift_N'] / l['mean_lift_N'] - 1)
                     for l, r in zip(left_rows, right_rows)]
            input_differences = [100 * (r['mean_equivalent_battery_input_W'] -
                l['mean_equivalent_battery_input_W']) / left['battery_power_W']
                for l, r in zip(left_rows, right_rows)]
            gain_change = gains[2] - gains[1]
            lift_ok = all(abs(r['half_window_drift_percent']) <= tolerance for r in (left, right))
            power_ok = bool(source_ok and max(abs(v) for v in input_differences) <= .5
                and left.get('late_power_agreement_passed', False)
                and right.get('late_power_agreement_passed', False))
            pair.update(source_qualified_all_three_intervals=source_ok,
                first_late_half_gain_percent=gains[1], last_late_half_gain_percent=gains[2],
                gain_half_change_percentage_points=gain_change,
                gain_stable_within_tolerance=bool(source_ok and abs(gain_change) <= tolerance),
                maximum_paired_input_difference_percent_of_budget=max(abs(v) for v in input_differences),
                paired_power_agreement_passed=power_ok, both_lift_drift_screens_passed=bool(lift_ok),
                temporal_screen_passed=bool(source_ok and power_ok and lift_ok and abs(gain_change) <= tolerance))


def image_html(path):
    return '<img alt="' + html.escape(path.stem) + '" src="data:image/png;base64,' + \
        base64.b64encode(path.read_bytes()).decode("ascii") + '">'


def table(rows, fields):
    if not rows:
        return '<p>No completed comparison is available.</p>'
    header = ''.join('<th>' + html.escape(label) + '</th>' for _, label, _ in fields)
    body = []
    for row in rows:
        values = []
        for key, _, spec in fields:
            value = row.get(key)
            text = '—' if value is None else format(value, spec) if spec else str(value)
            values.append('<td>' + html.escape(text) + '</td>')
        body.append('<tr>' + ''.join(values) + '</tr>')
    return '<div class="scroll"><table><tr>' + header + '</tr>' + ''.join(body) + '</table></div>'


def make_plots(out, records, summary):
    # A refreshed report must not retain plots from an older role/matrix.
    for old in list(out.glob('heatmap_*.png')) + list(out.glob('lift_vs_box_width_*.png')) + list(out.glob('same_hub_tilt_gain_*.png')) + [out/name for name in
            ('supported_mass_reference.png','planform_lift_comparison.png','rotor_count_lift_comparison.png')]:
        if old.is_file():
            old.unlink()
    paths = []
    for rows, left_key, right_key, left_name, right_name, filename, title in (
        (summary.get('matched_planform_comparisons',[]),'square_lift_N','circle_lift_N',
         'Square perimeter','Circular ring','planform_lift_comparison.png','1. Square versus circular eight-rotor layout'),
        (summary.get('matched_rotor_count_comparisons',[]),'four_rotor_lift_N','lift_N',
         'Four rotors','Eight rotors','rotor_count_lift_comparison.png','2. Four versus eight rotors')):
        if not rows:
            continue
        fig,ax=plt.subplots(figsize=(10.5,max(4.,.85*len(rows)+1.8)))
        y=np.arange(len(rows))
        ax.barh(y-.18,[r[left_key] for r in rows],height=.33,color='#e78c32',label=left_name)
        ax.barh(y+.18,[r[right_key] for r in rows],height=.33,color='#2878bd',label=right_name)
        labels=[]
        for index,row in enumerate(rows):
            tilt=row.get('outer_edge_angle_label','Flat' if abs(row['tilt_deg'])<1e-8 else f'{row["tilt_deg"]:g}° signed')
            init=str(row['initialization_method']).replace('_',' ')
            width=row.get('square_projected_width_cm',100*row.get('projected_width_m',0.))
            layout=row.get('layout','').replace('_',' ')
            marker = '' if row.get('temporal_screen_passed', False) else ' †'
            labels.append(f'{row["level"]} · {tilt} · {init}{marker}\n{layout+" · " if layout else ""}matched box width {width:.2f} cm')
            for offset,key in ((-.18,left_key),(.18,right_key)):
                ax.text(row[key]+.01,index+offset,f'{row[key]:.4f} N',va='center',fontsize=9)
        ax.set(yticks=y,yticklabels=labels,xlabel='Time-averaged gross vertical lift [N]')
        ax.set_xlim(0,max(r[k] for r in rows for k in (left_key,right_key))*1.2)
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        ax.legend(loc='lower center',bbox_to_anchor=(.5,1.02),ncol=2,fontsize=9)
        ax.set_title(title+'\nMatched footprint, power, grid, initialization and numerical method',pad=50,fontsize=11)
        unsettled = any(not r.get('temporal_screen_passed', False) for r in rows)
        if unsettled:
            fig.text(.5, .01, '† Preliminary mean: the matched pair fails the late-window lift, gain or input screen.',
                     ha='center', fontsize=9)
        fig.tight_layout(rect=(0, .05 if unsettled else 0, 1, 1));path=out/filename
        fig.savefig(path,dpi=170,bbox_inches='tight',pad_inches=.15);plt.close(fig);paths.append(path)
    same_hub_groups={}
    for pair in summary.get('same_hub_tilt_comparisons',[]):
        same_hub_groups.setdefault(pair['flat_case'],[]).append(pair)
    for reference,rows in sorted(same_hub_groups.items()):
        rows=sorted(rows,key=lambda r:r['tilt_deg'])
        fig,ax=plt.subplots(figsize=(10.5,max(4.,.65*len(rows)+2.2)))
        y=np.arange(len(rows))
        gains=[r['gain_percent'] for r in rows]
        ax.barh(y,gains,color=['#2878bd' if g>=0 else '#d97706' for g in gains],alpha=.85)
        labels=[r['outer_edge_angle_label']+('' if r.get('temporal_screen_passed',False) else ' †') for r in rows]
        span=max(max(gains),0)-min(min(gains),0)
        padding=max(.03,.025*span)
        for i,row in enumerate(rows):
            value=row['gain_percent']
            ax.text(value+(padding if value>=0 else -padding),i,
                f'{value:+.3f}% · {row["candidate_lift_N"]:.5f} N',
                va='center',ha='left' if value>=0 else 'right',fontsize=9)
        ax.axvline(0,color='#475569',lw=.8)
        ax.set(yticks=y,yticklabels=labels,xlabel='Vertical lift change versus flat at the same hub positions [%]')
        ax.set_xlim(min(min(gains),0)-max(.25,.3*span),max(max(gains),0)+max(.6,.4*span))
        ax.grid(axis='x',alpha=.2);ax.set_axisbelow(True)
        r=rows[0]
        ax.set_title(f'{r["study_role"].upper()} · {r["rotors"]} rotors · {r["layout_label"]} · {r["level"]}\n'
            f'Fixed hubs s={r["nearest_spacing_cm"]:.4g} cm · {r["initialization_method"].replace("_"," ")} · '
            f'{r["start_s"]:g}–{r["stop_s"]:g} s\n'
            f'Flat reference {r["flat_lift_N"]:.5f} N · {r["battery_power_W"]:.4g} W input budget',fontsize=11)
        footer='Same centers, grid, power, physics, initialization, verified method and window; projected box can change.'
        if any(not r.get('temporal_screen_passed',False) for r in rows):
            footer+='\n† Candidate/flat pair fails late-window lift, gain or input checks; means remain preliminary.'
        else:
            footer+='\nPairs pass the finite late-window screen; this is not a proof of stationarity or hardware performance.'
        fig.text(.5,.015,footer,ha='center',fontsize=8)
        fig.tight_layout(rect=(0,.09,1,1))
        path=out/('same_hub_tilt_gain_'+hashlib.sha256(reference.encode()).hexdigest()[:12]+'.png')
        fig.savefig(path,dpi=170,bbox_inches='tight',pad_inches=.15);plt.close(fig);paths.append(path)
    nominal = [r for r in records if primary(r) and r["role_window_consistent"]]
    plot_groups = {(r["study_role"], config_key(r), initialization_key(r), numerical_key(r)) for r in nominal}
    for role, key, init, method in sorted(plot_groups, key=repr):
        rows = [r for r in nominal if config_key(r) == key and r["study_role"] == role
                and initialization_key(r) == init and numerical_key(r) == method]
        if len({(round(r["nearest_spacing_cm"],6), r["tilt_deg"]) for r in rows}) < 2:
            continue
        levels = sorted({r["level"] for r in rows}, key=lambda level:
            max(level_key(r) for r in rows if r["level"] == level))
        fig, axes = plt.subplots(1, len(levels), squeeze=False,
                                 figsize=(6 * len(levels), 6.2), layout='constrained')
        cmap = plt.get_cmap("viridis").copy(); cmap.set_bad('#e5e7eb')
        lower, upper = min(r["mean_lift_N"] for r in rows), max(r["mean_lift_N"] for r in rows)
        upper = max(upper, lower + 1e-6)
        for ax, level in zip(axes[0], levels):
            local = [r for r in rows if r["level"] == level]
            distances = sorted({round(r["nearest_spacing_cm"],6) for r in local})
            angles = sorted({r["tilt_deg"] for r in local})
            matrix = np.full((len(angles), len(distances)), np.nan)
            for row in local:
                matrix[angles.index(row["tilt_deg"]), distances.index(round(row["nearest_spacing_cm"],6))] = row["mean_lift_N"]
            im = ax.imshow(np.ma.masked_invalid(matrix), origin='lower', interpolation='nearest',
                           aspect='auto', cmap=cmap, vmin=lower, vmax=upper)
            for row in local:
                x, y = distances.index(round(row["nearest_spacing_cm"],6)), angles.index(row["tilt_deg"])
                color = 'white' if (row["mean_lift_N"] - lower) / (upper - lower) < .55 else 'black'
                # This is the absolute row lift/input screen, not a paired-gain test.
                temporal_marker = '' if row.get('late_window_stability_screen_passed', False) else '†'
                ax.text(x, y, f'{row["mean_lift_N"]:.4f}{temporal_marker}', ha='center', va='center', fontsize=8, color=color)
                if not qualified(row):
                    ax.scatter([x], [y], marker='x', color='crimson', s=100, linewidths=2)
                elif not row.get('optimization_spacing_in_range',False):
                    ax.text(x+.35,y+.34,'B',ha='center',va='center',fontsize=8,color='crimson',weight='bold')
            labels = ['Flat' if abs(a) < 1e-10 else f'{abs(a):g}° {"raised" if a < 0 else "lowered"}' for a in angles]
            ax.set(xticks=range(len(distances)), xticklabels=[f'{d:g}' for d in distances],
                   yticks=range(len(angles)), yticklabels=labels,
                   xlabel='Nearest hub-center spacing [cm]', ylabel='Outer rotor edges', title=level)
            fig.colorbar(im, ax=ax, label='Mean vertical lift [N]', shrink=.8)
        start, stop = ROLE_WINDOWS[role]
        fig.suptitle(config_label(key) +
                     f'\n{role.upper()} · {start:g}–{stop:g} s · {str(init[0]).replace("_", " ")}' +
                     f' · method {method[:10] if numerical_signature(rows[0]) else "UNKNOWN"}' +
                     '\nSampled points; gray = missing; × = fails input/source checks; B = spacing benchmark' +
                     '\n† = late-window row lift/input screen failed or unavailable' +
                     '\nRow screen only; no paired-gain check or stationarity claim', fontsize=10)
        init_token = str(init[0]) + '_' + hashlib.sha256(repr(init).encode()).hexdigest()[:8]
        method_token = hashlib.sha256(method.encode()).hexdigest()[:8]
        path = out / ('heatmap_' + role + '_' + init_token + '_method' + method_token + '_' + config_id(key) + '.png')
        fig.savefig(path, dpi=170, bbox_inches='tight'); plt.close(fig); paths.append(path)
    for group in summary.get('lift_footprint_tradeoffs',[]):
        rows=group['cases']
        if len(rows)<2:
            continue
        fig,ax=plt.subplots(figsize=(11.2,6.8))
        styles={(4,'square_perimeter'):('#d97706','s'),
                (8,'square_perimeter'):('#2878bd','o'),(8,'circular_ring'):('#8b4fb5','D')}
        for kind in sorted({(r['rotors'],r['layout']) for r in rows}):
            color,marker=styles.get(kind,('#475569','o'))
            for benchmark in (False,True):
                local=[r for r in rows if (r['rotors'],r['layout'])==kind
                    and (not r.get('optimization_spacing_in_range',False))==benchmark]
                if not local:
                    continue
                ax.scatter([100*r['projected_width_m'] for r in local],
                    [r['mean_lift_N'] for r in local],marker=marker,s=65,
                    facecolors='none' if benchmark else color,edgecolors=color,linewidths=1.4,
                    label=f'{kind[0]} rotors · {local[0]["layout_label"]}'+(' · benchmark' if benchmark else ''))
                labelled={max(local,key=lambda r:r['mean_lift_N'])['case'],
                          min(local,key=lambda r:r['projected_width_m'])['case']}
                for r in local:
                    if r['case'] not in labelled:
                        continue
                    angle='flat' if abs(r['tilt_deg'])<1e-8 else f'{abs(r["tilt_deg"]):g}° '+('raised' if r['tilt_deg']<0 else 'lowered')
                    label=f's {r["nearest_spacing_cm"]:.3g} cm · {angle}'
                    if not r.get('late_window_stability_screen_passed',False):
                        label+=' †'
                    ax.annotate(label,(100*r['projected_width_m'],r['mean_lift_N']),
                        xytext=(5,7),textcoords='offset points',fontsize=8,alpha=.85)
        frontier=sorted([r for r in rows if r['case'] in group['optimization_frontier_cases']],
                        key=lambda r:r['projected_width_m'])
        if frontier:
            ax.plot([100*r['projected_width_m'] for r in frontier],
                [r['mean_lift_N'] for r in frontier],color='#334155',ls='--',lw=1,zorder=0,
                label='Search frontier of sampled means')
        ax.set(xlabel='Actual projected box width [cm]',ylabel='Time-averaged gross vertical lift [N]')
        ax.margins(x=.12,y=.2);ax.grid(alpha=.2);ax.set_axisbelow(True)
        ax.legend(fontsize=8,loc='lower center',bbox_to_anchor=(.5,1.02),ncol=2)
        method=(group['numerical_method_signature'] or 'UNKNOWN')[:10]
        ax.set_title(f'{group["study_role"].upper()} · {group["level"]} · {group["battery_power_W"]:.4g} W · '
            f'{str(group["initialization_method"]).replace("_"," ")} · method {method}\n'
            f'{group["start_s"]:g}–{group["stop_s"]:g} s · lift is the primary objective',pad=65,fontsize=11)
        fig.text(.5,.025,'Hollow markers: spacing benchmarks outside current per-layout search limits. † Late lift/input screen not passed.\n'
            'Labels show greatest lift and smallest width per design family; all samples remain in CSV. Dashed line joins sampled means only.',
            ha='center',fontsize=8)
        fig.tight_layout(rect=(0,.075,1,1))
        path=out/('lift_vs_box_width_'+group['protocol_id']+'.png')
        fig.savefig(path,dpi=170,bbox_inches='tight',pad_inches=.15);plt.close(fig);paths.append(path)
    winners = summary["best_on_each_grid"]
    if winners:
        fig, ax = plt.subplots(figsize=(11.5, max(4., .85 * len(winners) + 1.8)))
        labels = [f'{r["rotors"]} rotors, {r["layout_label"]}, {r["level"]}\n'
                  f'hub spacing {r["nearest_spacing_cm"]:.3g} cm · {r["outer_edge_angle_label"].replace("Outer edges ", "")}\n'
                  f'{r["battery_power_W"]:.3f} W · {r.get("initialization_family", "unknown")} start · box {100*r["projected_width_m"]:.2f} cm'
                  for r in winners]
        ax.barh(range(len(winners)), [r["supported_mass_g"] for r in winners], color='#2563eb', alpha=.8)
        ax.set(yticks=range(len(winners)), yticklabels=labels,
               xlabel='Idealized supported mass from gross vertical lift [g]')
        for index, row in enumerate(winners):
            temporal_marker = '' if row.get('late_window_stability_screen_passed', False) else '†'
            ax.text(row["supported_mass_g"] + 1, index, f'{row["supported_mass_g"]:.1f} g{temporal_marker}', va='center', fontsize=9)
        ax.axvline(80, color='#ea580c', linestyle='--', label='80 g reference')
        ax.axvline(87, color='#7c3aed', linestyle=':', label='87 g guarded-mass reference')
        ax.set_xlim(0, max(100, max(r["supported_mass_g"] for r in winners) * 1.16))
        ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
        ax.legend(fontsize=9, loc='lower center', bbox_to_anchor=(.5, 1.02), ncol=2)
        ax.set_title('VALIDATION: source-qualified best tested sample on each grid\n'
                     'Mass postprocessing; numerical protocols remain separate', pad=40)
        fig.text(.5,.012,'† = absolute row late-window lift/input screen failed or unavailable.\n'
                 'This is not a paired-gain check, confidence interval or proof of stationarity.',
                 ha='center',fontsize=9)
        fig.tight_layout(rect=(0,.055,1,1)); path = out / 'supported_mass_reference.png'
        fig.savefig(path, dpi=170, bbox_inches='tight', pad_inches=.15)
        plt.close(fig); paths.append(path)
    return paths


def write_report(out, info, metadata, images):
    records = info["cases"]
    findings = []
    for entry in info["best_by_configuration"].values():
        row = entry["best_tested"]
        text = (f'{entry["configuration"]}: highest qualified tested {row["level"]}-grid sample is '
            f'{row["mean_lift_N"]:.5f} N at nearest hub spacing {row["nearest_spacing_cm"]:.3f} cm, '
            f'projected box {100*row["projected_width_m"]:.2f} × {100*row["projected_depth_m"]:.2f} cm, '
            f'{row["outer_edge_angle_label"]}. Ideal supported mass {row["supported_mass_g"]:.2f} g; '
            f'headroom relative to 80/87 g is {row["ideal_payload_headroom_80g_g"]:+.2f}/'
            f'{row["ideal_payload_headroom_87g_g"]:+.2f} g.')
        if entry["coarsest_maximum_needs_finer_check"]:
            text += ' The coarsest-grid maximum still lacks a matching finer check.'
        if not row.get("late_window_stability_screen_passed", False):
            text += ' Its mean lift/input has not passed the finite late-window stability screen.'
        findings.append('<li>' + html.escape(text) + '</li>')
    if not findings:
        findings.append('<li>No completed, qualified validation sample is available; screening results are not substituted for a validation winner.</li>')
    screening_rows = []
    for entry in info["summaries_by_role"]["screening"]["best_by_configuration"].values():
        screening_rows.append(dict(configuration=entry["configuration"],
            finer_check_needed=entry["coarsest_maximum_needs_finer_check"],
            **entry["coarsest_grid_best"]))
    screening_table = table(screening_rows, [
        ('configuration','Screening configuration',None), ('case','Largest coarsest-grid sample',None),
        ('mean_lift_N','Lift N','.5f'), ('half_window_drift_percent','Half-window drift %','+.3f'),
        ('finer_check_needed','Matching finer screening check still needed',None)])
    banner = ('<p class="note"><strong>Preliminary report.</strong> ' +
        html.escape(' '.join(info["preliminary_reasons"])) +
        ' Completion and a longer end time do not establish stationarity or a resolved optimum.</p>') if info["preliminary"] else ''
    selection=info['case_selection']
    if selection['mode']=='explicit_exact_case_names':
        selected_list=''.join('<li>'+html.escape(name)+'</li>' for name in selection['selected_names'])
        excluded_list=''.join('<li>'+html.escape(name)+'</li>' for name in selection['excluded_prepared_names'])
        nested_list=''.join('<li>'+html.escape(name)+'</li>' for name in selection['discovered_nested_geometry_parent_paths'])
        selection_section=(f'<p class="note"><strong>Explicit analysis scope:</strong> {selection["selected_count"]} exact case names were supplied; '
            f'{selection["excluded_prepared_count"]} discovered prepared cases are outside this scope. '
            'Selection is independent of lift and qualification. Missing or invalid selected cases remain reported; '
            'controls and poorly performing or unqualified completed tests must not be removed to improve a result.</p>'
            '<details><summary>Frozen scope and excluded-input audit</summary><p>Selection file: '+
            html.escape(selection['selection_path'])+'<br>SHA256: <code>'+selection['selection_sha256']+
            '</code></p><h3>Selected names</h3><ul>'+selected_list+'</ul><h3>Excluded prepared inputs</h3><ul>'+
            excluded_list+'</ul><h3>Additional nested geometry artifacts</h3><ul>'+nested_list+
            '</ul><p>Direct prepared cases and nested geometry/template paths are distinguished. Default recursive processing is unchanged. Excluded inputs are not automatically classified as deferred/unrun. Terminal solver or run-state evidence remains visible below and forces a scope-review preliminary warning.</p>'+
            table(selection['excluded_run_states'],[('case','Excluded case/geometry path',None),('run_state','Run state',None),
                ('returncode','Exit code',None),('validated','Run validator',None),
                ('solver_End_in_log_tail','Solver End in last 16 KiB',None),('terminal_run_evidence','Terminal evidence',None)])+
            '<h3>Selected cases unavailable or invalid</h3>'+table(info['skipped_cases'],[('case','Selected case',None),('reason','Reason',None)])+'</details>')
    else:
        selection_section='<p>Analysis scope uses the unchanged recursive discovery of prepared geometry files; no explicit case-name filter was supplied.</p>'
    all_table = table(records, [
        ('case','Case',None), ('study_role','Role',None), ('study_role_source','Role provenance',None),
        ('role_window_consistent','Expected role interval',None),
        ('initialization_method','Initialization',None),
        ('initialization_source_case','Seed source case',None),
        ('initialization_provenance_consistent','Initialization provenance',None),
        ('numerical_method_label','Numerical method',None),
        ('numerical_audit_status','Numerical input audit',None),
        ('layout_label','Planform',None),('nearest_spacing_cm','Nearest hub spacing cm','.3f'),
        ('analysis_circle_max_spacing_cm','Explicit Circle8 analysis maximum cm','.3f'),
        ('optimization_max_nearest_spacing_m','Current per-layout maximum m','.3f'),
        ('optimization_constraint_source','Analysis constraint source',None),
        ('generation_spacing_above_optimizer_limit_is_matched_control','Historical generation control declaration',None),
        ('optimization_spacing_in_range','Nearest spacing in current search',None),
        ('optimization_eligible','Optimization eligible',None),
        ('eligible_for_nominal_comparison','Comparison eligible',None),
        ('optimization_control_reason','Search / benchmark reason',None),
        ('layout_geometry_metadata_consistent','Geometry metadata checks',None),
        ('projected_width_m','Projected box width m','.5f'),('projected_depth_m','Projected box depth m','.5f'),
        ('projected_max_span_m','Projected maximum span m','.7f'),
        ('projected_convex_hull_area_m2','Projected convex-hull area m²','.9f'),
        ('projected_geometry_metric_method','Hull/span method',None),
        ('projected_geometry_metric_reliable','Hull/span check',None),
        ('geometry_parameter_label','Geometry parameter',None),('outer_edge_angle_label','Tilt',None),
        ('mean_lift_N','Gross vertical lift N','.5f'), ('supported_mass_g','Ideal supported mass g','.2f'),
        ('net_margin_80g_N','Net margin vs 80 g, N','+.4f'),
        ('ideal_payload_headroom_80g_g','Headroom vs 80 g, g','+.2f'),
        ('net_margin_87g_N','Net margin vs 87 g, N','+.4f'),
        ('ideal_payload_headroom_87g_g','Headroom vs 87 g, g','+.2f'),
        ('mean_equivalent_battery_input_W','Inferred input W','.4f'),
        ('battery_power_W','Budget W','.4f'), ('half_window_drift_percent','Half-window drift %','+.3f'),
        ('qualified_for_comparison','Input/source checks',None),
        ('late_window_stability_screen_passed','Late lift/input screen',None)])
    controls = table(info["gains_vs_nominal_flat_control"], [
        ('case','Candidate',None), ('reference_case','Flat control, same grid',None),
        ('gain_percent','Lift change %','+.3f'), ('projected_width_ratio','Width ratio','.4f')])
    same_hub_tilts=table(info.get('same_hub_tilt_comparisons',[]),[
        ('candidate_case','Tilted case',None),('flat_case','Flat at identical hubs',None),
        ('level','Grid',None),('layout_label','Planform',None),
        ('nearest_spacing_cm','Fixed nearest hubs cm','.4f'),('outer_edge_angle_label','Tilt',None),
        ('flat_lift_N','Flat lift N','.5f'),('candidate_lift_N','Tilted lift N','.5f'),
        ('gain_percent','Primary lift change %','+.3f'),
        ('first_late_half_gain_percent','First-half change %','+.3f'),
        ('last_late_half_gain_percent','Last-half change %','+.3f'),
        ('gain_half_change_percentage_points','Late gain change pp','+.3f'),
        ('left_half_window_drift_percent','Flat mean drift %','+.3f'),
        ('right_half_window_drift_percent','Tilted mean drift %','+.3f'),
        ('left_lift_drift_screen_passed','Flat mean drift passes',None),
        ('right_lift_drift_screen_passed','Tilted mean drift passes',None),
        ('maximum_paired_input_difference_percent_of_budget','Maximum paired input gap % budget','.4f'),
        ('paired_power_agreement_passed','Input agreement',None),
        ('gain_stable_within_tolerance','Late gain stable',None),
        ('temporal_screen_passed','Full pair screen',None)])
    matched = table(info["matched_layout_comparisons"], [
        ('case','Eight-rotor case',None),('layout','Eight-rotor planform',None),
        ('four_rotor_case','Four-rotor matched-footprint control',None),('four_rotor_layout','Four-rotor planform',None),
        ('gain_percent','Equal-budget lift change %','+.3f'),
        ('left_half_window_drift_percent','Four-rotor drift %','+.3f'),
        ('right_half_window_drift_percent','Eight-rotor drift %','+.3f'),
        ('temporal_screen_passed','Pair late-window screen',None)])
    planforms = table(info.get('matched_planform_comparisons',[]),[
        ('square_case','Square perimeter',None),('circle_case','Circular ring',None),
        ('level','Grid',None),('outer_edge_angle_label','Tilt',None),
        ('square_lift_N','Square lift N','.5f'),('circle_lift_N','Circle lift N','.5f'),
        ('circle_gain_percent','Circle change %','+.3f'),
        ('square_nearest_spacing_cm','Square nearest hubs cm','.3f'),
        ('circle_nearest_spacing_cm','Circle nearest hubs cm','.3f'),
        ('square_projected_width_cm','Square box width cm','.3f'),
        ('circle_projected_width_cm','Circle box width cm','.3f'),
        ('square_projected_max_span_m','Square max span m','.7f'),
        ('circle_projected_max_span_m','Circle max span m','.7f'),
        ('square_convex_hull_area_m2','Square convex-hull area m²','.9f'),
        ('circle_convex_hull_area_m2','Circle convex-hull area m²','.9f'),
        ('left_half_window_drift_percent','Square drift %','+.3f'),
        ('right_half_window_drift_percent','Circle drift %','+.3f'),
        ('gain_half_change_percentage_points','Late gain change pp','+.3f'),
        ('temporal_screen_passed','Pair late-window screen',None)])
    maxspans=table(info.get('matched_max_span_planform_comparisons',[]),[
        ('square_case','Square case',None),('circle_case','Circle case',None),('level','Grid',None),
        ('outer_edge_angle_label','Tilt',None),('square_projected_max_span_m','Square max span m','.7f'),
        ('circle_projected_max_span_m','Circle max span m','.7f'),
        ('square_box_width_m','Square box width m','.5f'),('circle_box_width_m','Circle box width m','.5f'),
        ('circle_gain_percent','Circle lift change %','+.3f'),
        ('temporal_screen_passed','Pair late-window screen',None)])
    maxspan_section=('<h3>Optional matched maximum-span planform pairs</h3><p>These actual completed pairs hold projected maximum span within 0.05%, '
        'along with power, diameter, thickness, tilt, grid, initialization and verified numerical method. Their box widths can differ. '
        'A matched maximum span also does not imply equal convex-hull area.</p>'+maxspans
        if info.get('matched_max_span_planform_comparisons') else '')
    mesh = table(info["same_geometry_mesh_diagnostics"]["comparisons"], [
        ('study_role','Role',None),
        ('initialization_method','Initialization',None),
        ('coarse_case','Coarser case',None), ('finer_case','Finer case',None),
        ('start_s','Common start s','.3f'), ('stop_s','Common stop s','.3f'),
        ('coarse_lift_N','Coarser lift N','.5f'), ('finer_lift_N','Finer lift N','.5f'),
        ('lift_change_percent','Change %','+.3f'), ('qualified_for_mesh_comparison','Both qualify',None)])
    paired = table(info["same_geometry_mesh_diagnostics"]["paired_gains_vs_flat_control"], [
        ('study_role','Role',None),
        ('initialization_method','Initialization',None),
        ('case_coarse','Coarser candidate',None), ('case_finer','Finer candidate',None),
        ('coarse_gain_percent','Coarser gain vs flat %','+.3f'),
        ('finer_gain_percent','Finer gain vs flat %','+.3f'),
        ('gain_change_percentage_points','Gain change, pp','+.3f'), ('sign_agrees','Sign agrees',None)])
    late_rows = []
    for item in info["late_window_diagnostics"]["ranking_sensitivity"]:
        for name, row in item["best_by_window"].items():
            late_rows.append(dict(configuration=item["configuration"], study_role=item["study_role"], window=name,
                                 stable_best=item["same_best_case_all_three"], **row))
    late = table(late_rows, [
        ('configuration','Configuration',None), ('study_role','Role',None), ('window','Re-average',None),
        ('start_s','Start s','.3f'), ('stop_s','Stop s','.3f'),
        ('nearest_spacing_cm','Best nearest hub spacing cm','.3f'), ('outer_edge_angle_label','Tilt',None),
        ('lift_N','Best lift N','.5f'), ('gain_vs_nominal_flat_percent','Gain vs flat %','+.3f'),
        ('stable_best','Same best in all three',None)])
    stability = info["late_window_stability_diagnostics"]
    stability_table = table(stability["paired_gains_vs_flat_control"], [
        ('study_role','Role',None), ('case','Candidate',None), ('reference_case','Flat control',None),
        ('primary_gain_percent','Primary gain %','+.3f'),
        ('first_late_half_gain_percent','First-half gain %','+.3f'),
        ('last_late_half_gain_percent','Last-half gain %','+.3f'),
        ('gain_half_change_percentage_points','Gain change pp','+.3f'),
        ('candidate_and_control_lift_stable','Both mean lifts stable',None),
        ('paired_power_agreement_passed','Input agreement',None),
        ('gain_stable_within_tolerance','Gain stable',None),
        ('stability_screen_passed','All finite-window checks',None)])
    init = info.get("initialization_sensitivity", {})
    init_table = table(init.get("comparisons", []), [
        ('cold_case','Cold case',None), ('mapped_case','Mapped case',None),
        ('comparison_kind','Interpretation',None),
        ('level','Grid',None), ('cold_study_role','Cold role',None),
        ('mapped_study_role','Mapped role',None), ('mapped_source_case','Mapped seed source',None),
        ('cold_lift_N','Cold lift N','.5f'), ('mapped_lift_N','Mapped lift N','.5f'),
        ('mapped_minus_cold_lift_percent','Mapped minus cold %','+.3f'),
        ('input_agreement_within_0_5_percent','Input agreement',None),
        ('qualified_for_combined_comparison','Source/provenance checks',None),
        ('qualified_for_pure_initialization_comparison','Pure initialization qualifies',None)])
    init_gains = table(init.get("paired_gains_vs_flat_control", []), [
        ('cold_candidate','Cold candidate',None), ('mapped_candidate','Mapped candidate',None),
        ('comparison_kind','Interpretation',None),
        ('cold_flat_control','Cold flat control',None), ('mapped_flat_control','Mapped flat control',None),
        ('cold_gain_percent','Cold gain %','+.3f'), ('mapped_gain_percent','Mapped gain %','+.3f'),
        ('gain_change_percentage_points','Gain change pp','+.3f'), ('sign_agrees','Sign agrees',None),
        ('qualified_for_pure_initialization_comparison','Pure initialization qualifies',None),
        ('paired_input_agreement_within_0_5_percent','Paired input agreement',None)])
    sources = []
    for source in metadata.get('official_sources', []):
        url = str(source.get('url', ''))
        if url.startswith(('https://','http://')):
            sources.append('<li><a href="' + html.escape(url) + '">' + html.escape(url) + '</a>' +
                           (f' (page {source["page"]})' if 'page' in source else '') + '</li>')
    source_text = '<ul>' + ''.join(sources) + '</ul>' if sources else '<p>Reference-source URLs were not supplied in study_metadata.json.</p>'
    estimated = metadata.get('estimated_power', {})
    energy, duration = float(estimated.get('rated_energy_Wh',4.18)), float(estimated.get('endurance_minutes',13))
    chosen_power = energy / (duration / 60)
    planform_images=''.join(image_html(path) for path in images if path.name=='planform_lift_comparison.png')
    rotor_images=''.join(image_html(path) for path in images if path.name=='rotor_count_lift_comparison.png')
    same_hub_images=''.join(image_html(path) for path in images if path.name.startswith('same_hub_tilt_gain_'))
    image_text = ''.join(image_html(path) for path in images if path.name not in
        ('planform_lift_comparison.png','rotor_count_lift_comparison.png')
        and not path.name.startswith('same_hub_tilt_gain_'))
    flow_images = ''.join(image_html(path) + ('<p>Actual instantaneous snapshots at t=1.2 s, on the z=−4 cm plane. These are not time-averaged flow fields. Snapshot sources, initialization and numerical regimes are retained in flow_provenance.json.</p>'
        if path.name == 'flow_comparison.png' else '') for path in sorted(out.glob('flow_*.png')))
    layout_geometry_image = image_html(out/'circle_geometry.png') if (out/'circle_geometry.png').is_file() else ''
    tilt_geometry_image = image_html(out/'tilt_convention.png') if (out/'tilt_convention.png').is_file() else ''
    gpu_section = ''
    gpu_path = out/'gpu_benchmark_accuracy_results.json'
    if gpu_path.is_file():
        gpu = json.loads(gpu_path.read_text())
        reference = next(r for r in gpu['rows'] if r['variant'] == gpu['reference'])
        candidate = next(r for r in gpu['rows'] if r['variant'] == 'cuda_mpi2')
        change = 100*(candidate['full_wall_s']/reference['full_wall_s']-1)
        gpu_image = image_html(out/'gpu_benchmark_speed_comparison.png') if (out/'gpu_benchmark_speed_comparison.png').is_file() else ''
        gpu_table = table(gpu['rows'], [('variant','Backend',None),
            ('full_wall_s','Full runner seconds','.3f'),('steady_wall_s','Steady solver seconds','.3f'),
            ('mean_lift_difference_percent','Lift change vs best CPU %','+.6f'),
            ('final_U_relative_L2_percent','Final U L2 %','.6f'),
            ('final_p_relative_L2_percent','Final p L2 %','.6f'),
            ('continuity_review_flag','Continuity review flag retained',None)])
        gpu_section = ('<h2>Measured CPU and CUDA feasibility</h2>'
            f'<p>The private CUDA pressure-solver bridge executed on the RTX N1X. The controlled '
            f'{gpu["mesh"]["cells"]:,}-cell benchmark used the same frozen flow state from '
            f'{gpu["simulated_window_s"][0]:g} to {gpu["simulated_window_s"][1]:g} s. '
            f'CUDA took {candidate["full_wall_s"]:.3f} s versus {reference["full_wall_s"]:.3f} s '
            f'for the faster fresh native CPU reference ({change:.1f}% longer). '
            'CPU remains the study default. Build/download time is excluded from these run timings.</p>'
            '<p>Force, inferred power and final-field checks met their registered limits. '
            'An intermediate local-continuity flag is retained; the final pressure correction '
            'was below the native continuity envelope. The speed requirement failed independently. '
            'This warm fine-grid performance probe is separate from the lift-study averages '
            'and does not establish cold coarse-grid throughput.</p>' + gpu_image + gpu_table
            + '<p>A separate official stdpar GPU implementation covers incompressible flow. '
            'The pressure-only bridge benchmark above cannot establish its performance. '
            'At the 2 November 2026 check, official core/develop identifies the GPU-branch merge '
            '(68a81857, API 2609). No native stdpar OpenFOAM build or actuator test was run here: '
            'nvc++ is absent, and the Foundation actuator requires a verified target-branch port '
            'and suitable memory mode. Published large-grid speedups are not measurements for '
            'this 922,576-cell study. See the '
            '<a href="../gpu_feasibility/native_stdpar/README.md">source-based feasibility assessment '
            'and local inventory</a>, '
            '<a href="https://gitlab.com/openfoam/core/openfoam/-/tree/develop">official current source</a> '
            'and <a href="https://pasc-conference.org/pasc26/presentation/?id=pap122&amp;sess=sess174">'
            'authors’ incompressible-flow research</a>.</p>')
    interval_text = ', '.join(f'{a:g}–{b:g} s' for a,b in sorted({(round(r['start_s'],9),round(r['stop_s'],9)) for r in records}))
    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Tello-based rotor refinement — actual CFD</title>
<style>body{{font:16px/1.6 system-ui,sans-serif;max-width:1200px;margin:36px auto;padding:0 24px;color:#1e293b}}h1{{line-height:1.2}}img{{max-width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:12px}}td,th{{padding:7px;text-align:left;border-bottom:1px solid #ccd}}.scroll{{overflow-x:auto}}.note{{padding:16px;background:#fff3d5}}code{{background:#eee}}</style></head><body>
<h1>Maximum-lift comparison: planform, rotor count, then tilt and spacing</h1>
{banner}
{selection_section}
<p><strong>Primary objective: maximum gross vertical lift at the common electrical budget, within the current per-layout nearest-hub spacing limits.</strong> {html.escape(info['optimization_range'])} Any eligible four/eight-rotor, square/circular or flat/tilted candidate may win. The raw largest qualified tested force remains primary: no 1% near-band or footprint preference overrides a resolved lift gain. A separately listed smaller candidate within 0.25% is descriptive only, not a replacement winner, statistical tie or confidence bound.</p>
<p>Explicit Circle8 analysis maximum: <code>{html.escape(str(info['optimization_constraints']['circle_max_spacing_cm']))}</code> cm (None means the historical 10 cm default). This postprocessing constraint changes optimization eligibility only. Actual force, inferred power, averaging windows, source/input checks, comparison qualification and historical generation declarations remain unchanged. Outside-limit exploratory points remain controls and carry B in heatmaps; they cannot be optimization winners.</p>
<p><strong>Matched-footprint benchmarks are retained, outside the optimization range.</strong> The four-rotor 23.62 cm box control has nearest hubs 16 cm apart (about 16.06 cm when tilted 10°); legacy four-rotor square d=10 cm means actual nearest spacing 20 cm. Such rows remain in matched planform/count comparisons, flat references, mesh and initialization diagnostics, and raw tables, but cannot be search winners. CSV flags distinguish source/input qualification, nominal comparison eligibility and optimization eligibility. Actual centers determine this range; legacy parameter labels do not.</p>
<p><strong>Primary ranking scope: VALIDATION only, separated by planform, initialization and numerical method.</strong> Each regime's finest available qualified grid supplies its tested best; there is no pooled winner across unmatched regimes. SCREENING is shown separately and is never pooled with validation replicas of the same geometry. Explicit SENSITIVITY cases remain visible but cannot enter nominal rankings or mesh groups.</p>
<h2>1. Square versus circular eight-rotor layouts</h2>
<p>These comparisons hold rotor count, electrical budget, propeller size, tilt, projected box width/depth (within 0.05%), grid, loss map, initial-state regime and verified numerical method fixed. Nearest hub spacing can differ substantially inside the same outer box. Equal box dimensions do not imply equal maximum span or convex-hull area, and one matched box does not establish an inherent layout advantage over a broader spacing search. Missing matched completed pilots remain pending; no result is inferred from an earlier layout.</p>{layout_geometry_image}{planform_images}{planforms}{maxspan_section}
<h2>2. Four versus eight rotors</h2>
<p>These pairs use the same electrical budget, projected box, tilt, grid, initialization and verified numerical method. The same square four-rotor control can serve both eight-rotor planforms. Planforms are labelled explicitly: a circular eight-rotor versus square four-rotor pair also changes hub positions, so it is not a count-only change.</p>{rotor_images}{matched}
<h2>3. Tilt and nearest hub spacing</h2>
{tilt_geometry_image}
<ul>{''.join(findings)}</ul>
<h3>Isolated tilt comparison at fixed hub positions</h3>
<p>These VALIDATION pairs compare a tilted candidate against flat rotors at the same unordered 3D hub positions, rounded to 12 decimal places. Rotor count, diameter/thickness, electrical budget, source/loss law, domain, grid/quadrature, study role, initialization regime, verified numerical method and averaging interval must match. Only tilt changes; its projected swept-disk envelope can change. This differs from the nominal flat d=10 cm comparison, which can also change hub spacing. It also differs from a fixed-box tilt experiment, whose adjusted hub positions are not admitted as an identical-hub pair.</p>
<p>Each pair has its own independent first/last-half qualifications, absolute flat and tilted lift-drift flags, paired-input agreement, and gain-change check. A drifting nominal wide flat control does not invalidate a separate stable flat control at the candidate's own hub spacing. Passing the finite-window screen does not prove stationarity, mesh independence or a hardware improvement, and this section does not replace the maximum-lift ranking. same_hub_tilt_comparisons.csv retains separately labelled screening and validation pairs.</p>
{same_hub_images}{same_hub_tilts}
{image_text}
<p class="note"><strong>Idealized Tello-based geometry, not a stock Tello simulation.</strong> The cases use interacting finite actuator cylinders. They do not include stock blades, fuselage, guards, motors, frame drag, synchronized blade passage or a calibrated electrical-to-thrust map. Gross lift is simulated; electrical/shaft powers are inferred through the stated assumed loss law. No conversion efficiency was fitted to the vehicle mass or endurance.</p>
<h2>Reference inputs and selected power budget</h2>
<p>The dimensional reference is the published 3-inch propeller size, exactly 0.0762 m; each actual case's diameter remains explicit in CSV/JSON. The calculation {energy:g} Wh / ({duration:g} min / 60) = {chosen_power:.8f} W defines a comparison budget from nominal battery energy and advertised maximum endurance. Ryze's endurance test describes windless forward flight at 15 km/h, whereas this CFD uses still-air, stationary rotor forcing. The chosen power is an inference, not a measured hover, maximum-power, motor or shaft operating point; usable energy during that test is unspecified. Dividing the same nominal energy by this chosen budget returns {duration:g} minutes by construction and provides no independent endurance validation. Any lower-energy-fraction cases are separate assumptions, not additional measurements.</p>
{source_text}
<p>The references supply dimensional, battery and mass inputs; they do not validate this actuator model. Each case's budget and diameter are read from metadata, rather than fixed at the earlier study's 20/40 W or 8 cm. No old results have been rescaled into new CFD samples.</p>
<h2>Read-only numerical-method audit</h2>
<p>The optional numerical audit expands the effective OpenFOAM 14 dictionaries using the existing canonicalizer. It includes fvSolution, fvSchemes, time-stepping controls and decomposition settings. Numerical signatures are attached only after the canonical digest and hashes of the current geometry and four numerical input files match the audit. The signature deliberately excludes end/averaging times and initial conditions; these remain separate comparison requirements. Missing, stale or unknown signatures cannot establish a match, even when two cases both lack metadata. Such cases remain visible and are isolated per case for ranking. Rank counts describe the decomposition input, rather than an independent observation of the process launch. Verified completed cases: {sum(bool(numerical_signature(r)) for r in records)} / {len(records)}.</p>
<h2>Geometry and operating assumptions</h2>
<p>Legacy square-perimeter centers occupy (±d,±d,0), with eight rotors adding the four side midpoints. In those old files d is nearest original-to-added spacing for eight rotors, while nearest quad hubs are 2d apart. New pilot files explicitly define their distance parameter; circular centers come from their own ring radius rather than square d. All displayed nearest spacings and projected boxes are independently derived from actual centers/normals. The supplied definition and metadata checks remain in CSV/JSON, and old geometry files are not rewritten. Missing old layout labels are explicitly inferred as square_perimeter. Negative signed tilt raises outer edges, points craft thrust inward/upward and applies air force outward/downward. Positive tilt reverses the horizontal force direction. Actual velocity and wakes can bend and mix. Synchronization is assumed to avoid contact; blade phase is not resolved. The angle grids accept either sign.</p>
<p>Projected maximum span is the greatest horizontal distance between any two points of the swept disks, irrespective of direction. Projected convex-hull area means the area enclosing the convex hull of their union, <strong>not disk-union area</strong>. Both exclude the finite actuator thickness. Flat disks use the analytic convex hull of the hubs expanded by a circle: area = hub-hull area + radius × hub-hull perimeter + π radius²; maximum span = hub-hull diameter + propeller diameter. Tilted disks use affine projected ellipses with doubled angular sampling until area/span bounds and a refinement check pass. Sampled values are lower estimates; their upper bounds, angular counts, changes and reliability flags are in CSV/JSON. The area bound must be within 1 part per million of area and the span bound within 0.2 µm; unresolved metrics are omitted rather than treated as exact. These are geometry-discretization checks, not CFD uncertainty bounds.</p>
<p>The lift-versus-box-width plots keep grid, time window, initialization, power, loss law, diameter/thickness, domain, physical source and numerical method separate. Hollow wider controls are benchmarks. Their dashed search frontiers connect nondominated sampled means inside the spacing range, not interpolated solutions or a proof of statistical/physical dominance. Maximum lift is still primary; comparisons at different footprints are labelled explicitly with box width, maximum span and convex-hull area.</p>
<p>The unchanged nominal loss map reserves 0.5 W for electronics, uses 95% ESC efficiency, subtracts 0.10 W idle loss per motor, converts 60% of the remainder to shaft power, and assigns 50% of shaft power to axial forcing: <code>Pshaft=0.60·[0.95·(Pe−0.5)−0.10N]</code>, <code>Pair=0.50Pshaft</code>. Each rotor receives Pair/N. Thrust relaxes toward (Pair/N)/max(w,1 m/s), with a 0.03 s time constant and 0.50 N cap. RPM, blade pitch and a real synchronized drive's power distribution are not predicted. Case-specific changed loss maps or tagged thickness/domain checks are kept separate from nominal ranking.</p>
<p>The configured fluid is incompressible air, ρ=1.225 kg/m³ and ν=1.5×10⁻⁵ m²/s, with laminar stress. The standard forcing thickness is 0.012 m and geometry quadrature uses 16×16 horizontal subcells with exact vertical-line intersections; actual parameters and mesh dimensions are retained per case. Overlapping forces share one pressure/velocity field. Opposing components can cancel within a cell; separate subcell counterflows and real rotor turbulence are unresolved. Domain independence and a continuous optimum require evidence beyond solver completion.</p>
<h2>Lift, mass support and ideal payload headroom</h2>
<p>Supported mass is gross vertical force divided by g={G0:g} m/s². The identical 80 g total-mass assumption is applied to BOTH layouts, retaining the requested no-added-mass comparison; the 87 g guarded-mass reference is a separate postprocessing scenario. Their weights are 0.784532 N and 0.853179 N. Guard aerodynamics are absent. Net margin is lift minus reference weight; signed ideal payload headroom is supported mass minus 80/87 g. A negative value is a deficit, not negative physical payload. Changing the reference mass affects only these derived force/headroom metrics; it does not change the fixed-geometry flow or ranking. No battery, motor, frame or synchronizer mass is newly estimated here.</p>
<p>Primary averages follow each geometry.json ({html.escape(interval_text)}). Screening uses 0.4–0.8 s; validation uses 0.8–1.2 s. An explicit study_role is honored; older cases without it are classified by their original primary interval, with provenance retained. Sensitivity roles retain their declared valid interval. A nominal role/interval mismatch, unknown interval or inconsistent initialization provenance is excluded from ranking. Re-averaging never changes a case's study role. Integration uses real time weights and interpolated endpoints. Qualification requires mean equivalent electrical input within ±0.5% of budget, loss/projection consistency within 0.05%, and source-volume error within 1% when DISK_VOLUME diagnostics are available. Missing source-volume diagnostics are reported as unchecked. Input/source qualification is separate from temporal stability. Actual input agreement tests the assumed loss law, not real motor measurements.</p>
{all_table}
<h2>Separate early screening results</h2>
<p>These shorter runs locate candidates. Their largest coarse samples retain flags for a missing finer screening check; validation replicas and later validation evidence remain in their own scope. Screening drift or small spacing/angle differences do not establish a winner.</p>{screening_table}
<h2>Validation gains versus nominal flat controls on the same grid</h2>{controls}
<p>Explicit pilot comparison-footprint targets select matching flat controls within the same planform. Old square sweeps retain the nominal square d={info['control_distance_cm']:g} cm flat control. Rings without an explicit target use their largest available flat projected box on the matching grid/regime. These rules never reinterpret a ring radius or a newly defined nearest spacing as legacy square d. Width ratios remain explicit when spacings/tilts change the footprint.</p>
<h2>Adjacent late-window sensitivity</h2>
<p>The first and last halves are independently re-averaged and qualified: validation 0.8–1.0 s versus 1.0–1.2 s; screening 0.4–0.6 s versus 0.6–0.8 s. They reuse the same histories, not independent simulations. Changing qualification can change the candidate set. Temporal standard deviation and half-window drift are not confidence intervals.</p>{late}
<p>The finite-window screen checks mean-lift drift within ±{stability['lift_drift_tolerance_percent']:g}% for both candidate and control, and the change in their paired gain within ±{stability['gain_change_tolerance_percentage_points']:g} percentage points. It also requires independent input/source qualification in all three intervals, late input change within 0.5% of budget, and candidate/control mean-input difference within 0.5% of budget in each interval. A stable gain can coexist with drifting absolute lift, so both checks are required. Passing these checks does not prove stationarity, a unique optimum or a physical performance improvement.</p>{stability_table}
<h2>Matched-geometry mesh checks at a fixed time window</h2>
<p>Each pair holds diameter, thickness, centers, normals, budget, loss map, domain, study role, initialization regime and verified numerical-method signature fixed. This includes pressure direct-coarsest settings and decomposition rank count. The initialization match includes method, initial/source times and actuator-state policy; cold and mapped histories cannot masquerade as a mesh pair. Flat controls and paired-gain comparisons also hold the verified numerical method fixed. Validation comparisons use 0.8–1.2 s consistently on coarse, medium and fine grids; screening comparisons, if present, use 0.4–0.8 s. Both histories are independently qualified. Screening/validation replicas of one coarse geometry never become a mesh pair, and sampling intervals are not silently mixed. All common-window flags remain in mesh_window_summary.csv.</p>{mesh}{paired}
<p>Absolute force changes and changes in the gain versus flat controls are distinct diagnostics. Four qualified histories are required for a paired gain. Subpercent separation, ranking changes, drift or gains comparable to refinement effects do not establish a unique optimum or proven hardware improvement. A finest-grid best is only a tested qualified sample; missing finer checks of coarser maxima remain flagged.</p>
<h2>Optional initialization sensitivity: cold versus mapped</h2>
<p>This section compares completed histories at the same geometry and grid over 0.8–1.2 s. It deliberately crosses validation/sensitivity roles and never replaces nominal rankings or mesh checks. Only matching verified numerical signatures qualify as pure initialization comparisons. Different methods are retained and labelled combined initialization/numerical-method effects; unknown settings cannot qualify as a pure comparison. Where present, a mapped start uses its own geometry's coarse U and p fields at the recorded source time; mapping and controller reinitialization policies remain explicit in initialization.json. Mapping is an initialization assumption, not a force rescaling or continuation with a fully preserved actuator state. The analyzer records the sidecar's SHA256 and its declared source/mapped-field hashes; it does not independently re-hash the large fields. Missing or inconsistent mapped provenance cannot enter nominal ranking. No mapped run is assumed present when this table is empty.</p>{init_table}
<p>A change in candidate lift alone can differ from a change in its gain relative to flat. The paired table requires both geometries under both initialization regimes, all four source/provenance qualifications, and each regime's own flat control. Matching numerical methods are preferred for each control; all four signatures must match to qualify the change as pure initialization sensitivity.</p>{init_gains}
{('<h2>Saved actual flow fields</h2>' + flow_images) if flow_images else ''}
{gpu_section}
<h2>Evidence and reproduction</h2>
<p>Complete cases: {len(records)}; unavailable/incomplete/invalid cases: {len(info['skipped_cases'])}. Cases are included only after the solver reports End. summary.csv and statistics.json hold actual-log statistics and qualification flags; late_window_summary.csv and mesh_window_summary.csv retain independently re-averaged diagnostics. Initialization comparisons and paired gains have separate CSV files, with per-case sidecar provenance retained in initialization_provenance.json. Per-case history CSV files preserve the source diagnostics. Collect the optional read-only audit with <code>python3 collect_numerics.py --root CASES --out numerical_configurations.json</code> in the OpenFOAM 14 environment, then analyze with <code>python3 analyze_refinement.py --root CASES --out results --numerics numerical_configurations.json</code>. Keep analysis_helpers.py, geometry_metrics.py, initialization_diagnostics.py, collect_numerics.py and study_metadata.json beside this script. The collector also requires prepare_mapped.py for its canonicalizer. The setup and solver files are delivered separately.</p>
<p>For a separately frozen final scope, add <code>--case-list FROZEN_CASE_NAMES.json</code>, containing a JSON list of exact direct-child case names or <code>{{"cases": ["name", "another_name"]}}</code>. Include completed controls, unsuccessful tests and valid data that fail qualification; this option never chooses a winner or filters by a result. Deferred prepared inputs may be excluded explicitly. The selection file path, SHA256, names/count, discovered/excluded inputs, terminal-evidence audit and selected failures remain in statistics.json and this report. The live/default command continues to discover all prepared geometry files recursively.</p>
</body></html>'''
    (out / 'report.html').write_text(page, encoding='utf-8')


def run(args):
    circle_limit=validate_circle_max_spacing_cm(getattr(args,'circle_max_spacing_cm',None))
    root, out = Path(args.root), Path(args.out)
    geometry_paths,selection=case_scope(root,getattr(args,'case_list',None))
    out.mkdir(parents=True, exist_ok=True)
    metadata_path = Path(args.metadata) if args.metadata else Path(__file__).with_name('study_metadata.json')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8-sig')) if metadata_path.exists() else {}
    numerics_path = getattr(args, 'numerics', None)
    numerical_audit = load_audit(numerics_path)
    control_distance = float(metadata.get('nominal_control_distance_cm', 10.))
    records, samples, skipped = [], {}, []
    for gp in geometry_paths:
        try:
            g = json.loads(gp.read_text(encoding='utf-8-sig'))
            if not all(key in g for key in ('battery_power_W','tilt_deg','rotors')):
                if selection['mode']=='explicit_exact_case_names':
                    raise ValueError('Selected geometry lacks required rotor/power/tilt metadata')
                continue
            data, volumes = read_history(gp.parent, with_source=True)
            initialization = read_initialization(gp.parent, g)
            numerics = case_numerics(gp.parent, g, numerical_audit)
            row = calculate(gp.parent, g, data, volumes=volumes, initialization=initialization, numerics=numerics,
                            circle_max_spacing_cm=circle_limit)
        except (OSError, ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
            skipped.append(dict(case=str(gp.parent), reason=str(exc))); continue
        records.append(row)
        samples[row['case']] = dict(path=gp.parent, geometry=g, history=data, volumes=volumes,
                                    initialization=initialization, numerics=numerics,circle_max_spacing_cm=circle_limit)
        np.savetxt(out / (row['case'] + '_history.csv'), data, delimiter=',', header=HISTORY_HEADER, comments='')
    records.sort(key=lambda r: (not primary(r), r['study_role'], config_key(r), level_key(r), r['nearest_spacing_cm'], r['tilt_deg'], r['case']))
    late, late_rows = late_window_diagnostics(records, samples, control_distance)
    tolerance = float(getattr(args, 'stability_tolerance_percent', .25))
    if not math.isfinite(tolerance) or tolerance <= 0:
        raise ValueError('stability tolerance must be finite and positive')
    stability = stability_diagnostics(records, late, control_distance, tolerance)
    scopes = summarize_scopes(records, control_distance)
    for scope in scopes.values():
        annotate_matched_pair_stability(scope, records, late, tolerance)
    info = dict(scopes['validation'])
    mesh = mesh_diagnostics(records, samples, control_distance)
    init = compare_initializations(records, samples, physical_geometry_signature, reaverage, control_distance)
    preliminary_reasons = []
    if getattr(args, 'preliminary', False) or metadata.get('preliminary_report', False):
        preliminary_reasons.append('The report was requested as preliminary.')
    if not any(ranking_eligible(r, 'validation') and r['level'] == 'fine' for r in records):
        preliminary_reasons.append('No completed qualified fine-grid validation result is available yet.')
    if skipped:
        scope_label='selected' if selection['mode']=='explicit_exact_case_names' else 'discovered'
        preliminary_reasons.append(f'{len(skipped)} {scope_label} cases are incomplete, unavailable or invalid.')
    if selection['excluded_terminal_case_names']:
        preliminary_reasons.append(f'{len(selection["excluded_terminal_case_names"])} excluded prepared cases have terminal solver/run evidence; review the scientific scope before treating it as final.')
    selection.update(included_complete_case_names=[r['case'] for r in records],
        included_complete_case_count=len(records),selected_skipped_cases=skipped,
        selected_skipped_case_count=len(skipped))
    info.update(cases=records, skipped_cases=skipped, control_distance_cm=control_distance,
        optimization_constraints=dict(circle_max_spacing_cm=circle_limit,
            square_and_four_rotor_max_spacing_cm=10.,
            interpretation=optimization_range_text(records),
            source='Explicit CLI user constraint' if circle_limit is not None else 'Historical 0–10 cm analysis default',
            applies_only_to='Eight rotors with layout=circular_ring',
            changes_only='Optimization eligibility and rankings; all raw metrics, source/comparison qualifications and historical input metadata are retained'),
        case_selection=selection,
        late_window_diagnostics=late, same_geometry_mesh_diagnostics=mesh,
        summaries_by_role=scopes, screening_summary=scopes['screening'],
        validation_summary=scopes['validation'], primary_ranking_scope='validation',
        late_window_stability_diagnostics=stability,
        initialization_sensitivity=init,
        lift_footprint_tradeoffs=footprint_tradeoffs(records),
        numerical_audit_source=str(numerics_path) if numerics_path else None,
        layout_case_counts={layout:sum(r['layout']==layout for r in records)
                            for layout in sorted({r['layout'] for r in records})},
        layout_metadata_mismatches=[r['case'] for r in records if not r['layout_geometry_metadata_consistent']],
        numerical_audit_summary=dict(verified_cases=sum(bool(numerical_signature(r)) for r in records),
            unknown_or_stale_cases=[dict(case=r['case'], status=r['numerical_audit_status'])
                                   for r in records if not numerical_signature(r)]),
        preliminary=bool(preliminary_reasons), preliminary_reasons=preliminary_reasons,
        role_case_counts={role: sum(r['study_role'] == role for r in records)
                          for role in (*ROLE_WINDOWS, 'sensitivity', 'unclassified')},
        role_interval_mismatches=[r['case'] for r in records if not r['role_window_consistent']],
        reference_masses_g=[80,87], standard_gravity_m_s2=G0,
        metadata_source=str(metadata_path), study_metadata=metadata,
        result_kind='Actual CFD gross vertical lift; assumed-loss inferred electrical/shaft powers; reference masses applied only in postprocessing')
    (out / 'statistics.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    write_csv(out / 'summary.csv', records)
    write_csv(out / 'planform_comparisons.csv', info['matched_planform_comparisons'])
    write_csv(out / 'rotor_count_comparisons.csv', info['matched_rotor_count_comparisons'])
    write_csv(out / 'max_span_planform_comparisons.csv', info['matched_max_span_planform_comparisons'])
    write_csv(out / 'same_hub_tilt_comparisons.csv',
        [pair for scope in scopes.values() for pair in scope['same_hub_tilt_comparisons']])
    write_csv(out / 'late_window_summary.csv', late_rows)
    write_csv(out / 'mesh_window_summary.csv', mesh['cases'])
    write_csv(out / 'stability_summary.csv', stability['cases'])
    write_csv(out / 'paired_gain_stability.csv', stability['paired_gains_vs_flat_control'])
    write_csv(out / 'initialization_comparisons.csv', init['comparisons'])
    write_csv(out / 'initialization_paired_gains.csv', init['paired_gains_vs_flat_control'])
    provenance = {name: dict(**sample['initialization']['row'],
                            recorded_manifest=sample['initialization']['manifest'])
                  for name,sample in samples.items()}
    (out / 'initialization_provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf-8')
    images = make_plots(out, records, info)
    write_report(out, info, metadata, images)
    print(json.dumps(dict(completed_cases=len(records), skipped_cases=len(skipped),
        qualified_primary_cases=sum(ranking_eligible(r, 'validation') for r in records),
        study_role_counts=info['role_case_counts'], preliminary=info['preliminary'],
        best={key: {field: entry['best_tested'][field] for field in
              ('case','level','layout','nearest_spacing_cm','projected_width_m','tilt_deg','mean_lift_N','supported_mass_g')}
              for key,entry in info['best_by_configuration'].items()}, report=str(out/'report.html')), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--metadata')
    parser.add_argument('--numerics', help='Read-only numerical_configurations.json audit; current case input hashes are checked')
    parser.add_argument('--case-list', help='Optional exact case-name JSON list or {"cases": [names]}; scope is audited independently of results/qualification')
    parser.add_argument('--circle-max-spacing-cm',type=float,default=None,
                        help='Optional circular eight-rotor optimization-only nearest-hub maximum (0–10 cm); omitted preserves legacy 10 cm for all layouts. Completed controls remain visible.')
    parser.add_argument('--preliminary', action='store_true', help='Force a preliminary-results banner')
    parser.add_argument('--stability-tolerance-percent', type=float, default=.25,
                        help='Lift drift tolerance in percent and paired-gain change tolerance in percentage points')
    run(parser.parse_args())
