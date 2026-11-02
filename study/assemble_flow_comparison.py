"""Assemble two native OpenFOAM/ParaView renderings with a common readable scale.

Run with Python, NumPy and Matplotlib. Inputs are the unmodified 1100x900 PNGs
from the render requests in flow_provenance.json. The same pixel crop removes
automatic annotations from both panels; no CFD values are calculated here.
"""
from pathlib import Path
import argparse
import hashlib
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--four', type=Path, required=True)
    p.add_argument('--eight', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 6.5), layout='constrained')
    for ax, path, label in zip(axes, (a.four, a.eight), ('Four rotors', 'Eight rotors')):
        picture = mpimg.imread(path)
        if picture.shape[:2] != (900, 1100):
            raise ValueError('Expected the recorded common 1100x900 rendering')
        ax.imshow(picture[150:750, 200:900], interpolation='nearest')
        ax.set_title(label, fontsize=15)
        ax.set_axis_off()
    fig.colorbar(ScalarMappable(norm=Normalize(0, 12), cmap='viridis'), ax=axes,
                 label='Air speed [m/s]', ticks=[0, 3, 6, 9, 12], shrink=.75, pad=.025)
    fig.suptitle('Actual OpenFOAM flow: flat reference layouts\n'
        '7.62 cm propellers · same 27.62 cm footprint · estimated 19.3 W total input each', fontsize=14)
    fig.supxlabel('Snapshot at 1.2 s, 4 cm below the rotor plane. Same camera, crop and speed scale.\n'
        'Actuator model; blade shapes and synchronization are not resolved.', fontsize=10)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    print(json.dumps(dict(image=str(a.out), crop_pixels_xy=[200, 150, 900, 750],
        source_sha256={str(x):hashlib.sha256(x.read_bytes()).hexdigest() for x in (a.four,a.eight)})))


if __name__ == '__main__':
    main()
