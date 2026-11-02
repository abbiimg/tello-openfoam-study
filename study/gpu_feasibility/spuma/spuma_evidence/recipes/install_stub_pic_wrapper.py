"""Apply the diagnosed link-only fix inside SPUMA's private command env."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, shutil

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma');WORK=Path(__file__).resolve().parent
assert os.getuid()==999
marker=BASE/'provenance/stub_pic_wrapper_install.json';assert not marker.exists()
failure=BASE/'logs/finiteVolume_library.log';text=failure.read_text()
assert 'R_AARCH64_LD64_GOTPAGE_LO15' in text and 'too many GOT entries for -fpic' in text
assert 'linkstub.c:' in text and 'pgcudareg' in text and 'pgcudafat' in text
target=BASE/'tools/stub-gcc-wrapper/gcc';assert not target.exists()
target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WORK/'stub_gcc_wrapper.py',target);target.chmod(0o755)
env=BASE/'env.sh';old=env.read_text();assert 'stub-gcc-wrapper' not in old
original_env=BASE/'provenance/env.before_stub_pic.sh';assert not original_env.exists();original_env.write_text(old)
new=old+'\n# Scoped CUDA registration-stub PIC fix; system compiler and SDK unchanged.\nexport PATH="'+str(target.parent)+':$PATH"\n'
env.write_text(new)
config_path=BASE/'provenance/private_build_configuration.json';config=json.loads(config_path.read_text())
(BASE/'provenance/private_build_configuration.before_stub_pic.json').write_text(json.dumps(config,indent=2)+'\n')
record=dict(kind='Diagnosed AArch64 generated CUDA linkstub GOT fix, private child environment only',
    recorded_utc=datetime.now(timezone.utc).isoformat(),failure_log=str(failure),failure_log_sha256=hashlib.sha256(failure.read_bytes()).hexdigest(),
    diagnostic='NVHPC generated registration linkstub used -fpic and exceeded GOT range; same confirmed native-route issue',
    wrapper=str(target),wrapper_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
    env_sha256_before=hashlib.sha256(old.encode()).hexdigest(),env_sha256_after=hashlib.sha256(new.encode()).hexdigest(),
    filter='Only SDK26.9 include_acc/linkstub.c compiled with -c, pgcudareg output, and explicit -fpic; replace that flag alone with -fPIC',
    system_compiler_or_SDK_changed=False,upstream_source_or_cached_objects_changed=False,
    reference_recipe='work/native_stdpar_install/stub_gcc_wrapper.py; own SPUMA log/provenance locations')
config['environment_sha256']=record['env_sha256_after'];config['private_linker_compatibility_fix']=record
config_path.write_text(json.dumps(config,indent=2)+'\n')
(WORK/'private_build_configuration.json').write_text(json.dumps(config,indent=2)+'\n')
marker.write_text(json.dumps(record,indent=2)+'\n')
(WORK/'stub_pic_wrapper_install.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record),flush=True)
