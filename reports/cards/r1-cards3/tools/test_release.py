"""Filesystem-only controls; never imports an engine or touches real roots."""
import errno
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('cards3_release', Path(__file__).with_name('release.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class ReleaseControls(unittest.TestCase):
    def test_publish_never_replaces_existing_empty_destination(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); src = root / 'staging'; dst = root / 'existing'
            src.mkdir(); dst.mkdir(); (src / 'owned').write_text('preserve')
            with self.assertRaises(OSError) as caught: m.publish(src, dst)
            self.assertEqual(caught.exception.errno, errno.EEXIST)
            self.assertTrue(dst.is_dir()); self.assertEqual(list(dst.iterdir()), [])
            self.assertEqual((src / 'owned').read_text(), 'preserve')

    def test_freeze_does_not_follow_external_symlink(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); outside = root / 'outside'; outside.write_text('unchanged')
            before = outside.stat().st_mode; tree = root / 'tree'; tree.mkdir()
            (tree / 'regular').write_text('inside'); (tree / 'link').symlink_to(outside)
            m.freeze(tree)
            self.assertTrue(m.readonly(tree)); self.assertEqual(outside.stat().st_mode, before)
            self.assertEqual(outside.read_text(), 'unchanged')
            tree.chmod(0o700); (tree / 'regular').chmod(0o600)

    def test_inventory_detects_content_mode_and_link_changes(self):
        with tempfile.TemporaryDirectory() as name:
            tree = Path(name); p = tree / 'file'; p.write_text('first')
            h = m.digest(m.inventory(tree)); p.write_text('second')
            self.assertNotEqual(h, m.digest(m.inventory(tree)))
            h = m.digest(m.inventory(tree)); p.chmod(p.stat().st_mode ^ 0o100)
            self.assertNotEqual(h, m.digest(m.inventory(tree)))
            link = tree / 'link'; link.symlink_to('file'); h = m.digest(m.inventory(tree))
            link.unlink(); link.symlink_to('elsewhere')
            self.assertNotEqual(h, m.digest(m.inventory(tree)))

    def test_metadata_output_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as name:
            p = Path(name) / 'receipt'; m.write_new(p, {'original': True})
            with self.assertRaises(AssertionError): m.write_new(p, {'replacement': True})
            self.assertEqual(json.loads(p.read_text()), {'original': True})

    def test_create_preserves_sources_parents_and_existing_releases(self):
        with tempfile.TemporaryDirectory() as name:
            root = Path(name); job = root / 'job'; job.mkdir()
            roots = root / 'releases'; roots.mkdir()
            old_roots, old_native = m.RUNTIMES, m.NATIVE
            try:
                m.RUNTIMES = roots
                for parent in ('r1-cards2-r3', 'live16402b-r3'):
                    tree = roots / parent; tree.mkdir(); (tree / 'data').write_text(parent)
                    receipt = tree / 'RECEIPT.json'; receipt.write_text('{}')
                    m.freeze(tree); manifest = m.digest(m.inventory(tree, True))
                    receipt.chmod(0o600); receipt.write_text(json.dumps({'content_manifest_sha256':manifest})); receipt.chmod(0o400)
                source = job / 'publish-inputs/r1-cards3'; (source / 'native').mkdir(parents=True)
                (source / 'native/clasher_core.abi3.so').write_bytes(b'test-native')
                (source / 'gamedata.json').write_text('{}')
                m.NATIVE = m.sha(source / 'native/clasher_core.abi3.so'); m.freeze(source)
                expected = dict(content_manifest_sha256=m.digest(m.inventory(source)), overlay_files={},
                    assembler_receipts={}, gamedata_sha256=m.sha(source / 'gamedata.json'))
                manifest_path = job / 'publish-inputs/SOURCE.json'
                manifest_path.write_text(json.dumps({'roots':{'r1-cards3':expected}}))
                verifier = job / 'release-verifier/bot/players/runtime.py'; verifier.parent.mkdir(parents=True); verifier.write_text('# test verifier')
                before = m.parents(); source_before = m.inventory(source)
                m.run(job, 'r1-cards3', 'create', m.sha(manifest_path))
                target = roots / 'r1-cards3'; self.assertTrue(m.readonly(target))
                self.assertEqual(m.inventory(source), source_before); self.assertEqual(m.parents(), before)
                self.assertEqual(m.digest(m.inventory(target, True)), expected['content_manifest_sha256'])
                h = m.digest(m.inventory(target))
                (job / 'r1-cards3-create.json').unlink()
                with self.assertRaises(AssertionError): m.run(job, 'r1-cards3', 'create', m.sha(manifest_path))
                self.assertEqual(m.digest(m.inventory(target)), h)
            finally:
                m.RUNTIMES, m.NATIVE = old_roots, old_native
                # Only this test's temporary tree; permit TemporaryDirectory cleanup.
                for path in [root, *root.rglob('*')]:
                    if not path.is_symlink(): path.chmod(path.stat().st_mode | 0o700)


if __name__ == '__main__': unittest.main()
