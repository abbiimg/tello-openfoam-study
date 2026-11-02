"""Publish already-rendered matched pilot snapshots with their provenance.

Run on the OpenFOAM host after prepare_flow_snapshots.py and the recorded
connected render requests. This script runs no solver or renderer.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sources', type=Path, required=True)
    p.add_argument('--out-dir', type=Path, required=True)
    a = p.parse_args()
    sources = json.loads(a.sources.read_text())
    panels, requests, widths = [], [], []
    for record in sources:
        target = Path(record['visualization_copy'])
        g = json.loads((target / 'geometry.json').read_text())
        if abs(g['tilt_deg']) > 1e-12:
            raise ValueError('This figure is for the flat pilot comparison')
        widths += [max(c[k] for c in g['centers']) - min(c[k] for c in g['centers']) + g['diameter_m']
                   for k in (0, 1)]
        time = f"{record['snapshot_time_s']:g}"
        original = sorted((target / 'images').glob(f'U_slice_{time}_*.png'))[-1]
        name = f"layout_{g['layout']}_{g['rotors']}rotors_t{time.replace('.', 'p')}.png"
        destination = a.out_dir / 'flow_sources' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(original, destination)
        label = f"{g['rotors']} rotors · {g['layout'].replace('_', ' ')}\nnearest hubs {100*g['nearest_spacing_m']:.3g} cm"
        panels.append(dict(image=str(destination.relative_to(a.out_dir)), label=label))
        requests.append(dict(case=Path(record['source_case']).name, field='U', mode='slice',
            time=time, slice_normal='z', slice_origin=[0, 0, -.04], view='+z', range=[0, 12],
            colormap='viridis', background='light', width=1100, height=900, zoom=1.8,
            rendered_image_sha256=hashlib.sha256(destination.read_bytes()).hexdigest()))
    if max(widths) - min(widths) > 1e-9 or len({r['snapshot_time_s'] for r in sources}) != 1:
        raise ValueError('Snapshot box/time mismatch')
    manifest = dict(panels=panels, footprint_cm=100*widths[0],
                    snapshot_time_s=sources[0]['snapshot_time_s'])
    panel_path = a.out_dir / 'layout_flow_panels.json'
    panel_path.write_text(json.dumps(manifest, indent=2) + '\n')
    provenance = dict(description='Actual coarse-grid final pilot velocity snapshots, not time-averaged flow',
        source_cases=sources, render_requests_for_logical_cases=requests,
        renderer='Connected OpenFOAM render tool / ParaView5.11', common_crop_pixels_xy=[200, 150, 900, 750],
        note='Rendering ran on separate verified copies. Original CFD inputs and fields were unchanged.')
    (a.out_dir / 'layout_flow_provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    subprocess.run([sys.executable, str(Path(__file__).with_name('assemble_layout_flow.py')),
        '--manifest', str(panel_path), '--out', str(a.out_dir / 'flow_layout_comparison.png')], check=True)


if __name__ == '__main__':
    main()
