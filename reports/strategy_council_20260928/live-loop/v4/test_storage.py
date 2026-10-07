import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import shipper

class ShippingTest(unittest.TestCase):
    def make(self,root):
        folder=root/'v4-test-1';folder.mkdir()
        (folder/'video.mp4').write_bytes(b'not-real-video')
        (folder/'events.jsonl').write_text('{}\n')
        (folder/'receipt.json').write_text('{}\n')
        return folder
    def test_failed_remote_hash_preserves_every_local_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=self.make(root)
            def run(args,**kw):
                if 'python3 -B -c ' in args[-1]:return SimpleNamespace(stdout=json.dumps(dict(episode=folder.name,hashes={},verified_files=0)))
                return SimpleNamespace(stdout='')
            with patch.object(shipper,'run',run),self.assertRaises(ValueError):shipper.ship(folder,root/'receipts')
            self.assertTrue((folder/'video.mp4').exists())
            self.assertTrue((folder/'receipt.json').exists())
            self.assertFalse((root/'receipts').exists())
    def test_matching_remote_hash_retains_labels_and_receipt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=self.make(root)
            def run(args,**kw):
                if 'python3 -B -c ' in args[-1]:
                    h=json.loads((folder/'sha256.json').read_text())
                    return SimpleNamespace(stdout=json.dumps(dict(episode=folder.name,hashes=h,verified_files=len(h),bytes=20)))
                return SimpleNamespace(stdout='')
            with patch.object(shipper,'run',run):shipper.ship(folder,root/'receipts')
            self.assertFalse(folder.exists())
            self.assertTrue((root/'verified-labels/v4-test-1/events.jsonl').exists())
            self.assertTrue((root/'receipts/v4-test-1.json').exists())
    def test_local_mutation_after_remote_ack_cannot_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=self.make(root)
            def run(args,**kw):
                if 'python3 -B -c ' in args[-1]:
                    h=json.loads((folder/'sha256.json').read_text());(folder/'video.mp4').write_bytes(b'changed')
                    return SimpleNamespace(stdout=json.dumps(dict(episode=folder.name,hashes=h,verified_files=len(h),bytes=20)))
                return SimpleNamespace(stdout='')
            with patch.object(shipper,'run',run),self.assertRaises(ValueError):shipper.ship(folder,root/'receipts')
            self.assertTrue((folder/'video.mp4').exists())

class GuardTest(unittest.TestCase):
    def test_cap_and_free_space(self):
        import collector
        with patch.object(collector,'buffer_bytes',return_value=shipper.CAP-100),patch.object(collector.shutil,'disk_usage',return_value=SimpleNamespace(free=30*1024**3)):
            self.assertFalse(collector.guard(101));self.assertTrue(collector.guard(100))
        with patch.object(collector,'buffer_bytes',return_value=0),patch.object(collector.shutil,'disk_usage',return_value=SimpleNamespace(free=shipper.FLOOR-1)):
            self.assertFalse(collector.guard(0))
if __name__=='__main__':unittest.main()
