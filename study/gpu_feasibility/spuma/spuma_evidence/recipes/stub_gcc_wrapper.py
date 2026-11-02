#!/usr/bin/python3
"""Task-private GCC trampoline, limited to NVHPC's CUDA registration stub."""
from pathlib import Path
import hashlib, json, os, shutil, sys, time

BASE=Path('/opt/openfoam-workspace/gpu-feasibility/spuma')
SDK=Path('/opt/openfoam-workspace/gpu-feasibility/native-stdpar/nvhpc/Linux_aarch64/26.9')
args=sys.argv[1:]
source=SDK/'compilers/include_acc/linkstub.c'
output=args[args.index('-o')+1] if '-o' in args and args.index('-o')+1<len(args) else ''
changed=('-c' in args and str(source) in args and Path(output).name.startswith('pgcudareg') and '-fpic' in args)
forward=['-fPIC' if changed and item=='-fpic' else item for item in args]
record=dict(time_ns=time.time_ns(),pid=os.getpid(),original_args=args,forwarded_args=forward,
            changed_only_generated_registration_pic=changed)
if changed:
    record['linkstub_source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    for item in args:
        if item.startswith('-DREGFILE='):
            registration=Path(item.split('=',1)[1].strip(chr(34)))
            if registration.is_file() and registration.stat().st_size<10_000_000:
                folder=BASE/'provenance/stub_compilations';folder.mkdir(exist_ok=True)
                saved=folder/(str(os.getpid())+'_'+registration.name)
                shutil.copyfile(registration,saved)
                record.update(registration_source=str(saved),registration_source_sha256=hashlib.sha256(saved.read_bytes()).hexdigest())
with (BASE/'logs/stub_gcc_wrapper.jsonl').open('a') as log:log.write(json.dumps(record)+'\n')
os.execv('/usr/bin/gcc',['/usr/bin/gcc',*forward])
