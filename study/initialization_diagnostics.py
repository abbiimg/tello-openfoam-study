"""Optional same-grid initialization sensitivity; never changes nominal ranks."""
from __future__ import annotations

import math

from analysis_helpers import (config_key, initialization_key, qualified,
                              numerical_signature, same_numerics, flat_geometry_candidates)


def compare_initializations(records, samples, physical_signature, reaverage, control_distance=10.):
    groups, cache = {}, {}
    for row in records:
        # Initialization sensitivity is allowed to cross study roles deliberately.
        # Thickness/loss/domain sensitivities remain outside these nominal-physics pairs.
        if row["is_domain_check"] or row["is_model_sensitivity"]:
            continue
        signature = (row["level"], row["mesh_cells"],
                     physical_signature(row, samples[row["case"]]))
        groups.setdefault(signature, []).append(row)
    def at(row):
        if row["case"] not in cache:
            cache[row["case"]] = reaverage(samples[row["case"]], .8, 1.2)
        return cache[row["case"]]
    def eligible(row):
        return bool(qualified(row) and row["initialization_provenance_consistent"])
    def flat_candidates(row):
        g = samples[row["case"]]["geometry"]
        pool = [r for r in records if not r["is_domain_check"] and not r["is_model_sensitivity"]
            and r["level"] == row["level"] and r["mesh_cells"] == row["mesh_cells"]
            and config_key(r) == config_key(row)
            and initialization_key(r) == initialization_key(row)
            and math.isclose(r["thickness_m"], row["thickness_m"], abs_tol=1e-10, rel_tol=0)
            and r["loss_model"] == row["loss_model"]
            and all(samples[r["case"]]["geometry"].get(k) == g.get(k)
                    for k in ("domain_xy_m", "domain_z_m", "source_sha256"))]
        return flat_geometry_candidates(row,pool,control_distance)
    comparisons, paired, skipped = [], [], []
    for rows in groups.values():
        cold = [r for r in rows if r["initialization_family"] == "cold"]
        mapped = [r for r in rows if r["initialization_family"] == "mapped"]
        for cold_row in cold:
            for mapped_row in mapped:
                try:
                    c, w = at(cold_row), at(mapped_row)
                except (ValueError, KeyError, TypeError, ZeroDivisionError) as exc:
                    skipped.append(dict(cold_case=cold_row["case"], mapped_case=mapped_row["case"],
                                        reason=str(exc))); continue
                valid = bool(eligible(c) and eligible(w))
                method_match = same_numerics(c, w)
                both_known = bool(numerical_signature(c) and numerical_signature(w))
                kind = ("pure_initialization" if method_match else
                        "combined_initialization_and_numerical_method" if both_known else
                        "initialization_with_unknown_numerical_method")
                difference = 100 * (w["mean_equivalent_battery_input_W"] -
                                    c["mean_equivalent_battery_input_W"]) / c["battery_power_W"]
                comparisons.append(dict(cold_case=c["case"], mapped_case=w["case"],
                    cold_study_role=c["study_role"], mapped_study_role=w["study_role"],
                    level=c["level"], mesh_cells=c["mesh_cells"], rotors=c["rotors"],
                    battery_power_W=c["battery_power_W"], diameter_m=c["diameter_m"],
                    distance_cm=c["distance_cm"], tilt_deg=c["tilt_deg"], start_s=.8, stop_s=1.2,
                    layout=c['layout'],nearest_spacing_cm=c['nearest_spacing_cm'],
                    cold_method=c["initialization_method"], mapped_method=w["initialization_method"],
                    cold_numerical_signature=numerical_signature(c),
                    mapped_numerical_signature=numerical_signature(w),
                    numerical_methods_match=method_match, comparison_kind=kind,
                    cold_rank_count=c.get("numerical_rank_count"),
                    mapped_rank_count=w.get("numerical_rank_count"),
                    cold_direct_coarsest_p=c.get("numerical_direct_coarsest_p"),
                    mapped_direct_coarsest_p=w.get("numerical_direct_coarsest_p"),
                    mapped_source_case=w["initialization_source_case"],
                    mapped_source_time_s=w["initialization_source_time_s"],
                    cold_source_sha256=c["initialization_source_sha256"],
                    mapped_source_sha256=w["initialization_source_sha256"],
                    cold_lift_N=c["mean_lift_N"], mapped_lift_N=w["mean_lift_N"],
                    cold_inferred_input_W=c["mean_equivalent_battery_input_W"],
                    mapped_inferred_input_W=w["mean_equivalent_battery_input_W"],
                    cold_half_window_drift_percent=c["half_window_drift_percent"],
                    mapped_half_window_drift_percent=w["half_window_drift_percent"],
                    cold_source_qualified=bool(qualified(c)), mapped_source_qualified=bool(qualified(w)),
                    cold_provenance_consistent=c["initialization_provenance_consistent"],
                    mapped_provenance_consistent=w["initialization_provenance_consistent"],
                    qualified_for_combined_comparison=valid,
                    qualified_for_initialization_comparison=bool(valid and method_match and abs(difference) <= .5),
                    qualified_for_pure_initialization_comparison=bool(valid and method_match and abs(difference) <= .5),
                    input_difference_percent_of_budget=difference,
                    input_agreement_within_0_5_percent=bool(valid and abs(difference) <= .5),
                    mapped_minus_cold_lift_percent=(100 * (w["mean_lift_N"] / c["mean_lift_N"] - 1)
                                                   if valid else None)))
                if any(r['case']==c['case'] for r in flat_candidates(c)):
                    continue
                controls = []
                for row in (c, w):
                    available = []
                    for reference in flat_candidates(row):
                        try:
                            record = at(reference)
                        except (ValueError, KeyError, TypeError, ZeroDivisionError):
                            continue
                        if eligible(record):
                            available.append(record)
                    matching = [r for r in available if same_numerics(row, r)]
                    if matching:
                        available = matching
                    controls.append(available)
                if not valid or any(len(rows) != 1 for rows in controls):
                    continue
                rc, rw = (rows[0] for rows in controls)
                cg = 100 * (c["mean_lift_N"] / rc["mean_lift_N"] - 1)
                wg = 100 * (w["mean_lift_N"] / rw["mean_lift_N"] - 1)
                power = max(abs(100 * (candidate["mean_equivalent_battery_input_W"] -
                    reference["mean_equivalent_battery_input_W"]) / candidate["battery_power_W"])
                    for candidate, reference in ((c,rc),(w,rw)))
                signatures = [numerical_signature(r) for r in (c,rc,w,rw)]
                all_known = all(signatures)
                pure = bool(all_known and len(set(signatures)) == 1)
                kind = ("pure_initialization" if pure else
                        "combined_initialization_and_numerical_method" if all_known else
                        "initialization_with_unknown_numerical_method")
                paired.append(dict(cold_candidate=c["case"], mapped_candidate=w["case"],
                    cold_flat_control=rc["case"], mapped_flat_control=rw["case"],
                    level=c["level"], start_s=.8, stop_s=1.2, distance_cm=c["distance_cm"],
                    layout=c['layout'],nearest_spacing_cm=c['nearest_spacing_cm'],
                    tilt_deg=c["tilt_deg"], cold_method=c["initialization_method"],
                    mapped_method=w["initialization_method"], cold_gain_percent=cg,
                    cold_candidate_numerical_signature=signatures[0],
                    cold_control_numerical_signature=signatures[1],
                    mapped_candidate_numerical_signature=signatures[2],
                    mapped_control_numerical_signature=signatures[3],
                    numerical_methods_match_all_four=pure, comparison_kind=kind,
                    qualified_for_combined_comparison=True,
                    qualified_for_pure_initialization_comparison=bool(pure and power <= .5),
                    mapped_gain_percent=wg, gain_change_percentage_points=wg-cg,
                    sign_agrees=(int(cg>0)-int(cg<0) == int(wg>0)-int(wg<0)),
                    all_four_histories_source_and_provenance_qualified=True,
                    maximum_candidate_control_input_difference_percent_of_budget=power,
                    paired_input_agreement_within_0_5_percent=bool(power <= .5)))
    return dict(basis="Optional same-geometry, same-grid cold versus mapped comparison over 0.8–1.2 s; deliberately crosses validation/sensitivity roles and never changes nominal ranking or mesh groups. Only matching VERIFIED numerical signatures qualify as pure initialization sensitivity; mixed/unknown methods are retained and explicitly labelled combined/unresolved effects.",
        comparisons=comparisons, paired_gains_vs_flat_control=paired,
        cases=list(cache.values()), skipped_pairs=skipped,
        recorded_field_hashes_are_not_independently_rehashed_by_analyzer=True)
