"""Generalized helpers adapted from the earlier actual tilted-rotor analysis.

No fixed rotor diameter, battery budget, rotor count, or averaging window is
imposed. Electrical quantities remain inferred by each case's assumed loss map.
"""
from __future__ import annotations

import math
import re
import hashlib
import json
from pathlib import Path

import numpy as np
from geometry_metrics import swept_disk_envelope_metrics

# NumPy 2.4 removed trapz; retain identical trapezoidal integration on older hosts.
_trapezoid = np.trapezoid if hasattr(np, 'trapezoid') else np.trapz

G0 = 9.80665
REFERENCE_MASSES_G = (80., 87.)
DEFAULT_LOSS = dict(auxiliary_W=.5, esc_efficiency=.95,
                    idle_W_per_motor=.10, motor_conversion=.60, axial_fraction=.50)
LEVEL_ORDER = {"coarse": 0, "medium": 1, "fine": 2}
ROLE_WINDOWS = {"screening": (.4, .8), "validation": (.8, 1.2)}
OPTIMIZATION_MAX_NEAREST_SPACING_M = .10
LAYOUT_LABELS = {"square_perimeter": "Square perimeter", "circular_ring": "Circular ring"}
HISTORY_HEADER = ("time_s,vertical_lift_N,axial_air_work_W,inferred_shaft_power_W,"
                  "equivalent_battery_input_W,sum_rotor_thrust_N,net_reaction_x_N,net_reaction_y_N")


def config_key(row):
    return (int(row["rotors"]), float(row["battery_power_W"]), float(row["diameter_m"]),
            str(row.get("layout", "square_perimeter")))


def config_id(key):
    return f"n{key[0]}_P{key[1]:.12g}_D{key[2]:.12g}_{key[3] if len(key)>3 else 'square_perimeter'}"


def config_label(key):
    layout = key[3] if len(key)>3 else "square_perimeter"
    return f"{key[0]} rotors / {LAYOUT_LABELS.get(layout, layout)} / {key[1]:.4g} W / {100 * key[2]:g} cm props"


def flat_geometry_candidates(row, records, control_distance=10.):
    """Select geometric flat controls after the caller filters role/method/init.

    Explicit pilot footprint targets supersede the old square d=10 cm policy.
    Rings without a target use their largest available flat projected box.
    """
    rows = [r for r in records if config_key(r) == config_key(row)
        and r['level'] == row['level'] and abs(r['thickness_m']-row['thickness_m']) < 1e-10
        and abs(r['tilt_deg']) < 1e-8]
    target_w, target_d = row.get('comparison_footprint_width_m'), row.get('comparison_footprint_depth_m')
    if target_w is not None and target_d is not None:
        return [r for r in rows if np.allclose((r['projected_width_m'],r['projected_depth_m']),
            (target_w,target_d),rtol=5e-4,atol=1e-7)]
    if row.get('layout','square_perimeter') == 'square_perimeter':
        return [r for r in rows if r.get('distance_cm') is not None
                and abs(r['distance_cm']-control_distance) < 1e-8]
    if not rows:
        return []
    largest=max(r['projected_box_area_m2'] for r in rows)
    return [r for r in rows if abs(r['projected_box_area_m2']-largest) < 1e-10]


def same_projected_box(a,b):
    return bool(np.allclose((a['projected_width_m'],a['projected_depth_m']),
                           (b['projected_width_m'],b['projected_depth_m']),rtol=5e-4,atol=1e-7))


def loss_budget(n, power, loss):
    aux, esc, idle, motor, axial = (float(loss[k]) for k in
        ("auxiliary_W", "esc_efficiency", "idle_W_per_motor", "motor_conversion", "axial_fraction"))
    if not (0 < esc <= 1 and 0 < motor <= 1 and 0 < axial <= 1):
        raise ValueError("conversion assumptions must lie in (0,1]")
    available = esc * (power - aux) - n * idle
    if n < 1 or available <= 0 or aux < 0 or idle < 0:
        raise ValueError("invalid rotor count or insufficient battery budget")
    shaft = motor * available
    return dict(shaft_budget_W=shaft, axial_air_budget_W=axial * shaft)


def read_history(case, with_source=False):
    """Read complete logs, including optional MPI prefixes and checkpoints.

    Source diagnostics must already be globally reduced. Conflicting duplicate
    TILT lines at one time in a single log are rejected as an accounting error.
    Later checkpoint logs replace older entries at the same timestamp.
    """
    case = Path(case)
    production = (case / "log.foamRun").read_text(errors="replace")
    if not re.search(r"^\s*(?:\[\d+\]\s*)?End\s*$", production, re.M):
        raise ValueError("solver has not reported End")
    if re.search(r"FOAM FATAL|MPI_ABORT", production):
        raise ValueError("production log contains a fatal error")
    startup = sorted(case.glob("log.startup*"), key=lambda p: p.stat().st_mtime)
    texts = [p.read_text(errors="replace") for p in startup if p.is_file()] + [production]
    rows, volumes = {}, {}
    for text in texts:
        local = {}
        for line in text.splitlines():
            match = re.match(r"^(?:\[\d+\]\s*)?TILT\s+(.+?)\s*$", line)
            if match:
                values = [float(v) for v in match.group(1).split()]
                if len(values) != 8 or not np.isfinite(values).all():
                    raise ValueError("expected eight finite TILT values")
                t = values[0]
                if t in local and not np.allclose(local[t], values, rtol=2e-6, atol=1e-9):
                    raise ValueError(f"conflicting MPI/source diagnostics at t={t:g}")
                local[t] = values
            match = re.match(r"^(?:\[\d+\]\s*)?DISK_VOLUME\s+(\d+)\s+(\S+)", line)
            if match:
                volumes[int(match.group(1))] = float(match.group(2))
        rows.update(local)
    if len(rows) < 3:
        raise ValueError("insufficient TILT history")
    data = np.asarray([rows[t] for t in sorted(rows)], dtype=float)
    return (data, volumes) if with_source else data


def window(data, start, stop):
    if stop <= start or data[0, 0] > start + 1e-7 or data[-1, 0] < stop - 1e-7:
        raise ValueError(f"history does not cover valid interval {start:g}–{stop:g} s")
    def at(t):
        return [t] + [np.interp(t, data[:, 0], data[:, i]) for i in range(1, data.shape[1])]
    return np.vstack((at(start), data[(data[:, 0] > start) & (data[:, 0] < stop)], at(stop)))


def time_mean(data, column):
    return float(_trapezoid(data[:, column], data[:, 0]) / (data[-1, 0] - data[0, 0]))


def projected_footprint(geometry, n, radius, theta):
    centers = np.asarray(geometry["centers"], dtype=float)
    normals = np.asarray(geometry.get("normals", []), dtype=float)
    if centers.shape == (n, 2):
        centers = np.column_stack((centers, np.zeros(n)))
    if normals.size == 0 and abs(theta) < 1e-10:
        normals = np.tile((0., 0., 1.), (n, 1))
    if centers.shape != (n, 3) or normals.shape != (n, 3):
        raise ValueError("one 3D center and normal are required per rotor")
    if not np.isfinite(centers).all() or not np.isfinite(normals).all():
        raise ValueError("non-finite rotor geometry")
    if not np.allclose(np.linalg.norm(normals, axis=1), 1, atol=1e-6, rtol=0):
        raise ValueError("non-unit rotor normal")
    if not np.allclose(normals[:, 2], math.cos(math.radians(theta)), atol=1e-6, rtol=0):
        raise ValueError("normals do not match the common tilt")
    radial = np.asarray(geometry.get("radials", []), dtype=float)
    if radial.shape == (n, 3) and not np.allclose(normals[:, :2],
            radial[:, :2] * math.sin(math.radians(theta)), atol=1e-6, rtol=0):
        raise ValueError("normal sign does not match signed radial tilt")
    ex = radius * np.sqrt(np.maximum(0., 1 - normals[:, 0] ** 2))
    ey = radius * np.sqrt(np.maximum(0., 1 - normals[:, 1] ** 2))
    return (float(np.max(centers[:, 0] + ex) - np.min(centers[:, 0] - ex)),
            float(np.max(centers[:, 1] + ey) - np.min(centers[:, 1] - ey)))


def qualified(row):
    return (row["power_within_0_5_percent"] and row["loss_diagnostic_consistent"]
            and row["force_projection_diagnostic_consistent"]
            and row.get("actuator_volume_check_passed") is not False)


def primary(row):
    return (row.get("study_role") != "sensitivity" and not row["is_domain_check"]
            and not row["is_model_sensitivity"])


def read_initialization(case, geometry):
    """Read provenance only; recorded field hashes are not re-hashed here."""
    path = Path(case) / "initialization.json"
    raw = path.read_bytes() if path.exists() else None
    manifest = json.loads(raw.decode("utf-8-sig")) if raw is not None else {}
    if not isinstance(manifest, dict):
        raise ValueError("initialization.json must contain an object")
    embedded = geometry.get("initialization", {})
    embedded = embedded if isinstance(embedded, dict) else {"method": embedded}
    def value(name, *alternatives, default=None):
        for source in (geometry, embedded, manifest):
            for key in (name, *alternatives):
                if key in source:
                    return source[key]
        return default
    explicit = value("initialization_method", "method")
    mapped_manifest = bool(manifest.get("mapped_fields") or manifest.get("map_command"))
    label = str(explicit).strip().lower() if explicit is not None else ""
    mapped = mapped_manifest or any(word in label for word in ("mapped", "mapfields", "warm"))
    cold = any(word in label for word in ("cold", "zero"))
    family = "mapped" if mapped else "cold" if cold or not label else "other"
    method = "mapped_coarse_fields" if family == "mapped" else "cold_start" if family == "cold" else label
    start = float(value("initialization_start_time_s", "target_start_time_s", "start_time_s", "initial_time_s", default=.6 if mapped else 0.))
    source_time = value("initialization_source_time_s", "source_time_s", "source_time_directory")
    source_time = float(source_time) if source_time is not None else None
    source_case = value("initialization_source_case", "source_case")
    controller = str(value("initialization_controller_state_policy", "controller_state_policy",
        default="unspecified mapped controller state" if mapped else "cold default actuator initialization"))
    provenance_ok = bool(not (cold and mapped_manifest) and start >= 0 and
                         start <= float(geometry["averaging_start_s"]) + 1e-9)
    if mapped:
        provenance_ok = bool(provenance_ok and raw is not None and source_case is not None
            and source_time is not None and math.isfinite(source_time)
            and math.isclose(start, source_time, rel_tol=0, abs_tol=1e-9)
            and manifest.get("source_unchanged") is not False)
    source_fields = manifest.get("source_case_files_before", {})
    if not isinstance(source_fields, dict) or not isinstance(manifest.get("mapped_fields", {}), dict):
        raise ValueError("initialization field-hash groups must contain objects")
    recorded_source_hashes = {k: v.get("sha256") for k,v in source_fields.items()
        if isinstance(v, dict) and k.endswith(("/U", "/p"))}
    recorded_mapped_hashes = {k: v.get("sha256") for k,v in manifest.get("mapped_fields", {}).items()
        if isinstance(v, dict)}
    def hashes_complete(values):
        return ({k.rsplit("/", 1)[-1] for k in values} == {"U", "p"}
                and all(isinstance(v, str) and re.fullmatch(r"[0-9a-fA-F]{64}", v)
                        for v in values.values()))
    if mapped:
        provenance_ok = bool(provenance_ok and hashes_complete(recorded_source_hashes)
            and hashes_complete(recorded_mapped_hashes)
            and manifest.get("source_unchanged") is True
            and manifest.get("consistent_geometry") is not False
            and manifest.get("actual_source_and_target_fvModels_and_rotorParameters_byte_identical") is not False
            and controller != "unspecified mapped controller state")
    row = dict(initialization_method=method, initialization_family=family,
        initialization_declared_method=explicit,
        initialization_provenance_source=("geometry_and_sidecar" if raw is not None else
            "geometry_only" if explicit is not None else "legacy_inferred_cold"),
        initialization_start_time_s=start, initialization_source_time_s=source_time,
        initialization_source_case=source_case,
        initialization_mapping_method=value("mapping_method"),
        initialization_controller_state_policy=controller,
        initialization_source_sha256=value("source_sha256"),
        initialization_manifest_sha256=hashlib.sha256(raw).hexdigest() if raw is not None else None,
        initialization_recorded_source_field_hashes=json.dumps(recorded_source_hashes, sort_keys=True),
        initialization_recorded_mapped_field_hashes=json.dumps(recorded_mapped_hashes, sort_keys=True),
        initialization_provenance_consistent=provenance_ok,
        initialization_field_hashes_reverified_by_analyzer=False)
    return dict(row=row, manifest=manifest)


def initialization_key(row):
    """Hold the initial-state regime fixed while source fields vary by geometry."""
    return (row.get("initialization_method", "cold_start"),
            row.get("initialization_start_time_s", 0.), row.get("initialization_source_time_s"),
            row.get("initialization_controller_state_policy", "cold default actuator initialization"))


def numerical_signature(row):
    value = row.get("numerical_method_signature")
    return value if row.get("numerical_audit_valid") and isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else None


def same_numerics(a, b):
    """Unknown or stale settings cannot establish a method match."""
    signature = numerical_signature(a)
    return signature is not None and signature == numerical_signature(b)


def numerical_key(row):
    signature = numerical_signature(row)
    return signature if signature is not None else "unknown_case_" + row["case"]


def study_role(geometry):
    """Keep old short screening runs separate from longer validation replicas.

    The role is inferred from the geometry's ORIGINAL primary interval, never
    from a diagnostic re-average. Unexpected intervals remain unclassified.
    """
    explicit = geometry.get("study_role")
    start = float(geometry["averaging_start_s"])
    stop = float(geometry["averaging_stop_s"])
    if explicit is not None:
        role, source = str(explicit).strip().lower(), "explicit_metadata"
        if role not in (*ROLE_WINDOWS, "sensitivity"):
            raise ValueError(f"unknown study_role {explicit!r}")
    else:
        role = next((name for name, bounds in ROLE_WINDOWS.items()
                     if np.allclose((start, stop), bounds, rtol=0, atol=1e-8)), "unclassified")
        source = "legacy_primary_window_inference" if role != "unclassified" else "unclassified_interval"
    expected = ROLE_WINDOWS.get(role)
    consistent = (bool(start >= 0 and stop > start) if role == "sensitivity" else
                  expected is not None and bool(np.allclose((start, stop), expected, rtol=0, atol=1e-8)))
    return role, source, consistent


def comparison_eligible(row, role):
    """Qualified nominal rows, including out-of-search matched controls."""
    return (primary(row) and qualified(row) and row.get("study_role") == role
            and row.get("role_window_consistent", False)
            and row.get("layout_geometry_metadata_consistent", True)
            and row.get("initialization_provenance_consistent", True))


def optimization_spacing_in_range(row):
    nearest = row.get('nearest_spacing_m')
    maximum = row.get('optimization_max_nearest_spacing_m',OPTIMIZATION_MAX_NEAREST_SPACING_M)
    return bool(nearest is not None and math.isfinite(nearest)
                and -1e-12 <= nearest <= maximum+1e-10)


def validate_circle_max_spacing_cm(value):
    if value is None:return None
    value=float(value)
    if not math.isfinite(value) or not 0 <= value <= 100*OPTIMIZATION_MAX_NEAREST_SPACING_M:
        raise ValueError('circle maximum spacing must be finite and within 0–10 cm')
    return value


def optimization_range_text(records):
    circle_limit=next((r.get('analysis_circle_max_spacing_cm') for r in records
                       if r.get('analysis_circle_max_spacing_cm') is not None),None)
    if circle_limit is None:
        return 'Actual nearest hub spacing 0–10 cm. Wider matched-box controls remain comparison/diagnostic references, not search winners.'
    return (f'Actual nearest hub spacing 0–{circle_limit:g} cm for circular eight-rotor layouts; '
            '0–10 cm for Square eight-rotor and four-rotor layouts. Outside-limit completed tests remain comparison/diagnostic controls, not search winners. '
            'This explicit analysis constraint does not change historical generation metadata or CFD inputs.')


def ranking_eligible(row, role):
    """Actual nearest spacing, rather than a legacy d label, sets search scope."""
    return comparison_eligible(row,role) and optimization_spacing_in_range(row)


def centers_only_hash(centers):
    """Permutation-invariant 3D hub multiset, rounded to 12 decimal places.

    Normals, layout labels and operating settings are intentionally absent.
    Comparisons using this hash must separately match their full protocol.
    Duplicate/coincident hubs remain separate entries in the multiset.
    """
    centers=np.asarray(centers,dtype=float)
    if centers.ndim==2 and centers.shape[1]==2:
        centers=np.column_stack((centers,np.zeros(len(centers))))
    if centers.ndim!=2 or centers.shape[1]!=3 or not len(centers) or not np.isfinite(centers).all():
        raise ValueError('Require finite 3D hub centers')
    rounded=sorted(tuple(0. if round(float(v),12)==0 else round(float(v),12)
                         for v in center) for center in centers)
    return hashlib.sha256(json.dumps(rounded,separators=(',',':')).encode()).hexdigest()


def calculate(case, geometry, data, start=None, stop=None, volumes=None, initialization=None, numerics=None,
              circle_max_spacing_cm=None):
    circle_max_spacing_cm=validate_circle_max_spacing_cm(circle_max_spacing_cm)
    n, power = int(geometry["rotors"]), float(geometry["battery_power_W"])
    radius = float(geometry["radius_m"] if "radius_m" in geometry else float(geometry["diameter_m"]) / 2)
    diameter = float(geometry.get("diameter_m", 2 * radius))
    thickness = float(geometry["thickness_m"])
    layout = str(geometry.get('layout','square_perimeter'))
    if layout not in LAYOUT_LABELS:
        raise ValueError('unsupported layout: '+layout)
    theta = float(geometry["tilt_deg"])
    distance = float(geometry['distance_cm']) if geometry.get('distance_cm') is not None else None
    if n < 1 or power <= 0 or radius <= 0 or thickness <= 0 or (distance is not None and distance < 0) or not -90 < theta < 90:
        raise ValueError("invalid rotor geometry or operating point")
    if not math.isclose(diameter, 2 * radius, abs_tol=1e-10, rel_tol=0):
        raise ValueError("radius/diameter metadata disagree")
    width, depth = projected_footprint(geometry, n, radius, theta)
    metric_normals = geometry.get('normals', [[0.,0.,1.]]*n)
    envelope_metrics = swept_disk_envelope_metrics(geometry['centers'],metric_normals,radius)
    centers = np.asarray(geometry['centers'],dtype=float)
    pair_distances = np.linalg.norm(centers[:,None,:2]-centers[None,:,:2],axis=2)
    np.fill_diagonal(pair_distances,np.inf)
    nearest = float(np.min(pair_distances)) if n>1 else None
    declared_nearest = geometry.get('nearest_spacing_m')
    nearest_error = abs(float(declared_nearest)-nearest) if declared_nearest is not None and nearest is not None else None
    radii = np.linalg.norm(centers[:,:2],axis=1)
    ring_radius = float(geometry.get('center_ring_radius_m',np.mean(radii))) if layout=='circular_ring' else None
    ring_error = float(np.max(np.abs(radii-ring_radius))) if ring_radius is not None else None
    declared_width = geometry.get('projected_footprint_width_m',geometry.get('projected_width_m',geometry.get('footprint_side_m')))
    declared_depth = geometry.get('projected_footprint_depth_m',geometry.get('projected_depth_m',declared_width))
    box_error = max(abs(float(declared_width)-width),abs(float(declared_depth)-depth)) if declared_width is not None and declared_depth is not None else None
    geometry_ok = all(v is None or v<=1e-6 for v in (nearest_error,ring_error,box_error))
    default_definition = ('Legacy square half-side d; nearest original-to-added spacing d for eight rotors, nearest hub spacing 2d for four.'
        if layout=='square_perimeter' else 'Ring radius and explicit centers define geometry; no square half-side is inferred.')
    distance_definition = str(geometry.get('distance_parameter_definition',default_definition))
    parameter_label = (f'Center-ring radius {100*ring_radius:g} cm' if ring_radius is not None else
        f'Nearest hub spacing {100*nearest:g} cm' if 'distance_parameter_definition' in geometry else
        f'Square d={distance:g} cm' if distance is not None else 'Explicit square hub centers')
    rotor_geometry_hash = hashlib.sha256(json.dumps(dict(layout=layout,radius_m=radius,
        thickness_m=thickness,centers=np.round(centers,12).tolist(),
        normals=np.round(np.asarray(geometry.get('normals',[[0,0,1]]*n)),12).tolist()),
        sort_keys=True,separators=(',',':')).encode()).hexdigest()
    start = float(geometry["averaging_start_s"] if start is None else start)
    stop = float(geometry["averaging_stop_s"] if stop is None else stop)
    loss = {k: float(geometry.get("loss_model", {}).get(k, v)) for k, v in DEFAULT_LOSS.items()}
    budget = loss_budget(n, power, loss)
    w = window(data, start, stop)
    means = [time_mean(w, i) for i in range(1, 8)]
    first = time_mean(window(data, start, (start + stop) / 2), 1)
    last = time_mean(window(data, (start + stop) / 2, stop), 1)
    variance = float(_trapezoid((w[:, 1] - means[0]) ** 2, w[:, 0]) / (stop - start))
    shaft = w[:, 2] / loss["axial_fraction"]
    inferred_input = loss["auxiliary_W"] + (shaft / loss["motor_conversion"]
                       + n * loss["idle_W_per_motor"]) / loss["esc_efficiency"]
    consistency = max(float(np.max(np.abs(inferred_input - w[:, 4])) / power),
        float(np.max(np.abs(shaft - w[:, 3])) / budget["shaft_budget_W"]))
    projection = float(np.max(np.abs(w[:, 1] - w[:, 5] * math.cos(math.radians(theta)))) /
                       max(abs(means[0]), 1e-10))
    tag = str(geometry.get("tag", ""))
    domain = "domain" in (tag + " " + Path(case).name).lower()
    init_tag = any(word in tag.lower() for word in ("initial", "cold", "warm", "mapped"))
    sensitivity = (not domain) and (any(word in tag.lower() for word in
        ("half", "thin", "thick")) or ("sens" in tag.lower() and not init_tag)
        or any(not math.isclose(loss[k], v,
        abs_tol=1e-10, rel_tol=0) for k, v in DEFAULT_LOSS.items()))
    volume_error, volume_pass = None, None
    role, role_source, role_consistent = study_role(geometry)
    if volumes:
        expected = math.pi * radius ** 2 * thickness
        if set(volumes) != set(range(n)):
            volume_pass = False
        else:
            volume_error = 100 * max(abs(v / expected - 1) for v in volumes.values())
            volume_pass = bool(math.isfinite(volume_error) and volume_error <= 1.)
    row = dict(case=Path(case).name, rotors=n, battery_power_W=power,
        diameter_m=diameter, radius_m=radius, thickness_m=thickness,
        distance_cm=distance, tilt_deg=theta,
        layout=layout,layout_label=LAYOUT_LABELS[layout],
        layout_metadata_source='explicit_geometry' if 'layout' in geometry else 'legacy_inferred_square_perimeter',
        geometry_parameter_label=parameter_label,
        distance_parameter_definition=distance_definition,rotor_geometry_sha256=rotor_geometry_hash,
        rotor_centers_sha256=centers_only_hash(centers),rotor_centers_hash_rounding_decimal_places=12,
        purpose=geometry.get('purpose'),experiment_stage=geometry.get('experiment_stage'),
        generation_spacing_above_optimizer_limit_is_matched_control=geometry.get('spacing_above_optimizer_limit_is_matched_control'),
        declared_max_span_m=geometry.get('max_span_m'),
        nearest_spacing_m=nearest,nearest_spacing_cm=100*nearest if nearest is not None else None,
        declared_nearest_spacing_m=declared_nearest,nearest_spacing_metadata_error_m=nearest_error,
        center_ring_radius_m=ring_radius,center_ring_radius_metadata_error_m=ring_error,
        projected_box_metadata_error_m=box_error,layout_geometry_metadata_consistent=bool(geometry_ok),
        comparison_footprint_width_m=geometry.get('comparison_footprint_width_m'),
        comparison_footprint_depth_m=geometry.get('comparison_footprint_depth_m'),
        outer_edge_angle_label=("Flat" if abs(theta) < 1e-10 else
            f"Outer edges {'raised' if theta < 0 else 'lowered'} {abs(theta):g}°"),
        projected_width_m=width, projected_depth_m=depth, projected_box_area_m2=width * depth,
        level=str(geometry.get("level", Path(case).name.split("_")[0])),
        mesh_cells=int(geometry.get("mesh_cells", 0)),
        inner_xy_cell_width_m=geometry.get("inner_xy_cell_width_m"),
        inner_z_cell_width_m=geometry.get("inner_z_cell_width_m"),
        domain_xy_m=geometry.get("domain_xy_m"),
        domain_z_m=geometry.get('domain_z_m'),physical_source_sha256=geometry.get('source_sha256'),
        quadrature_subcells_xy=geometry.get("quadrature_subcells_xy", geometry.get("quadrature_subcells")),
        tag=tag, is_domain_check=domain, is_model_sensitivity=sensitivity,
        study_role=role, study_role_source=role_source, role_window_consistent=role_consistent,
        primary_averaging_start_s=float(geometry["averaging_start_s"]),
        primary_averaging_stop_s=float(geometry["averaging_stop_s"]),
        start_s=start, stop_s=stop, final_time_s=float(data[-1, 0]), samples_in_window=len(w),
        mean_lift_N=means[0], mean_air_power_W=means[1], mean_shaft_power_W=means[2],
        mean_equivalent_battery_input_W=means[3], mean_sum_rotor_thrust_N=means[4],
        mean_reaction_x_N=means[5], mean_reaction_y_N=means[6],
        mean_horizontal_reaction_N=math.hypot(means[5], means[6]),
        target_shaft_power_W=budget["shaft_budget_W"], target_air_power_W=budget["axial_air_budget_W"],
        lift_std_N=math.sqrt(max(0., variance)), first_half_lift_N=first, last_half_lift_N=last,
        half_window_drift_percent=100 * (last - first) / means[0] if means[0] else None,
        power_error_percent=100 * (means[3] / power - 1),
        power_within_0_5_percent=bool(abs(means[3] / power - 1) <= .005),
        loss_diagnostic_error_percent=100 * consistency,
        loss_diagnostic_consistent=bool(consistency <= .0005),
        force_projection_error_percent=100 * projection,
        force_projection_diagnostic_consistent=bool(projection <= .0005),
        actuator_volume_max_error_percent=volume_error, actuator_volume_check_passed=volume_pass,
        supported_mass_g=1000 * means[0] / G0, loss_model=loss)
    for mass in REFERENCE_MASSES_G:
        label = f"{mass:g}g"
        row[f"reference_weight_{label}_N"] = mass / 1000 * G0
        row[f"net_margin_{label}_N"] = means[0] - mass / 1000 * G0
        row[f"ideal_payload_headroom_{label}_g"] = row["supported_mass_g"] - mass
    row["qualified_for_comparison"] = bool(qualified(row))
    row.update((initialization if initialization is not None else
                read_initialization(case, geometry))["row"])
    row.update(numerics if numerics is not None else dict(
        numerical_method_signature=None, numerical_audit_valid=False,
        numerical_audit_status="not_supplied",
        numerical_method_label="Unknown numerical method (no verified audit)",
        declared_numerical_method_signature=geometry.get("solver_configuration_sha256"),
        numerical_rank_count=None, numerical_direct_coarsest_p=None,
        numerical_direct_coarsest_pFinal=None))
    row.update(envelope_metrics)
    circle_applies=circle_max_spacing_cm is not None and n==8 and layout=='circular_ring'
    maximum=circle_max_spacing_cm/100 if circle_applies else OPTIMIZATION_MAX_NEAREST_SPACING_M
    row.update(analysis_circle_max_spacing_cm=circle_max_spacing_cm,
        analysis_circle_spacing_limit_applied=circle_applies,
        optimization_max_nearest_spacing_m=maximum,
        optimization_constraint_source='explicit_circle_cli_limit' if circle_applies else 'legacy_0_to_10_cm_analysis_default')
    in_range = optimization_spacing_in_range(row)
    nominal_role = row['study_role'] in ROLE_WINDOWS
    row.update(optimization_spacing_in_range=in_range,
        eligible_for_nominal_comparison=bool(nominal_role and comparison_eligible(row,row['study_role'])),
        optimization_eligible=bool(nominal_role and ranking_eligible(row,row['study_role'])),
        optimization_control_reason=(f'Benchmark/reference only: actual nearest hub spacing exceeds {100*maximum:g} cm search limit; retained for matched comparisons and diagnostics.'
            if nearest is not None and nearest>maximum+1e-10 else
            f'Nearest spacing unavailable or outside 0–{100*maximum:g} cm search range.' if not in_range else
            f'Inside 0–{100*maximum:g} cm search range; nominal ranking also requires role, source, power, geometry and initialization qualification.'),
        projected_convex_hull_area_definition='Convex hull of the union of horizontally projected swept disks; not union area; excludes actuator thickness.')
    return row
