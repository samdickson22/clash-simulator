"""Legacy BC run metadata stays readable without modifying the original receipt."""
import importlib.util
import json
from pathlib import Path
import threading


def test_legacy_donor_count_and_six_fraction_reports(tmp_path, monkeypatch):
    path = Path(__file__).resolve().parents[3]/'reports/bot/pretrain-v1/sweep/followup_05.py'
    spec = importlib.util.spec_from_file_location('scaling_reader', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    monkeypatch.setattr(m, 'ROOT', tmp_path)
    original = dict(rows=100, train_rows=80, dev_rows=10, dev_eval_rows=10,
                    steps_per_epoch=1, sampler={'donors': 7})
    def selected(remote, local):
        local.mkdir(parents=True, exist_ok=True)
        (local/'run.json').write_text(json.dumps(original))
        return dict(sha256='a'*64, ep=3, selection={'gate_ece': .01})
    monkeypatch.setattr(m, 'copy_selected', selected)
    m.scaling_readout(threading.Event())
    d = json.loads((tmp_path/'scaling-read.json').read_text())
    assert set(d['runs']) == {'S25', 'S50', 'S100', 'M25', 'M50', 'M100'}
    for name, row in d['runs'].items():
        assert row['status'] == 'complete' and row['sample_sizes']['train_donors'] == 7
        assert json.loads((tmp_path/'scaling'/name/'run.json').read_text()) == original
