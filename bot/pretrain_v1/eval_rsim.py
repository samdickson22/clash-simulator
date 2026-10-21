"""Offline evaluation hook (a): pretrain-v1 policy-only arm on the rl-search-prior-20261020-r2 paired bank.

Same harness, bank, opponents, levels and seeds as r2 (RoyaleSim 16.402, account levels on the HOG26-acct row,
opponents LIVE-K4CW-r16-fp / R3a constructed exactly as screen_r2.py does). Only the own seat changes: the
current live search (r2 arm f1a2, rows already sealed in r2/screen/rows/NNNN-f1a2.json) is replaced by
sim_rsim.PolicyV1Player. Pairing is by identical initial conditions (deck order, levels, seat, opponent, seed), not
by trajectory. Every attempted case gets a sealed row (no retries); errors stay rows.

    R2=/mpac/sdicks02/scratch/rl-search-prior-20261020-r2
    $R2/run.sh /mpac/sdicks02/repos/clasher-pretrain-v1/bot/pretrain_v1/eval_rsim.py \
        --ckpt CKPT --out DIR --rows HOG26-acct --workers 16 [--limit N] [--arm NAME]
    ... eval_rsim.py --summarise --out DIR
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import sys
import time
import traceback
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_BOT = HERE.parents[1]
R2 = Path('/mpac/sdicks02/scratch/rl-search-prior-20261020-r2')
GiB = 1024**3


def mem_available():
    return int(next(l.split()[1] for l in open('/proc/meminfo') if l.startswith('MemAvailable:')))*1024


def dump(path, row):
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(row))
    tmp.replace(path)


CASE_KEYS = ('index', 'id', 'row', 'seed', 'seat', 'opponent', 'own_deck', 'own_levels', 'own_king', 'opponent_deck',
             'opponent_levels', 'opponent_king')


def same_case(row, case):
    return all(row.get(k) == case[k] for k in CASE_KEYS)


def external_identity():
    """sha256 of everything outside this package the comparison depends on, resolved through the ACTUAL import path
    of this process (run under r2's run.sh): the RoyaleSim package really imported, r2's harness / evaluation code,
    its code tree (bot.players, opponents, search), the runtime-joint Python, vocab / player config / level profile
    and every opponent model file."""
    import royalesim
    rsim = Path(royalesim.__file__).resolve().parent
    py = lambda d: [p for p in Path(d).rglob('*.py') if '__pycache__' not in p.parts]
    files = sorted(set(list(R2.glob('*.py')) + py(R2/'evaluation') + py(R2/'code-tree') + py(R2/'runtime-joint')
                       + [R2/'run.sh', R2/'evaluation/vocab-full.json', R2/'evaluation/player-config.json',
                          R2/'rl-source/bot/levels/profile.py']
                       + [p for p in (R2/'evaluation/models').rglob('*') if p.is_file()]
                       + [p for p in rsim.rglob('*') if p.is_file() and '__pycache__' not in p.parts]))
    out = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    out['royalesim_module'] = str(rsim)
    return out


def control_pins(cases):
    """The runtime pins every sealed r2 control (f1a2) row of the assigned cases was produced under (must agree)."""
    pins = set()
    for c in cases:
        q = R2/'screen'/'rows'/f"{c['index']:04}-f1a2.json"
        if q.exists():
            pins.add(json.dumps(json.loads(q.read_text()).get('runtime_pins'), sort_keys=True))
    if len(pins) != 1:
        raise SystemExit(f'control rows carry {len(pins)} distinct runtime pin sets')
    return json.loads(pins.pop())


def setup():
    sys.path.insert(0, str(R2))
    import eval_setup
    import bot
    import importlib.util
    # ONLY bot.pretrain_v1 comes from this repo, registered by an explicit package spec; the repository's bot
    # directory never joins bot.__path__ (otherwise a lazy `import bot.<x>` absent from r2, e.g. bot.cyclemodel,
    # would silently load this repo's code into an opponent; Sol R8)
    if 'bot.pretrain_v1' not in sys.modules:
        spec = importlib.util.spec_from_file_location('bot.pretrain_v1', HERE.parent/'__init__.py',
                                                      submodule_search_locations=[str(HERE.parent)])
        pkg = importlib.util.module_from_spec(spec)
        sys.modules['bot.pretrain_v1'] = pkg
        spec.loader.exec_module(pkg)
        bot.pretrain_v1 = pkg
    assert str(REPO_BOT) not in [str(Path(p)) for p in bot.__path__]
    eval_setup.sim_modules()
    import fullpool_eval as fp
    fp.MODEL_ROOT = R2/'evaluation/models'
    fp.FAST = f'student:{fp.MODEL_ROOT}/fits/f1a2/step-001200.pt'
    fp.OLD_FAST = f'student:{fp.MODEL_ROOT}/students/it5s2-step001200.pt@0.5375'
    return fp


HARNESS_MODULES = ('bot', 'bot.players', 'bot.players.base', 'bot.players.policy', 'bot.players.royalesim_match',
                   'bot.players.royalesim_translate', 'bot.players.royalesim_adapter', 'bot.players.runtime',
                   'bot.eval.headline', 'bot.livediag.k4cw_fp', 'bot.live.player', 'bot.search.lopp_fast')


def _origin_ok(name, loc):
    own = name == 'bot.pretrain_v1' or name.startswith('bot.pretrain_v1.')
    root = HERE.parent.resolve() if own else R2.resolve()
    loc = Path(loc)
    return loc == root or root in loc.parents


def module_origins():
    """Every LOADED bot / bot.* module and where it came from (after importing the checked harness modules):
    {module: {'file': path or None, 'paths': [package search paths]}}. Every location must lie inside r2 (code tree /
    evaluation), except the bot.pretrain_v1 namespace, which must be this package. Called before the first game and
    after every game (success or failure), so controller-dependent lazy imports are caught too; raises SystemExit on
    a violation."""
    import importlib
    for name in HARNESS_MODULES:
        importlib.import_module(name)
    out = {}
    for name, m in sorted(sys.modules.items()):
        if m is None or not (name == 'bot' or name.startswith('bot.')):
            continue
        f = getattr(m, '__file__', None)
        rec = dict(file=str(Path(f).resolve()) if f else None,
                   paths=[str(Path(p).resolve()) for p in (getattr(m, '__path__', None) or [])])
        for loc in ([rec['file']] if rec['file'] else []) + rec['paths']:
            if not _origin_ok(name, loc):
                raise SystemExit(f'{name} resolved outside its approved root: {loc}')
        out[name] = rec
    return out


def origins_valid(origins):
    """Shared resume / summary validator: complete evidence (every harness module and bot.pretrain_v1 recorded) and
    every recorded file / package path inside its approved root. -> (ok, reason)."""
    if not isinstance(origins, dict):
        return False, 'no module-origin evidence'
    for name in HARNESS_MODULES + ('bot.pretrain_v1',):
        if name not in origins:
            return False, f'origin evidence lacks {name}'
    for name, rec in origins.items():
        if not isinstance(rec, dict) or 'paths' not in rec:
            return False, f'{name}: incomplete origin record'
        for loc in ([rec['file']] if rec.get('file') else []) + list(rec['paths']):
            if not _origin_ok(name, loc):
                return False, f'{name} outside its approved root: {loc}'
    return True, None


def worker(wid, workers, a, cases):
    import torch
    torch.set_num_threads(1)
    fp = setup()
    from screen_r2 import runtime
    from bot.livediag.k4cw_fp import make_k4cw_fp
    from bot.eval.headline import make_player
    from bot.players.royalesim_match import play_match
    from bot.pretrain_v1.policy import load
    from bot.pretrain_v1.sim_rsim import PolicyV1Player
    import importlib.util
    spec = importlib.util.spec_from_file_location('eval_profile', R2/'rl-source/bot/levels/profile.py')
    profile = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = profile
    spec.loader.exec_module(profile)
    rt = runtime()
    origins = module_origins()
    man = json.loads((Path(a.out)/'manifest.json').read_text())
    if json.dumps(rt.pins, sort_keys=True) != json.dumps(man['runtime_pins'], sort_keys=True):
        raise SystemExit('this runtime differs from the controls\' runtime pins')
    if external_identity() != man['external_sha256']:
        raise SystemExit('this worker imports a harness / simulator / model set that differs from the run manifest')
    vocab = json.loads((R2/'evaluation/vocab-full.json').read_text())
    model, ck = load(a.ckpt)
    ck_sha = hashlib.sha256(Path(a.ckpt).read_bytes()).hexdigest()
    bank_sha = hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest()
    out = Path(a.out)
    for pos, case in enumerate(cases):
        if pos % workers != wid:
            continue
        dest = out/'rows'/f"{case['index']:04}-{a.arm}.json"
        if dest.exists():
            kept = json.loads(dest.read_text())
            if (kept.get('ckpt_sha256') != ck_sha or kept.get('bank_sha256') != bank_sha or not same_case(kept, case)
                    or kept.get('runtime_pins') != man['runtime_pins']):
                raise SystemExit(f'{dest}: retained row from another checkpoint / bank / case')
            if not kept.get('error') and not kept.get('invalid'):
                ok, why = origins_valid(kept.get('module_origins_after'))
                if not ok:
                    raise SystemExit(f'{dest}: retained row has invalid provenance ({why})')
            continue
        marker = dest.with_suffix('.attempt')
        if marker.exists():                          # an interrupted attempt: retained as an infrastructure failure
            dump(dest, dict(json.loads(marker.read_text()), error='interrupted attempt (no sealed row)'))
            marker.unlink()
            continue
        while mem_available() <= 28*GiB or os.getloadavg()[0] > 90:
            print('ADMISSION_HOLD', wid, case['index'], flush=True)
            time.sleep(15)
        row = dict(case, arm=a.arm, ckpt=a.ckpt, ckpt_sha256=ck_sha, bank_sha256=bank_sha, host=os.uname().nodename,
                   started=time.time(), pid=os.getpid(), runtime_pins=rt.pins, module_origins=origins)
        dump(marker, row)
        t = time.monotonic()
        try:
            seat = case['seat']
            own = PolicyV1Player(rt, model, name=f'pretrain-v1:{a.arm}')
            if case['opponent'] == 'LIVE-K4CW-r16-fp':
                other = fp.Observed(make_k4cw_fp(rt, fp.FAST), 'strong full-pool', 'FullPoolBelief',
                                    fp.FAST.split(':', 1)[1])
            else:
                other = fp.Observed(make_player(rt, case['opponent']), f"full-pool {case['opponent']}")
            other.rec.act = other.rec.inner.act
            players = {seat: own, 1 - seat: other}
            decks = [case['own_deck'], case['opponent_deck']]
            otherlevels = {c: max(profile.FLOOR.get(profile.rarity(rt, c), 1), int(l))
                           for c, l in case['opponent_levels'].items()}
            levels = [case['own_levels'], otherlevels]
            towers = [case['own_king'], case['opponent_king']]
            if seat == 1:
                decks.reverse()
                levels.reverse()
                towers.reverse()
            result = play_match(rt, players, seed=case['seed'], decks=decks, vocab=vocab, client='16.402',
                                levels=levels, tower_levels=towers, verbose=True)
            issues, invalid = [], []
            if not result['terminal']:
                invalid.append('nonterminal')                 # a failure, never a draw
            if result['channels'][seat]['rejected']:
                issues.append('our command rejections')
            bad = {k: v for k, v in own.counts.items()
                   if k.startswith(('frame_error', 'feature_error', 'unoriented', 'shadow_MISMATCH', 'channel_mismatch'))}
            if bad:
                invalid.append(f'projection/contract failure {bad}')
            row.update(invalid=invalid)
            row.update(result=result, score=.5 if result['winner'] is None else float(result['winner'] == seat),
                       win=int(result['winner'] == seat), draw=int(result['winner'] is None), issues=issues,
                       policy_counts=own.counts, frame_stats=own.frames.stats, n_plays=len(own.decisions))
        except BaseException as ex:
            row.update(error=repr(ex), traceback=traceback.format_exc())
        try:
            row['module_origins_after'] = module_origins()
        except SystemExit as ex:
            row.setdefault('invalid', []).append(f'provenance: {ex}')
            row['seconds'] = time.monotonic() - t
            dump(dest, row)
            marker.unlink()
            raise
        row['seconds'] = time.monotonic() - t
        dump(dest, row)
        marker.unlink()
        print('ROW', wid, case['index'], row.get('score'), row.get('issues'), row.get('error'), round(row['seconds'], 1),
              flush=True)
        players = own = other = result = row = None
        gc.collect()


def summarise(a):
    """DEV readout over the ASSIGNED cases frozen in the run manifest (no case is dropped):
      complete_pairs  mean of policy - search over pairs where both arms produced a valid terminal game; a controller
                      stratum without valid pairs leaves the pooled estimate undefined
      itt_lower/upper every assigned case: a candidate that failed OR did not run scores 0 (lower) / 1 (upper); a
                      failed control scores 1 (lower) / 0 (upper)
    Point estimates and the 20,000-draw PCG64 case bootstrap (stratified by opponent controller) use the SAME fixed
    equal controller weights; 95% and 97.5% intervals. Every candidate and control row is checked against its
    assigned case and the manifest. DEV / selection evidence only, not a registered confirmation."""
    import numpy as np
    man = json.loads((Path(a.out)/'manifest.json').read_text())
    bank = json.loads((R2/'evaluation/bank.json').read_text())
    if hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest() != man['bank_sha256']:
        raise SystemExit('bank changed since the run manifest')
    by_index = {c['index']: c for c in bank['cases']}
    cases = [by_index[i] for i in man['assigned']]
    recs = []
    for c in cases:
        p = Path(a.out)/'rows'/f"{c['index']:04}-{man['arm']}.json"
        r = json.loads(p.read_text()) if p.exists() else None
        if r is not None and (r.get('ckpt_sha256') != man['ckpt_sha256'] or r.get('bank_sha256') != man['bank_sha256']
                              or not same_case(r, c) or r.get('runtime_pins') != man['runtime_pins']):
            raise SystemExit(f'{p}: row does not match the run manifest / assigned case / runtime pins')
        if r is not None and not r.get('error') and not r.get('invalid'):
            ok, why = origins_valid(r.get('module_origins_after'))
            if not ok:
                raise SystemExit(f'{p}: row claims validity but its provenance fails ({why})')
        q = R2/'screen'/'rows'/f"{c['index']:04}-f1a2.json"
        b = json.loads(q.read_text()) if q.exists() else None
        if b is not None and (not same_case(b, c) or b.get('arm') != 'f1a2' or b.get('bank_sha256') != man['bank_sha256']
                              or b.get('runtime_pins') != man['runtime_pins']):
            raise SystemExit(f'{q}: control row does not match its case / arm / bank / runtime pins')
        cand_ok = (r is not None and 'score' in r and not r.get('error') and not r.get('invalid')
                   and (r.get('result') or {}).get('terminal'))
        ctrl_ok = b is not None and 'score' in b and not b.get('error') and (b.get('result') or {}).get('terminal')
        recs.append(dict(index=c['index'], opp=c['opponent'], cand=r['score'] if cand_ok else None,
                         ctrl=b['score'] if ctrl_ok else None, ran=r is not None))
    opps = sorted({x['opp'] for x in recs})
    out = dict(arm=man['arm'], assigned=len(recs), ran=sum(x['ran'] for x in recs),
               complete=all(x['ran'] for x in recs),
               candidate_failures=sum(x['ran'] and x['cand'] is None for x in recs),
               candidate_not_run=sum(not x['ran'] for x in recs),
               control_failures=sum(x['ctrl'] is None for x in recs), controller_weights={o: 1/len(opps) for o in opps},
               manifest={k: man[k] for k in ('ckpt', 'ckpt_sha256', 'bank_sha256', 'feature_hash', 'rows')})
    rng = np.random.Generator(np.random.PCG64(2026102021))

    def estimate(diffs):
        point = sum(np.mean(diffs[o])/len(opps) for o in opps)
        stats = np.zeros(20000)
        for o in opps:
            d = np.array(diffs[o])
            stats += rng.choice(d, size=(20000, len(d))).mean(1)/len(opps)
        return float(point), [float(np.quantile(stats, q)) for q in (.0125, .025, .975, .9875)]
    for label, fc, fk, need_run in (('complete_pairs', None, None, True), ('itt_lower', 0.0, 1.0, False),
                                    ('itt_upper', 1.0, 0.0, False)):
        diffs = {o: [] for o in opps}
        pol, src = {o: [] for o in opps}, {o: [] for o in opps}
        for x in recs:
            cnd = x['cand'] if x['cand'] is not None else fc
            ctl = x['ctrl'] if x['ctrl'] is not None else fk
            if cnd is None or ctl is None:
                continue
            diffs[x['opp']].append(cnd - ctl)
            pol[x['opp']].append(cnd)
            src[x['opp']].append(ctl)
        strata = {o: dict(n=len(diffs[o]), policy=float(np.mean(pol[o])) if pol[o] else None,
                          search=float(np.mean(src[o])) if src[o] else None,
                          delta=float(np.mean(diffs[o])) if diffs[o] else None) for o in opps}
        if any(not diffs[o] for o in opps):
            out[label] = dict(n=sum(len(v) for v in diffs.values()), delta=None, by_opponent=strata,
                              note='undefined: a controller stratum has no valid pair')
            continue
        point, q = estimate(diffs)
        out[label] = dict(n=sum(len(v) for v in diffs.values()), delta=point, ci95=[q[1], q[2]], ci975=[q[0], q[3]],
                          by_opponent=strata)
    rows = [json.loads(p.read_text()) for p in sorted((Path(a.out)/'rows').glob(f"*-{man['arm']}.json"))]
    if external_identity() != man['external_sha256']:
        raise SystemExit('the r2 harness / opponent models / RoyaleSim changed since the run manifest')
    out['runtime_pins'] = man['runtime_pins']
    plays = [r.get('n_plays', 0) for r in rows if 'n_plays' in r]
    out['plays_per_game_mean'] = sum(plays)/max(1, len(plays))
    agg = {}
    for r in rows:
        for k, v in (r.get('policy_counts') or {}).items():
            agg[k] = agg.get(k, 0) + v
    out['policy_counts'] = agg
    out['invalid'] = sum(bool(r.get('invalid')) for r in rows)
    out['invalid_provenance'] = sum(any(str(x).startswith('provenance') for x in (r.get('invalid') or [])) for r in rows)
    out['errors'] = sum('error' in r for r in rows)
    (Path(a.out)/f"summary-{man['arm']}.json").write_text(json.dumps(out, indent=1) + '\n')
    print(json.dumps(out, indent=1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ckpt')
    ap.add_argument('--out', required=True)
    ap.add_argument('--arm', default='pv1')
    ap.add_argument('--rows', nargs='+', default=['HOG26-acct'])
    ap.add_argument('--workers', type=int, default=8)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--summarise', action='store_true')
    a = ap.parse_args()
    if a.summarise:
        return summarise(a)
    out = Path(a.out)
    (out/'rows').mkdir(parents=True, exist_ok=True)
    # NEVER import the `bot` package here: the forked workers must resolve `bot` to r2's code tree (setup()). The
    # featurizer hash comes from a standalone load of featurize.py (stdlib + numpy only).
    import importlib.util
    spec = importlib.util.spec_from_file_location('pv1_featurize_standalone', HERE.parent/'featurize.py')
    F = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(F)
    assert 'bot' not in sys.modules, 'the bot package must not be imported before the workers fork'
    man = dict(arm=a.arm, ckpt=a.ckpt, ckpt_sha256=hashlib.sha256(Path(a.ckpt).read_bytes()).hexdigest(),
               bank_sha256=hashlib.sha256((R2/'evaluation/bank.json').read_bytes()).hexdigest(), rows=a.rows,
               feature_hash=F.feature_hash(), code_sha256={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                                           for p in sorted(HERE.parent.glob('*.py'))})
    bank = json.loads((R2/'evaluation/bank.json').read_text())
    cases = [c for c in bank['cases'] if c['row'] in a.rows]
    if a.limit:
        cases = cases[:a.limit]
    man['assigned'] = [c['index'] for c in cases]
    man['runtime_pins'] = control_pins(cases)
    man['external_sha256'] = external_identity()
    mp = out/'manifest.json'
    keys = ('arm', 'ckpt_sha256', 'bank_sha256', 'feature_hash', 'rows', 'assigned', 'code_sha256', 'runtime_pins',
            'external_sha256')
    if mp.exists():
        old = json.loads(mp.read_text())
        diff = [k for k in keys if old.get(k) != man[k]]
        if diff:
            raise SystemExit(f'output directory belongs to another run (manifest differs in {diff})')
    else:
        mp.write_text(json.dumps(man, indent=1) + '\n')
    while mem_available() < (28 + 1.5*a.workers)*GiB or os.getloadavg()[0] + a.workers > 90:
        print('PARENT_ADMISSION_HOLD', flush=True)
        time.sleep(30)
    children = []
    for w in range(a.workers):
        pid = os.fork()
        if pid == 0:
            try:
                worker(w, a.workers, a, cases)
            except BaseException:
                traceback.print_exc()
                os._exit(1)
            os._exit(0)
        children.append(pid)
    for pid in children:
        os.waitpid(pid, 0)


if __name__ == '__main__':
    main()
