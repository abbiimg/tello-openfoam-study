"""Focused path/pin adversarial fixtures; no case restoration or solver launch.

Run beside restore_pilots.py with --seed-dir pointing to the external frozen
benchmark_reproduction package. Temporary symlink fixtures touch only a fresh
TemporaryDirectory and never modify the real seed.
"""
from pathlib import Path
import argparse
import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
import sys

sys.dont_write_bytecode=True

spec=importlib.util.spec_from_file_location('restore_under_test',Path(__file__).with_name('restore_pilots.py'))
restore=importlib.util.module_from_spec(spec)
spec.loader.exec_module(restore)
FIXTURE_REJECTIONS=0

class PathChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='amgx-restore-paths-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'seed'; self.source.mkdir()
        self.outside=self.root/'outside.txt'; self.outside.write_text('must remain unchanged\n')
        self.before=self.outside.read_bytes()
        self.dest=self.root/'not-created'
        self.manifest=copy.deepcopy(MANIFEST)
        self.variant=self.manifest['variants']['cpu_serial']
        self.original=copy.deepcopy(ORIGINAL)

    def tearDown(self):
        self.assertEqual(self.outside.read_bytes(),self.before)
        self.assertFalse(self.dest.exists())

    def test_real_catalogue_and_safe_file_names(self):
        restore.validate_catalogues(self.manifest,self.variant,self.original)
        for path in ('0.6/U','system/fvSolution','constant/polyMesh/points','.hidden/file.txt'):
            target=restore.safe_join(self.dest,path)
            self.assertTrue(target.is_relative_to(self.dest))

    def test_every_external_catalogue_rejects_unsafe_names_before_mkdir(self):
        global FIXTURE_REJECTIONS
        bad=('', '.', '..', '/escape', '//server/share', 'a/../escape', 'a/./b',
             './a', 'a//b', 'a/', 'C:/escape', 'C:\\escape', '\\\\server\\share',
             'a\\b', 'file:stream', 'a\x00b')
        for catalogue in ('override_files','shared_seed_files','frozen_inputs'):
            for path in bad:
                with self.subTest(catalogue=catalogue,path=repr(path)):
                    manifest=copy.deepcopy(MANIFEST); variant=manifest['variants']['cpu_serial']; original=copy.deepcopy(ORIGINAL)
                    table=variant[catalogue] if catalogue=='override_files' else manifest[catalogue] if catalogue=='shared_seed_files' else original[catalogue]
                    table[path]=dict(sha256='0'*64,size_bytes=1)
                    with self.assertRaises(ValueError): restore.validate_catalogues(manifest,variant,original)
                    self.assertFalse(self.dest.exists())
                    FIXTURE_REJECTIONS+=1

    def test_external_records_cannot_replace_pinned_controls(self):
        self.variant['override_files']['system/controlDict']['sha256']='0'*64
        with self.assertRaises(ValueError): restore.validate_catalogues(self.manifest,self.variant,self.original)

    def test_self_consistent_replacement_cpu_manifest_rejected(self):
        folder=self.source/'overrides/cpu_serial'; folder.mkdir(parents=True)
        replacement=copy.deepcopy(ORIGINAL)
        replacement['end_time_s']=99
        payload=(json.dumps(replacement)+'\n').encode()
        (folder/'benchmark_manifest.json').write_bytes(payload)
        variant=copy.deepcopy(self.variant)
        variant['benchmark_manifest_sha256']=hashlib.sha256(payload).hexdigest()
        with self.assertRaises(ValueError): restore.load_pinned_cpu_manifest(self.source,variant)
        # Retaining the expected metadata hash cannot disguise changed file bytes.
        with self.assertRaises(ValueError): restore.load_pinned_cpu_manifest(self.source,self.variant)

    def test_pinned_cpu_manifest_positive_control(self):
        folder=self.source/'overrides/cpu_serial'; folder.mkdir(parents=True)
        (folder/'benchmark_manifest.json').write_bytes(CPU_BYTES)
        self.assertEqual(restore.load_pinned_cpu_manifest(self.source,self.variant),ORIGINAL)

    def test_source_symlink_ancestors_leaves_inside_and_dangling_rejected(self):
        folder=self.source/'overrides/cpu_serial'; folder.mkdir(parents=True)
        (folder/'outside-dir').symlink_to(self.root,target_is_directory=True)
        (folder/'outside-leaf').symlink_to(self.outside)
        (folder/'inside').write_text('regular\n')
        (folder/'inside-link').symlink_to(folder/'inside')
        (folder/'dangling').symlink_to(self.root/'absent')
        for path in ('outside-dir/outside.txt','outside-leaf','inside-link','dangling'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError): restore.safe_join(folder,path,must_exist=True)
        self.assertEqual(restore.safe_join(folder,'inside',must_exist=True).read_text(),'regular\n')

    def test_destination_symlink_ancestor_leaf_and_selected_root_rejected(self):
        selected=self.root/'selected'; selected.mkdir()
        (selected/'escape').symlink_to(self.root,target_is_directory=True)
        (selected/'leaf').symlink_to(self.outside)
        for path in ('escape/new-case/U','leaf'):
            with self.subTest(path=path):
                with self.assertRaises(ValueError): restore.safe_join(selected,path)
        chosen=self.root/'chosen-link'; chosen.symlink_to(selected,target_is_directory=True)
        with self.assertRaises(ValueError): restore.no_symlink_path(chosen/'new-case')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed-dir',type=Path,required=True)
    parser.add_argument('--report',type=Path)
    args=parser.parse_args()
    global MANIFEST,ORIGINAL,CPU_BYTES
    MANIFEST=json.loads((args.seed_dir/'reproduction_manifest.json').read_text())
    CPU_BYTES=(args.seed_dir/'overrides/cpu_serial/benchmark_manifest.json').read_bytes()
    if hashlib.sha256(CPU_BYTES).hexdigest()!=restore.CPU_MANIFEST_SHA:
        raise ValueError('Positive-control CPU manifest is not the pinned actual file')
    ORIGINAL=json.loads(CPU_BYTES)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(PathChecks))
    report=dict(kind='Focused external-path and manifest-pin fixtures',passed=result.wasSuccessful(),
                tests_run=result.testsRun,unsafe_catalogue_names_rejected=FIXTURE_REJECTIONS,
                failures=len(result.failures),errors=len(result.errors),skips=len(result.skipped),
                actual_cpu_manifest_sha256=restore.CPU_MANIFEST_SHA,
                real_seed_modified=False,case_restoration_executed=False,
                build_or_solver_launched=False,
                scope='Static unsafe metadata and existing symlink traversal; not a hostile concurrent-filesystem race proof')
    if args.report: args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['passed'] else 1)

if __name__=='__main__': main()
