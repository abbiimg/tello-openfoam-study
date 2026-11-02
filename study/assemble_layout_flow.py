"""Assemble native ParaView snapshots; pixels are cropped, CFD values unchanged.

Input JSON: {"panels": [{"image": "...png", "label": "..."}],
"footprint_cm": 23.62, "snapshot_time_s": 1.2}. Render all panels with the
requests recorded in layout_flow_provenance.json before using this script.
"""
import argparse
import hashlib
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    m = json.loads(a.manifest.read_text())
    panels = m['panels']
    if len(panels) not in (2, 3):
        raise ValueError('Expected two or three matched panels')
    fig, axes = plt.subplots(1, len(panels), figsize=(6 * len(panels) + .5, 6.5),
                             layout='constrained', squeeze=False)
    hashes = {}
    for ax, panel in zip(axes[0], panels):
        path = Path(panel['image'])
        if not path.is_absolute():
            path = a.manifest.parent / path
        picture = mpimg.imread(path)
        if picture.shape[:2] != (900, 1100):
            raise ValueError('Expected a common 1100 by 900 rendering')
        ax.imshow(picture[150:750, 200:900], interpolation='nearest')
        ax.set_title(panel['label'], fontsize=14)
        ax.set_axis_off()
        hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    fig.colorbar(ScalarMappable(norm=Normalize(0, 12), cmap='viridis'), ax=list(axes[0]),
                 label='Air speed [m/s]', ticks=[0, 3, 6, 9, 12], shrink=.75, pad=.025)
    fig.suptitle('Actual OpenFOAM flow: matched flat layouts\n'
        f"Coarse pilot grid · 7.62 cm propellers · {m['footprint_cm']:g} cm square footprint · inferred 19.3 W input budget each",
        fontsize=13)
    fig.supxlabel(f"Snapshot at {m['snapshot_time_s']:g} s, 4 cm below the rotor plane; same camera and speed scale.\n"
        'Actuator model; blade shapes and synchronization are not resolved. These are instantaneous fields.', fontsize=10)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(json.dumps(dict(image=str(a.out), crop_pixels_xy=[200, 150, 900, 750], source_sha256=hashes)))


if __name__ == '__main__':
    main()
