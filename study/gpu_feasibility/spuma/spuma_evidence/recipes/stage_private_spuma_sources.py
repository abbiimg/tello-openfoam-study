"""Pinned shallow private sources only; no submodule fetch, install, build or CFD."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,time
BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');assert BASE.resolve()==BASE and not BASE.is_symlink() and BASE.stat().st_uid==os.getuid()
assert os.getuid()==999
JOURNAL=BASE/'source_staging.json'
def now():return datetime.now(timezone.utc).isoformat()
def save():
    data['updated_utc']=now();temp=JOURNAL.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2)+'\n');temp.replace(JOURNAL)
def git(cwd,*arguments):
    with log.open('a') as stream:
        result=subprocess.run(['git','-c','credential.interactive=never','-c','pack.threads=1','-c','index.threads=1',*map(str,arguments)],
            cwd=cwd,stdout=stream,stderr=subprocess.STDOUT,timeout=180)
    assert result.returncode==0,'Git metadata/source staging failed; see '+str(log)
def output(case,*arguments):return subprocess.check_output(['git','-C',str(case),*arguments],text=True,timeout=15).strip()
assert not JOURNAL.exists(),'Inspect existing staging rather than overwrite'
log=BASE/'source_staging.log';assert not log.exists()
data=dict(kind='private_pinned_SPUMA_and_Umpire_source_staging',state='staging',started_utc=now(),sources=[],
    source_root=str(BASE),submodules_fetched=False,compiler_invoked=False,build_started=False,install_started=False,
    tutorial_or_CFD_started=False,shared_install_changed=False,production_inputs_results_or_writers_changed=False,
    index_pack_threads=1,network_fetch_timeout_seconds=180,git_history_depth=1)
save()
try:
    requested=[('SPUMA','https://gitlab.hpc.cineca.it/exafoam/spuma.git','1ff2d45c002b7afb599b9dd8c4c6874666242349',BASE/'source'),
        ('Umpire','https://github.com/LLNL/Umpire.git','1ed0669c57f041baa1f1070693991c3a7a43e7ee',BASE/'dependencies/Umpire-v2025.03.0')]
    for name,url,sha,case in requested:
        assert not case.exists() and not case.is_symlink();assert BASE in case.resolve().parents
        case.mkdir(parents=True);git(case,'init','--initial-branch=private-staging')
        git(case,'remote','add','origin',url);data.update(active_source=name);save()
        git(case,'-c','protocol.version=2','fetch','--depth=1','--no-tags','--no-recurse-submodules','origin',sha)
        assert sum(p.stat().st_size for p in (case/'.git/objects').rglob('*') if p.is_file())<512*1024**2
        git(case,'-c','submodule.recurse=false','checkout','--detach',sha)
        assert output(case,'rev-parse','HEAD')==sha and output(case,'status','--porcelain')==''
        files=[p for p in case.rglob('*') if p.is_file() and not p.is_symlink()];size=sum(p.stat().st_size for p in files)
        assert size<1536*1024**2,'Shallow source staging exceeded1.5GB bound'
        row=dict(name=name,url=url,commit_sha=sha,path=str(case),history_depth=1,tracked_worktree_clean=True,
            bytes=size,file_count=len(files),submodules_fetched=False,build_started=False,
            gitmodules=(case/'.gitmodules').read_text() if (case/'.gitmodules').exists() else None)
        if name=='SPUMA':
            row.update(actual_project_version='v2512',arm64_nvidia_rules_present=(case/'wmake/rules/linuxARM64Nvidia/c++').is_file())
            assert 'WM_PROJECT_VERSION=v2512' in (case/'etc/bashrc').read_text()
        data['sources'].append(row);save();print(json.dumps(row),flush=True)
    data.update(state='pinned_sources_staged_no_build',finished_utc=now(),active_source=None,
        next_gate='Wait for root to provide passing shared NVHPC/Umpire gates and an explicit build-budget release; do not invoke Allwmake or CMake.')
    save();print(json.dumps(dict(journal=str(JOURNAL),state=data['state'],build_started=False)),flush=True)
except BaseException as error:
    data.update(state='staging_failed_preserved',error=repr(error),finished_utc=now());save();raise
