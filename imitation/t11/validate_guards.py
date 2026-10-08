"""Synthetic checks that scoring embargoes fail before checkpoint/model IO."""
import json
from pathlib import Path
import socket
import sys
import tempfile
from unittest.mock import patch
from . import score,select


def main():
    assert socket.gethostname()=='127x01'
    root=Path(tempfile.mkdtemp(prefix='t11-guard-validation-',dir='/mpac/sdicks02/tmp'))
    selection=root/'selection.json';selection.write_text(json.dumps({'runs':{k:{'checkpoint_sha256':'same'} for k in select.RUNS},'manifest_sha256':'manifest'}))
    argv=['score','score','--freeze','unused','--checkpoint','unread','--store','/synthetic/eval',
          '--assets','unread','--output',str(root/'never-created'),'--selection',str(selection),'--run','main-2026100821']
    checks={}
    with patch.object(score,'frozen',return_value=({'assets_sha256':'same'},{'T11_manifest':'manifest'})), \
         patch.object(score,'sha',return_value='same'),patch.object(score.torch,'load',side_effect=RuntimeError('checkpoint must not be opened')):
        with patch.object(sys,'argv',argv):
            try:score.main()
            except AssertionError:checks['absent_heldout_release_rejected_before_checkpoint']=True
            else:raise AssertionError('embargo failed')
    assert not (root/'never-created').exists()
    paused=root/'paused';paused.mkdir();(paused/'complete.json').write_text(json.dumps({'stopped_by_signal':True}))
    (paused/'segments.jsonl').write_text(json.dumps({'status':'checkpointed'})+'\n')
    dummy=root/'manifest.json';dummy.write_text('{}\n')
    argv=['select','run','--input',str(paused),'--output',str(root/'never-selected.json'),
          '--manifest',str(dummy),'--run','main-2026100821']
    with patch.object(sys,'argv',argv),patch('torch.load',side_effect=RuntimeError('checkpoint must not be opened')):
        try:select.main()
        except AssertionError:checks['paused_run_cannot_be_selected']=True
        else:raise AssertionError('paused run accepted')
    assert not (root/'never-selected.json').exists()
    receipt=Path('/mpac/sdicks02/repos/clasher/imitation/t11/receipts/guard-validation.json')
    from imitation.t5.guards import sha
    receipt.write_text(json.dumps(dict(passed=True,real_fitting=False,heldout_scored=False,checks=checks,
                                       score_sha256=sha(score.__file__),select_sha256=sha(select.__file__)),indent=2)+'\n')
    print(receipt.read_text())


if __name__=='__main__':main()
