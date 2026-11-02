#!/usr/bin/env python3
"""Download one official private SDK, verify official MD5 and record SHA-256."""
import hashlib
import json
import os
import pathlib
import time
import urllib.request
from datetime import datetime, timezone

PREFIX = pathlib.Path("/opt/openfoam-workspace/gpu-feasibility/native-stdpar")
FILENAME = "nvhpc_2026_269_Linux_aarch64_cuda_13.3.tar.gz"
URL = "https://developer.download.nvidia.com/hpc-sdk/26.9/" + FILENAME
CHECKSUM_URL = "https://developer.download.nvidia.com/hpc-sdk/26.9/md5sum.txt"
UID, GID = 999, 989

def utc():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    os.replace(tmp, path)
    os.chown(path, UID, GID)

def main():
    os.nice(15)
    for p in [PREFIX, PREFIX/"downloads", PREFIX/"logs", PREFIX/"source", PREFIX/"provenance"]:
        p.mkdir(exist_ok=True, parents=True)
        os.chown(p, UID, GID)
    with urllib.request.urlopen(CHECKSUM_URL, timeout=60) as r:
        checksum_bytes = r.read()
    (PREFIX/"provenance/nvidia-official-md5sum.txt").write_bytes(checksum_bytes)
    matches = [line.split()[0] for line in checksum_bytes.decode().splitlines() if line.split() and line.split()[-1].lstrip("*").split("/")[-1] == FILENAME]
    if len(matches) != 1:
        raise RuntimeError("Official MD5 entry missing/ambiguous: " + repr(matches))
    expected_md5 = matches[0].lower()
    target = PREFIX/"downloads"/FILENAME
    part = target.with_suffix(target.suffix + ".part")
    state_path = PREFIX/"download_progress.json"
    started = time.monotonic()
    sha, md5 = hashlib.sha256(), hashlib.md5()
    count = 0
    if part.exists():
        with part.open("rb") as f:
            while chunk := f.read(16*1024*1024):
                sha.update(chunk); md5.update(chunk); count += len(chunk)
    if target.exists():
        part = target
        sha, md5, count = hashlib.sha256(), hashlib.md5(), 0
        with target.open("rb") as f:
            while chunk := f.read(16*1024*1024):
                sha.update(chunk); md5.update(chunk); count += len(chunk)
        total = count
    else:
        req = urllib.request.Request(URL, headers={"Range": "bytes=" + str(count) + "-"} if count else {})
        with urllib.request.urlopen(req, timeout=90) as r:
            if count and r.status != 206:
                raise RuntimeError("Resume requires HTTP 206, received " + str(r.status))
            total = int(r.headers["Content-Length"]) + count
            last = 0.0
            with part.open("ab" if count else "wb") as f:
                while chunk := r.read(8*1024*1024):
                    f.write(chunk); sha.update(chunk); md5.update(chunk); count += len(chunk)
                    now = time.monotonic()
                    if now-last >= 5:
                        atomic_json(state_path, {"stage":"downloading","updated_utc":utc(),"url":URL,"downloaded_bytes":count,"total_bytes":total,"elapsed_s":now-started,"nice":os.getpriority(os.PRIO_PROCESS,0)})
                        last = now
    if md5.hexdigest().lower() != expected_md5:
        raise RuntimeError("Official MD5 verification failed")
    if count != total:
        raise RuntimeError("Size mismatch")
    if part != target:
        os.replace(part, target)
    os.chown(target, UID, GID)
    result = {"stage":"download_verified","completed_utc":utc(),"url":URL,"archive":str(target),"bytes":count,"sha256":sha.hexdigest(),"md5":md5.hexdigest(),"official_md5":expected_md5,"official_md5_url":CHECKSUM_URL,"official_checksum_document_sha256":hashlib.sha256(checksum_bytes).hexdigest(),"elapsed_s":time.monotonic()-started,"nice":os.getpriority(os.PRIO_PROCESS,0),"no_driver_or_system_package_changes":True}
    atomic_json(PREFIX/"provenance/nvhpc_archive.json",result)
    atomic_json(state_path,result)
    print(json.dumps(result),flush=True)

if __name__ == "__main__":
    main()

