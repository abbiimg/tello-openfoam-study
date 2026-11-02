#!/usr/bin/env python3
"""Compose a labelled scientific figure from the preserved, actual CFD render."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize
from PIL import Image


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=Path(__file__).resolve().parent/'results')
    args = parser.parse_args()
    out = args.out.resolve()
    case = 'finemapped_n8_e19.2923_d0800_am0750'
    raw = out/'final_flow_sources/square_inward7p5_U_slice.png'
    source = out/'final_flow_sources/square_inward7p5_source_manifest.json'
    render = out/'final_flow_sources/square_inward7p5_render.json'
    geometry = out/'final_flow_sources/square_inward7p5_geometry.json'
    rows = list(csv.DictReader((out/'summary.csv').open(newline='')))
    row, = [r for r in rows if r['case'] == case]
    lift = float(row['mean_lift_N'])
    power = float(row['mean_equivalent_battery_input_W'])
    assert abs(lift-1.3111381053597881) < 1e-11
    assert abs(power-19.293344568300032) < 1e-10
    copied = json.loads(source.read_text())[0]
    assert copied['source_unchanged'] is True
    assert copied['snapshot_time_s'] == 1.2
    assert copied['source_hashes'] == copied['copied_hashes']
    crop = (200, 150, 900, 750)
    with Image.open(raw) as original:
        assert original.size == (1100, 900)
        pixels = original.crop(crop).copy()
    fig, ax = plt.subplots(figsize=(8.8, 8))
    ax.imshow(pixels)
    ax.axis('off')
    ax.set_title('Square, 8 rotors: 8 cm nearest hubs, outer edges raised 7.5°\n'
                 'Highest tested fine-grid mean; instantaneous velocity magnitude', fontsize=12, pad=12)
    bar = fig.colorbar(plt.cm.ScalarMappable(norm=Normalize(0, 12), cmap='viridis'),
                       ax=ax, fraction=.045, pad=.025)
    bar.set_label('|U| [m/s]')
    fig.text(.5, .085, 'Snapshot: t = 1.2 s, z = −4 cm, view +z (x right, y up).',
             ha='center', fontsize=10)
    fig.text(.5, .052, f'Separate 0.8–1.2 s means: lift {lift:.4f} N; inferred electrical input {power:.3f} W.',
             ha='center', fontsize=10)
    fig.text(.5, .02, 'Interacting actuator CFD; synchronized blade motion and collisions are not resolved.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, 1))
    image = out/'flow_best_square.png'
    fig.savefig(image, dpi=170, bbox_inches='tight', pad_inches=.15)
    plt.close(fig)
    manifest = {
        'kind': 'Presentation derivative of an actual instantaneous CFD render; no new flow data',
        'case': case, 'source_render': str(raw.relative_to(out)), 'raw_render_sha256': sha(raw),
        'source_manifest_sha256': sha(source), 'render_settings_sha256': sha(render),
        'geometry_sha256': sha(geometry), 'summary_csv_sha256': sha(out/'summary.csv'),
        'crop_original_pixels_left_top_right_bottom': crop, 'magnitude_color_range_m_s': [0, 12],
        'snapshot_time_s': 1.2, 'slice_z_m': -.04, 'view': '+z',
        'mean_interval_s': [.8, 1.2], 'mean_lift_N': lift,
        'mean_inferred_electrical_input_W': power,
        'field_hashes': copied['source_hashes'], 'image_sha256': sha(image),
        'publisher_sha256': sha(Path(__file__).resolve()),
        'not_time_averaged_flow': True, 'not_unique_hardware_optimum': True,
    }
    (out/'flow_best_square_provenance.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps({'image': str(image), 'image_sha256': sha(image)}))


if __name__ == '__main__':
    main()
