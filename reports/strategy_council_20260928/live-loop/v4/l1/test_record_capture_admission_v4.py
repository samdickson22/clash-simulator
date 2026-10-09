"""File-backed authentication tests; no model/data payloads outside tiny fixtures."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import record_capture_admission_v4 as module


class CaptureAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.folder=root/'capture';self.folder.mkdir()
        self.bundle=root/'bundle';self.bundle.mkdir();self.plan=root/'plan.json'
        self.equality=root/'equality.json';self.equality.write_text('{}')
        self.episodes={'v-%02d'%i:2 for i in range(64)}
        self.ready=dict(validated=True,validation_matches=64,bundle_sha256='a'*64,
            checkpoint_sha256={'1':'b'*64},validation_receipt_sha256={})
        def put(path,value):
            path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
        self.put=put
        put(self.bundle/'fit/model/manifest.json',{'cards':['Knight']})
        for ep,count in self.episodes.items():
            p=self.bundle/'matches'/ep/'receipt.json'
            put(p,dict(episode=ep,frames=count,split='validation'))
            self.ready['validation_receipt_sha256'][ep]=module.sha(p)
        put(self.plan,dict(schema='clasher.v4.epoch-fanout-plan.v2',source_files={},
                          epoch_assignments={'test-host':[{'epoch':1}]}))
        put(self.folder/'manifest.json',dict(schema='clasher.v4.shared-epoch-capture.v1',epoch=1,
            checkpoint_sha256='b'*64,bundle_sha256='a'*64,equality_sha256=module.sha(self.equality),
            spells=[],body_thresholds=[i/10 for i in range(1,10)],event_threshold=.5,
            storage='lossless JSON/gzip1 pre-NMS records',heldout_payloads_opened=False,selection_seal=False))
        pins={'manifest.json':module.sha(self.folder/'manifest.json')}
        for i in range(1,10):
            for ep in self.episodes:
                p=self.folder/('body-%d'%i)/(ep+'-decoder.jsonl.gz');p.parent.mkdir(exist_ok=True)
                p.write_bytes(b'synthetic records');pins[str(p.relative_to(self.folder))]=module.sha(p)
                # Completion files deliberately ABSENT: they must never be opened.
                pins['body-%d/%s-completion.jsonl'%(i,ep)]='c'*64
        put(self.folder/'complete.json',dict(schema='clasher.v4.shared-epoch-capture-complete.v1',
            files_sha256=pins,episodes=self.episodes,frames=128,heldout_payloads_opened=False,selection_seal=False))
        self.kw=dict(complete_sha=module.sha(self.folder/'complete.json'),readiness=self.ready,
            bundle=self.bundle,plan=self.plan,plan_sha=module.sha(self.plan),host='test-host',
            equality=self.equality,equality_sha=module.sha(self.equality))
        self.auth=patch.object(module,'authorize',return_value={});self.auth.start();self.addCleanup(self.auth.stop)
        loader=SimpleNamespace(get_card=lambda _:SimpleNamespace(card_type='troop'))
        self.loader=patch('clasher.data.CardDataLoader',return_value=loader);self.loader.start();self.addCleanup(self.loader.stop)

    def call(self):return module.authenticate_record_capture(self.folder,**self.kw)

    def test_clock_files_never_opened(self):
        x=self.call();self.assertFalse(x['clocks_read']);self.assertEqual(len(x['files_sha256']),577)
        self.assertFalse(any(n.endswith('-completion.jsonl') for n in x['files_sha256']))

    def test_changed_record_rejected(self):
        (self.folder/'body-1/v-00-decoder.jsonl.gz').write_bytes(b'changed')
        with self.assertRaises(ValueError):self.call()

    def test_missing_record_rejected(self):
        (self.folder/'body-1/v-00-decoder.jsonl.gz').unlink()
        with self.assertRaises((ValueError,FileNotFoundError)):self.call()

    def test_completion_pin_required(self):
        self.kw['complete_sha']='0'*64
        with self.assertRaises(ValueError):self.call()

    def test_validation_receipt_pin_and_split(self):
        p=self.bundle/'matches/v-00/receipt.json';x=json.loads(p.read_text());x['split']='heldout';self.put(p,x)
        self.ready['validation_receipt_sha256']['v-00']=module.sha(p)
        with self.assertRaises(ValueError):self.call()

    def test_wrong_assignment(self):
        self.kw['host']='another-host'
        with self.assertRaises(ValueError):self.call()


if __name__=='__main__':unittest.main()
