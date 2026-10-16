"""Temporary-directory safety checks; never accesses runtime roots or hosts."""
from pathlib import Path
import tempfile
import unittest

from reports.cards.runtime.tools.release_objects import publish_new, validate_layout


class ReleaseSafetyTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.source=self.root/'source';self.source.mkdir()
        self.parent=self.root/'parent';self.parent.mkdir()
        self.target=self.root/'target'
        self.out=self.root/'verify.json'

    def test_output_cannot_overlap_source_parent_or_target(self):
        for base in (self.source,self.parent,self.target):
            with self.subTest(base=base):
                with self.assertRaisesRegex(SystemExit,'overlaps'):
                    validate_layout(self.source,self.parent,self.target,base/'receipt.json',creating=True)

    def test_symlinked_output_ancestor_rejected(self):
        alias=self.root/'alias';alias.symlink_to(self.root,target_is_directory=True)
        with self.assertRaisesRegex(SystemExit,'symlinked destination ancestor'):
            validate_layout(self.source,self.parent,self.target,alias/'verify.json',creating=True)

    def test_existing_output_preserved(self):
        self.out.write_text('preserve')
        with self.assertRaisesRegex(AssertionError,'OUTPUT_EXISTS_STOP'):
            validate_layout(self.source,self.parent,self.target,self.out,creating=True)
        self.assertEqual(self.out.read_text(),'preserve')

    def test_publish_cannot_replace_even_empty_existing_root(self):
        staging=self.root/'staging';staging.mkdir()
        (staging/'payload').write_text('candidate')
        self.target.mkdir();before=self.target.stat().st_ino
        with self.assertRaises(FileExistsError):publish_new(staging,self.target)
        self.assertEqual(self.target.stat().st_ino,before)
        self.assertEqual((staging/'payload').read_text(),'candidate')

    def test_publish_new_root(self):
        staging=self.root/'staging';staging.mkdir()
        (staging/'payload').write_text('candidate')
        publish_new(staging,self.target)
        self.assertFalse(staging.exists())
        self.assertEqual((self.target/'payload').read_text(),'candidate')


if __name__=='__main__':unittest.main()
