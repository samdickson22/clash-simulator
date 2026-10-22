"""Read-only sidecar for frozen eval_rsim rows, with explicit input pins.

Run with `python -m bot.pretrain_v1.report_operational_rejections --help`.
--candidate-root is the frozen bot/pretrain_v1 package, whose source files must
match the manifest. All three SHA arguments are caller-approved input pins.
--bc-start requires version 0 and checkpoint == anchor. To compare a snapshot,
pass --baseline and --baseline-sha256 for a previously frozen sidecar report.
The baseline must have every assigned row sealed, matching size, anchor, bank,
scope, external/runtime pins and observed telemetry cases. Assigned error rows
remain failures and make exposure partial even when every row is sealed.

No simulator, policy or scientific evaluator is imported. Errors remain assigned
failures. A report is not a scientific evaluation verdict or launch permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from . import operational_rejections as O

SCHEMA = 'pretrain-v1.operational-rejections.v1'
CASE_KEYS = ('index', 'id', 'row', 'seed', 'seat', 'opponent', 'own_deck', 'own_levels', 'own_king',
             'opponent_deck', 'opponent_levels', 'opponent_king')
HARNESS = ('bot', 'bot.players', 'bot.players.base', 'bot.players.policy', 'bot.players.royalesim_match',
           'bot.players.royalesim_translate', 'bot.players.royalesim_adapter', 'bot.players.runtime',
           'bot.eval.headline', 'bot.livediag.k4cw_fp', 'bot.live.player', 'bot.search.lopp_fast', 'bot.pretrain_v1')
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def pinned_json(path, sha):
    data = Path(path).read_bytes()
    O.require(hashlib.sha256(data).hexdigest() == sha, f'input hash mismatch: {path}')
    return json.loads(data)


def origins_valid(origins, candidate_root):
    O.require(isinstance(origins, dict) and all(k in origins for k in HARNESS), 'incomplete module origins')
    for name, rec in origins.items():
        O.require(name == 'bot' or name.startswith('bot.'), 'unknown module identity')
        O.require(isinstance(rec, dict) and isinstance(rec.get('paths'), list), 'invalid module origins')
        root = candidate_root if name == 'bot.pretrain_v1' or name.startswith('bot.pretrain_v1.') else R2
        locs = ([rec['file']] if rec.get('file') else [])+rec['paths']
        O.require(bool(locs), f'empty module origin: {name}')
        for loc in locs:
            path = Path(loc).resolve()
            O.require(path == root or root in path.parents, f'unapproved module origin: {name}: {loc}')


def compatible_baseline(current, baseline):
    """Frozen, complete own-size BC start on identical assigned/observed exposure."""
    O.require(current.get('provenance_valid') is True, 'current snapshot provenance invalid')
    O.require(baseline.get('schema') == SCHEMA and baseline.get('role') == 'bc_start' and
              baseline.get('version') == 0, 'baseline must be a pinned BC-start sidecar')
    O.require(baseline.get('complete') is True, 'partial baseline cannot be frozen')
    O.require(baseline.get('provenance_valid') is True, 'baseline provenance invalid')
    O.require(baseline['inputs']['checkpoint_sha256'] == baseline['inputs']['anchor_sha256'],
              'baseline checkpoint is not its BC anchor')
    keys = ('size', 'scope', 'exposure_sha256')
    O.require(all(current[k] == baseline[k] for k in keys), 'baseline size/scope/exposure mismatch')
    keys = ('anchor_sha256', 'bank_sha256', 'catalog_sha256', 'feature_hash', 'runtime_pins', 'external_sha256')
    O.require(all(current['inputs'][k] == baseline['inputs'][k] for k in keys), 'baseline provenance mismatch')
    O.require(current['telemetry_cases'] == baseline['telemetry_cases'], 'baseline observed exposure mismatch')


def report(eval_dir, *, manifest_sha256, bank, bank_sha256, anchor, anchor_sha256,
           candidate_root, size, version, scope, bc_start=False):
    eval_dir, candidate_root = Path(eval_dir), Path(candidate_root).resolve()
    O.require(size in ('S100', 'M') and O.integer(version) and bool(scope), 'explicit size/version/scope required')
    man = pinned_json(eval_dir/'manifest.json', manifest_sha256)
    frozen_bank = pinned_json(bank, bank_sha256)
    O.require(digest(anchor) == anchor_sha256 and man['bank_sha256'] == bank_sha256, 'anchor/bank pin mismatch')
    O.require(digest(man['ckpt']) == man['ckpt_sha256'], 'snapshot checkpoint hash mismatch')
    O.require(not bc_start or (version == 0 and man['ckpt_sha256'] == anchor_sha256), 'BC-start identity mismatch')
    O.require(isinstance(man['arm'], str) and '/' not in man['arm'] and '\\' not in man['arm'], 'invalid arm identity')
    O.require(bool(man['code_sha256']), 'missing candidate source pins')
    for filename, sha in man['code_sha256'].items():
        O.require(Path(filename).name == filename and digest(candidate_root/filename) == sha,
                  f'frozen candidate source mismatch: {filename}')
    assigned = man['assigned']
    O.require(isinstance(assigned, list) and assigned and all(O.integer(i) for i in assigned) and
              len(set(assigned)) == len(assigned), 'empty/duplicate/invalid assignment')
    by_index = {c['index']: c for c in frozen_bank['cases']}
    O.require(len(by_index) == len(frozen_bank['cases']) and set(assigned) <= set(by_index), 'invalid bank accounting')
    cases = [by_index[i] for i in assigned]
    cards = O.known_cards()
    for case in cases:
        O.require(type(case['seat']) is int and case['seat'] in (0, 1), 'unknown assigned seat')
        O.require(set(case['own_deck']) <= cards and set(case['opponent_deck']) <= cards, 'unknown assigned card')
    inputs = dict(manifest_path=str(eval_dir/'manifest.json'), manifest_sha256=manifest_sha256,
        bank_path=str(bank), bank_sha256=bank_sha256, anchor_path=str(anchor), anchor_sha256=anchor_sha256,
        checkpoint_sha256=man['ckpt_sha256'], candidate_root=str(candidate_root),
        catalog_sha256=digest(Path(__file__).parent/'catalog/catalog.json'),
        feature_hash=man['feature_hash'], runtime_pins=man['runtime_pins'], external_sha256=man['external_sha256'])
    out = dict(schema=SCHEMA, role='bc_start' if bc_start else 'snapshot', size=size, version=version, scope=scope,
        inputs=inputs, exposure_sha256=identity(cases), assigned=len(cases), sealed=0, valid=0, missing=0,
        other_execution_failures=[], contract_failures=[], row_evidence=[], telemetry_cases=[], provenance_valid=True)
    records = []
    expected_files = {f"{i:04}-{man['arm']}.json" for i in assigned}
    extras = {p.name for p in (eval_dir/'rows').glob('*.json')}-expected_files
    if extras:
        out['contract_failures'].append(dict(error='unassigned/unrecognized row files', files=sorted(extras)))
        out['provenance_valid'] = False
    for case in cases:
        path = eval_dir/'rows'/f"{case['index']:04}-{man['arm']}.json"
        evidence = dict(index=case['index'], path=str(path))
        out['row_evidence'].append(evidence)
        if not path.exists():
            out['missing'] += 1
            evidence['status'] = 'missing'
            continue
        out['sealed'] += 1
        try:
            data = path.read_bytes()
            evidence['sha256'] = hashlib.sha256(data).hexdigest()
            row = json.loads(data)
            O.require(all(row.get(k) == case[k] for k in CASE_KEYS) and row.get('arm') == man['arm'] and
                      row.get('ckpt_sha256') == man['ckpt_sha256'] and row.get('bank_sha256') == bank_sha256 and
                      row.get('runtime_pins') == man['runtime_pins'], 'row case/arm/checkpoint/bank/runtime mismatch')
            O.require(isinstance(row.get('invalid'), list) or 'error' in row, 'missing invalid/error evidence')
            origins_valid(row['module_origins_after'], candidate_root)
            if 'error' in row or row.get('invalid') or not (row.get('result') or {}).get('terminal'):
                evidence['status'] = 'execution_failure'
                out['other_execution_failures'].append(dict(index=case['index'], error=row.get('error'),
                    invalid=row.get('invalid'), terminal=(row.get('result') or {}).get('terminal')))
            else:
                O.require(type(row['result']['terminal']) is bool, 'invalid terminal identity')
                counts = row.get('policy_counts', {})
                allowed = {'shadow_equal', 'play', 'wait', 'forced', 'stale'}
                O.require(all(k in allowed and O.integer(v) for k, v in counts.items()),
                          'unrecognized policy status/error')
                O.require(not row.get('issues') or row['issues'] == ['our command rejections'], 'unknown execution issues')
                evidence['status'] = 'valid'
                out['valid'] += 1
            if row.get('result') is not None:
                record = O.game_counts(row['result'], case['seat'])
                O.game_counts(row['result'], 1-case['seat'])
                own_logs = O.seat_value(row['result']['play_log'], case['seat'])
                O.require(all(log[1] in case['own_deck'] for log in own_logs), 'executed card outside assigned own deck')
                records.append(record)
                out['telemetry_cases'].append(case['index'])
        except (RuntimeError, ValueError, TypeError, KeyError, OSError) as ex:
            if evidence.get('status') == 'valid':
                out['valid'] -= 1
            evidence['status'] = 'contract_failure'
            out['contract_failures'].append(dict(index=case['index'], error=repr(ex)))
            out['provenance_valid'] = False
    out['complete'] = out['sealed'] == out['assigned']
    out['partial_exposure'] = len(records) != out['assigned']
    out['status'] = 'pass' if out['valid'] == out['assigned'] and not out['contract_failures'] else 'failed'
    out['operational_rejections'] = O.aggregate(records)
    out['baseline_comparison'] = dict(status='unavailable', reason='no pinned frozen baseline supplied')
    return out


def apply_baseline(current, baseline):
    compatible_baseline(current, baseline)
    telemetry = current['operational_rejections']
    base = baseline['operational_rejections']
    telemetry['counts']['comparison'] = O.comparison(telemetry['counts'], base['counts'])
    for card, counts in telemetry['by_card'].items():
        counts['comparison'] = O.comparison(counts, base['by_card'].get(card))
    current['baseline_comparison'] = dict(status='matched', partial_exposure=baseline['partial_exposure'],
        manifest_sha256=baseline['inputs']['manifest_sha256'], checkpoint_sha256=baseline['inputs']['checkpoint_sha256'],
        counts=base['counts'], by_card=base['by_card'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('eval-dir', 'bank', 'anchor', 'candidate-root', 'out'):
        p.add_argument('--'+name, required=True, type=Path)
    for name in ('manifest-sha256', 'bank-sha256', 'anchor-sha256', 'scope'):
        p.add_argument('--'+name, required=True)
    p.add_argument('--size', required=True, choices=('S100', 'M'))
    p.add_argument('--version', required=True, type=int)
    p.add_argument('--bc-start', action='store_true')
    p.add_argument('--baseline', type=Path)
    p.add_argument('--baseline-sha256')
    a = p.parse_args()
    # Outputs never enter the frozen input tree and never replace evidence.
    O.require(a.out.resolve() != a.eval_dir.resolve() and a.eval_dir.resolve() not in a.out.resolve().parents,
              'sidecar output must be outside frozen eval directory')
    result = dict(schema=SCHEMA, status='failed')
    try:
        O.require(bool(a.baseline) == bool(a.baseline_sha256), 'baseline path and hash required together')
        result = report(a.eval_dir, manifest_sha256=a.manifest_sha256, bank=a.bank, bank_sha256=a.bank_sha256,
            anchor=a.anchor, anchor_sha256=a.anchor_sha256, candidate_root=a.candidate_root,
            size=a.size, version=a.version, scope=a.scope, bc_start=a.bc_start)
        if a.baseline:
            apply_baseline(result, pinned_json(a.baseline, a.baseline_sha256))
            result['baseline_comparison']['report_sha256'] = a.baseline_sha256
    except (RuntimeError, ValueError, TypeError, KeyError, OSError) as ex:
        result.update(status='failed', error=repr(ex))
    with a.out.open('x') as f:
        f.write(json.dumps(result, indent=2, allow_nan=False)+'\n')
    return 0 if result['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
