#!/usr/bin/env python3
"""Verify or restore exact optional inputs from the separately supplied ZIP.

Default: verify archive, selected members and existing destinations; write nothing.
With --restore: stage and verify every missing file before publishing complete
files atomically without replacement. No bulk extraction, CFD or network.
An interrupted publication can leave a subset of complete verified files; rerun
safely skips those files. It never replaces an existing mismatched destination.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
import zipfile

MANIFEST_SHA256 = "67b8c09c37c5ed1939152c4f5b7732a377e94bddb8ae007cee10fcd2873f4e79"
CHUNK = 1024 * 1024
HEX = re.compile(r"[0-9a-f]{64}\Z")
RESERVED = re.compile(r"(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?\Z", re.I)


def fail(message):
    raise ValueError(message)


def native_path(path):
    """Explicit long-path IO on Windows; no machine policy/registry changes."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        fail("Use direct absolute paths")
    if os.name == "nt" and not str(path).startswith("\\\\?\\"):
        if not re.fullmatch(r"[A-Za-z]:", path.drive):
            fail("Windows restoration uses local drive paths")
        return Path("\\\\?\\" + str(path))
    return path


def relative_name(value):
    if not isinstance(value, str) or not value or "\\" in value or ":" in value or "\0" in value:
        fail("Unsafe relative name")
    parts = value.split("/")
    if any(p in ("", ".", "..") or p.endswith((".", " ")) or RESERVED.fullmatch(p)
           or any(c in '<>"|?*' or ord(c) < 32 for c in p) for p in parts):
        fail("Unsafe relative path component")
    if PurePosixPath(value).is_absolute():
        fail("Absolute paths are forbidden")
    return parts


def no_links(path, *, allow_missing=False):
    """Inspect lexical ancestors before resolve; reject all Windows reparses."""
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        fail("Use a lexical absolute path without parent traversals")
    parts = list(reversed((path, *path.parents)))
    for item in parts:
        try:
            info = item.lstat()
        except FileNotFoundError:
            if allow_missing:
                return
            raise
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            fail(f"Symlink, junction or reparse point forbidden: {item}")


def digest_stream(stream, output=None):
    digest, size = hashlib.sha256(), 0
    for block in iter(lambda: stream.read(CHUNK), b""):
        digest.update(block)
        size += len(block)
        if output is not None:
            output.write(block)
    return digest.hexdigest(), size


def digest_file(path):
    no_links(path)
    if not stat.S_ISREG(path.lstat().st_mode):
        fail(f"Expected regular file: {path}")
    with path.open("rb") as stream:
        return digest_stream(stream)


def check_record(record):
    if not isinstance(record.get("sha256"), str) or not HEX.fullmatch(record["sha256"]):
        fail("Invalid SHA256")
    if type(record.get("size_bytes")) is not int or record["size_bytes"] < 0:
        fail("Invalid file size")


def validate_manifest(manifest):
    if manifest.get("schema") != "tello-external-inputs-v1":
        fail("Unexpected manifest schema")
    check_record(manifest["archive"])
    targets, members = set(), set()
    for row in manifest["files"]:
        relative_name(row["repository_path"])
        relative_name(row["archive_member"])
        check_record(row)
        target = row["repository_path"].casefold()
        if relative_name(row["repository_path"])[0].casefold() in (".git", ".hg", ".svn"):
            fail("Version-control metadata is not a restoration target")
        if target in targets or row["archive_member"] in members:
            fail("Duplicate or aliased requested member/destination")
        targets.add(target)
        members.add(row["archive_member"])
    if len(targets) != manifest["file_count"] or sum(r["size_bytes"] for r in manifest["files"]) != manifest["total_size_bytes"]:
        fail("Manifest count/size mismatch")
    for row in manifest["project_identity"]:
        relative_name(row["path"])
        check_record(row)


def checked_destination(root, name):
    path = root.joinpath(*relative_name(name))
    no_links(path, allow_missing=True)
    return path


def existing_exact(path, record):
    no_links(path, allow_missing=True)
    if not path.exists():
        return False
    if digest_file(path) != (record["sha256"], record["size_bytes"]):
        fail(f"Existing destination differs; no overwrite allowed: {path}")
    return True


def validate_project(root, manifest):
    no_links(root)
    if not root.is_dir() or root == Path(root.anchor):
        fail("Project root must be an existing non-root directory")
    for row in manifest["project_identity"]:
        path = checked_destination(root, row["path"])
        if digest_file(path) != (row["sha256"], row["size_bytes"]):
            fail("Project identity differs; select the matching source repository")


def archive_catalog(archive, manifest):
    result = {}
    for info in archive.infolist():
        if info.orig_filename != info.filename:
            fail("Truncated or normalized ZIP name")
        name = info.filename[:-1] if info.is_dir() else info.filename
        relative_name(name)
        if info.filename in result:
            fail("Duplicate ZIP member")
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR) or info.flag_bits & 1:
            fail("Linked, special or encrypted ZIP member")
        result[info.filename] = info
    if len(result) != manifest["archive"]["members"]:
        fail("ZIP membership count differs")
    for row in manifest["files"]:
        info = result.get(row["archive_member"])
        if info is None or info.is_dir() or info.file_size != row["size_bytes"]:
            fail(f"Selected ZIP member missing or wrong size: {row['archive_member']}")
    return result


def restore_from_archive(root, archive_path, manifest, *, restore=False):
    """Library entry point; CLI additionally pins the exact manifest bytes."""
    validate_manifest(manifest)
    root = native_path(root)
    archive_path = native_path(archive_path)
    validate_project(root, manifest)
    no_links(archive_path)
    if not stat.S_ISREG(archive_path.lstat().st_mode):
        fail("Archive must be a regular file")
    destinations = {}
    matching = []
    for row in manifest["files"]:
        dest = checked_destination(root, row["repository_path"])
        destinations[row["repository_path"]] = dest
        if existing_exact(dest, row):
            matching.append(row["repository_path"])
    staged = None
    temporary_paths = []
    published = []
    try:
        with archive_path.open("rb") as source:
            before = os.fstat(source.fileno())
            expected = manifest["archive"]
            if before.st_size != expected["size_bytes"] or digest_stream(source) != (expected["sha256"], expected["size_bytes"]):
                fail("Whole archive SHA256/size differs")
            source.seek(0)
            with zipfile.ZipFile(source) as archive:
                catalog = archive_catalog(archive, manifest)
                if restore:
                    no_links(root)
                    staged = Path(tempfile.mkdtemp(prefix=".external-inputs-", dir=root))
                for number, row in enumerate(manifest["files"]):
                    temporary = None
                    if restore and row["repository_path"] not in matching:
                        temporary = staged / str(number)
                        with temporary.open("xb") as target:
                            temporary_paths.append(temporary)
                            with archive.open(catalog[row["archive_member"]]) as member:
                                actual = digest_stream(member, target)
                            target.flush()
                            os.fsync(target.fileno())
                        os.chmod(temporary, 0o644)
                    else:
                        with archive.open(catalog[row["archive_member"]]) as member:
                            actual = digest_stream(member)
                    if actual != (row["sha256"], row["size_bytes"]):
                        fail(f"Selected member SHA256/size differs: {row['archive_member']}")
            after = os.fstat(source.fileno())
            if (before.st_size, before.st_mtime_ns, before.st_dev, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_dev, after.st_ino):
                fail("Archive changed during verification")
        if restore:
            validate_project(root, manifest)
            # All payloads have passed before the first destination is published.
            for number, row in enumerate(manifest["files"]):
                dest = destinations[row["repository_path"]]
                if existing_exact(dest, row):
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                no_links(dest.parent)
                no_links(staged / str(number))
                # Windows rename fails if destination exists; POSIX rename can
                # replace it, so POSIX uses atomic create-if-absent hard links.
                if os.name == "nt":
                    os.rename(staged / str(number), dest)
                else:
                    os.link(staged / str(number), dest, follow_symlinks=False)
                    (staged / str(number)).unlink()
                no_links(dest)
                published.append(row["repository_path"])
        return {"archive_verified": True, "selected_members_verified": len(manifest["files"]),
                "selected_bytes": manifest["total_size_bytes"], "restore_requested": restore,
                "already_matching": matching, "restored": published,
                "note": "Exact optional inputs only; no solver, build, bulk extraction or network."}
    finally:
        if staged is not None:
            # Remove only exact files we created, never arbitrary recursive trees.
            no_links(staged)
            if staged.parent != root or not staged.name.startswith(".external-inputs-"):
                fail("Refusing cleanup outside our exact owned staging directory")
            for path in temporary_paths:
                no_links(path, allow_missing=True)
                if not path.exists():
                    continue
                if not stat.S_ISREG(path.lstat().st_mode):
                    fail("Staging file type changed; preserve it for review")
                path.unlink()
            staged.rmdir()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if ".." in args.project_root.parts or ".." in args.archive.parts:
        fail("Parent traversal is forbidden; use direct paths")
    root = native_path(args.project_root.absolute())
    archive_path = native_path(args.archive.absolute())
    no_links(root)
    manifest_path = root / "external_inputs_manifest.json"
    no_links(manifest_path)
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != MANIFEST_SHA256:
        fail("External-input manifest differs from this reviewed helper")
    manifest = json.loads(raw)
    print(json.dumps(restore_from_archive(root, archive_path, manifest, restore=args.restore), indent=2))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
