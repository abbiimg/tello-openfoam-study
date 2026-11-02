"""Frozen isolated CPU/CUDA benchmark runner; requires explicit --run.

Preparation/verification never launches CFD. Execution agent alone invokes
Allrun. Case input/initial-field hashes are verified before and after execution.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import threading
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''): h.update(block)
    return h.hexdigest()


def verify(case, manifest):
    for relative, record in manifest['frozen_inputs'].items():
        path = case/relative
        assert path.is_file() and path.stat().st_size==record['size_bytes'], relative
        assert digest(path)==record['sha256'], relative
    assert not (case/'0.6/phi').exists(), 'Never seed an old flux field'
    backend = manifest.get('gpu_library')
    if backend:
        assert digest(Path(backend['path']))==backend['sha256'], 'GPU adapter changed'
        for item in backend['ginkgo_library_closure']:
            assert digest(Path(item['path']))==item['sha256'], item['path']
    return True


def case_processes(case):
    result = []
    for directory in Path('/proc').iterdir():
        if not directory.name.isdigit(): continue
        try:
            comm = (directory/'comm').read_text().strip()
            if comm not in ('foamRun','mpirun'): continue
            if (directory/'cwd').resolve() != case: continue
            maps = (directory/'maps').read_text()
            libraries = sorted(set(line.split()[-1] for line in maps.splitlines()
                if any(key in line for key in ('libOGL','libginkgo_cuda','libcuda.so','libcudart','libcusparse'))))
            result.append(dict(pid=int(directory.name),comm=comm,loaded_gpu_libraries=libraries))
        except (FileNotFoundError,ProcessLookupError,PermissionError,OSError): pass
    return result


def sample_gpu(case, stopped):
    binary = shutil.which('nvidia-smi')
    if not binary and Path('/usr/lib/wsl/lib/nvidia-smi').exists():
        binary = '/usr/lib/wsl/lib/nvidia-smi'
    queries = {
        'gpu': '--query-gpu=timestamp,name,uuid,utilization.gpu,utilization.memory,memory.used,memory.total,power.draw',
        'compute_apps': '--query-compute-apps=pid,process_name,used_gpu_memory,gpu_uuid',
    }
    with (case/'gpu_usage.jsonl').open('w') as stream:
        while not stopped.is_set():
            host_foam = []
            for directory in Path('/proc').iterdir():
                if not directory.name.isdigit(): continue
                try:
                    if (directory/'comm').read_text().strip()!='foamRun': continue
                    fields = (directory/'stat').read_text().rsplit(')',1)[1].split()
                    host_foam.append(dict(pid=int(directory.name),state=fields[0],
                        user_cpu_ticks=int(fields[11]),system_cpu_ticks=int(fields[12])))
                except (FileNotFoundError,ProcessLookupError,PermissionError,OSError): pass
            row = dict(unix_s=time.time(),monotonic_s=time.monotonic(),
                case_processes=case_processes(case),nvidia_smi_available=bool(binary),
                host_foam_process_states=host_foam,host_load_average=os.getloadavg(),
                limitations='WSL utilization, memory totals and process attribution can be unsupported/incomplete. Corroborate with OGL_RUNTIME_EXECUTOR from actual Ginkgo, library mappings and CUDA-buffer/kernel gate; never infer offload from this sampler alone.')
            if binary:
                for key, query in queries.items():
                    try:
                        proc = subprocess.run([binary,query,'--format=csv,noheader,nounits'],
                            text=True,capture_output=True,timeout=3)
                        row[key] = dict(returncode=proc.returncode,stdout=proc.stdout.strip(),stderr=proc.stderr.strip())
                    except subprocess.TimeoutExpired: row[key] = dict(timeout=True)
            stream.write(json.dumps(row)+'\n')
            stream.flush()
            stopped.wait(1.0)


def command(case, argv, log, limit=None):
    began = time.monotonic()
    with (case/log).open('w') as stream:
        process = subprocess.Popen(argv,cwd=case,stdout=stream,stderr=subprocess.STDOUT,
            start_new_session=True)
        try: code = process.wait(timeout=limit)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
            raise RuntimeError('Bounded benchmark command timed out: '+argv[0])
    elapsed = time.monotonic()-began
    assert code==0, (argv,code,log)
    return elapsed


def observe_steps(case, stopped, rows):
    """Observe flushed native time records; never launch or change a solver."""
    pending = b''
    physical = None
    stream = None
    with (case/'benchmark_step_times.jsonl').open('w') as output:
        try:
            while True:
                if stream is None and (case/'log.foamRun').exists():
                    stream = (case/'log.foamRun').open('rb')
                data = stream.read(65536) if stream else b''
                if data:
                    pending += data
                    lines = pending.split(b'\n')
                    pending = lines.pop()
                    for raw in lines:
                        line = raw.decode('utf-8','replace')
                        found = re.match(r'^\s*(?:\[\d+\]\s*)?Time\s*=\s*([0-9.eE+-]+)\s*s?\s*$',line)
                        if found: physical=float(found.group(1))
                        found = re.search(r'ExecutionTime\s*=\s*([0-9.eE+-]+)\s*s\s+ClockTime\s*=\s*([0-9.eE+-]+)\s*s',line)
                        if found and physical is not None:
                            row = dict(physical_time_s=physical,observed_monotonic_s=time.monotonic(),
                                reported_cpu_s=float(found.group(1)),reported_clock_s=float(found.group(2)))
                            rows.append(row)
                            output.write(json.dumps(row)+'\n')
                            output.flush()
                elif stopped.is_set(): break
                else: stopped.wait(0.02)
        finally:
            if stream: stream.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',type=Path,default=Path('.'))
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--verify-only',action='store_true')
    mode.add_argument('--run',action='store_true')
    args = parser.parse_args()
    case = args.case.resolve()
    manifest = json.loads((case/'benchmark_manifest.json').read_text())
    assert os.environ.get('WM_PROJECT_VERSION')=='14', 'Use installed Foundation14'
    overall_start = time.monotonic()
    verify(case,manifest)
    if args.verify_only:
        print(json.dumps(dict(case=str(case),verified=True,solver_launched=False,
            variant=manifest['variant'],solver_configuration_sha256=manifest['solver_configuration_sha256'])))
        return
    assert os.geteuid()!=0, 'Execution agent must launch as openfoam, not root'
    assert not (case/'.benchmark-started').exists() and not (case/'log.foamRun').exists()
    assert not list(case.glob('processor*')), 'Refuse an already decomposed benchmark'
    ranks = manifest['mpi_ranks']
    (case/'.benchmark-started').write_text(datetime.datetime.now(datetime.timezone.utc).isoformat()+'\n')
    phases = {}
    report = dict(kind='Actual isolated CFD CPU/CUDA timing benchmark',variant=manifest['variant'],
        case=str(case),mpi_ranks=ranks,started_unix_s=time.time(),completed=False,
        source_initial_hashes=manifest['source_initial_hashes'],
        solver_configuration_sha256=manifest['solver_configuration_sha256'],
        no_production_case_changes=True)
    report.update(accuracy_gate_performed=False,speedup_calculated=False,adoption_qualified=False)
    stopped = threading.Event()
    sampler = threading.Thread(target=sample_gpu,args=(case,stopped),daemon=True)
    sampler.start()
    step_stopped = threading.Event()
    step_rows = []
    step_observer = None
    solver_started = None
    try:
        if ranks==2:
            phases['decomposition_s'] = command(case,['decomposePar','-time','0.6'],'log.decomposePar',180)
            for rank in range(ranks):
                dest = case/f'processor{rank}/constant/rotorParameters'
                shutil.copy2(case/'constant/rotorParameters',dest)
                assert digest(dest)==digest(case/'constant/rotorParameters')
        argv = ['foamRun'] if ranks==1 else ['mpirun','--bind-to','none','-np','2','foamRun','-parallel']
        step_observer = threading.Thread(target=observe_steps,args=(case,step_stopped,step_rows),daemon=True)
        step_observer.start()
        solver_started = time.monotonic()
        try:
            phases['solver_elapsed_s'] = command(case,argv,'log.foamRun',manifest['max_solver_wall_s'])
        finally:
            step_stopped.set()
            step_observer.join(timeout=2)
        text = (case/'log.foamRun').read_text()
        assert re.search(r'^End\s*$',text,re.M) and 'FOAM FATAL' not in text
        runtime = [line for line in text.splitlines() if 'OGL_RUNTIME_EXECUTOR' in line]
        if manifest['variant']=='cuda_mpi2':
            assert any('owner=1' in line and 'CudaExecutor' in line for line in runtime), runtime
            assert any('owner=0' in line and 'ReferenceExecutor' in line for line in runtime), runtime
            assert 'cuda' in text and 'GKOCG' in text
        report['actual_ginkgo_executor_records'] = runtime
        if ranks==2:
            phases['reconstruction_s'] = command(case,
                ['reconstructPar','-time','0.60000001:'],'log.reconstructPar',180)
        assert (case/'0.62/U').is_file() and (case/'0.62/p').is_file()
        verify(case,manifest)
        report.update(completed=True,end_marker=True,initial_inputs_preserved=True,
            physical_time_final=0.62,nvidia_smi_is_only_corroboration=True)
    except BaseException as error:
        report['error'] = repr(error)
        raise
    finally:
        stopped.set()
        sampler.join(timeout=8)
        if solver_started is not None and step_rows:
            phases['startup_through_first_completed_step_s'] = step_rows[0]['observed_monotonic_s']-solver_started
            phases['steady_wall_s'] = step_rows[-1]['observed_monotonic_s']-step_rows[0]['observed_monotonic_s']
            phases['steady_physical_s'] = step_rows[-1]['physical_time_s']-step_rows[0]['physical_time_s']
            phases['steady_completed_steps'] = len(step_rows)-1
            if phases['steady_wall_s']>0:
                phases['steady_simulated_s_per_wall_s'] = phases['steady_physical_s']/phases['steady_wall_s']
            phases['step_observation_poll_interval_s'] = 0.02
            phases['first_native_step'] = step_rows[0]
            phases['last_native_step'] = step_rows[-1]
        report['step_observer_finished'] = step_observer is None or not step_observer.is_alive()
        report.update(phases=phases,total_runner_elapsed_s=time.monotonic()-overall_start,
            finished_unix_s=time.time(),sampler_finished=not sampler.is_alive(),
            scope='Includes input verification, decomposition if needed, first CUDA setup/transfers inside solver, reconstruction if needed, and sampler cleanup. Solver phase is also reported separately. No speedup denominator is supplied here.',
            comparison_required='Compare the better fresh cpu_serial/cpu_mpi2 elapsed time under the SAME host load; require pressure/continuity/field/lift/power accuracy gates before adoption.')
        (case/'benchmark_timing.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report,indent=2))


if __name__=='__main__': main()
