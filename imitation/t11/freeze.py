"""Freeze before production fitting. Runs on hub after store and adapter PASS."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import socket
import sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
IM=ROOT/'reports/strategy_council_20260928/imitation'
SOURCE=Path('/mpac/sdicks02/jobs/clasher/t11-20261008-v1/source')
sys.path.insert(0,str(SOURCE))
sys.path.insert(0,str(IM))
from imitation.t5.guards import sha,qualification,write_once


def main():
    assert socket.gethostname()=='127x01'
    data=IM/'data';store=data/'v2-store-v1';out=ROOT/'imitation/gate-a-v2'
    receipt_path=data/'receipts/T11-STORE-PASS.json';receipt=json.loads(receipt_path.read_text())
    assert receipt['passed'] and receipt['roundtrip_exact'] and not receipt['heldout_scored']
    assert sha(store/'manifest.json')==receipt['store_manifest_sha256']
    validation=ROOT/'imitation/t11/receipts/adapter-validation.json'
    validated=json.loads(validation.read_text());assert validated['passed']
    assert validated['sampling_sha256']==sha(SOURCE/'imitation/t11/sampling.py')
    assert validated['loader_sha256']==sha(SOURCE/'imitation/t5/resources.py')
    guards_path=ROOT/'imitation/t11/receipts/guard-validation.json'
    guarded=json.loads(guards_path.read_text());assert guarded['passed']
    assert guarded['score_sha256']==sha(SOURCE/'imitation/t11/score.py')
    assert guarded['select_sha256']==sha(SOURCE/'imitation/t11/select.py')
    padding_path=ROOT/'imitation/t11/receipts/frequency-padding-validation.json'
    padding=json.loads(padding_path.read_text());assert padding['passed']
    assert padding['adapter_sha256']==sha(SOURCE/'imitation/t11/frequency.py')
    assert padding['frequency_counts_sha256']==receipt['frequency_counts_sha256']
    t4,t4sha=qualification(SOURCE)
    r2=json.loads((ROOT/'imitation/t11/receipts/t5-r2-executable-manifest.json').read_text())
    for n in ('imitation/t5/resources.py','imitation/t5/guards.py','imitation/t5/baseline.py','imitation/t5/analyze.py'):
        assert sha(SOURCE/n)==r2['files'][n],n
    names=list(t4['files'])+['imitation/t5/__init__.py','imitation/t5/resources.py','imitation/t5/guards.py','imitation/t5/baseline.py','imitation/t5/analyze.py',
                          'imitation/t11/__init__.py','imitation/t11/train.py','imitation/t11/sampling.py','imitation/t11/preflight.py',
                          'imitation/t11/select.py','imitation/t11/score.py','imitation/t11/analyze.py','imitation/t11/frequency.py']
    files={n:sha(SOURCE/n) for n in sorted(names)}
    asset=Path('/mpac/sdicks02/jobs/clasher/t11-20261008-v1/inputs/assets.npz')
    assert sha(asset)==r2['assets_sha256']
    # The frozen extractor's slug mapping defines card tokens and actor scope.
    from replay_sidecars import cb,ContractV5ObservationBuilder
    builder=ContractV5ObservationBuilder();slugs=cb.slug_map()
    roster=json.loads((data/'receipts/T9-payloads.json').read_text())['roster']
    assert len(roster)==121 and 'three-musketeers' not in roster
    scope=sorted(builder.token_id(slugs[c],namespace='card_action') for c in roster)
    assert len(set(scope))==121
    assets=np.load(asset,allow_pickle=False)
    p16_paths=[IM/'baselines.py',IM/'p16_upgrade.py',IM/'replay_sidecars.py',ROOT/'imitation/t11/p16_baseline.py']
    p16_paths += [IM.parent/'c56/data/runtime-engine-v3b/src/clasher/rl'/n for n in ('model.py','human_replay_bc.py','human_replay_v5.py','contract_v5.py')]
    checkpoint=IM.parent/'human-prior-p16/checkpoints/human-bc-natural-seed2903.pt'
    checkpoint_hash=sha(checkpoint)
    assert checkpoint_hash=='49be14806a7e7e6ab26621e25230d3f6f7f0be4d84aabd480cbb8097de4ab482'
    m=dict(schema='clasher.imitation.t11-executable.v1',qualified_code_sha256=t4['code_sha256'],
           throughput_receipt_sha256=t4sha,files=files,assets_sha256=sha(asset),store_receipt_sha256=sha(receipt_path),
           store_manifest_sha256=receipt['store_manifest_sha256'],role_manifests=receipt['role_manifests'],
           role_file_sha256=receipt['role_file_sha256'],eval_spec_sha256=receipt['eval_spec_sha256'],
           frequency_counts_sha256=receipt['frequency_counts_sha256'],adapter_validation_sha256=sha(validation),guard_validation_sha256=sha(guards_path),
           padding_validation_sha256=sha(padding_path),padding_amendment_sha256=sha(out/'AMENDMENT-padding-baseline.md'),
           t5_resource_r2_manifest_sha256=sha(ROOT/'imitation/t11/receipts/t5-r2-executable-manifest.json'),
           card_scope_c56=r2['card_scope'],card_scope_s122=scope,
           card_names={str(i):str(assets['names'][i]) for i in scope},card_arenas={str(i):str(assets['arenas'][i]) for i in scope},
           p16_sources={str(p.relative_to(ROOT)):sha(p) for p in p16_paths},p16_checkpoint_sha256=checkpoint_hash,
           seeds=[2026100821,2026100822],execution=dict(workers=1,microbatch=7168,effective_batch=8192,max_epochs=6),
           bootstrap=dict(seed=2026100825,resamples=10000),heldout_release_required='completed/sealed v2 training+calibration AND published v1 gate(a)')
    out.mkdir(parents=True,exist_ok=True)
    write_once(out/'executable-manifest.json',m)
    draft=(out/'PREREG.draft.md').read_text()
    draft=draft.replace('This draft becomes binding only when PREREG.md and freeze.json are published\nbefore either v2 training run or any v2 held-out scoring.',
                        'Frozen before either v2 training run or any v2 held-out scoring.')
    appendix='\n## Frozen content hashes\n\n'+ '\n'.join('- '+k+': `'+str(v)+'`.' for k,v in m.items() if k.endswith('sha256'))+'\n'
    appendix+='- Executable manifest: `'+sha(out/'executable-manifest.json')+'`.\n'
    appendix+='\n'+(out/'AMENDMENT-padding-baseline.md').read_text()
    with (out/'PREREG.md').open('x') as f:f.write(draft+appendix)
    write_once(out/'freeze.json',dict(frozen_at=datetime.now(timezone.utc).isoformat(),prereg_sha256=sha(out/'PREREG.md'),
                                    manifest_sha256=sha(out/'executable-manifest.json'),training_started=False,heldout_scored=False))
    print((out/'freeze.json').read_text())


if __name__=='__main__':main()
