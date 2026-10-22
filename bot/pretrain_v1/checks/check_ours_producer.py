"""CPU-only calibrated-engine producer qualification. No learner, rollout queue or HP1 process changes."""
import argparse
from collections import deque
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time


def bootstrap(runtime, source, manifest):
    if any(n == 'clasher' or n.startswith('clasher.') or n == 'bot' for n in sys.modules):
        raise RuntimeError('bootstrap the pinned runtime before importing engine or bot modules')
    d = json.loads(manifest.read_text())
    expected = dict(files='380c8141ab1c3cc26ea9490869b0023be9e37481532cdbeda75817462410bd30',
                    source_files='43c20b2df9880af8634e1cd3efefb8ae369e3dad615af7f75bc830b59a9c6583')
    for key, root in [('files', runtime), ('source_files', source)]:
        digest = hashlib.sha256(json.dumps(d[key], sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        assert digest == expected[key], 'unapproved actor/runtime manifest identity'
        for name, digest in d[key].items():
            assert hashlib.sha256((root/name).read_bytes()).hexdigest() == digest, name
    os.environ.update(CUDA_VISIBLE_DEVICES='', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1',
                      CLASHER_ROOT=str(runtime), CLASHER_EVAL_RUNTIME_ROOT=str(runtime),
                      CLASHER_BOT_RUNTIME=str(runtime), CLASHER_DELAY_NATIVE_DIR=str(runtime/'native'),
                      CLASHER_BOT_RUNTIME_PINS='hp1rl-joint-0dcab45f7')
    sys.path.insert(0, str(source))
    from bot.players.runtime import Runtime
    rt = Runtime()  # Must precede bot.levels.match, which imports engine classes.
    here = Path(__file__).resolve().parents[1]
    import bot
    spec = importlib.util.spec_from_file_location('bot.pretrain_v1', here/'__init__.py',
                                                submodule_search_locations=[str(here)])
    package = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = package; spec.loader.exec_module(package); bot.pretrain_v1 = package
    return rt, d


def check_origins(runtime, source):
    for name, module in list(sys.modules.items()):
        loc = getattr(module, '__file__', None)
        if not loc:
            continue
        if name == 'clasher' or name.startswith('clasher.'):
            assert runtime in Path(loc).resolve().parents, (name, loc)
        elif name == 'bot' or name.startswith('bot.'):
            root = Path(__file__).resolve().parents[1] if name.startswith('bot.pretrain_v1') else source
            assert root in Path(loc).resolve().parents, (name, loc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--runtime', type=Path, required=True)
    ap.add_argument('--actor-source', type=Path, required=True)
    ap.add_argument('--manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--smoke-checkpoint', type=Path, help='one retained CPU readiness game; never training')
    a = ap.parse_args()
    assert os.uname().nodename.split('.')[0] in ['127x05', '127x08']
    if a.out.exists():
        raise SystemExit('fresh qualification output required; preserve failed attempts')
    t0 = time.time()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    os.environ['NUMBA_CACHE_DIR'] = str(a.out.parent/('numba-'+os.uname().nodename))
    try:
        rt, lineage = bootstrap(a.runtime.resolve(), a.actor_source.resolve(), a.manifest)
    except BaseException as ex:
        a.out.write_text(json.dumps(dict(status='failed', stage='bootstrap', error=repr(ex)))+'\n')
        raise
    from bot.levels.match import level_battle, resolve
    from clasher.arena import Position
    from bot.pretrain_v1 import featurize as F
    from bot.pretrain_v1.sim_ours import OursFrames, new_builder, record_from_line
    levels = dict(Skeletons=8, Musketeer=7, IceGolem=7, Cannon=9, Fireball=8, Zap=9, IceSpirit=8, HogRider=10)
    counts = dict(records=0, parity=0, private_mutations=0, deployments=0)
    cases = []
    try:
        for ci, card in enumerate(levels):
            own = [card]+[c for c in levels if c != card]
            decks = [own, list(levels)]
            spec = resolve(dict(cards={0: levels, 1: levels}, towers={0: 9, 1: 9}, planner='l11'), decks)
            b = level_battle(2026102204000000+ci, decks, rt.R.builder.loader, spec)
            frames = [OursFrames(b, seat, decks[seat], ci) for seat in [0, 1]]
            shadow = [new_builder(deck) for deck in decks]
            histories = [F.History(), F.History()]
            replay = [F.History(), F.History()]
            deployment = None
            while b.tick <= 240:
                if b.tick == 121:
                    b.players[0].elixir = 10.
                    aim = Position(7.5, 22.5 if card in ['Fireball', 'Zap'] else 10.5)
                    deployment = b.deploy_card(0, card, aim)
                    assert deployment, f'qualification deployment refused: {card}'
                    counts['deployments'] += 1
                if b.tick >= 90 and b.tick % 5 == 0:
                    for seat in [0, 1]:
                        f = frames[seat]
                        before = json.dumps(f.frame(), sort_keys=True)
                        other = b.players[1-seat]
                        saved = (other.hand, other.cycle_queue, other.elixir, b.rng.getstate())
                        try:
                            other.hand = list(reversed(other.hand)); other.cycle_queue = deque(reversed(other.cycle_queue))
                            other.elixir = .123; b.rng.seed(910000+ci)
                            assert json.dumps(f.frame(), sort_keys=True) == before, 'private engine state entered frame'
                        finally:
                            other.hand, other.cycle_queue, other.elixir, rng = saved; b.rng.setstate(rng)
                        counts['private_mutations'] += 1
                        (record, extras), line = f.record()
                        sh, why = record_from_line(line, shadow[seat]); assert sh is not None, why
                        x = F.observe(record, extras, histories[seat]); y = F.observe(sh[0], sh[1], replay[seat])
                        assert F.feature_bytes(x) == F.feature_bytes(y)
                        counts['records'] += 1; counts['parity'] += 1
                b.step()
            cases.append(dict(card=card, deployed=deployment, final_tick=b.tick))
        smoke = None
        if a.smoke_checkpoint:
            from bot.players.ours import play_match
            from bot.eval.headline import make_player
            from bot.pretrain_v1.policy import load
            from bot.pretrain_v1.sim_ours import PolicyOursPlayer, bind_matches
            model, checkpoint = load(a.smoke_checkpoint)
            own = PolicyOursPlayer(model)
            players = {0: own, 1: make_player(rt, 'R3a')}
            actual_levels = dict(cards={0: levels, 1: levels}, towers={0: 9, 1: 9}, planner='l11')
            start = time.monotonic()
            with bind_matches(players):
                match = play_match(rt, players, seed=2026102204000100, decks=[list(levels), list(levels)],
                                   levels=actual_levels, verbose=True)
            assert match['terminal'], 'readiness game did not reach a true terminal state'
            smoke = dict(match=match, decisions=len(own.rows), counts=own.counts, params=model.n_params(),
                         checkpoint_sha256=hashlib.sha256(a.smoke_checkpoint.read_bytes()).hexdigest(),
                         seconds=time.monotonic()-start, logp_finite=all(__import__('math').isfinite(r[4]) for r in own.rows))
            assert smoke['logp_finite']
        check_origins(a.runtime.resolve(), a.actor_source.resolve())
        result = dict(status='pass', counts=counts, cases=cases, smoke=smoke, runtime_pins=rt.pins,
                      runtime_manifest=lineage['runtime_manifest_sha256'], actor_manifest=lineage['actor_manifest_sha256'],
                      feature_hash=F.feature_hash(), seconds=time.time()-t0)
    except BaseException as ex:
        result = dict(status='failed', error=repr(ex), counts=counts, cases=cases, seconds=time.time()-t0)
        raise
    finally:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(json.dumps(result, indent=1)+'\n')
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
