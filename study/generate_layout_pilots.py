"""Prepare matched-footprint cold layout/count pilots; never launch a solver.

Stage1: square and regular circular eight-rotor layouts, both flat.
Stage2: flat four-rotor control of the same projected width/depth.
New distance_cm explicitly denotes nearest horizontal hub spacing.
"""
from pathlib import Path
import argparse
import json
import math
import shutil
import subprocess
import sys

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--journal',type=Path,required=True)
    p.add_argument('--owner')
    p.add_argument('--stage',choices=('all','layout','rotor_count'),default='all')
    a=p.parse_args()
    root=a.root.resolve();here=Path(__file__).resolve().parent
    root.mkdir(parents=True,exist_ok=True)
    private_generator=root/'_layout_input_generator'
    private_generator.mkdir(exist_ok=True)
    for filename in ('generate_tello.py','base_generator.py'):
        shutil.copy2(here/filename,private_generator/filename)
    d=.08;diameter=.0762;r=diameter/2;h=.012;half=h/2
    width=2*d+diameter
    square=[(-d,-d,0),(d,-d,0),(d,d,0),(-d,d,0),(0,-d,0),(d,0,0),(0,d,0),(-d,0,0)]
    radius=d/math.cos(math.pi/8)
    circular=[(radius*math.cos(math.pi/8+k*math.pi/4),radius*math.sin(math.pi/8+k*math.pi/4),0) for k in range(8)]
    specs=[(8,'layoutpilot_square','square_perimeter','layout_pilot',square),
           (8,'layoutpilot_circle','circular_ring','layout_pilot',circular),
           (4,'rotorcountpilot','square_perimeter','rotor_count_pilot',square[:4])]
    records=(json.loads(a.journal.read_text())['cases']
             if a.stage=='rotor_count' and a.journal.exists() else [])
    def save():
        a.journal.parent.mkdir(parents=True,exist_ok=True)
        temporary=a.journal.with_suffix('.updated')
        temporary.write_text(json.dumps(dict(cases=records,comparison_footprint_m=[width,width]),indent=2)+'\n')
        temporary.replace(a.journal)
    for n,tag,layout,stage,centers in specs:
        if a.stage=='layout' and stage!='layout_pilot':continue
        if a.stage=='rotor_count' and stage!='rotor_count_pilot':continue
        nearest=min(math.hypot(x[0]-y[0],x[1]-y[1]) for i,x in enumerate(centers) for y in centers[i+1:])
        base_distance_cm=d*100 if n==4 else nearest*100
        before={x.name for x in root.iterdir() if x.is_dir()}
        subprocess.run([sys.executable,str(private_generator/'generate_tello.py'),'--root',str(root),
            '--rotors',str(n),'--distances',str(base_distance_cm),'--angles','0',
            '--level','coarse','--tag',tag,'--study-role','validation',
            '--end','1.2','--average-duration','.4'],check=True)
        fresh=[x for x in root.iterdir() if x.is_dir() and x.name not in before
               and (x/'geometry.json').is_file()]
        assert len(fresh)==1,fresh
        case=fresh[0]
        if n==4:
            target=case.with_name(case.name.replace(f'_d{round(base_distance_cm*100):04d}_',f'_d{round(nearest*100*100):04d}_'))
            if target.exists():raise FileExistsError(target)
            assert case.resolve().parent==root and target.resolve().parent==root
            case.rename(target);case=target
        g=json.loads((case/'geometry.json').read_text())
        radials=[(x/math.hypot(x,y),y/math.hypot(x,y),0) for x,y,z in centers]
        normals=[(0,0,1)]*n
        bounds=[[min(c[k]-r for c in centers),max(c[k]+r for c in centers)] for k in (0,1)]
        extents=[b[1]-b[0] for b in bounds]
        assert all(math.isclose(v,width,abs_tol=1e-12) for v in extents)
        g.update(layout=layout,purpose='layout_comparison',experiment_stage=stage,
            centers=centers,radials=radials,normals=normals,
            distance_cm=nearest*100,nearest_spacing_m=nearest,
            generated_base_square_parameter_cm=base_distance_cm,
            distance_parameter_definition='nearest horizontal rotor-center distance',
            comparison_footprint_width_m=width,comparison_footprint_depth_m=width,
            projected_bounds_xy_m=bounds,projected_footprint_xy_m=extents,
            footprint_side_m=width,projected_footprint_m=width,footprint_m=width,
            forcing_footprint_side_m=width,forcing_footprint_xy_m=extents,
            flat_footprint_side_m=width,forcing_z_extent_m=[-half,half],
            footprint_definition='axis-aligned projected rotor-sweep width and depth',
            max_span_m=max(math.dist(x,y) for x in centers for y in centers)+diameter)
        if layout=='circular_ring':g['center_ring_radius_m']=radius
        (case/'geometry.json').write_text(json.dumps(g,indent=2)+'\n')
        def vectors(values):return '('+' '.join('('+' '.join(f'{v:.12g}' for v in row)+')' for row in values)+')'
        parameters='FoamFile {format ascii;class dictionary;object rotorParameters;}\n'
        parameters+=f'centres {vectors(centers)};\nnormals {vectors(normals)};\nradials {vectors(radials)};\n'
        parameters+=f'radius {r:.12g};halfThickness {half:.12g};tiltSin 0;tiltCos 1;batteryPower {g["battery_power_W"]:.15g};auxiliaryPower .5;etaEsc .95;idlePower .10;etaMotor .60;etaAxial .50;\n'
        (case/'constant/rotorParameters').write_text(parameters)
        records.append(dict(case=case.name,stage=stage,layout=layout,rotors=n,state='preparing'))
        save()
        command=[sys.executable,str(here/'prepare_serial_cold.py'),'--case',str(case)]
        if a.owner:command+=['--owner',a.owner]
        subprocess.run(command,check=True)
        records[-1].update(state='ready',nearest_spacing_cm=nearest*100,projected_width_cm=width*100)
        save()
    print(json.dumps(dict(prepared=len(records),journal=str(a.journal))))

if __name__=='__main__':main()
