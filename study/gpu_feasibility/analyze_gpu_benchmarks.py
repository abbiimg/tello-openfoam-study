"""Read-only analysis of the three actual completed CPU/CUDA benchmarks.

Never launches OpenFOAM, writes case fields, edits inputs, or infers a CFD
speedup from any historical run. Outputs are outside the private case tree.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import re
import sys

for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def scalar_field(path,cells,probe):
    text,digest=probe.ascii_text(path)
    dim=re.search(r'\bdimensions\s*\[([^\]]+)\]',text)
    assert dim and [int(x) for x in dim.group(1).split()]==[0,2,-2,0,0,0,0]
    match=re.search(r'\binternalField\s+nonuniform\s+List<scalar>',text)
    assert match
    count,body=probe.list_body(text,match.end())
    assert count==cells
    values=np.fromstring(body,sep=' ')
    assert values.size==cells and np.isfinite(values).all()
    boundary=text[text.index('boundaryField'):]
    gauge={key:re.search(r'\b'+key+r'\s+([^;]+);',boundary).group(1).strip()
        for key in ('type','rho','psi','gamma','p0')}
    assert gauge['type']=='totalPressure' and gauge['p0']=='uniform 0'
    return values,digest,gauge


def relative_l2(candidate,reference,volume):
    diff=candidate-reference
    if diff.ndim==2:
        numerator=float(np.sum(volume*np.sum(diff*diff,axis=1)))
        denominator=float(np.sum(volume*np.sum(reference*reference,axis=1)))
    else:
        numerator=float(np.dot(volume,diff*diff))
        denominator=float(np.dot(volume,reference*reference))
    assert denominator>1e-30
    return math.sqrt(numerator/denominator),math.sqrt(numerator),math.sqrt(denominator)


def log_metrics(text):
    number=r'[-+0-9.eE]+'
    linear=[]
    for match in re.finditer(r'Solving for\s+(\w+),\s*Initial residual\s*=\s*('+number+
        r'),\s*Final residual\s*=\s*('+number+r'),\s*No Iterations\s+(\d+)',text):
        linear.append(dict(field=match.group(1),initial=float(match.group(2)),
            final=float(match.group(3)),iterations=int(match.group(4))))
    assert linear and all(math.isfinite(x[k]) for x in linear for k in ('initial','final'))
    continuity=[]
    for match in re.finditer(r'time step continuity errors\s*:\s*sum local\s*=\s*('+number+
        r'),\s*global\s*=\s*('+number+r')(?:,\s*cumulative\s*=\s*('+number+r'))?',text):
        continuity.append(dict(local=float(match.group(1)),global_value=float(match.group(2)),
            cumulative=float(match.group(3)) if match.group(3) is not None else None))
    assert continuity
    final=[x for x in continuity if x['cumulative'] is not None]
    def peak(rows,key): return max(abs(x[key]) for x in rows if x[key] is not None)
    pressure=[x for x in linear if x['field']=='p']
    return dict(end_marker=bool(re.search(r'^\s*(?:\[\d+\]\s*)?End\s*$',text,re.M)),
        fatal_errors=len(re.findall(r'FOAM FATAL|MPI_ABORT',text)),
        linear_solve_count=len(linear),pressure_solve_count=len(pressure),
        max_pressure_iterations=max(x['iterations'] for x in pressure),
        mean_pressure_iterations=float(np.mean([x['iterations'] for x in pressure])),
        pressure_iteration_sum=sum(x['iterations'] for x in pressure),
        max_all_linear_iterations=max(x['iterations'] for x in linear),
        max_iteration_hits=sum(x['iterations']>=1000 for x in linear),
        max_iteration_limit=1000,
        max_iteration_limit_basis='Native Foundation14 default and explicit GPU maxIter1000; all U/p limits retained.',
        continuity_count=len(continuity),final_corrector_continuity_count=len(final),
        continuity_peaks=dict(local_all=peak(continuity,'local'),global_all=peak(continuity,'global_value'),
            cumulative=peak(final,'cumulative'),local_final=peak(final,'local'),global_final=peak(final,'global_value')),
        last_final_corrector_continuity=final[-1])


def gpu_metrics(path):
    rows=[json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    own=set(p['pid'] for row in rows for p in row['case_processes'] if p['comm']=='foamRun')
    other_states=[]
    parsed=[]
    all_parsed=[]
    loaded=set()
    for row in rows:
        other_states.extend((p['pid'],p['state'],p['user_cpu_ticks'],p['system_cpu_ticks'])
            for p in row['host_foam_process_states'] if p['pid'] not in own)
        active=any(p['comm']=='foamRun' for p in row['case_processes'])
        for process in row['case_processes']: loaded.update(process['loaded_gpu_libraries'])
        gpu=row.get('gpu',{})
        if gpu.get('returncode')==0:
            for fields in csv.reader(io.StringIO(gpu.get('stdout',''))):
                if len(fields)<8: continue
                try: util=float(fields[3].strip())
                except ValueError: continue
                entry=dict(unix_s=row['unix_s'],gpu_util_percent=util,
                    memory_util_percent=float(fields[4].strip()),reported_used_MiB=float(fields[5].strip()),
                    reported_total_MiB=float(fields[6].strip()),reported_gpu_power_W=float(fields[7].strip()))
                all_parsed.append(entry)
                if active: parsed.append(entry)
    other={}
    for pid,state,user,system in other_states:
        other.setdefault(pid,[]).append((state,user,system))
    unchanged=all(len({(user,system) for _,user,system in data})==1 for data in other.values())
    return dict(samples=len(rows),active_solver_gpu_samples=len(parsed),
        full_runner_gpu_samples=len(all_parsed),
        full_runner_sampled_gpu_util_mean_percent=float(np.mean([p['gpu_util_percent'] for p in all_parsed])) if all_parsed else None,
        sampled_gpu_util_mean_percent=float(np.mean([p['gpu_util_percent'] for p in parsed])) if parsed else None,
        sampled_gpu_util_max_percent=max((p['gpu_util_percent'] for p in parsed),default=None),
        sampled_gpu_nonzero_fraction=float(np.mean([p['gpu_util_percent']>0 for p in parsed])) if parsed else None,
        other_foam_pids=sorted(other),other_foam_all_stopped=all(state in ('T','t') for data in other.values() for state,_,_ in data),
        other_foam_cpu_ticks_unchanged=unchanged,own_foam_pids=sorted(own),
        loaded_gpu_libraries=sorted(loaded),
        limitations='nvidia-smi WSL memory totals/process attribution/utilization can be incomplete; samples corroborate actual Ginkgo executor/device logs and device-buffer/kernel gate, never replace them.',
        trace=parsed)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=Path('/opt/openfoam-workspace/gpu-feasibility/pressure-offload/benchmarks_20261101'))
    parser.add_argument('--out',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    root=args.root.resolve();out=args.out.resolve();out.mkdir(exist_ok=True,parents=True)
    assert not out.is_relative_to(root)
    project=Path(__file__).resolve().parents[3]
    probe=module(project/'outputs/toy_8cm_tilt/probe_fields.py','probe_read_only')
    sys.path.insert(0,str(out.parent))
    import analysis_helpers as history
    variants=('cpu_serial','cpu_mpi2','cuda_mpi2')
    timings={name:json.loads((root/name/'benchmark_timing.json').read_text()) for name in variants}
    assert all(item['completed'] and item['initial_inputs_preserved'] for item in timings.values())
    reference=min(variants[:2],key=lambda name:timings[name]['total_runner_elapsed_s'])
    acceptance=json.loads((root/reference/'benchmark_acceptance.json').read_text())
    acceptance_sha=sha(root/reference/'benchmark_acceptance.json')
    cells=json.loads((root/reference/'geometry.json').read_text())['mesh_cells']
    mesh=probe.RectilinearMesh(root/reference,cells)
    volume=(np.diff(mesh.z)[:,None,None]*np.diff(mesh.y)[None,:,None]*np.diff(mesh.x)[None,None,:]).ravel()
    assert volume.size==cells and np.all(volume>0)
    measured_volume=float(volume.sum())
    analytical_volume=float((mesh.x[-1]-mesh.x[0])*(mesh.y[-1]-mesh.y[0])*(mesh.z[-1]-mesh.z[0]))
    assert math.isclose(measured_volume,analytical_volume,rel_tol=1e-14)
    fields={};rows=[];details={}
    for name in variants:
        case=root/name
        manifest=json.loads((case/'benchmark_manifest.json').read_text())
        assert sha(case/'benchmark_acceptance.json')==acceptance_sha
        assert manifest['preregistered_acceptance_sha256']==acceptance_sha
        assert manifest['frozen_inputs']['constant/polyMesh/points']['sha256']==mesh.points_sha256
        velocity,uhash=probe.read_velocity(case/'0.62/U',cells)
        pressure,phash,gauge=scalar_field(case/'0.62/p',cells,probe)
        fields[name]=(velocity,pressure)
        text=(case/'log.foamRun').read_text(errors='replace')
        diagnostic=history.window(history.read_history(case),.61,.62)
        means={key:history.time_mean(diagnostic,column) for key,column in
            [('lift_N',1),('air_work_W',2),('inferred_shaft_W',3),('inferred_input_W',4),('sum_rotor_thrust_N',5)]}
        log=log_metrics(text)
        runtime=gpu_metrics(case/'gpu_usage.jsonl')
        timing=timings[name];phase=timing['phases']
        row=dict(variant=name,mpi_ranks=timing['mpi_ranks'],reference=name==reference,
            full_wall_s=timing['total_runner_elapsed_s'],solver_wall_s=phase['solver_elapsed_s'],
            startup_s=phase['startup_through_first_completed_step_s'],steady_wall_s=phase['steady_wall_s'],
            steady_physical_s=phase['steady_physical_s'],steady_steps=phase['steady_completed_steps'],
            steady_throughput=phase['steady_simulated_s_per_wall_s'],
            decomposition_s=phase.get('decomposition_s',0),reconstruction_s=phase.get('reconstruction_s',0),
            mean_lift_N=means['lift_N'],mean_air_work_W=means['air_work_W'],
            mean_inferred_shaft_W=means['inferred_shaft_W'],mean_inferred_input_W=means['inferred_input_W'],
            max_pressure_iterations=log['max_pressure_iterations'],mean_pressure_iterations=log['mean_pressure_iterations'],
            max_iteration_hits=log['max_iteration_hits'],fatal_errors=log['fatal_errors'],
            peak_continuity_local_all=log['continuity_peaks']['local_all'],
            peak_continuity_global_all=log['continuity_peaks']['global_all'],
            peak_continuity_cumulative=log['continuity_peaks']['cumulative'],
            peak_continuity_local_final=log['continuity_peaks']['local_final'],
            peak_continuity_global_final=log['continuity_peaks']['global_final'],
            sampled_gpu_util_mean_percent=runtime['sampled_gpu_util_mean_percent'],
            sampled_gpu_util_full_runner_mean_percent=runtime['full_runner_sampled_gpu_util_mean_percent'],
            sampled_gpu_util_max_percent=runtime['sampled_gpu_util_max_percent'])
        rows.append(row)
        details[name]=dict(timing=timing,means=means,log=log,runtime=runtime,
            actual_final_field_hashes=dict(U=uhash,p=phash),log_sha256=sha(case/'log.foamRun'),
            pressure_gauge=gauge,solver_configuration_sha256=manifest['solver_configuration_sha256'])
    ref=next(row for row in rows if row['variant']==reference)
    assert all(details[name]['pressure_gauge']==details[reference]['pressure_gauge'] for name in variants)
    native_envelope={key:max(details[name]['log']['continuity_peaks'][key] for name in variants[:2])
        for key in ('local_all','global_all','cumulative')}
    for row in rows:
        name=row['variant']
        urel,uabs,uref=relative_l2(fields[name][0],fields[reference][0],volume)
        prel,pabs,pref=relative_l2(fields[name][1],fields[reference][1],volume)
        lift=row['mean_lift_N']/ref['mean_lift_N']-1
        power=row['mean_inferred_input_W']/ref['mean_inferred_input_W']-1
        flags=[key for key,limit in native_envelope.items()
            if details[name]['log']['continuity_peaks'][key]>limit+1e-12]
        row.update(mean_lift_difference_percent=100*lift,mean_input_difference_percent=100*power,
            final_U_relative_L2_percent=100*urel,final_p_relative_L2_percent=100*prel,
            full_throughput_ratio_vs_best_CPU=ref['full_wall_s']/row['full_wall_s'],
            full_wall_change_percent=100*(row['full_wall_s']/ref['full_wall_s']-1),
            steady_throughput_ratio_vs_best_CPU=row['steady_throughput']/max(r['steady_throughput'] for r in rows[:2]),
            force_power_field_gates_pass=bool(abs(lift)<=.001 and abs(power)<=.001 and urel<=.002 and prel<=.002),
            continuity_review_flag=bool(flags),continuity_flagged_metrics=';'.join(flags))
        row['all_accuracy_gates_pass']=bool(row['force_power_field_gates_pass'] and not flags and
            row['fatal_errors']==0 and row['max_iteration_hits']==0)
        details[name]['field_comparison']=dict(reference=reference,U_relative_L2=urel,p_relative_L2=prel,
            U_absolute_volume_L2=uabs,p_absolute_volume_L2=pabs,U_reference_volume_L2=uref,p_reference_volume_L2=pref,
            no_pressure_gauge_offset_fitted=True,continuity_review_flags=flags)
    native_consistent=all(row['force_power_field_gates_pass'] and row['max_iteration_hits']==0 and row['fatal_errors']==0 for row in rows[:2])
    gpu=next(row for row in rows if row['variant']=='cuda_mpi2')
    cuda_evidence=timings['cuda_mpi2']['actual_ginkgo_executor_records']
    matched_load=all(details[name]['runtime']['other_foam_all_stopped'] and details[name]['runtime']['other_foam_cpu_ticks_unchanged'] for name in variants)
    practical=bool(matched_load and gpu['full_wall_s']<=.8*ref['full_wall_s'] and gpu['steady_throughput_ratio_vs_best_CPU']>=1)
    diagnosis=json.loads((out/'performance_diagnosis.json').read_text()) if (out/'performance_diagnosis.json').exists() else None
    diagnosis_matches=bool(diagnosis and all(diagnosis.get('cases',{}).get(name,{}).get('log_sha256')==details[name]['log_sha256'] for name in variants))
    report=dict(kind='Actual completed CPU/CUDA CFD benchmark accuracy and timing comparison',
        case_root=str(root),reference=reference,acceptance_file='benchmark_acceptance.json',
        preregistered_acceptance_sha256=acceptance_sha,registered_before_runs=True,
        mean_window_s=[.61,.62],final_field_time_s=.62,simulated_window_s=[.6,.62],
        mesh=dict(cells=cells,shape=[mesh.nx,mesh.ny,mesh.nz],ordering_check=mesh.ordering_check,
            points_sha256=mesh.points_sha256,volume_sum_m3=measured_volume,box_volume_m3=analytical_volume,
            volume_method='Exact axis-aligned hexahedron volumes from saved mesh point coordinates; every cell ordering verified against an actual owned face.'),
        rows=rows,details=details,native_continuity_envelope=native_envelope,
        native_consistency_passed=native_consistent,matched_stopped_host_foam_evidence=matched_load,
        actual_cuda_executor_device_evidence=cuda_evidence,
        performance_diagnosis_log_hashes_match=diagnosis_matches,
        logged_pressure_host_wall_costs=diagnosis['cost_summary'] if diagnosis_matches else None,
        gpu_force_power_field_gates_passed=gpu['force_power_field_gates_pass'],
        gpu_continuity_requires_review=gpu['continuity_review_flag'],
        gpu_all_accuracy_gates_passed=gpu['all_accuracy_gates_pass'],
        practical_timing_gate_passed=practical,cuda_default_qualified=False,cpu_default_retained=True,
        interpretation='The tested OGL/Ginkgo CUDA pressure configuration does not improve runtime against the better fresh native CPU run. This does not establish that CUDA cannot accelerate other methods/configurations/problems.',
        limitations=['One short0.02s run per variant, not a statistically replicated long-run or batch throughput study.',
            'Lift is actual actuator reaction from computed fields; electrical/shaft input remains inferred through the unchanged assumed loss law.',
            'WSL nvidia-smi telemetry has limitations; actual Ginkgo executor/device records and CUDA-buffer/reduction gate corroborate execution.',
            'Any preregistered continuity review flag remains flagged even if final-field and force/power gates pass.'],
        solver_launched_by_analysis=False,case_files_written_by_analysis=False)
    (out/'benchmark_accuracy_results.json').write_text(json.dumps(report,indent=2)+'\n')
    with (out/'benchmark_results.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    plot(rows,out)
    lines=['Actual Foundation14 CPU/CUDA benchmark',
        '922,576 cells; identical frozen mesh/0.6 U,p/physics/controller reset; simulated 0.600–0.620 s.',
        'Reference: faster fresh native CPU run = '+reference+'.',
        'Variant | full wall s | startup s | steady wall s | lift N | inferred input W | U L2 % | p L2 %']
    for r in rows:
        lines.append(f"{r['variant']} | {r['full_wall_s']:.3f} | {r['startup_s']:.3f} | {r['steady_wall_s']:.3f} | {r['mean_lift_N']:.9f} | {r['mean_inferred_input_W']:.9f} | {r['final_U_relative_L2_percent']:.7g} | {r['final_p_relative_L2_percent']:.7g}")
    lines += ['',f"CUDA full wall: {gpu['full_wall_change_percent']:.2f}% longer than {reference}; steady throughput {gpu['steady_throughput_ratio_vs_best_CPU']:.4f} times the better native CPU rate.",
        f"Native consistency: {native_consistent}. GPU force/power/field gates: {gpu['force_power_field_gates_pass']}. GPU continuity review flag: {gpu['continuity_flagged_metrics'] or 'none'}. Max-iteration hits: {gpu['max_iteration_hits']}; fatal errors: {gpu['fatal_errors']}.",
        'The 20% full-wall reduction screen failed. CPU stays default. No new variants or solver runs were launched by this analysis.',
        'Mean electrical input is inferred using the unchanged loss assumptions, not a battery measurement.',
        'The continuity flag concerns intermediate local continuity before the final pressure correction. Final-corrector local/global/cumulative continuity is below the native envelope. The preregistered flag is retained, not waived.',
        f"Reported GPU utilization: {gpu['sampled_gpu_util_full_runner_mean_percent']:.2f}% mean over full-run monitor samples; {gpu['sampled_gpu_util_mean_percent']:.2f}% while foamRun was present; peak {gpu['sampled_gpu_util_max_percent']:.0f}%. WSL telemetry has limitations; real Ginkgo CudaExecutor/device 0 records corroborate use.",
        'See benchmark_accuracy_results.json for volumes, output hashes, convergence/continuity, telemetry and exact gates; performance_diagnosis.json for the bounded source/log diagnosis.']
    if diagnosis_matches:
        cost=diagnosis['cost_summary'];candidate=diagnosis['one_possible_candidate'];scenario=candidate['optimistic_arithmetic_scenario_not_simulated']
        lines += [f"Logged GPU pressure host-wall scopes: {cost['gpu_preconditioner_total_s']:.3f}s recurring AMG preconditioner update, {cost['gpu_CG_solve_total_s']:.3f}s CG solve, {cost['logged_matrix_update_s']:.3f}s matrix update, {cost['logged_copy_back_s']:.3f}s copy-back. These are host scopes, not CUDA-event kernel profiles; parent/child nested timers must not be added.",
            'Hierarchy reuse was active, but caching0 rebuilds coarse operators/smoothers/coarse solver each pressure call.',
            f"Unrun projection only: caching1 could optimistically remove {candidate['measured_second_corrector_setup_total_s']:.3f}s second-corrector setup, leaving {scenario['projected_full_s']:.3f}s full. Even free removal of all logged setup leaves {scenario['even_removing_ALL_logged_preconditioner_setup_full_s']:.3f}s versus {ref['full_wall_s']:.3f}s CPU2. No tuning was implemented or rerun."]
    (out/'benchmark_comparison.txt').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(reference=reference,rows=rows,native_consistent=native_consistent,
        matched_host_load=matched_load,gpu_all_accuracy_gates=gpu['all_accuracy_gates_pass'],
        output=str(out/'benchmark_accuracy_results.json')),indent=2))


def plot(rows,out):
    labels=['CPU serial','CPU ·2 ranks','CUDA ·2 ranks /1 GPU']
    fig,(left,right)=plt.subplots(1,2,figsize=(12,5.2),gridspec_kw={'width_ratios':[1.45,1]})
    x=np.arange(3);bottom=np.zeros(3)
    segments=[('Setup / reconstruction',np.array([r['decomposition_s']+r['reconstruction_s']+r['full_wall_s']-r['solver_wall_s']-r['decomposition_s']-r['reconstruction_s'] for r in rows]),'#a8b3c1'),
        ('Solver startup',np.array([r['startup_s'] for r in rows]),'#edb458'),
        ('Steady solver',np.array([r['steady_wall_s'] for r in rows]),'#37658e'),
        ('Solver finish',np.array([r['solver_wall_s']-r['startup_s']-r['steady_wall_s'] for r in rows]),'#dce3eb')]
    for label,values,color in segments:
        left.bar(x,values,bottom=bottom,label=label,color=color,width=.65);bottom+=values
    for i,r in enumerate(rows): left.text(i,r['full_wall_s']+4,f"{r['full_wall_s']:.1f}s",ha='center',fontsize=11)
    left.set_xticks(x,labels,fontsize=9);left.set_ylabel('Measured full runner wall time (s)')
    left.set_ylim(0,max(r['full_wall_s'] for r in rows)*1.19);left.grid(axis='y',alpha=.2);left.set_axisbelow(True)
    left.legend(frameon=False,fontsize=8,loc='upper center',ncol=2)
    width=.32
    right.bar(x-width/2,[r['full_throughput_ratio_vs_best_CPU'] for r in rows],width,label='Full runner',color='#37658e')
    right.bar(x+width/2,[r['steady_throughput_ratio_vs_best_CPU'] for r in rows],width,label='Steady solver',color='#edb458')
    right.axhline(1,color='#65778b',linestyle='--',linewidth=1)
    right.set_xticks(x,labels,fontsize=9);right.set_ylim(0,1.32)
    right.set_ylabel('Throughput / better fresh native CPU');right.legend(frameon=False,fontsize=9)
    right.grid(axis='y',alpha=.2);right.set_axisbelow(True)
    for ax in (left,right):
        for side in ('top','right'): ax.spines[side].set_visible(False)
    fig.suptitle('Measured CPU versus CUDA CFD runtime',fontsize=16,fontweight='bold',x=.06,ha='left')
    fig.text(.06,.89,'Foundation14 ·922,576 cells ·0.600–0.620 s ·same frozen seed and physics',fontsize=10,color='#475569')
    gpu=rows[2]
    fig.text(.06,.025,f"Tested CUDA configuration: {gpu['full_wall_change_percent']:.1f}% longer full wall; {gpu['steady_throughput_ratio_vs_best_CPU']:.3f}× native steady throughput. CPU remains default.",fontsize=10)
    fig.subplots_adjust(left=.075,right=.98,bottom=.16,top=.83,wspace=.3)
    fig.savefig(out/'benchmark_speed_comparison.png',dpi=180,facecolor='white')
    fig.savefig(out/'benchmark_speed_comparison.svg',facecolor='white')
    plt.close(fig)


if __name__=='__main__': main()
