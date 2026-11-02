"""Publish four verified native ParaView snapshots; never render or run CFD.

Initial publication runs on the OpenFOAM host, with source/copy files available:
  python3 publish_layout_stage_flow.py [--out layout_stage/nearest8_v2]
Portable reassembly needs only the delivered provenance and flow_sources/:
  python3 publish_layout_stage_flow.py --reassemble --out DELIVERED_STAGE
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent
WORK=HERE.parents[1]/'work'
CASES={
    'square_flat':'finemapped_n8_e19.2923_d0800_az0000',
    'square_inward10':'finemapped_n8_e19.2923_d0800_am1000',
    'circle_flat':'finecircle_flat_candidate_circular_ring_n8_mapped_689ac2e20f88',
    'circle_inward10':'finecircle_inward_candidate_circular_ring_n8_mapped_8846f63e5424'}
REQUEST=dict(field='U',component='Magnitude',mode='slice',slice_normal='z',
    slice_origin=[0,0,-.04],view='+z',time='1.2',range=[0,12],colormap='viridis',
    background='light',width=1100,height=900,zoom=1.8)
CROP=[200,150,900,750]


def load(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def hashes(root,expected):
    actual={}
    for relative in expected:
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts:raise ValueError('Escaping source manifest path')
        path=root/p
        if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink():
            raise ValueError('Aliased source manifest path')
        actual[relative]=digest(path)
    if actual!=expected:raise ValueError('Source/copy bytes no longer match source manifest: '+str(root))
    return actual


def display_metadata(metadata):
    return dict(time=metadata.get('time'),bounds=metadata.get('bounds'),is_2d=metadata.get('is_2d'),
        mode=metadata.get('mode'),slice=metadata.get('slice'),view=metadata.get('view'),
        color={k:metadata.get('color',{}).get(k) for k in ('field','component','range')},
        fields=metadata.get('fields'),patches=metadata.get('patches'))


def copy_checked(source,destination):
    source=Path(source);destination=Path(destination);expected=digest(source)
    if destination.exists():
        if destination.is_symlink() or digest(destination)!=expected:
            raise ValueError('Existing published source differs: '+str(destination))
    else:
        destination.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,destination)
    if digest(source)!=expected or digest(destination)!=expected:raise ValueError('Copy/source changed during publication')
    return expected


def assemble(out,provenance):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.image as mpimg
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize
    fig,axes=plt.subplots(2,2,figsize=(12.7,11.2),layout='constrained')
    for index,panel_id in enumerate(('square_flat','circle_flat','square_inward10','circle_inward10')):
        panel=next(p for p in provenance['panels'] if p['id']==panel_id)
        image_path=out/panel['published_png'];geometry_path=out/panel['published_geometry']
        if digest(image_path)!=panel['png_sha256'] or digest(geometry_path)!=panel['geometry_sha256']:
            raise ValueError('Delivered PNG/geometry hash mismatch: '+panel_id)
        picture=mpimg.imread(image_path)
        if picture.shape[:2]!=(900,1100):raise ValueError('Expected identical 1100×900 native panels')
        ax=axes[index//2,index%2];x0,y0,x1,y1=CROP
        ax.imshow(picture[y0:y1,x0:x1],interpolation='nearest');ax.set_axis_off()
        family='Square' if panel_id.startswith('square') else 'Circle'
        angle='flat' if panel_id.endswith('_flat') else 'outer edges raised 10°'
        marker='' if panel['late_window_stability_screen_passed'] is True else '†'
        ax.set_title(f'{family} · {angle}\nMean vertical lift (0.8–1.2 s): {panel["mean_lift_N"]:.5f} N{marker}',fontsize=12)
    fig.colorbar(ScalarMappable(norm=Normalize(0,12),cmap='viridis'),ax=list(axes.flat),
        label='Instantaneous air speed |U| [m/s]',ticks=[0,3,6,9,12],shrink=.8,pad=.015)
    fig.suptitle('Actual OpenFOAM velocity snapshots — fine grid, t = 1.2 s\n'
        'Eight rotors · nearest hubs 8 cm · 7.62 cm actuator disks · modeled 19.29 W electrical budget',fontsize=14)
    fig.supxlabel('Slice z = −4 cm, view +z; identical camera, crop and 0–12 m/s viridis scale. Velocity fields are instantaneous, not time averaged.\n'
        'Finite actuator forcing; blade shapes, blade phase and synchronization are unresolved. † = row late-window screen fails/unavailable.\n'
        'Upstream coarse initialization numerics differ across layouts; these images do not isolate a layout effect.',fontsize=9)
    image=out/'flow_comparison.png';fig.savefig(image,dpi=180,bbox_inches='tight',facecolor='white');plt.close(fig)
    return image


def publish(args):
    rendered=load(args.render_panels);source_records=load(args.source_manifest)
    if rendered.get('snapshot_time_s')!=1.2 or rendered.get('snapshot_not_time_average') is not True:
        raise ValueError('Expected explicitly instantaneous 1.2 s renders')
    panels=rendered.get('panels',[])
    if len(panels)!=4 or {p['id'] for p in panels}!=set(CASES):raise ValueError('Expected exactly four fixed layout IDs')
    if len(source_records)!=4 or {Path(r['source_case']).name for r in source_records}!=set(CASES.values()):
        raise ValueError('Source manifest must contain exactly the four fixed cases')
    master_raw=args.master.read_bytes();master=json.loads(master_raw.decode('utf-8-sig'))
    selected=[r for r in master['cases'] if r['case'] in CASES.values()]
    if len(selected)!=4 or len({r['case'] for r in selected})!=4:raise ValueError('Four actual completed master rows required')
    by_name={r['case']:r for r in selected};first_display=None;validated=[]
    for p in panels:
        name=CASES[p['id']];source=Path(p['source_case']);clone=Path(p['visualization_copy'])
        if source.name!=name or clone.name!=name or source.resolve()==clone.resolve():raise ValueError('Unexpected source/clone identity')
        if p['render_request']!=REQUEST:raise ValueError('Render request differs from frozen common display')
        m=p['renderer_metadata'];display=display_metadata(m)
        if first_display is None:first_display=display
        if display!=first_display:raise ValueError('Nonidentical renderer display metadata')
        if (m.get('time')!=1.2 or m.get('view')!='+z' or m.get('mode')!='slice'
            or m.get('slice')!={'origin':[0,0,-.04],'normal':[0,0,1]}
            or display['color']!={'field':'U','component':'Magnitude','range':[0,12]}):
            raise ValueError('Renderer metadata does not confirm requested view/slice/scale')
        native=Path(m['image'])
        if not native.resolve().is_relative_to(clone.resolve()) or native.is_symlink():raise ValueError('Image is outside its visualization copy')
        original=next(r for r in source_records if r['source_case']==str(source))
        if (original['visualization_copy']!=str(clone) or original['snapshot_time_s']!=1.2
            or original.get('source_unchanged') is not True or original['source_hashes']!=original['copied_hashes']):
            raise ValueError('Original source/copy provenance mismatch')
        expected=original['source_hashes'];fresh_source=hashes(source,expected);fresh_clone=hashes(clone,expected)
        g=load(source/'geometry.json');r=by_name[name]
        nearest=min(math.dist(a[:2],b[:2]) for i,a in enumerate(g['centers']) for b in g['centers'][i+1:])
        theta=0. if p['id'].endswith('_flat') else -10.
        if (g['rotors']!=8 or g['level']!='fine' or not math.isclose(nearest,.08,abs_tol=1e-9)
            or g['tilt_deg']!=theta or r['level']!='fine'
            or not math.isclose(r['start_s'],.8,rel_tol=0,abs_tol=1e-9)
            or not math.isclose(r['stop_s'],1.2,rel_tol=0,abs_tol=1e-9)):
            raise ValueError('Unexpected geometry/grid/averaging protocol')
        if not math.isfinite(r['mean_lift_N']):raise ValueError('Nonfinite actual mean lift')
        validated.append(dict(panel=p,source=source,clone=clone,native=native,row=r,
            expected_hashes=expected,source_fresh_hashes=fresh_source,clone_fresh_hashes=fresh_clone))
    out=args.out.resolve()
    for v in validated:
        for forbidden in (v['source'].parent,v['clone'].parent,args.master.resolve().parent):
            if out==forbidden or forbidden in out.parents:raise ValueError('Cannot publish inside CFD/visualization/master result trees')
    out.mkdir(parents=True,exist_ok=True);assets=out/'flow_sources';assets.mkdir(exist_ok=True)
    records=[]
    for v in validated:
        p=v['panel'];r=v['row'];panel_id=p['id']
        png=assets/(panel_id+'_native.png');geometry=assets/(panel_id+'_geometry.json')
        png_hash=copy_checked(v['native'],png);geometry_hash=copy_checked(v['source']/'geometry.json',geometry)
        records.append(dict(id=panel_id,case=CASES[panel_id],source_case=str(v['source']),visualization_copy=str(v['clone']),
            native_image=str(v['native']),published_png=png.relative_to(out).as_posix(),png_sha256=png_hash,
            published_geometry=geometry.relative_to(out).as_posix(),geometry_sha256=geometry_hash,
            render_request=p['render_request'],renderer_metadata=p['renderer_metadata'],
            source_manifest_hashes=v['expected_hashes'],source_fresh_hashes=v['source_fresh_hashes'],clone_fresh_hashes=v['clone_fresh_hashes'],
            mean_lift_N=r['mean_lift_N'],mean_lift_window_s=[.8,1.2],mean_lift_source='Actual completed master primary-window statistics, not instantaneous field integration',
            source_master_row_sha256=canonical(r),qualified_for_comparison=r['qualified_for_comparison'],
            half_window_drift_percent=r.get('half_window_drift_percent'),late_window_stability_screen_passed=r.get('late_window_stability_screen_passed')))
    for source,name in ((args.render_panels,'render_panels.json'),(args.source_manifest,'source_hash_manifest.json')):
        copy_checked(source,assets/name)
    provenance=dict(schema='tello-nearest8-fine-layout-flow-v1',published_utc=datetime.now(timezone.utc).isoformat(),
        snapshot_time_s=1.2,snapshot_not_time_average=True,render_request=REQUEST,crop_pixels_xy=CROP,
        required_cases=CASES,master_path=str(args.master.resolve()),master_sha256=hashlib.sha256(master_raw).hexdigest(),
        render_metadata_sha256=digest(args.render_panels),source_manifest_sha256=digest(args.source_manifest),
        publisher_sha256=digest(Path(__file__)),panels=records,source_and_clone_hashes_verified=True,
        interpretation='Actual instantaneous CFD velocity magnitude; averaged force labels are a separate statistic. Actuator model, no resolved blades or phase. No automated winner or isolated layout-effect claim.')
    image=assemble(out,provenance)
    for v in validated:
        hashes(v['source'],v['expected_hashes']);hashes(v['clone'],v['expected_hashes'])
    provenance.update(source_and_clone_hashes_unchanged_after_publication=True,assembled_image=image.name,
                      assembled_image_sha256=digest(image))
    (out/'flow_provenance.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')
    return image,provenance


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--render-panels',type=Path,default=WORK/'tello_layout_fine_render_panels_complete.json')
    parser.add_argument('--source-manifest',type=Path,default=WORK/'tello_layout_fine_flow_sources.json')
    parser.add_argument('--master',type=Path,default=HERE/'results/statistics.json')
    parser.add_argument('--out',type=Path,default=HERE/'layout_stage/nearest8_v2')
    parser.add_argument('--reassemble',action='store_true',help='Verify delivered PNG/geometry hashes and reassemble without native CFD source paths')
    args=parser.parse_args()
    if args.reassemble:
        provenance=load(args.out/'flow_provenance.json')
        if provenance.get('required_cases')!=CASES or provenance.get('render_request')!=REQUEST or provenance.get('crop_pixels_xy')!=CROP:
            raise ValueError('Delivered bundle scope/display mismatch')
        if (digest(args.out/'flow_sources/render_panels.json')!=provenance['render_metadata_sha256']
            or digest(args.out/'flow_sources/source_hash_manifest.json')!=provenance['source_manifest_sha256']):
            raise ValueError('Delivered render/source metadata hash mismatch')
        image=assemble(args.out,provenance)
    else:image,provenance=publish(args)
    print(json.dumps(dict(image=str(image),image_sha256=digest(image),panels=len(provenance['panels']),
        source_and_clone_hashes_verified=provenance['source_and_clone_hashes_verified'],snapshot_not_time_average=True),indent=2))


if __name__=='__main__':main()
