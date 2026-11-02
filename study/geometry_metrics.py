"""Pure plan-view swept-disk envelope metrics; no CFD or file operations.

The convex hull encloses the union of the projected disks. Its area is NOT
the disk-union area. For flat disks, Steiner's formula is analytic. For tilted
disks, inscribed affine-circle polygons give a lower hull and explicit outer
area/diameter bounds; doubling the angular samples supplies a convergence check.
The bounds concern geometry discretization, not CFD or floating-point error.
"""
from __future__ import annotations

from functools import lru_cache
import math


def _cross(o, a, b):
    return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])


def convex_hull(points):
    """Counterclockwise hull, with point/segment degeneracies retained."""
    points = sorted(set(points))
    if len(points) < 3:
        return points
    lower, upper = [], []
    for p in points:
        while len(lower) >= 2 and _cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(points):
        while len(upper) >= 2 and _cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1]+upper[:-1]


def _hull_metrics(hull):
    n = len(hull)
    if n < 2:
        return 0., 0., 0.
    def d2(a, b):
        return (a[0]-b[0])**2+(a[1]-b[1])**2
    if n == 2:
        diameter = math.sqrt(d2(*hull))
        return 0., 2*diameter, diameter
    area = abs(math.fsum(hull[i][0]*hull[(i+1)%n][1]-
                        hull[i][1]*hull[(i+1)%n][0] for i in range(n)))/2
    perimeter = math.fsum(math.sqrt(d2(hull[i], hull[(i+1)%n])) for i in range(n))
    # Rotating antipodal calipers: linear in the number of hull vertices.
    j, diameter2 = 1, 0.
    for i in range(n):
        ni = (i+1)%n
        for _ in range(n):
            nj = (j+1)%n
            if _cross(hull[i],hull[ni],hull[nj]) <= _cross(hull[i],hull[ni],hull[j]):
                break
            j = nj
        diameter2 = max(diameter2, d2(hull[i],hull[j]),d2(hull[ni],hull[j]))
    return area, perimeter, math.sqrt(diameter2)


@lru_cache(maxsize=1024)
def _metrics(centers, normals, radius):
    flat = all(math.hypot(n[0],n[1]) <= 1e-12 for n in normals)
    if flat:
        area, perimeter, diameter = _hull_metrics(convex_hull(centers))
        return dict(projected_max_span_m=diameter+2*radius,
            projected_convex_hull_area_m2=area+radius*perimeter+math.pi*radius**2,
            projected_geometry_metric_method='analytic_flat_disk_Minkowski_hull',
            projected_geometry_metric_reliable=True,
            projected_geometry_angular_samples_per_disk=0,
            projected_max_span_bound_width_m=0., projected_convex_hull_area_bound_width_m2=0.,
            projected_geometry_refinement_span_change_m=0.,
            projected_geometry_refinement_area_change_m2=0.)
    previous = None
    for count in (256,512,1024,2048,4096):
        points = []
        angles = [(math.cos(2*math.pi*k/count),math.sin(2*math.pi*k/count)) for k in range(count)]
        for c,n in zip(centers,normals):
            horizontal = math.hypot(n[0],n[1])
            radial = (n[0]/horizontal,n[1]/horizontal) if horizontal > 1e-14 else (1.,0.)
            azimuthal = (-radial[1],radial[0])
            minor = radius*abs(n[2])
            points.extend((c[0]+minor*a*radial[0]+radius*b*azimuthal[0],
                           c[1]+minor*a*radial[1]+radius*b*azimuthal[1]) for a,b in angles)
        area, perimeter, diameter = _hull_metrics(convex_hull(points))
        # Every exact ellipse is within delta of its affine inscribed polygon.
        # Convexification preserves this inclusion. Steiner bounds the outer
        # parallel body's area; its diameter is at most diameter+2*delta.
        delta = radius*(1-math.cos(math.pi/count))
        area_error = delta*perimeter+math.pi*delta**2
        span_error = 2*delta
        change_area = abs(area-previous[0]) if previous else None
        change_span = abs(diameter-previous[1]) if previous else None
        reliable = bool(previous and area_error <= 1e-6*max(area,1e-20)
                        and span_error <= 2e-7
                        and change_area <= previous[2]+area_error+1e-14
                        and change_span <= previous[3]+span_error+1e-14)
        result = dict(projected_max_span_m=diameter if reliable else None,
            projected_convex_hull_area_m2=area if reliable else None,
            projected_geometry_metric_method='converged_inscribed_projected_ellipse_hull',
            projected_geometry_metric_reliable=reliable,
            projected_geometry_angular_samples_per_disk=count,
            projected_max_span_lower_bound_m=diameter,
            projected_max_span_upper_bound_m=diameter+span_error,
            projected_convex_hull_area_lower_bound_m2=area,
            projected_convex_hull_area_upper_bound_m2=area+area_error,
            projected_max_span_bound_width_m=span_error,
            projected_convex_hull_area_bound_width_m2=area_error,
            projected_geometry_refinement_span_change_m=change_span,
            projected_geometry_refinement_area_change_m2=change_area)
        if reliable:
            return result
        previous = area,diameter,area_error,span_error
    result['projected_geometry_metric_method']='unresolved_sampled_projected_ellipse_hull_bounds_only'
    return result


def swept_disk_envelope_metrics(centers, normals, radius):
    """Return horizontal maximum span and convex-hull area of swept disks.

    Returned sampled metrics are conservative lower estimates, with upper bounds
    and a second-resolution check. Unresolved estimates are omitted (None).
    Finite actuator thickness is deliberately excluded from swept-disk metrics.
    """
    centers = tuple((float(c[0]),float(c[1])) for c in centers)
    normals = tuple(tuple(float(v) for v in n) for n in normals)
    radius = float(radius)
    if not centers or len(centers)!=len(normals) or radius<=0 or not math.isfinite(radius):
        raise ValueError('one center and unit normal per disk, and a positive radius are required')
    if any(len(n)!=3 or not all(math.isfinite(v) for v in n) or
           abs(sum(v*v for v in n)-1)>2e-6 for n in normals):
        raise ValueError('non-finite or non-unit disk normal')
    if not all(math.isfinite(v) for c in centers for v in c):
        raise ValueError('non-finite disk center')
    norm_errors=[abs(math.sqrt(sum(v*v for v in n))-1) for n in normals]
    # The literal affine-map/Hausdorff bound assumes unit normals. Normalize
    # accepted roundoff-scale metadata, rather than allowing a semiaxis > R.
    normals=tuple(tuple(v/math.sqrt(sum(w*w for w in n)) for v in n) for n in normals)
    result=dict(_metrics(centers,normals,radius))
    result['projected_geometry_normal_max_norm_error']=max(norm_errors)
    result['projected_geometry_normal_policy']='Accepted unit-normal tolerance checked, then normalized for projected ellipse metrics.'
    return result
