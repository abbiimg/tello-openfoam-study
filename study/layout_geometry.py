"""Pure geometry for square/circular four/eight-rotor actuator designs.

All lengths are metres and angles are signed degrees. No filesystem or solver
operation occurs here. Positive tilt points craft thrust up/out; negative tilt
raises the outer edges and applies air force down/out.
"""
from __future__ import annotations

import hashlib
import json
import math

LAYOUTS = ('square_perimeter', 'circular_ring')
CORE_XY_M = .168
CORE_Z_M = .042
OPTIMIZER_MAX_SPACING_M = .10


def _finite_positive(value, name):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(name+' must be finite and positive')
    return value


def canonical_layout(rotors, requested_layout):
    if rotors not in (4,8) or requested_layout not in LAYOUTS:
        raise ValueError('Require four/eight rotors and square_perimeter/circular_ring')
    return 'square_perimeter' if rotors == 4 else requested_layout


def _centers_radials(rotors, layout, spacing):
    diagonal = math.sqrt(.5)
    if rotors == 4:
        signs = ((-1,-1),(1,-1),(1,1),(-1,1))
        centers = [(x*spacing/2,y*spacing/2,0.) for x,y in signs]
        radials = [(x*diagonal,y*diagonal,0.) for x,y in signs]
        return centers,radials,None
    if layout == 'square_perimeter':
        signs = ((-1,-1),(1,-1),(1,1),(-1,1),(0,-1),(1,0),(0,1),(-1,0))
        centers = [(x*spacing,y*spacing,0.) for x,y in signs]
        radials = [(x/math.hypot(x,y),y/math.hypot(x,y),0.) for x,y in signs]
        return centers,radials,None
    ring = spacing/(2*math.sin(math.pi/8))
    directions = [math.pi/8+k*math.pi/4 for k in range(8)]
    radials = [(math.cos(angle),math.sin(angle),0.) for angle in directions]
    centers = [(ring*x,ring*y,0.) for x,y,_ in radials]
    return centers,radials,ring


def _bounds(centers,normals,radius,half_thickness):
    physical=[];forcing=[]
    for k in (0,1):
        extents=[radius*math.sqrt(max(0.,1-normal[k]*normal[k])) for normal in normals]
        physical.append([min(c[k]-e for c,e in zip(centers,extents)),
                         max(c[k]+e for c,e in zip(centers,extents))])
        forced=[e+half_thickness*abs(n[k]) for e,n in zip(extents,normals)]
        forcing.append([min(c[k]-e for c,e in zip(centers,forced)),
                        max(c[k]+e for c,e in zip(centers,forced))])
    return physical,forcing


def geometry(rotors, requested_layout, nearest_spacing_m, tilt_deg=0., diameter_m=.0762,
             thickness_m=.012, enforce_core=True):
    """Build actual envelopes, retaining unit radial directions at zero spacing."""
    layout=canonical_layout(rotors,requested_layout)
    spacing=float(nearest_spacing_m);theta=float(tilt_deg)
    diameter=_finite_positive(diameter_m,'diameter_m')
    thickness=_finite_positive(thickness_m,'thickness_m')
    if not math.isfinite(spacing) or spacing<0:
        raise ValueError('Nearest spacing must be finite and nonnegative')
    if not math.isfinite(theta) or abs(theta)>45:
        raise ValueError('Signed tilt must lie between -45 and +45 degrees')
    centers,radials,ring=_centers_radials(rotors,layout,spacing)
    sn,cs=math.sin(math.radians(theta)),math.cos(math.radians(theta))
    normals=[(sn*x,sn*y,cs) for x,y,_ in radials]
    radius,half=diameter/2,thickness/2
    physical,forcing=_bounds(centers,normals,radius,half)
    zextent=radius*abs(sn)+half*abs(cs)
    within_xy=all(abs(v)<=CORE_XY_M+1e-12 for bounds in forcing for v in bounds)
    within_z=zextent<=CORE_Z_M+1e-12
    if enforce_core and not (within_xy and within_z):
        raise ValueError('Finite actuator support extends outside the uniform source core '
                         '(±0.168 m XY / ±0.042 m Z)')
    actual=min(math.hypot(a[0]-b[0],a[1]-b[1]) for i,a in enumerate(centers) for b in centers[i+1:])
    widths=[hi-lo for lo,hi in physical]
    forcing_widths=[hi-lo for lo,hi in forcing]
    flat_widths=[max(c[k] for c in centers)-min(c[k] for c in centers)+diameter for k in (0,1)]
    result=dict(rotors=rotors,layout=layout,requested_layout=requested_layout,
        four_rotor_layout_equivalence=('Four equally spaced circular hubs are the same canonical square quad; no second physical design.'
                                      if rotors==4 else None),
        centers=[list(v) for v in centers],radials=[list(v) for v in radials],
        normals=[list(v) for v in normals],tilt_deg=theta,diameter_m=diameter,
        radius_m=radius,thickness_m=thickness,half_thickness_m=half,
        requested_nearest_spacing_m=spacing,nearest_spacing_m=actual,distance_cm=100*actual,
        distance_parameter_definition='nearest horizontal rotor-center distance',
        center_ring_radius_m=ring,
        hub_circumradius_m=max(math.hypot(c[0],c[1]) for c in centers),
        projected_bounds_xy_m=physical,projected_footprint_xy_m=widths,
        projected_footprint_width_m=widths[0],projected_footprint_depth_m=widths[1],
        footprint_side_m=max(widths),projected_footprint_m=max(widths),footprint_m=max(widths),
        forcing_bounds_xy_m=forcing,forcing_footprint_xy_m=forcing_widths,
        forcing_footprint_side_m=max(forcing_widths),forcing_z_extent_m=[-zextent,zextent],
        flat_footprint_side_m=max(flat_widths),flat_projected_footprint_xy_m=flat_widths,
        uniform_source_core_xy_halfwidth_m=CORE_XY_M,uniform_source_core_z_halfwidth_m=CORE_Z_M,
        uniform_source_core_contains_forcing=bool(within_xy and within_z),
        footprint_definition='axis-aligned projected rotor-sweep width and depth')
    result['physical_geometry_sha256']=physical_fingerprint(result)
    return result


def for_box_width(rotors, requested_layout, projected_width_m, tilt_deg=0.,
                  diameter_m=.0762, thickness_m=.012):
    """Biselect the actual envelope; zero-spacing plateaus choose their lower end."""
    target=_finite_positive(projected_width_m,'projected_width_m')
    minimum=geometry(rotors,requested_layout,0.,tilt_deg,diameter_m,thickness_m)
    low_width=minimum['projected_footprint_width_m']
    if target<low_width-1e-12:
        raise ValueError(f'Target box is smaller than the zero-spacing projected width {low_width:g} m')
    if target>2*CORE_XY_M+1e-12:
        raise ValueError('Target projected box cannot fit inside the uniform XY source core')
    if abs(target-low_width)<=1e-12:
        answer=minimum
    else:
        lo,hi=0.,2*CORE_XY_M
        upper=geometry(rotors,requested_layout,hi,tilt_deg,diameter_m,thickness_m,enforce_core=False)
        if upper['projected_footprint_width_m']<target:
            raise ValueError('Could not bracket the requested projected box')
        for _ in range(100):
            mid=(lo+hi)/2
            trial=geometry(rotors,requested_layout,mid,tilt_deg,diameter_m,thickness_m,enforce_core=False)
            if trial['projected_footprint_width_m']<target:
                lo=mid
            else:
                hi=mid
        answer=geometry(rotors,requested_layout,hi,tilt_deg,diameter_m,thickness_m)
    if max(abs(answer[k]-target) for k in ('projected_footprint_width_m','projected_footprint_depth_m'))>1e-10:
        raise ValueError('Projected-box solve did not reach the target width')
    answer.update(comparison_footprint_width_m=target,comparison_footprint_depth_m=target,
        box_width_solution_policy='Actual-envelope monotone bisection; the minimum-width plateau selects zero spacing',
        box_width_error_m=answer['projected_footprint_width_m']-target)
    return answer


def physical_fingerprint(metadata, include_operating=False):
    """Permutation-invariant physical identity; layout/radial labels are ignored.

    Circular actuator geometry is fixed by centers, unit normals and r/h.
    This also recognizes coincident, flat square/circular eight-rotor designs.
    """
    def number(value,digits=12):
        value=float(value)
        return '0' if value==0. else format(value,f'.{digits}g')
    radius=(float(metadata['radius_m']) if 'radius_m' in metadata else float(metadata['diameter_m'])/2)
    count=int(metadata['rotors'])
    if len(metadata['centers'])!=count or len(metadata['normals'])!=count:
        raise ValueError('One center and normal are required per actuator')
    actuators=sorted([number(x) for x in center]+[number(x) for x in normal]
                     for center,normal in zip(metadata['centers'],metadata['normals']))
    payload=dict(rotors=count,radius_m=number(radius),
        half_thickness_m=number(float(metadata['thickness_m'])/2),
        actuators=actuators)
    if include_operating:
        payload.update(battery_power_W=number(metadata['battery_power_W'],15),
            loss_model=metadata['loss_model'],source_sha256=metadata['source_sha256'])
    return hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
