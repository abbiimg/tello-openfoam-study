"""SOURCE-ONLY V2 PROPOSAL: refresh study/** using native Windows file I/O.

No work occurs on import or without --execute. Root must review this source and
finish/close all GPU publications before executing the guarded command below.
Never imports or runs the Linux packagers, CFD, Git, or the case archive writer.

Pinned to Blender's existing CPython 3.13.13. Raw case local records are copied
without recompression; ZipInfo metadata is preserved except relocated offsets.
Private zipfile write bookkeeping is isolated in raw_copy_case_record().
"""
from __future__ import annotations

import argparse
import base64
import copy
import csv
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys
import time
import traceback
import uuid
import zipfile
from datetime import datetime, timezone


WORKSPACE = Path(r'C:\Users\abbii\Documents\Codex\2026-10-30\referenced-chatgpt-conversation-this-is-an')
OUT = WORKSPACE / 'outputs' / 'tello_refinement'
WORK = WORKSPACE / 'work' / 'native_compact_refresh_proposal'
NATIVE_PYTHON = Path(r'C:\Program Files\Blender Foundation\Blender 5.2\5.2\python\bin\python.exe')
COMPACT = OUT / 'setup_results.zip'
OLD_SHA256 = '2037fc17defc301532c51dc349c6323a46ac7a987c222c5b54763865f0fce7dd'
OLD_BYTES = 537362251
OLD_MEMBERS = 2468
EXPECTED_PROTECTED = {
    'cases.zip': 'ec070b211bad0b5e76d79ffb91c8c66a6cde3d778e4b02d6b9dc43b9472872df',
    'results/summary.csv': 'b0abc1404dadb4f9112ebdec73060f444df5aff67d491b4c96c5eda048a7b2c7',
    'approved_cases.json': '1b08141dc0929fd0adfaadbca62d97c611af8d7bb9f39d6137a1aa4cddf2c98d',
}
GPU_REPRODUCTION_ARCHIVES = frozenset((
    'gpu_feasibility/OGL_upstream_7c3ced4514fb.tar.gz',
    'gpu_feasibility/Ginkgo_upstream_13c917436066.tar.gz',
    'gpu_feasibility/benchmark_reproduction/shared_seed.zip',
))
SPUMA_PREFIX = PurePosixPath('gpu_feasibility/spuma')
SPUMA_MANIFEST_KEY = (SPUMA_PREFIX / 'manifest.json').as_posix()
SPUMA_MANIFEST_SHA256 = '4824419c7cb30822ddb51230c6976e0739028901d795a1365e331001319b4edd'
EMPTY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
SPUMA_DOTFILE_EXCEPTIONS = frozenset((
    'gpu_feasibility/spuma/spuma_evidence/original_failed/.spuma-smoke-started',
    'gpu_feasibility/spuma/spuma_evidence/strict_v2/.strict-v2-started',
))
# Receipts/checksums produced by this helper are always in WORK, never OUT.
# Also refuse accidental legacy copies of these external compact checksums.
EXTERNAL_RECEIPT_NAMES = frozenset((
    'setup_results.zip.sha256', 'setup_results.sha256',
    'setup_results.zip.receipt.json', 'setup_results.checksums.json',
    'compact_refresh_receipt.json', 'SHA256SUMS.setup_results',
))
CHUNK = 4 * 1024 * 1024
REPARSE_POINT = getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)


def fail(message):
    raise RuntimeError(message)


def lexical(path):
    return Path(os.path.abspath(os.fspath(path)))


def inside(path, root):
    path, root = lexical(path), lexical(root)
    try:
        path.relative_to(root)
    except ValueError:
        fail(f'Path is outside fixed allowed root: {path}')
    return path


def safe_path(path, *, root=WORKSPACE, missing_leaf=False):
    """Check every existing ancestor, including ancestors above WORKSPACE.

    Never resolve an unchecked junction or symlink. The fixed paths are local
    drive paths; UNC/device path aliases and reparse points are unsupported.
    """
    path = inside(path, root)
    if str(path).startswith(('\\\\', '\\?\\')):
        fail(f'UNC/device paths are not supported: {path}')
    for node in reversed((path,) + tuple(path.parents)):
        try:
            st = node.lstat()
        except FileNotFoundError:
            if missing_leaf and node == path:
                continue
            raise
        if stat.S_ISLNK(st.st_mode) or getattr(st, 'st_file_attributes', 0) & REPARSE_POINT:
            fail(f'Reparse point/symlink/junction is forbidden: {node}')
    return path


def stamp(path):
    safe_path(path)
    st = path.stat()
    if not stat.S_ISREG(st.st_mode):
        fail(f'Expected a regular file: {path}')
    if st.st_nlink != 1:
        fail(f'Hard-linked files are unsupported: {path}')
    return dict(size_bytes=st.st_size, mtime_ns=st.st_mtime_ns,
                ctime_ns=st.st_ctime_ns, device=st.st_dev, inode=st.st_ino,
                file_attributes=getattr(st, 'st_file_attributes', 0))


def stream_hash(stream, limit=None):
    h, count = hashlib.sha256(), 0
    while limit is None or count < limit:
        block = stream.read(CHUNK if limit is None else min(CHUNK, limit - count))
        if not block:
            break
        h.update(block); count += len(block)
    if limit is not None and count != limit:
        fail(f'Unexpected EOF: {count} of {limit} bytes')
    return h.hexdigest(), count


def file_record(path):
    before = stamp(path)
    with path.open('rb') as stream:
        sha, size = stream_hash(stream)
    after = stamp(path)
    if before != after or size != before['size_bytes']:
        fail(f'File changed while hashing: {path}')
    return dict(before, sha256=sha)


def json_closed(path, value):
    safe_path(path, root=WORK, missing_leaf=True)
    payload = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode('utf-8')
    with path.open('xb') as stream:
        stream.write(payload); stream.flush(); os.fsync(stream.fileno())
    return file_record(path)


def text_closed(path, text):
    safe_path(path, root=WORK, missing_leaf=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text); stream.flush(); os.fsync(stream.fileno())
    return file_record(path)


def reviewed_spuma_files():
    """Bind the two exact marker exceptions to the reviewed outer manifest.

    The pinned outer inventory also contains all nested manifest files. They
    are preserved as bytes, including historical candidate/review manifests;
    their historical relative namespaces are not reinterpreted as live roots.
    """
    manifest_path = OUT / Path(SPUMA_MANIFEST_KEY)
    before = file_record(manifest_path)
    if before['sha256'] != SPUMA_MANIFEST_SHA256:
        fail('Reviewed SPUMA outer manifest SHA256 changed')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if file_record(manifest_path) != before:
        fail('SPUMA outer manifest changed while parsing')
    files = manifest.get('files')
    if not isinstance(files, dict) or not files:
        fail('SPUMA outer manifest lacks its reviewed files mapping')
    expected = {}
    for name, row in files.items():
        if not isinstance(name, str):
            fail('SPUMA manifest paths must be strings')
        rel = PurePosixPath(name)
        if (not name or rel.is_absolute() or any(p in ('.', '..') for p in rel.parts)
                or '\\' in name or ':' in name or '\x00' in name or rel.as_posix() != name):
            fail(f'Unsafe SPUMA manifest path: {name!r}')
        if (not isinstance(row, dict) or not isinstance(row.get('bytes'), int)
                or row['bytes'] < 0 or not re.fullmatch(r'[0-9a-f]{64}', str(row.get('sha256', '')))):
            fail(f'Malformed SPUMA manifest record: {name}')
        expected[(SPUMA_PREFIX / rel).as_posix()] = dict(size_bytes=row['bytes'], sha256=row['sha256'])
    if SPUMA_MANIFEST_KEY in expected:
        fail('SPUMA outer manifest unexpectedly includes its own hash')
    expected[SPUMA_MANIFEST_KEY] = dict(size_bytes=before['size_bytes'], sha256=SPUMA_MANIFEST_SHA256)
    for key in SPUMA_DOTFILE_EXCEPTIONS:
        empty = dict(size_bytes=0, sha256=EMPTY_SHA256)
        if expected.get(key) != empty:
            fail(f'Exact empty marker is absent from reviewed SPUMA manifest: {key}')
        actual = file_record(OUT / Path(key))  # regular, no hardlinks/reparse ancestors
        if {name: actual[name] for name in empty} != empty:
            fail(f'Reviewed SPUMA marker is not the expected empty regular file: {key}')
    return expected


def require_spuma_inventory(records, expected, *, hashes):
    """No manifested file, including nested manifests, may be filtered out."""
    prefix = SPUMA_PREFIX.as_posix() + '/'
    actual_keys = {name for name in records if name.startswith(prefix)}
    if actual_keys != set(expected):
        fail('Study filter is not closed over reviewed SPUMA inventory; missing=' +
             repr(sorted(set(expected) - actual_keys)) + '; unexpected=' +
             repr(sorted(actual_keys - set(expected))))
    if hashes:
        for key, wanted in expected.items():
            actual = records[key]
            if any(actual[name] != value for name, value in wanted.items()):
                fail(f'SPUMA study file differs from its reviewed manifest: {key}')


def source_files():
    """Original filter plus ONLY two reviewed, manifest-bound SPUMA markers."""
    safe_path(OUT)
    spuma_expected = reviewed_spuma_files()
    selected = {}
    stack = [OUT]
    while stack:
        directory = stack.pop()
        safe_path(directory, root=OUT)
        for path in sorted(directory.iterdir(), key=lambda p: p.name):
            rel = path.relative_to(OUT)
            key = rel.as_posix()
            hidden = any(part.startswith('.') or part == '__pycache__' for part in rel.parts)
            if hidden and key not in SPUMA_DOTFILE_EXCEPTIONS:
                continue
            safe_path(path, root=OUT)
            if path.is_dir():
                stack.append(path)
                continue
            if not path.is_file() or path.suffix == '.pyc':
                continue
            if key in EXTERNAL_RECEIPT_NAMES:
                continue
            if path.suffix in ('.gz', '.zip') and key not in GPU_REPRODUCTION_ARCHIVES:
                continue
            if path == COMPACT or path.name == 'fullcases.zip':
                continue
            if key in selected:
                fail(f'Duplicate source key: {key}')
            selected[key] = path
    if not GPU_REPRODUCTION_ARCHIVES <= set(selected):
        fail('One or more required GPU reproduction archives are absent')
    require_spuma_inventory(selected, spuma_expected, hashes=False)
    return dict(sorted(selected.items()))


def inventory():
    records = {key: file_record(path) for key, path in source_files().items()}
    require_spuma_inventory(records, reviewed_spuma_files(), hashes=True)
    return records


def assert_current_inventory(expected, *, hashes):
    files = source_files()
    if set(files) != set(expected):
        fail('Study source membership changed during refresh')
    for key, path in files.items():
        current = file_record(path) if hashes else stamp(path)
        wanted = expected[key] if hashes else {k: v for k, v in expected[key].items() if k != 'sha256'}
        if current != wanted:
            fail(f'Study source changed during refresh: {key}')


def protected_snapshot():
    records = {}
    for key, expected in EXPECTED_PROTECTED.items():
        records[key] = file_record(OUT / key)
        if records[key]['sha256'] != expected:
            fail(f'Protected CPU84 SHA256 mismatch: {key}')
    return records


def member_name(name):
    rel = PurePosixPath(name)
    if (not name or '\\' in name or ':' in name or '\x00' in name or
            rel.is_absolute() or '..' in rel.parts or '.' in rel.parts or
            rel.as_posix() != name.rstrip('/')):
        fail(f'Unsafe/noncanonical ZIP member name: {name!r}')
    if not name.startswith(('cases/', 'study/')):
        fail(f'Unexpected ZIP member namespace: {name}')
    return rel


def catalog(archive):
    infos = archive.infolist()
    names = [i.filename for i in infos]
    if len(names) != len(set(names)):
        fail('ZIP contains duplicate member names')
    for info in infos:
        member_name(info.filename)
        if stat.S_ISLNK(info.external_attr >> 16):
            fail(f'ZIP symlink entry is unsupported: {info.filename}')
        if info.flag_bits & 1:
            fail(f'Encrypted ZIP entry is unsupported: {info.filename}')
    return {i.filename: i for i in infos}


def zip_metadata(info):
    fields = ('filename', 'orig_filename', 'date_time', 'compress_type',
              'create_system', 'create_version', 'extract_version', 'reserved',
              'flag_bits', 'volume', 'internal_attr', 'external_attr',
              'CRC', 'compress_size', 'file_size')
    result = {key: getattr(info, key) for key in fields}
    result['date_time'] = list(result['date_time'])
    result['extra_base64'] = base64.b64encode(info.extra).decode('ascii')
    result['comment_base64'] = base64.b64encode(info.comment).decode('ascii')
    return result


def offsets(archive):
    infos = sorted(archive.infolist(), key=lambda i: i.header_offset)
    if len({i.header_offset for i in infos}) != len(infos):
        fail('ZIP contains overlapping/duplicate local header offsets')
    spans = {}
    for index, info in enumerate(infos):
        end = infos[index + 1].header_offset if index + 1 < len(infos) else archive.start_dir
        if end <= info.header_offset or end - info.header_offset < 30 + info.compress_size:
            fail(f'Invalid ZIP local record boundary: {info.filename}')
        spans[info.filename] = (info.header_offset, end - info.header_offset)
    return spans


def approved_names():
    value = json.loads((OUT / 'approved_cases.json').read_text(encoding='utf-8'))
    if not isinstance(value, dict) or set(value) != {'cases'}:
        fail('Approved CPU84 JSON shape changed')
    names = value['cases']
    if (not isinstance(names, list) or len(names) != 84 or len(set(names)) != 84 or
            any(not isinstance(n, str) or not n or '/' in n or '\\' in n or ':' in n or n in ('.', '..') for n in names)):
        fail('Approved CPU84 membership is invalid')
    return sorted(names)


def membership_check(approved, old_members):
    old_cases = {PurePosixPath(name).parts[1] for name in old_members if name.startswith('cases/')}
    if old_cases != set(approved):
        fail('Old compact case membership differs from approved CPU84')
    with zipfile.ZipFile(OUT / 'cases.zip', 'r') as full:
        full_members = catalog(full)
        if any(not n.startswith('cases/') for n in full_members):
            fail('Full case archive contains an unexpected namespace')
        full_cases = {PurePosixPath(n).parts[1] for n in full_members}
    if full_cases != set(approved):
        fail('Full case archive membership differs from approved CPU84')
    with (OUT / 'results/summary.csv').open('r', encoding='utf-8', newline='') as stream:
        rows = list(csv.DictReader(stream))
    csv_names = [r['case'] for r in rows]
    if len(csv_names) != 84 or len(set(csv_names)) != 84 or set(csv_names) != set(approved):
        fail('CPU84 CSV case membership changed')
    return dict(approved_cases=approved, csv_cases=sorted(csv_names),
                old_compact_cases=sorted(old_cases), full_archive_cases=sorted(full_cases),
                full_archive_member_count=len(full_members))


def backup_old(destination):
    before = file_record(COMPACT)
    if before['sha256'] != OLD_SHA256 or before['size_bytes'] != OLD_BYTES:
        fail('Old compact archive differs from the pinned CPU84 snapshot')
    safe_path(destination, root=WORK, missing_leaf=True)
    h = hashlib.sha256()
    with COMPACT.open('rb') as source, destination.open('xb') as target:
        for block in iter(lambda: source.read(CHUNK), b''):
            h.update(block); target.write(block)
        target.flush(); os.fsync(target.fileno())
    if h.hexdigest() != OLD_SHA256 or file_record(COMPACT) != before:
        fail('Old compact archive changed while backing up')
    if file_record(destination)['sha256'] != OLD_SHA256:
        fail('Native backup verification failed')
    # Unique run path, exclusive creation, readonly attribute, and pinned hash.
    os.chmod(destination, stat.S_IREAD)
    result = file_record(destination)
    if not result['file_attributes'] & getattr(stat, 'FILE_ATTRIBUTE_READONLY', 1):
        fail('Immutable backup did not acquire the Windows readonly attribute')
    return result


def raw_copy_case_record(old_stream, target, info, span):
    """Preserve raw local header + compressed payload + descriptor/padding.

    A standard ZipFile writer emits the relocated central directory at close.
    Only header_offset is relocated; no case member is recompressed. Cases are
    written first so their new offsets stay below the old 537 MB boundary.
    """
    required = ('fp', 'filelist', 'NameToInfo', 'start_dir', '_didModify', '_writecheck')
    if not all(hasattr(target, name) for name in required):
        fail('Unexpected CPython zipfile implementation; raw copy is disabled')
    if info.filename in target.NameToInfo:
        fail(f'Duplicate output ZIP member: {info.filename}')
    copied = copy.copy(info)
    copied.header_offset = target.fp.tell()
    if copied.header_offset >= OLD_BYTES:
        fail('Raw case relocation unexpectedly exceeds original compact size')
    target._writecheck(copied)
    old_stream.seek(span[0])
    remaining, h = span[1], hashlib.sha256()
    while remaining:
        block = old_stream.read(min(CHUNK, remaining))
        if not block:
            fail('Unexpected EOF in old raw case record')
        target.fp.write(block); h.update(block); remaining -= len(block)
    target.filelist.append(copied)
    target.NameToInfo[copied.filename] = copied
    target.start_dir = target.fp.tell()
    target._didModify = True
    return dict(raw_record_sha256=h.hexdigest(), raw_record_bytes=span[1],
                source_header_offset=span[0], new_header_offset=copied.header_offset)


def add_study_file(target, key, record):
    path = OUT / Path(key)
    if file_record(path) != record:
        fail(f'Study file changed before copy: {key}')
    name = (PurePosixPath('study') / PurePosixPath(key)).as_posix()
    member_name(name)
    if name in target.NameToInfo:
        fail(f'Duplicate output ZIP member: {name}')
    info = zipfile.ZipInfo.from_file(path, arcname=name)
    info.compress_type = zipfile.ZIP_DEFLATED
    info._compresslevel = 6
    h, count = hashlib.sha256(), 0
    with path.open('rb') as source, target.open(info, 'w', force_zip64=True) as member:
        for block in iter(lambda: source.read(CHUNK), b''):
            h.update(block); count += len(block); member.write(block)
    if h.hexdigest() != record['sha256'] or count != record['size_bytes']:
        fail(f'Native study copy digest mismatch: {key}')
    if file_record(path) != record:
        fail(f'Study file changed after copy: {key}')


def create_candidate(backup, temporary, study):
    safe_path(temporary, root=OUT, missing_leaf=True)
    if temporary.exists():
        fail('Refusing to overwrite a candidate temporary ZIP')
    cases, old_study, case_raw = {}, {}, {}
    with zipfile.ZipFile(backup, 'r') as old, backup.open('rb') as raw:
        members = catalog(old)
        if len(members) != OLD_MEMBERS:
            fail(f'Pinned compact member count mismatch: {len(members)}')
        scope = membership_check(approved_names(), members)
        spans = offsets(old)
        for name, info in members.items():
            if name.startswith('cases/'):
                with old.open(info, 'r') as stream:
                    sha, size = stream_hash(stream)
                if size != info.file_size:
                    fail(f'Case member size mismatch: {name}')
                cases[name] = dict(sha256=sha, size_bytes=size, metadata=zip_metadata(info))
            else:
                old_study[name] = dict(size_bytes=info.file_size, CRC=info.CRC)
        with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED,
                             compresslevel=6, allowZip64=True) as new:
            new.comment = old.comment
            for info in sorted((i for i in members.values() if i.filename.startswith('cases/')),
                               key=lambda i: i.header_offset):
                case_raw[info.filename] = raw_copy_case_record(raw, new, info, spans[info.filename])
            for key, record in study.items():
                add_study_file(new, key, record)
    with temporary.open('r+b') as stream:
        stream.flush(); os.fsync(stream.fileno())
    return cases, case_raw, old_study, scope


def verify_candidate(path, cases, case_raw, study):
    expected = {name: {'sha256': r['sha256'], 'size_bytes': r['size_bytes']} for name, r in cases.items()}
    expected.update({(PurePosixPath('study') / PurePosixPath(key)).as_posix():
                     {'sha256': r['sha256'], 'size_bytes': r['size_bytes']} for key, r in study.items()})
    verified = {}
    with zipfile.ZipFile(path, 'r') as archive, path.open('rb') as raw:
        members = catalog(archive)
        if set(members) != set(expected):
            fail('Candidate archive membership is not exactly old cases + current study')
        spans = offsets(archive)
        for name, info in members.items():
            with archive.open(info, 'r') as stream:
                sha, size = stream_hash(stream)
            if {'sha256': sha, 'size_bytes': size} != expected[name]:
                fail(f'Candidate archive SHA256/size mismatch: {name}')
            verified[name] = dict(sha256=sha, size_bytes=size, CRC=info.CRC)
            if name in cases:
                if zip_metadata(info) != cases[name]['metadata']:
                    fail(f'Case ZipInfo/Unix mode changed: {name}')
                start, length = spans[name]
                raw.seek(start); raw_sha, raw_size = stream_hash(raw, length)
                if raw_sha != case_raw[name]['raw_record_sha256'] or raw_size != case_raw[name]['raw_record_bytes']:
                    fail(f'Raw compressed case record changed: {name}')
        bad = archive.testzip()
        if bad is not None:
            fail(f'Candidate full ZIP CRC failure: {bad}')
    return verified


def old_still_pinned():
    record = file_record(COMPACT)
    if record['sha256'] != OLD_SHA256 or record['size_bytes'] != OLD_BYTES:
        fail('The publish target changed; preserve all candidates for review')
    return record


def publish(temporary):
    safe_path(temporary, root=OUT)
    safe_path(COMPACT, root=OUT)
    # Same-directory Windows replace: never delete/rename the old archive first.
    for attempt in range(8):
        try:
            os.replace(temporary, COMPACT)
            return
        except OSError as exc:
            if getattr(exc, 'winerror', None) not in (32, 33) or attempt == 7:
                raise
            time.sleep(min(.25 * 2 ** attempt, 4))


def check_runtime():
    if os.name != 'nt' or platform.system() != 'Windows':
        fail('Native Windows I/O is mandatory; WSL/DrvFs execution is forbidden')
    if sys.version_info[:3] != (3, 13, 13):
        fail(f'Expected pinned CPython 3.13.13, got {sys.version}')
    executable = lexical(sys.executable)
    if os.path.normcase(str(executable)) != os.path.normcase(str(NATIVE_PYTHON)):
        fail(f'Use the existing pinned native Python: {NATIVE_PYTHON}')
    safe_path(WORKSPACE)
    safe_path(OUT)
    safe_path(WORK, root=WORK)


def main(args):
    plan = dict(mode='source-only proposal until explicit execution',
                helper_version=2, reviewed_SPUMA_manifest_sha256=SPUMA_MANIFEST_SHA256,
                exact_manifest_bound_dotfile_exceptions=sorted(SPUMA_DOTFILE_EXCEPTIONS),
                python=str(NATIVE_PYTHON), target=str(COMPACT), pinned_old_sha256=OLD_SHA256,
                source_scope='current filtered OUT files -> study/** only',
                cases_policy='raw copy every old cases/** local record; preserve content SHA256 and ZipInfo except offsets',
                backup_and_receipts_root=str(WORK), no_CFD_or_Git_or_case_archive_mutation=True)
    if not args.execute:
        print(json.dumps(plan, indent=2)); return
    if not args.confirm_gpu_publications_closed:
        fail('Execution requires --confirm-gpu-publications-closed after root closes every GPU output writer')
    check_runtime()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid.uuid4().hex[:12]
    run = WORK / ('run_' + run_id)
    safe_path(run, root=WORK, missing_leaf=True); run.mkdir()
    lock = WORK / '.refresh.lock'
    safe_path(lock, root=WORK, missing_leaf=True)
    lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    published = False
    try:
        os.write(lock_fd, (run_id + '\n').encode('ascii')); os.fsync(lock_fd)
        original = old_still_pinned()
        protected = protected_snapshot()
        study = inventory()
        json_closed(run / 'study_inventory_before.json', study)
        backup = run / 'CPU84_setup_results.original.zip'
        backup_record = backup_old(backup)
        temporary = OUT / ('.setup_results.zip.native-refresh-' + run_id + '.tmp')
        cases, raw_cases, old_study, scope = create_candidate(backup, temporary, study)
        json_closed(run / 'old_case_entry_manifest.json', cases)
        json_closed(run / 'case_raw_records.json', raw_cases)
        entries = verify_candidate(temporary, cases, raw_cases, study)
        entries_record = json_closed(run / 'candidate_entry_sha256.json', entries)
        candidate = file_record(temporary)
        json_closed(run / 'candidate_closed.json', dict(candidate, member_count=len(entries), full_crc_verified=True))
        # These are independent native reads, not size-only or prior-manifest shortcuts.
        if protected_snapshot() != protected:
            fail('Protected CPU84 files changed before publication')
        assert_current_inventory(study, hashes=True)
        json_closed(run / 'study_inventory_after.json', study)
        old_still_pinned()
        assert_current_inventory(study, hashes=False)
        if file_record(backup)['sha256'] != OLD_SHA256:
            fail('Immutable backup changed before publication')
        # Every study hash has been checked before/after its copy and in the ZIP;
        # the full rehash above plus immediate metadata pass checks the closed source set.
        publish(temporary); published = True
        closed = file_record(COMPACT)
        if closed['sha256'] != candidate['sha256'] or closed['size_bytes'] != candidate['size_bytes']:
            fail('Published compact ZIP differs from the closed verified candidate')
        if protected_snapshot() != protected:
            fail('Protected CPU84 files changed after publication')
        assert_current_inventory(study, hashes=True)
        closed_entries = verify_candidate(COMPACT, cases, raw_cases, study)
        if closed_entries != entries:
            fail('Published archive entry verification differs from candidate')
        added = sorted(set(entries) - set(old_study) - set(cases))
        removed = sorted(set(old_study) - set(entries))
        receipt = dict(format_version=1, helper_version=2, native_windows_io=True,
                       reviewed_SPUMA_manifest_sha256=SPUMA_MANIFEST_SHA256,
                       exact_manifest_bound_dotfile_exceptions=sorted(SPUMA_DOTFILE_EXCEPTIONS),
                       every_reviewed_SPUMA_manifest_member_in_study_inventory=True,
                       generated_utc=datetime.now(timezone.utc).isoformat(),
                       python=sys.version, executable=sys.executable, old_compact=original,
                       old_member_count=OLD_MEMBERS, immutable_backup=dict(path=str(backup), **backup_record),
                       new_compact=dict(path=str(COMPACT), **closed),
                       protected_CPU84_before_after_identical=protected,
                       membership=scope, study_member_count=len(study), case_member_count=len(cases),
                       new_member_count=len(entries), added_study_members=added, removed_study_members=removed,
                       candidate_entry_manifest=dict(path=str(run / 'candidate_entry_sha256.json'), **entries_record),
                       raw_case_records_identical=True, case_ZipInfo_and_Unix_modes_identical=True,
                       every_entry_SHA256_verified=True, full_CRC_candidate_and_published=True,
                       every_study_file_rehashed_before_after_copy_and_before_after_publish=True,
                       source_membership_unchanged=True, all_GPU_publications_closed_acknowledged=True,
                       full_case_archive_rebuilt=False, CFD_run=False, Git_changed=False)
        receipt_record = json_closed(run / 'receipt.json', receipt)
        text_closed(run / 'receipt.json.sha256', f'{receipt_record["sha256"]}  receipt.json\n')
        text_closed(run / 'setup_results.zip.sha256', f'{closed["sha256"]}  {COMPACT}\n')
        print(json.dumps(dict(status='published_verified', receipt=str(run / 'receipt.json'),
                              sha256=closed['sha256'], bytes=closed['size_bytes'], members=len(entries)), indent=2))
    except BaseException as exc:
        error = dict(error_type=type(exc).__name__, message=str(exc), target_already_published=published,
                     preserved_run_directory=str(run), traceback=traceback.format_exc())
        try:
            json_closed(run / 'failure.json', error)
        except BaseException:
            pass
        raise
    finally:
        os.close(lock_fd)
        safe_path(lock, root=WORK)
        # Fixed, checked, single file only; no recursive cleanup or deletion of evidence.
        lock.unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Mutate only after root reviews and closes all output writers')
    parser.add_argument('--confirm-gpu-publications-closed', action='store_true')
    main(parser.parse_args())
