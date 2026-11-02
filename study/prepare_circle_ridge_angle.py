"""Prepare one cold circle angle at the exact hubs of a selected flat control.

Does not run meshing utilities or CFD. The flat control and selection rationale
are recorded so this bounded adaptive choice can be reviewed and reproduced.
"""
from argparse import ArgumentParser, Namespace
from pathlib import Path
import hashlib
import json
import shutil
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_completed import atomic_json
from generate_design_case import generate


def hubs(g):
    return sorted(tuple(round(float(v), 12) for v in center) for center in g['centers'])


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('--flat-case', required=True, type=Path)
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--journal', required=True, type=Path)
    parser.add_argument('--rationale', required=True)
    parser.add_argument('--owner', default='openfoam:openfoam')
    a = parser.parse_args()
    if a.journal.exists():
        raise FileExistsError('Inspect the existing circle-angle journal before repeating')
    source = a.flat_case.resolve()
    raw = (source / 'geometry.json').read_bytes()
    flat = json.loads(raw)
    assert flat['layout'] == 'circular_ring' and int(flat['rotors']) == 8
    assert abs(float(flat['tilt_deg'])) < 1e-12
    requested = flat['requested_input']
    spacing = float(requested['nearest_spacing_cm'])
    result = generate(Namespace(root=str(a.root.resolve()), rotors=8,
        layout='circular_ring', nearest_spacing_cm=spacing, projected_box_width_cm=None,
        tilt_deg=-10., diameter_m=float(flat['diameter_m']),
        thickness_m=float(flat['thickness_m']), power_w=float(flat['battery_power_W']),
        level='coarse', end_s=1.2, average_start_s=.8, study_role='validation',
        tag='circleridgeangle', owner=a.owner))
    target = Path(result['case'])
    tilted = json.loads((target / 'geometry.json').read_text())
    assert hubs(flat) == hubs(tilted), 'Tilt comparison changed rotor centers'
    assert flat['source_sha256'] == tilted['source_sha256']
    if a.owner:
        user, group = a.owner.split(':', 1)
        shutil.chown(target / 'log.design_input_generation', user=user, group=group)
    atomic_json(a.journal, dict(stage='one_circle_ridge_angle', intended=1,
        prepared=[dict(**result, tilt_deg=-10., rotors=8)],
        paired_flat_case=str(source), paired_geometry_sha256=hashlib.sha256(raw).hexdigest(),
        same_hubs_verified=True, no_solver_launched=True, no_mesh_utility_launched=True,
        rationale=a.rationale))
    print(json.dumps(dict(journal=str(a.journal), case=str(target), same_hubs=True)))


if __name__ == '__main__':
    main()
