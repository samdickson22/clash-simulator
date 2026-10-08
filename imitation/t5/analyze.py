"""Analyze committed statistics only; this module performs no model inference."""
import argparse
import hashlib
import json
from pathlib import Path
import time
from collections import Counter
import numpy as np
from imitation.model.evaluate import summarize
from .guards import sha, write_once

SEED = 2026100805
RESAMPLES = 10000
GATE_METRICS = ('joint_nll', 'play_wait_nll', 'card_nll', 'tile_nll')


def read_statistics(directory):
    root = Path(directory)
    complete = json.loads((root/'complete.json').read_text())
    columns = {}
    for name, digest in sorted(complete['batches'].items()):
        if sha(root/name) != digest:
            raise ValueError('committed sufficient statistics changed')
        with np.load(root/name, allow_pickle=False) as z:
            for key in z.files:
                columns.setdefault(key, []).append(z[key])
    result = {k: np.concatenate(v) for k, v in columns.items()}
    if not np.array_equal(result['index'], np.arange(complete['rows'])):
        raise ValueError('score statistics not a full contiguous role')
    return result, complete


def paired_intervals(columns, clusters, resamples=RESAMPLES, seed=SEED):
    """All columns share the same sorted whole-perspective multinomial draws."""
    ids, inverse = np.unique(clusters, return_inverse=True)
    n = len(ids)
    sums, counts, labels = [], [], list(columns)
    for key in labels:
        v = np.asarray(columns[key]); use = np.isfinite(v)
        sums.append(np.bincount(inverse[use], weights=v[use], minlength=n))
        counts.append(np.bincount(inverse[use], minlength=n))
    sums, counts = np.stack(sums, 1), np.stack(counts, 1)
    rng = np.random.Generator(np.random.PCG64(seed)); samples = []
    for start in range(0, resamples, 128):
        weights = rng.multinomial(n, np.full(n, 1/n), size=min(128, resamples-start))
        denominator = weights@counts
        samples.append(np.divide(weights@sums, denominator, out=np.full(denominator.shape, np.nan), where=denominator>0))
    samples = np.concatenate(samples)
    output = {}
    for col, key in enumerate(labels):
        valid = samples[:, col][np.isfinite(samples[:, col])]
        output[key] = {'n': int(counts[:, col].sum()),
                       'value': float(sums[:, col].sum()/counts[:, col].sum()) if counts[:, col].sum() else None,
                       'ci95': np.quantile(valid, [.025, .975], method='linear').tolist() if len(valid) else None,
                       'valid_resamples': len(valid), 'undefined_resamples': resamples-len(valid)}
    return output


def describe(rows, clusters, selector=None):
    # Slices retain the complete perspective universe; ineligible rows become NaN.
    if selector is not None:
        rows = {k: np.where(selector, v, np.nan) for k, v in rows.items()}
    return summarize(rows, clusters, resamples=0, seed=SEED)


def analyze(directory, manifest, baseline):
    data, receipt = read_statistics(directory)
    role = receipt['role']
    metadata_path = Path(directory)/'slice-metadata.json'
    if sha(metadata_path) != receipt['slice_metadata_sha256']:
        raise ValueError('slice metadata changed')
    metadata = json.loads(metadata_path.read_text()); perspectives = metadata['perspectives']
    # Stable lexicographic match|side identity order, independent of packing IDs.
    ordered = sorted(perspectives, key=lambda k: perspectives[k]['identity'])
    order = {int(pid): rank for rank, pid in enumerate(ordered)}
    raw_ids, inverse = np.unique(data['perspective'], return_inverse=True)
    clusters = np.array([order[int(pid)] for pid in raw_ids])[inverse]
    identities = [perspectives[pid]['identity'] for pid in ordered]
    before = {k.split('__')[1]: v for k, v in data.items() if k.startswith('before__')}
    rows = {k.split('__')[1]: v for k, v in data.items() if k.startswith('after__')}
    frequency = {k.split('__')[1]: v for k, v in data.items() if k.startswith('frequency__')}
    delta = {}
    for key in GATE_METRICS:
        if not np.array_equal(np.isfinite(rows[key]), np.isfinite(frequency[key])):
            raise ValueError('frequency/model denominator differs')
        delta['A1_'+key] = rows[key]-frequency[key]
    for card in manifest['card_scope']:
        delta['A3_'+str(card)] = np.where(rows['label_card']==card, rows['tile_nll']-frequency['tile_nll'], np.nan)
    intervals = paired_intervals(delta, clusters)
    a1 = {key: intervals['A1_'+key] for key in GATE_METRICS}
    cards = {str(card): intervals['A3_'+str(card)] for card in manifest['card_scope']}
    for item in cards.values():
        item['significantly_worse'] = item['ci95'] is not None and item['ci95'][0] > 0
    selected = data['p16'].astype(bool)
    p16 = baseline['scores'][role]
    if p16['role'] != role or p16['perspectives'] != len(np.unique(clusters[selected])):
        raise ValueError('P16 role/scope/perspective alignment mismatch')
    a2 = {'pass': None, 'reason': 'no scoped P16 perspectives', 'details': {}}
    if p16['perspectives']:
        expected = p16['metrics']
        for key, count_key in (('joint_nll', 'rows'), ('tile_nll', 'play_rows'), ('play_wait_nll', 'playable_rows')):
            if int(np.isfinite(rows[key][selected]).sum()) != int(expected[count_key]):
                raise ValueError('P16 eligibility/count mismatch: '+key)
        for key in ('card_nll', 'tile_nll'):
            value = float(np.nanmean(rows[key][selected], dtype=np.float64))
            a2['details'][key] = {'model': value, 'baseline': expected[key], 'delta': value-expected[key],
                                  'pass': value <= expected[key]+.05}
        a2.update({'pass': all(x['pass'] for x in a2['details'].values()), 'reason': None,
                   'checkpoint_sha256': p16['checkpoint_sha256']})
    summary = summarize(rows, clusters, resamples=RESAMPLES, seed=SEED)
    gates = {'A1': {'pass': all(v['ci95'] is not None and v['ci95'][1]<0 for v in a1.values()), 'details': a1},
             'A2': a2,
             'A3': {'pass': all(v['n'] and not v['significantly_worse'] for v in cards.values()),
                    'passing_cards': sum(bool(v['n'] and not v['significantly_worse']) for v in cards.values()),
                    'scoped_cards': len(cards), 'cards': cards},
             'A4': {'pass': summary['gate_ece']['ece'] is not None and summary['gate_ece']['ece']<=.01,
                    **summary['gate_ece']}}
    slices = {'card': {}, 'arena': {}}
    for card in manifest['card_scope']:
        slices['card'][str(card)] = describe(rows, clusters, rows['label_card']==card)
    for arena in sorted(set(manifest['card_arenas'].values())):
        members = [int(k) for k, v in manifest['card_arenas'].items() if v==arena]
        slices['arena'][arena] = describe(rows, clusters, np.isin(rows['label_card'], members))
    ticks = data['submitted_ticks']
    family_counts = Counter(item['family'] for item in perspectives.values())
    top = {k for k, v in sorted(family_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]}
    def per_row(key):
        return np.array([perspectives[str(pid)][key] for pid in raw_ids])[inverse]
    families = per_row('family')
    fraction = ticks/np.maximum(1, per_row('end_tick'))
    labels = {'phase': np.where(ticks<2400, 'single', np.where(ticks<3600, 'double', 'overtime')),
              'match_part': np.where(fraction<.33, 'early', np.where(fraction<.66, 'mid', 'late')),
              'archetype': np.where(np.isin(families, list(top)), families, 'other'),
              'mode': per_row('mode'), 'p16': data['p16'], 'ood': np.full(len(clusters), role=='eval_ood'),
              'engine_phase': np.array(metadata['engine_phases'])[data['source_unit']],
              'ability_attributable': per_row('ability_attributable')}
    # Per-perspective forms apply only to its own labelled play card.
    forms = np.full(len(clusters), '', dtype='U16')
    for pid in raw_ids:
        item = perspectives[str(pid)]; start = item['start']; end = start+item['rows']
        if not np.all(data['perspective'][start:end]==pid):
            raise ValueError('perspective metadata/row identity mismatch')
        for card, form in item['forms'].items():
            forms[start:end][rows['label_card'][start:end]==int(card)] = form
    labels['forms'] = forms
    for key, column in labels.items():
        slices[key] = {str(label): describe(rows, clusters, column==label)
                       for label in np.unique(column) if str(label) != ''}
    return {'run': receipt['run'], 'role': role, 'checkpoint_sha256': receipt['checkpoint_sha256'],
            'manifest_sha256': receipt['T5_manifest'], 'statistics_complete_sha256': sha(Path(directory)/'complete.json'),
            'cluster_identity': 'lexicographically sorted T3 match|side identities; full universe, including zero-eligible clusters',
            'ordered_cluster_ids_sha256': hashlib.sha256(json.dumps(identities,separators=(',',':')).encode()).hexdigest(),
            'bootstrap': {'resamples': RESAMPLES, 'rng': 'PCG64', 'seed': SEED, 'quantile': 'linear'},
            'before': describe(before, clusters), 'after': summary, 'slices': slices, 'gates': gates,
            'gate_pass': all(g['pass'] is True for g in gates.values()),
            'frequency_means': {k: float(np.nanmean(v, dtype=np.float64)) for k, v in frequency.items()}}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--statistics', required=True); p.add_argument('--manifest', required=True)
    p.add_argument('--p16-receipt', required=True); p.add_argument('--output', required=True)
    a = p.parse_args(); start = time.monotonic()
    manifest = json.loads(Path(a.manifest).read_text())
    if manifest['bootstrap'] != {'resamples': RESAMPLES, 'rng': 'PCG64', 'seed': SEED, 'quantile': 'linear'}:
        raise ValueError('executable bootstrap differs from preregistration')
    if sha(a.p16_receipt) != manifest['p16_receipt_sha256']:
        raise ValueError('P16 pinned summary changed')
    result = analyze(a.statistics, manifest, json.loads(Path(a.p16_receipt).read_text()))
    result['analysis_wall_seconds'] = time.monotonic()-start
    write_once(a.output, result)


if __name__ == '__main__':
    main()
