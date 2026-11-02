"""Check exported file bytes without changing any CFD input."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import sys

root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'export_manifest.json').read_text())
errors=[]
verified=0
for record in manifest['files']:
    relative=PurePosixPath(record['repository_path'])
    if relative.is_absolute() or '..' in relative.parts:
        errors.append({'path':str(relative),'error':'unsafe manifest path'})
        continue
    path=root.joinpath(*relative.parts)
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root):
        errors.append({'path':str(relative),'error':'missing, symlink or outside repository'})
        continue
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):
            digest.update(block)
    actual=digest.hexdigest()
    expected=record.get('frozen_recorded_sha256')
    if actual!=record['sha256'] or (expected and actual!=expected):
        errors.append({'path':str(relative),'error':'SHA-256 differs'})
    elif path.stat().st_size!=record['size_bytes']:
        errors.append({'path':str(relative),'error':'size differs'})
    else:
        verified+=1
attributes=(root/'.gitattributes').read_text()
if '* -text' not in attributes.splitlines():
    errors.append({'path':'.gitattributes','error':'required byte-preservation rule missing'})
print(json.dumps({'verified_files':verified,'selected_cases':len(manifest['selected_cases']),
                  'errors':errors,'source_files_modified':False},indent=2))
sys.exit(bool(errors))
