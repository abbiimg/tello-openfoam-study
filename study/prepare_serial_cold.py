"""Prepare a NEW cold serial case with mapped-validation numerics.

No mesh utility or flow solver is launched. Existing/started cases are refused.
Accept explicit sensitivity cases or validation layout_comparison pilots.
Requires Foundation14 dictionary utilities on PATH.
"""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess

from prepare_mapped import enable_direct_coarsest, solver_configuration


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--case', type=Path, required=True)
    p.add_argument('--owner')
    a = p.parse_args()
    case = a.case.resolve(strict=True)
    g = json.loads((case/'geometry.json').read_text())
    if not (g.get('study_role') == 'sensitivity' or
            (g.get('study_role') == 'validation' and g.get('purpose') == 'layout_comparison')):
        raise ValueError('Require sensitivity role or explicit validation layout_comparison purpose')
    if any((case/n).exists() for n in ('run_status.json', 'log.foamRun',
            'initialization.json', 'cold_preparation.json', '.cold-solver-started')) or list(case.glob('processor*')):
        raise ValueError('Refusing an existing prepared/started case')
    for folder in case.iterdir():
        if folder.is_dir():
            try:
                value = float(folder.name)
            except ValueError:
                continue
            if value != 0:
                raise ValueError('Cold target already has nonzero time fields')
    here = Path(__file__).resolve().parent
    (case/'Allrun').write_text((here/'Allrun_cold_serial.template').read_text().replace('\r\n','\n'))
    (case/'Allrun').chmod(0o755)
    shutil.copyfile(here/'decomposeParDict_serial.template', case/'system/decomposeParDict')
    edit = enable_direct_coarsest(case)
    config, signature, direct = solver_configuration(case)
    runner_hash = hashlib.sha256((case/'Allrun').read_bytes()).hexdigest()
    g.update(initialization_method='cold_start', initialization_family='cold',
        initialization_start_time_s=0., solver_configuration=config,
        solver_configuration_sha256=signature, pressure_direct_solve_coarsest=direct)
    g['execution'] = dict(mpi_ranks=1, threads_per_rank=1, execution_mode='serial', decomposition='serial (1 process)',
        start='cold uniform rest; default actuator initialization', runner_sha256=runner_hash)
    (case/'geometry.json').write_text(json.dumps(g, indent=2)+'\n')
    record = dict(case=case.name, status='prepared_no_solver_run',
        study_role=g['study_role'], purpose=g.get('purpose','initialization_sensitivity'),
        initialization='cold', mpi_ranks=1, direct_coarsest_edit=edit,
        solver_configuration_sha256=signature, runner_sha256=runner_hash)
    (case/'cold_preparation.json').write_text(json.dumps(record, indent=2)+'\n')
    if a.owner:
        if os.geteuid() != 0:
            raise PermissionError('--owner requires root')
        subprocess.run(['chown', '-R', a.owner, str(case)], check=True)
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
