"""Fetch/extract the official ARM64 Nsight CLI into one fresh private prefix.

No package scripts, driver/system/profile/default changes, or GPU execution.
"""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess,urllib.request,urllib.parse
PREFIX=Path('/opt/openfoam-workspace/gpu-feasibility/nsight-systems-2026.5.1')
URL='https://developer.nvidia.com/downloads/assets/tools/secure/nsight-systems/2026_5/nsight-systems-cli-2026.5.1_2026.5.1.161-1_arm64.deb'
SOURCE='https://developer.nvidia.com/nsight-systems/get-started'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()
assert os.geteuid()==999 and PREFIX.parent.resolve()==Path('/opt/openfoam-workspace/gpu-feasibility')
assert not PREFIX.parent.is_symlink() and not PREFIX.is_symlink()
if PREFIX.exists():
    assert PREFIX.is_dir() and PREFIX.stat().st_uid==999
else:
    PREFIX.mkdir()
archive=PREFIX/'nsight-systems-cli-2026.5.1_2026.5.1.161-1_arm64.deb'
request=urllib.request.Request(URL,headers={'User-Agent':'OpenFOAM-local-dependency-setup'})
if not archive.exists():
    assert not list(PREFIX.iterdir())
    with urllib.request.urlopen(request,timeout=60) as response, archive.open('xb') as out:
        parsed=urllib.parse.urlsplit(response.url)
        assert parsed.scheme=='https' and parsed.hostname=='developer.download.nvidia.com'
        while True:
            block=response.read(1024*1024)
            if not block:break
            out.write(block)
        out.flush();os.fsync(out.fileno())
else:
    assert {p.name for p in PREFIX.iterdir()}=={archive.name} and not archive.is_symlink()
safe_final=URL.replace('https://developer.nvidia.com/downloads/','https://developer.download.nvidia.com/')
assert sha(archive)=='087c08b5ddf3ed6f913748f8206d6bbdc225f2aa275ff33af4c487e8b319c8ab'
metadata={}
for key in ['Package','Version','Architecture','Depends']:
    metadata[key]=subprocess.check_output(['dpkg-deb','--field',str(archive),key],text=True).strip()
assert metadata['Package']=='nsight-systems-cli-2026.5.1'
assert metadata['Architecture']=='arm64' and metadata['Version']=='2026.5.1.161-265138896106v0'
extracted=PREFIX/'extracted';extracted.mkdir()
subprocess.run(['dpkg-deb','--extract',str(archive),str(extracted)],check=True)
candidates=[p for p in extracted.rglob('nsys') if p.is_file() and os.access(p,os.X_OK)]
assert candidates,'No executable nsys in the official package'
receipt={'installed_utc':datetime.now(timezone.utc).isoformat(),
    'source_page':SOURCE,'canonical_download_url':URL,'final_download_url_without_query':safe_final,
    'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,
    'checksum_origin':'SHA256 of exact official-HTTPS download; no separate vendor checksum was supplied by the download page',
    'package_metadata':metadata,'extraction_root':str(extracted),
    'nsys_candidates':[{'path':str(p),'sha256':sha(p)} for p in candidates],
    'package_scripts_executed':False,'global_or_existing_SDK_files_changed':False,
    'GPU_or_CFD_executed':False,'default_backend_changed':False}
(PREFIX/'installation_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt,indent=2))
