"""X4S-4 (exploration, NEVER ADOPTABLE): verify, seal and gate packed training/diagnostic sets. r3 after Sol r2 (R2-F1,
R2-F5, R2-F9). Every read and write goes through x4s4io.

Modes (fixed roots and gates under <job>/data):
  O        onpolicy/          -> O-VERIFIED.json        bank C indices < 3500; every row a supervised scored root;
                                 recorded_outcome 0; 300,000 <= rows <= 450,000; per arm K4S-120 <= 200,000 and
                                 S-200 <= 250,000.
  holdout  onpolicy-holdout/  -> HOLDOUT-VERIFIED.json  bank C indices 3500-3999 (the O-holdout).
  OW       onpolicy-w/        -> OW-VERIFIED.json       bank C' only; selection exactly range(n); strict minimal prefix.

Source binding (R2-F5), every mode: each packed episode's source game directory is re-verified COMPLETELY
(x4s4io.verify_sealed_dir: exact inventory, no link/special file, every listed file re-hashed) and its manifest SHA must
equal the one recorded at packing; the packed bytes of every array slice must equal that source's arrays under
pack.py's exact transforms (offset arrays rebased, mask_index shifted, episode_ids/row_ids regenerated, mask table rows
copied). O/holdout: each source receipt must carry the label plan SHA, the plan entry's capture/kept-id SHAs, arm,
index, seed, rows, TEACHER and the label run's thread count; the packed game set equals the passed label receipts'
game set. OW: each source's projected replay identity (seed C'+g, index 56+seat, seat g%2, opponent v1) and manifest
SHA must equal the selection receipt's row for g; the acceptance smoke receipt must list exactly the two
qualification-bank games (seed 4503606337370496+g, g = 0, 1) with replay_exact, their re-verified seals and replay
identities, and the fixed v1/emitter SHAs.
Gates carry identities (R2-F9): label plan / label receipts / selection / acceptance / O-gate SHAs and the sorted
source list SHA, so later consumers can bind to them.
"""
import argparse, hashlib, io as _stdio, json, os, sys, time
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import x4s4io as io                                      # noqa: E402
import studytree                                          # noqa: E402

JOB = io.JOB
MODES = {'O': ('onpolicy', 'O-VERIFIED.json'), 'holdout': ('onpolicy-holdout', 'HOLDOUT-VERIFIED.json'),
         'OW': ('onpolicy-w', 'OW-VERIFIED.json')}
RECEIPT = 'VERIFY-RECEIPT.json'
OPERATIONAL = {'pack-log.txt'}
SCHEMA = io.SEAL_SCHEMA
O_MIN, O_MAX = 300_000, 450_000
ARM_CAPS = {'K4S-120': 200_000, 'S-200': 250_000}
HOLDOUT_MIN_INDEX = 3500
MISMATCH_LIMIT = 0.001
TEACHER = 'W-screen8 K4 anchor, no deadline, reserve_floor=False'
V1_SHA = 'd77005d59d6ed40ce7f9bfcfde569b54958bebf056e00653b10dcee3957272ed'
EMITTER_SHA = 'dab616517ea6b33ae1de6a34909526cf5409ec4ad71c180188d95d9716cfecc1'
QUAL_BASE = 4503606337370496
REPLAY_KEEP = ('seed', 'index', 'opponent', 'seat', 'replay_exact')


class ValidationError(Exception):
    pass


def check(cond, msg):
    if not cond: raise ValidationError(msg)


def npy(path):
    return np.load(_stdio.BytesIO(io.read_bytes(str(path))), allow_pickle=False)


def sha_json(obj): return hashlib.sha256(json.dumps(obj, sort_keys=True).encode()).hexdigest()


def episode_bytes_equal(packed, src, offs, entry, episode):
    """Packed slices == source arrays under pack.py's transforms."""
    n, ne, nr = entry['rows'], entry['entities'], entry['roots']
    for k, dest in packed.items():
        if k == 'mask_table': continue
        value = npy(f'{src}/train/{k}.npy')
        if k in ('entity_offsets', 'root_offsets'):
            base = offs['entities' if k == 'entity_offsets' else 'roots']
            ok = np.array_equal(dest[offs['rows']:offs['rows']+n+1], value+base)
        elif k.startswith('flat_entity_'): ok = np.array_equal(dest[offs['entities']:offs['entities']+ne], value, equal_nan=value.dtype.kind == 'f')
        elif k in ('root_actions', 'root_scores', 'root_valid'): ok = np.array_equal(dest[offs['roots']:offs['roots']+nr], value, equal_nan=value.dtype.kind == 'f')
        elif k == 'mask_index': ok = np.array_equal(dest[offs['rows']:offs['rows']+n], value+offs['masks'])
        elif k == 'episode_ids': ok = bool((dest[offs['rows']:offs['rows']+n] == episode).all())
        elif k == 'row_ids': ok = np.array_equal(dest[offs['rows']:offs['rows']+n], np.arange(offs['rows'], offs['rows']+n))
        else: ok = np.array_equal(dest[offs['rows']:offs['rows']+n], value, equal_nan=value.dtype.kind == 'f')
        check(ok, f'packed {k} of episode {episode} differs from its source {src}')
    table = npy(f'{src}/mask_table.npy')
    check(np.array_equal(packed['mask_table'][offs['masks']:offs['masks']+entry['masks']], table), f'packed mask table of episode {episode} differs')


def verify_batch(mode, d, lo, hi, banks):
    """Inventory, seal, row semantics, bank and per-episode source binding of one packed batch."""
    seal, digest = io.verify_sealed_dir(d, SCHEMA)
    check(seal.get('packed') is True, f'{d} is not a packed seal')
    keys = set(seal['files'])
    check(all(k == 'mask_table.npy' or k == 'sources.json' or k.startswith('train/') for k in keys), f'{d}: unexpected sealed file')
    arrays = {Path(k).stem: npy(f'{d}/{k}') for k in keys if k.startswith('train/') and k.endswith('.npy')}
    arrays['mask_table'] = npy(f'{d}/mask_table.npy')
    n = len(arrays['teacher_root'])
    check(n == int(seal['rows']) and n > 0, f'{d} row count')
    sizes = np.diff(arrays['root_offsets'])
    roots = arrays['teacher_root'].astype(bool) & (arrays['teacher_wait_kind'] == 0) & arrays['expert_action_supervision_valid'].astype(bool) & (sizes > 0)
    if mode in ('O', 'holdout'):
        check(bool(roots.all()), f'{d} non-root rows present')
        check(bool((arrays['recorded_outcome'] == 0).all()), f'{d} outcome stored')
    offs, valid = arrays['root_offsets'], arrays['root_valid']; ridx = np.flatnonzero(roots)
    check(all(bool(valid[offs[i]:offs[i+1]].any()) for i in ridx), f'{d} root without a valid score')
    seeds = arrays['perspective_ids']
    E, Cb = banks['reporting'], banks['collection']
    check(bool(((seeds >= lo) & (seeds < hi)).all()), f'{d} seed outside its bank range')
    check(not bool(((seeds >= E['base']) & (seeds < E['base']+E['count'])).any()), f'{d} evaluation-bank seed present')
    if mode == 'OW':
        check(not bool(((seeds >= Cb['base']) & (seeds < Cb['base']+Cb['count'])).any()), f'{d} collection-bank C seed in O_W')
    src = io.read_json(f'{d}/sources.json', 256 << 20)
    ep = arrays['episode_ids']
    check((int(ep.max())+1 if len(ep) else 0) == len(src['games']), f'{d}: episode ids do not match sources')
    eps, cur = [], dict(rows=0, entities=0, roots=0, masks=0)
    for e, g in enumerate(src['games']):
        path = g['path']
        _, msha = io.verify_sealed_dir(path, SCHEMA)                       # complete raw source re-verification
        check(msha == g['manifest_sha256'], f'source game {path} changed since packing')
        sel = ep == e
        check(int(sel.sum()) == int(g['rows']), f'episode {path} rows differ from sources.json')
        episode_bytes_equal(arrays, path, cur, g, e)
        eseeds = {int(x) for x in np.unique(seeds[sel])}
        check(len(eseeds) == 1, f'episode {path} mixes seeds')
        eps.append(dict(path=path, manifest_sha256=msha, rows=int(g['rows']), roots=int(roots[sel].sum()), seeds=eseeds))
        for k in cur: cur[k] += int(g[k])
    single = int((sizes[ridx] == 1).sum())
    return dict(name=Path(d).name, manifest_sha256=digest, rows=n, roots=int(roots.sum()), games=len(src['games'])), eps, single, d


def verify(mode, root, plan, label_receipts, selection, o_gate, label_plan, result, acceptance=None):
    banks = plan['seed_ranges']
    B = banks['collection_w'] if mode == 'OW' else banks['collection']
    lo, hi = B['base'], B['base']+B['count']
    if mode == 'O': hi = B['base']+HOLDOUT_MIN_INDEX
    if mode == 'holdout': lo = B['base']+HOLDOUT_MIN_INDEX
    names = io.listdir(root)
    check(RECEIPT not in names, 'receipt already exists')
    batches = sorted(n for n in names if io.is_real_dir(f'{root}/{n}'))
    check(batches and all(n.startswith('batch-') and n[6:].isdigit() and len(n) == 10 for n in batches), f'root directories {batches}')
    for n in batches:                                        # R7-F3: only a pack accepted by its guard.py run counts
        check(studytree.guarded_output(JOB, f'{root}/{n}') is not None, f'{root}/{n} has no passed guard receipt (guarded pack)')
    extra = set(names)-set(batches)-OPERATIONAL
    check(not extra, f'unexpected root entries: {sorted(extra)}')
    for n in sorted(OPERATIONAL & set(names)): io.stat_leaf(f'{root}/{n}')
    total_rows = total_roots = single = 0; out, eps, dirs = [], [], []
    for name in batches:
        row, e, s, d = verify_batch(mode, f'{root}/{name}', lo, hi, banks)
        out.append(row); eps += e; single += s; dirs.append(d); total_rows += row['rows']; total_roots += row['roots']
    per_arm = {}
    if mode in ('O', 'holdout'):
        raw_root = JOB+f'/data/raw-{mode}'
        check(label_plan is not None, 'label plan required')
        plan_sha = label_plan['__sha256__']
        check(label_receipts and all(r.get('passed') is True and r.get('set') == mode and r.get('plan_sha256') == plan_sha
                                     and r.get('drop_rate', 1) <= MISMATCH_LIMIT for r in label_receipts),
              'label receipts not passed for this set and plan')
        threads = {r.get('threads') for r in label_receipts}
        check(len(threads) == 1, 'label receipts disagree on the thread count')
        planned = {(g['arm'], g['index']): g for g in label_plan['sets'][mode]}
        receipt_games = {tuple(x) for r in label_receipts for x in r['games']}
        packed = set()
        for e in eps:
            p = e['path']; arm, gname = p.split('/')[-2:]
            check(p == f'{raw_root}/{arm}/{gname}' and arm in ARM_CAPS and gname.startswith('game-'), f'source {p} is not under {raw_root}/<arm>/')
            index = int(gname.split('-')[1])
            g = planned.get((arm, index)); check(g is not None, f'source game {arm}/{index} not in the label plan set {mode}')
            r = io.read_json(p+'/receipt.json', 16 << 20)
            for k, v in dict(arm=arm, index=index, seed=g['seed'], capture_sha256=g['sha256'], plan_sha256=plan_sha,
                             keep_sha256=g['keep_sha256'], rows=e['rows'], teacher=TEACHER, search_threads=next(iter(threads))).items():
                check(r.get(k) == v, f'source game {arm}/{index} receipt {k} {r.get(k)!r} != {v!r}')
            check(e['seeds'] == {g['seed']}, f'source game {arm}/{index} packed seeds != planned seed')
            packed.add((arm, index)); per_arm[arm] = per_arm.get(arm, 0)+e['rows']
        check(packed == receipt_games, f'packed games != label receipt games ({len(packed)} vs {len(receipt_games)})')
        labeled = sum(int(r['rows']) for r in label_receipts)
        check(total_rows == labeled, f'packed rows {total_rows} != label receipts rows {labeled}')
    if mode == 'O':
        check(O_MIN <= total_rows <= O_MAX, f'O rows {total_rows} outside [{O_MIN}, {O_MAX}]')
        check(all(per_arm.get(k, 0) <= v for k, v in ARM_CAPS.items()), f'per-arm caps exceeded {per_arm}')
    if mode == 'OW':
        verify_acceptance(acceptance)
        sel_games = selection.get('selected_games')
        nsel = len(sel_games or [])
        check(selection.get('reached') is True and sel_games == list(range(nsel)) and nsel > 0, 'selection is not exactly range(n)')
        check(selection.get('v1_sha256') == V1_SHA and selection.get('emitter_sha256') == EMITTER_SHA, 'selection producer identity')
        check(selection['target_roots'] == o_gate['rows'], 'O_W target != |O|')
        rows_by_g = {r['g']: r for r in selection.get('games', [])}
        check(sorted(rows_by_g) == list(range(nsel)), 'selection identity rows != range(n)')
        by_g = {}
        for e in eps:
            p = e['path']
            check(os.path.dirname(p) == JOB+'/data/raw-OW' and Path(p).name.startswith('game-'), f'source {p} not under raw-OW')
            g = int(Path(p).name.split('-')[1]); check(g not in by_g, f'duplicate source game {g}')
            check(e['seeds'] == {B['base']+g}, f"source game {g} seed != C'+{g}")
            rv = io.project_json(p+'/replay.json', REPLAY_KEEP)
            sr = rows_by_g.get(g, {})
            check(rv.get('seed') == B['base']+g and rv.get('seat') == g % 2 and rv.get('index') == 56+g % 2 and rv.get('opponent') == 'v1',
                  f'source game {g} realized identity')
            check(sr.get('manifest_sha256') == e['manifest_sha256'] and sr.get('seed') == B['base']+g and sr.get('seat') == g % 2
                  and sr.get('own') == g % 5 and sr.get('opponent') == (g//5) % 5 and sr.get('roots') == e['roots'],
                  f'source game {g} differs from its selection row')
            by_g[g] = e['roots']
        check(sorted(by_g) == list(range(nsel)), 'O_W sources != the selected prefix range(n)')
        prefix_before = sum(by_g[g] for g in range(nsel-1))
        check(prefix_before < o_gate['rows'] <= total_roots, f'O_W prefix not minimal or short: {prefix_before} < {o_gate["rows"]} <= {total_roots}')
        check(total_roots == selection['selected_roots'] and by_g[nsel-1] == selection.get('last_game_roots'),
              'selection root counts differ from the packed rows')
        per_arm['O_W'] = total_rows
    for d in dirs:                                               # read-only sealing of the packed corpus
        for k in io.verify_sealed_dir(d, SCHEMA)[0]['files']: io.chmod_readonly(f'{d}/{k}')
        io.chmod_readonly(f'{d}/manifest.json')
    result.update(batches=out, rows=total_rows, roots=total_roots, rows_per_arm=per_arm, sealed=True,
                  single_candidate_roots=single, single_candidate_root_share=single/max(1, total_roots),
                  sources_sha256=sha_json(sorted([e['path'], e['manifest_sha256']] for e in eps)))


def verify_acceptance(acc):
    """R2-F5: exactly the two qualification-bank acceptance games, re-verified seals and replay identities."""
    check(acc is not None, 'acceptance smoke receipt required')
    check(acc.get('schema') == 'x4s4.ow-acceptance.v2' and acc.get('passed') is True and acc.get('bank') == 'qualification'
          and acc.get('base') == QUAL_BASE, 'acceptance receipt schema/bank')
    check(acc.get('v1_sha256') == V1_SHA and acc.get('emitter_sha256') == EMITTER_SHA, 'acceptance producer identity')
    games = acc.get('games') or []
    check([g.get('g') for g in games] == [0, 1], 'acceptance must hold exactly games 0 and 1')
    for row in games:
        g = row['g']; d = f'{JOB}/data/raw-OW-acceptance/game-{g:05d}'
        check(row.get('status') == 'sealed' and row.get('replay_exact') is True and row.get('seed') == QUAL_BASE+g, f'acceptance game {g} row')
        _, msha = io.verify_sealed_dir(d, SCHEMA)
        check(msha == row.get('manifest_sha256'), f'acceptance game {g} seal differs from its receipt')
        rv = io.project_json(d+'/receipt.json', REPLAY_KEEP)            # the sealed receipt carries replay_exact
        check(rv.get('seed') == QUAL_BASE+g and rv.get('seat') == g % 2 and rv.get('index') == 56+g % 2 and rv.get('opponent') == 'v1'
              and rv.get('replay_exact') is True, f'acceptance game {g} replay identity')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=sorted(MODES), required=True)
    ap.add_argument('--plan', required=True)                       # x4s4 plan.json (banks)
    ap.add_argument('--label-receipts', nargs='*', default=[])
    ap.add_argument('--selection')                                 # OW only: <job>/data/raw-OW-selection.json
    a = ap.parse_args(argv)
    studytree.require_guard(f'verify_onpolicy {a.mode}')                   # R7: runs only under guard.py
    root = JOB+'/data/'+MODES[a.mode][0]; gate = JOB+'/data/'+MODES[a.mode][1]
    t0 = time.monotonic()
    result = dict(passed=False, sealed=False, mode=a.mode, root=root, label='X4S-4 exploration, NEVER ADOPTABLE',
                  python_optimize=sys.flags.optimize)
    ids = {}
    try:
        check(not io.lexists(gate), 'gate already exists')
        plan = io.read_json(a.plan, 16 << 20)
        for p in a.label_receipts:                               # R7: guarded acceptance of every label run
            check(studytree.guarded_output(JOB, p) is not None, f'label receipt {p} has no passed guard receipt')
        receipts = [io.read_json(p, 64 << 20) for p in a.label_receipts]
        ids['label_receipts_sha256'] = sorted(io.sha256_file(p) for p in a.label_receipts)
        selection = o_gate = label_plan = acceptance = None
        if a.mode in ('O', 'holdout'):
            raw = io.read_bytes(JOB+'/data/label-plan.json', 1 << 30)
            label_plan = io.loads_strict(raw); label_plan['__sha256__'] = ids['label_plan_sha256'] = hashlib.sha256(raw).hexdigest()
            import label                                              # R3-F5: re-run parity admission on the plan's receipt
            label.recheck_parity(label_plan); ids['parity_receipt_sha256'] = label_plan['parity_receipt_sha256']
            check(a.selection is None, '--selection only for OW')
        else:
            check(a.selection == JOB+'/data/raw-OW-selection.json', '--selection must be <job>/data/raw-OW-selection.json')
            check(studytree.guarded_output(JOB, a.selection) is not None, 'the O_W selection has no passed guard receipt')
            selection = io.read_json(a.selection, 64 << 20); ids['selection_sha256'] = io.sha256_file(a.selection)
            o_gate = io.read_json(JOB+'/data/'+MODES['O'][1], 64 << 20); ids['o_gate_sha256'] = io.sha256_file(JOB+'/data/'+MODES['O'][1])
            accp = JOB+'/data/raw-OW-acceptance-smoke.json'
            check(studytree.guarded_output(JOB, accp) is not None, 'the O_W acceptance smoke has no passed guard receipt')
            acceptance = io.read_json(accp, 16 << 20); ids['acceptance_sha256'] = io.sha256_file(accp)
        verify(a.mode, root, plan, receipts, selection, o_gate, label_plan, result, acceptance)
        result['passed'] = True
    except Exception as e:                                         # any failure is a failed, receipted verification
        result['error'] = repr(e)
    result.update(ids, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), wall_seconds=time.monotonic()-t0)
    io.write_json_once(root+'/'+RECEIPT, result, roles=('data',), mode=0o444)
    if result['passed']:
        gate_body = dict(utc=result['utc'], mode=a.mode, batches=result['batches'], rows=result['rows'], roots=result['roots'],
                         rows_per_arm=result['rows_per_arm'], single_candidate_root_share=result['single_candidate_root_share'],
                         receipt_sha256=io.sha256_file(root+'/'+RECEIPT), sources_sha256=result['sources_sha256'], **ids,
                         label='X4S-4 %s, exploration, NEVER ADOPTABLE' % a.mode)
        io.write_json_once(gate, gate_body, roles=('data',), mode=0o444)
    print(json.dumps({k: v for k, v in result.items() if k != 'batches'}), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
