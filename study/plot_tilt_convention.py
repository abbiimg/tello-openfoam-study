"""Draw the radial tilt convention used by the actuator geometry (not CFD)."""
import argparse
import math
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.8), sharex=True, sharey=True,
                             layout='constrained')
    for ax, angle, label in zip(axes, (-10, 0, 10), (
        'Outer edges raised 10°\nThrust toward craft center',
        'Level rotors\nVertical thrust',
        'Inner edges raised 10°\nThrust away from craft center')):
        theta = math.radians(angle)
        nx, nz = math.sin(theta), math.cos(theta)
        cx, radius = 8., 3.81
        dx, dz = radius * nz, -radius * nx
        ax.axhline(0, color='#cbd5e1', lw=1, ls='--')
        ax.plot((cx-dx, cx+dx), (-dz, dz), color='#334155', lw=4)
        ax.scatter([cx], [0], color='#334155', s=25, zorder=3)
        ax.scatter([0], [0], color='#64748b', marker='+', s=60)
        ax.annotate('craft center', (0, 0), xytext=(0, -1), fontsize=9)
        for sign, color in ((1, '#15803d'), (-1, '#2563eb')):
            ax.annotate('', (cx+sign*3*nx, sign*3*nz), (cx, 0),
                        arrowprops=dict(arrowstyle='-|>', color=color, lw=2))
        ax.set_title(label, fontsize=11)
        ax.text(.04, .93, f'CSV angle θ = {angle:+g}°', transform=ax.transAxes, fontsize=10)
        ax.set(xlim=(-.5, 12.5), ylim=(-3.8, 4.), xlabel='Radial distance from craft center [cm]')
        ax.set_aspect('equal')
        ax.grid(alpha=.15)
    axes[0].set_ylabel('Height [cm]')
    fig.suptitle('Tilt direction used in the simulations', fontsize=15)
    fig.legend(handles=[Line2D([0], [0], color='#334155', lw=4, label='Swept rotor plane'),
        Line2D([0], [0], color='#15803d', lw=2, label='Rotor reaction on craft'),
        Line2D([0], [0], color='#2563eb', lw=2, label='Force on air')],
        loc='lower center', bbox_to_anchor=(.5, -.07), ncol=3, frameon=False)
    fig.supxlabel('Geometry diagram: one representative 7.62 cm rotor. Hub shown at 8 cm only to illustrate orientation.', fontsize=10)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(a.out, dpi=180, bbox_inches='tight', facecolor='white')
    plt.close(fig)


if __name__ == '__main__':
    main()
