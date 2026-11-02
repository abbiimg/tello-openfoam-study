"""Compare flat square-perimeter and regular-octagon geometry; no CFD estimate."""
from pathlib import Path
import json
import math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Rectangle


def main():
    out = Path(__file__).resolve().parent/'results'
    diameter, d = 7.62, 8.
    phi = math.pi/8
    square = np.array([[-d,-d],[0,-d],[d,-d],[d,0],[d,d],[0,d],[-d,d],[-d,0]])
    radius = d/math.cos(phi)
    angles = phi+np.arange(8)*math.pi/4
    circular = np.column_stack((radius*np.cos(angles),radius*np.sin(angles)))
    spacing = 2*d*math.tan(phi)
    width = 2*d+diameter
    same_spacing_width = d/math.tan(phi)+diameter
    fig, axes = plt.subplots(1,2,figsize=(11.8,6.7),layout='constrained',sharex=True,sharey=True)
    for ax, centers, title, minimum in zip(axes,(square,circular),
            ('Current square arrangement','Eight hubs on one circle'),(d,spacing)):
        for x,y in centers:
            ax.add_patch(Circle((x,y),diameter/2,facecolor='#38bdf8',edgecolor='#0369a1',alpha=.30,lw=1.3))
        ax.scatter(centers[:,0],centers[:,1],s=22,color='#0c4a6e',zorder=5)
        if ax is axes[0]:
            ax.plot([-d,d,d,-d,-d],[-d,-d,d,d,-d],color='#64748b',ls=':',lw=1)
        else:
            ax.add_patch(Circle((0,0),radius,fill=False,edgecolor='#64748b',ls=':',lw=1))
        ax.add_patch(Rectangle((-width/2,-width/2),width,width,fill=False,edgecolor='#94a3b8',ls='--'))
        ax.set(aspect='equal',xlim=(-13,13),ylim=(-14,13),xlabel='x [cm]',ylabel='y [cm]',
            title=f'{title}\nNearest centres: {minimum:.2f} cm')
        ax.annotate('',xy=(width/2,-12.8),xytext=(-width/2,-12.8),
            arrowprops=dict(arrowstyle='<->',color='#475569'))
        ax.text(0,-12.1,f'{width:.2f} cm overall width',ha='center',fontsize=9,color='#334155')
        ax.grid(alpha=.14);ax.set_axisbelow(True)
    fig.suptitle('Circle versus square at the same overall width\n7.62 cm propellers; flat swept disks',fontsize=15)
    fig.supxlabel('Geometry comparison only. Shaded disks show propeller sweep, without guards.\n'
        'Overlap is allowed under the synchronization assumption; this figure does not predict lift.',fontsize=10)
    out.mkdir(exist_ok=True)
    fig.savefig(out/'circle_geometry.png',dpi=180,bbox_inches='tight')
    plt.close(fig)
    metrics=dict(kind='Geometric calculation, not CFD or a lift estimate',units='cm',
        propeller_diameter=diameter,square_d=d,equal_width=width,
        circle_orientation_deg=22.5,circle_center_radius=radius,
        circle_nearest_spacing_at_equal_width=spacing,
        circle_width_at_equal_nearest_spacing=same_spacing_width,
        square_centers=square.tolist(),circle_equal_width_centers=circular.tolist(),
        footprint_definition='axis-aligned width and depth of flat swept disks')
    (out/'circle_geometry_comparison.json').write_text(json.dumps(metrics,indent=2)+'\n')
    print(json.dumps(metrics,indent=2))


if __name__ == '__main__':
    main()
