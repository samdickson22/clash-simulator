"""Small read-only accounting fixtures, never engine games or eval evidence."""
import copy
import json
from pathlib import Path

import pytest

from bot.pretrain_v1 import operational_rejections as O
from bot.pretrain_v1 import report_operational_rejections as R


def game(rejected=False, pending=1):
    return dict(terminal=True, ticks=140,
        channels={'0': dict(submitted=1+pending, executed=1, rejected=int(rejected), pending_at_end=pending),
                  '1': dict(submitted=0, executed=0, rejected=0, pending_at_end=0)},
        play_log={'0': [[117, 'Cannon', 1933, not rejected]], '1': []},
        accepted={'0': int(not rejected), '1': 0})


def test_lagged_execution_uses_sampled_snapshot_and_pending_exclusion():
    g = game(True)
    subs = [dict(tick=90, card='Cannon', action=1933, version=0, policy_sha256='a'*64),
            dict(tick=130, card='Knight', action=0, version=1, policy_sha256='b'*64)]
    saved = copy.deepcopy((g, subs))
    rec = O.game_counts(g, 0, cards={'Cannon', 'Knight'}, submissions=subs)
    assert rec['counts'] == dict(submitted=2, executed=1, accepted=0, rejected=1, pending=1)
    assert rec['by_snapshot']['0']['counts']['rejected'] == 1
    assert rec['by_snapshot']['1']['counts']['pending'] == 1
    assert rec['by_snapshot']['1']['counts']['executed'] == 0
    assert rec['by_snapshot']['0']['policy_sha256'] == 'a'*64
    assert O.rate(rec['counts']) == 1
    assert (g, subs) == saved


@pytest.mark.parametrize('current,baseline,expected', [
    ((2, 100), (1, 100), False), ((3, 100), (1, 100), True),
    ((0, 100), (0, 50), False), ((1, 100), (0, 50), True),
    ((1, 100), (0, 0), None), ((0, 0), (1, 10), None),
    ((2**60+1, 2**62), (2**59, 2**62), True),
])
def test_exact_strict_rate_boundary(current, baseline, expected):
    c, b = (dict(rejected=x[0], executed=x[1]) for x in (current, baseline))
    assert O.comparison(c, b)['alert'] is expected
    assert O.comparison(c)['status'] == 'unavailable'


def test_per_card_rates_and_missing_frozen_pending_identity():
    rec = O.game_counts(game(True), 0, cards={'Cannon', 'Knight'})
    assert rec['by_card']['Cannon']['submitted'] is None
    assert rec['unattributed_pending'] == 1
    report = O.aggregate([rec], O.aggregate([O.game_counts(game(False, 0), 0, cards={'Cannon', 'Knight'})]))
    assert report['by_card']['Cannon']['rejected_executed_rate'] == 1
    assert report['by_card']['Cannon']['comparison']['alert'] is True
    assert report['by_card']['Knight']['comparison']['status'] == 'unavailable'
    assert report['counts']['pending'] == 1


@pytest.mark.parametrize('corrupt', ['unknown_card', 'bad_count', 'bad_bool', 'unknown_seat', 'missing_log', 'bad_accept'])
def test_bad_identity_or_accounting_fails_closed(corrupt):
    g = game()
    if corrupt == 'unknown_card':
        g['play_log']['0'][0][1] = 'Mystery'
    elif corrupt == 'bad_count':
        g['channels']['0']['submitted'] += 1
    elif corrupt == 'bad_bool':
        g['play_log']['0'][0][3] = 1
    elif corrupt == 'unknown_seat':
        g['channels']['2'] = g['channels'].pop('1')
    elif corrupt == 'missing_log':
        g['play_log']['0'] = []
    else:
        g['accepted']['0'] = 9
    with pytest.raises(RuntimeError):
        O.game_counts(g, 0, cards={'Cannon'})


@pytest.fixture
def frozen(tmp_path):
    root = tmp_path/'candidate'
    root.mkdir()
    (root/'eval_rsim.py').write_text('frozen scientific evaluator\n')
    anchor = tmp_path/'anchor.pt'
    anchor.write_bytes(b'anchor')
    case = dict(index=0, id='case0', row='HOG', seed=1, seat=0, opponent='R3a',
        own_deck=['Cannon'], own_levels={'Cannon': 9}, own_king=9,
        opponent_deck=['Knight'], opponent_levels={'Knight': 9}, opponent_king=9)
    bank = tmp_path/'bank.json'
    bank.write_text(json.dumps(dict(cases=[case, dict(case, index=1, id='case1', seat=1)])))
    ev = tmp_path/'eval'
    (ev/'rows').mkdir(parents=True)
    man = dict(assigned=[0, 1], arm='pv1', bank_sha256=R.digest(bank), ckpt=str(anchor), ckpt_sha256=R.digest(anchor),
        code_sha256={'eval_rsim.py': R.digest(root/'eval_rsim.py')}, feature_hash='f'*64,
        runtime_pins={'engine': 'frozen'}, external_sha256={'external': 'e'*64})
    (ev/'manifest.json').write_text(json.dumps(man))
    origins = {k: dict(file=str((root if k == 'bot.pretrain_v1' else R.R2)/'module.py'), paths=[]) for k in R.HARNESS}
    row = dict(case, arm='pv1', ckpt_sha256=man['ckpt_sha256'], bank_sha256=man['bank_sha256'],
        runtime_pins=man['runtime_pins'], invalid=[], result=game(False, 0),
        module_origins_after=origins, policy_counts={'shadow_equal': 2, 'play': 1, 'wait': 1}, issues=[])
    (ev/'rows/0000-pv1.json').write_text(json.dumps(row))
    args = dict(manifest_sha256=R.digest(ev/'manifest.json'), bank=bank, bank_sha256=R.digest(bank),
        anchor=anchor, anchor_sha256=R.digest(anchor), candidate_root=root, size='S100', version=0,
        scope='fixture matched eval bank', bc_start=True)
    return ev, args, row


def test_sidecar_all_assigned_accounting_errors_are_separate_and_partial_not_baseline(frozen):
    ev, args, row = frozen
    out = R.report(ev, **args)
    assert (out['assigned'], out['sealed'], out['valid'], out['missing']) == (2, 1, 1, 1)
    assert out['partial_exposure'] and not out['complete']
    assert out['operational_rejections']['counts']['executed'] == 1
    with pytest.raises(RuntimeError, match='partial baseline'):
        R.apply_baseline(copy.deepcopy(out), out)
    err = dict(row, index=1, id='case1', seat=1, error='unrecognized execution error')
    err.pop('result')
    (ev/'rows/0001-pv1.json').write_text(json.dumps(err))
    out = R.report(ev, **args)
    assert out['complete'] and out['status'] == 'failed' and out['partial_exposure']
    assert len(out['other_execution_failures']) == 1
    assert out['operational_rejections']['counts']['rejected'] == 0
    assert out['operational_rejections']['counts']['executed'] == 1
    R.apply_baseline(out, copy.deepcopy(out))
    assert out['baseline_comparison']['status'] == 'matched'


@pytest.mark.parametrize('corrupt', ['row_hash', 'origin', 'unknown_status', 'unknown_issue', 'unknown_card', 'accounting'])
def test_sidecar_contract_failures_are_reported(frozen, corrupt):
    ev, args, row = frozen
    if corrupt == 'row_hash':
        row['ckpt_sha256'] = 'x'*64
    elif corrupt == 'origin':
        row['module_origins_after']['bot.players.base']['file'] = '/outside/module.py'
    elif corrupt == 'unknown_status':
        row['policy_counts']['novel_error'] = 1
    elif corrupt == 'unknown_issue':
        row['issues'] = ['unknown engine error']
    elif corrupt == 'unknown_card':
        row['result']['play_log']['0'][0][1] = 'Mystery'
    else:
        row['result']['channels']['0']['executed'] = 100
    (ev/'rows/0000-pv1.json').write_text(json.dumps(row))
    out = R.report(ev, **args)
    assert out['status'] == 'failed' and out['contract_failures']
    assert not out['provenance_valid']
    assert out['operational_rejections']['counts']['executed'] == 0


@pytest.mark.parametrize('field,value', [('size', 'M'), ('scope', 'train/R3a'), ('exposure_sha256', 'other')])
def test_no_false_baseline_comparison(frozen, field, value):
    ev, args, row = frozen
    (ev/'rows/0001-pv1.json').write_text(json.dumps(dict(row, index=1, id='case1', seat=1,
        error='recorded failure', result=None)))
    # Preserve failure rather than manufacture a valid second-seat log.
    r = R.report(ev, **args)
    baseline = copy.deepcopy(r)
    baseline[field] = value
    with pytest.raises(RuntimeError):
        R.apply_baseline(r, baseline)


def test_cli_persists_final_pin_failure(frozen, tmp_path, monkeypatch):
    import sys
    ev, args, _ = frozen
    output = tmp_path/'failed-sidecar.json'
    argv = ['report', '--eval-dir', str(ev), '--out', str(output), '--size', 'S100', '--version', '0', '--bc-start']
    for name in ('bank', 'anchor', 'candidate_root', 'bank_sha256', 'anchor_sha256', 'scope'):
        argv += ['--'+name.replace('_', '-'), str(args[name])]
    argv += ['--manifest-sha256', '0'*64]
    monkeypatch.setattr(sys, 'argv', argv)
    assert R.main() == 1
    result = json.loads(output.read_text())
    assert result['status'] == 'failed' and 'input hash mismatch' in result['error']


def test_valid_schema_has_no_valid_boolean_and_stale_is_known(frozen):
    ev, args, row = frozen
    row['policy_counts']['stale'] = 1
    assert 'valid' not in row
    (ev/'rows/0000-pv1.json').write_text(json.dumps(row))
    result = R.report(ev, **args)
    assert result['valid'] == 1 and not result['contract_failures']


def test_unknown_submission_policy_and_unmatched_execution_fail_closed():
    sub = dict(tick=90, card='Cannon', action=1933, version=0, policy_sha256='a'*64)
    with pytest.raises(RuntimeError, match='sampled policy identity'):
        O.game_counts(game(False, 0), 0, submissions=[dict(sub, version=-1)])
    with pytest.raises(RuntimeError, match='no sampled command provenance'):
        O.game_counts(game(False, 0), 0, submissions=[dict(sub, tick=95)])
