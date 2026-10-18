"""RL rollout actors (CPU): the learner's student plays league games in our engine and records its decisions.

    bot/exit/cpu_job.sh 48 bot/exit/run.sh -m bot.rl.actor --run RUN --workers 48 --block 0

RUN layout (shared with bot.rl.learner):
- RUN/policies/LATEST: "<version> <path>" of the current policy (student-checkpoint format);
- RUN/snapshots/LIST: one snapshot checkpoint path per line (league 'self' opponents);
- RUN/rollouts/v<version>-g<game>.npz (+ RUN/rollouts/games-<block>-<worker>.jsonl summary rows);
- RUN/STOP_ACTORS: workers exit after their current game.
Game g = block*10**6 + k*workers + w uses x4s_setup(g, RL_BANK) (learner seat g%2); the opponent is drawn by a
hash of g from the league shares. Only polls where the learner can act and has a legal play are recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from pathlib import Path

import numpy as np

# int.from_bytes(os.urandom(6),'big')<<4, drawn on 127x04 2026-10-14T19:51Z (reports/bot/rl/PROGRESS.md)
RL_BANK = int(os.environ.get('BOT_RL_BANK', '1462854985943728'))
HEADLINE = (1455777415631152, 10**5)
TRAIN1 = (874184153281168, 10**8)
IT5S2 = '/mpac/sdicks02/repos/clasher-bot-runtime/students/it5s2-step001200.pt'
# 'self' opponent before the first snapshot exists (default it5s2; full-pool runs set the init checkpoint)
SELF0 = os.environ.get('BOT_RL_SELF0', IT5S2)
# full-pool mode: search opponents get C56 decks unless BOT_RL_OPP_C56=0 (roots with R.bots widened, OWN=full)
OPP_C56 = os.environ.get('BOT_RL_OPP_C56', '1') != '0'
# deployed gate threshold of the init (= gate centre of the explore policy, the 'self' snapshots' decode and every
# published policy's calibration); rl5/it5s2 0.5375. Learner and actors must share it (rollout meta is checked).
TAU0 = float(os.environ.get('BOT_RL_TAU0', '0.5375'))
# 'x4s' (default) or a full-pool deck spec (bot/fullpool/banks.py), e.g. BOT_RL_DECKS='fullpool:11433651'. In
# full-pool mode the opponent deck is C56 whenever the league opponent is a search player (R.bots is C56).
RL_DECKS = os.environ.get('BOT_RL_DECKS', 'x4s')
_LEAGUE0 = (('v1', .30), ('R3a', .25), ('it5s2', .20), ('self', .15), ('K4C-r16', .10))
# Optional player spec per league name, 'name=spec|name=spec' (e.g. 'f1a2=student:<ckpt>@0.5375'); names without one
# are HEADLINE player names. 'LIVE-K4CW-r16-fp' is built by bot.livediag.k4cw_fp with fast tier BOT_RL_K4CW_FAST.
LEAGUE_SPECS = dict(t.split('=', 1) for t in os.environ.get('BOT_RL_LEAGUE_SPECS', '').split('|') if t)
K4CW_FAST = os.environ.get('BOT_RL_K4CW_FAST', '')


def _envs(spec):
    """BOT_RL_ENVS='engine;levels;decks@share|...' (engine ours|rsim16402, levels none|max): a per-game mixture of
    match environments, picked by a hash of g. Unset = one environment ('ours', 'none', BOT_RL_DECKS), as before."""
    if not spec:
        return (('ours', 'none', RL_DECKS, 1.),)
    out = []
    for t in spec.split('|'):
        body, share = t.rsplit('@', 1)
        engine, levels, decks = body.split(';', 2)
        if engine not in ('ours', 'rsim16402') or levels not in ('none', 'max') or not decks:
            raise ValueError(f'BOT_RL_ENVS entry {t!r}')
        share = float(share)
        if not (math.isfinite(share) and share >= 0):
            raise ValueError(f'BOT_RL_ENVS entry {t!r}: share must be finite and >= 0')
        out.append((engine, levels, decks, share))
    if abs(sum(e[3] for e in out) - 1) > 1e-9 or len({e[:3] for e in out}) != len(out):
        raise ValueError('BOT_RL_ENVS needs distinct entries with shares summing to 1')
    return tuple(out)


ENVS = _envs(os.environ.get('BOT_RL_ENVS', ''))
RSIM_VOCAB = os.environ.get('BOT_RL_RSIM_VOCAB', '')   # RoyaleSim translator vocab json (default: the C56 vocab)
MAX_LEVEL = 16


def _league(spec, names_spec=''):
    """BOT_RL_LEAGUE='v1:.15,R3a:.35,...' changes the shares only; names and their order (= critic opponent ids)
    stay those of _LEAGUE0. BOT_RL_LEAGUE_NAMES='v1:.15,...,LIVE-K4CW-r16:.10' (new runs only) sets the names, order
    and shares itself: any HEADLINE player name, plus 'it5s2' / 'self' as below."""
    if names_spec:
        league = tuple((n, float(v)) for n, v in (t.rsplit(':', 1) for t in names_spec.split(',')))
        if abs(sum(v for _, v in league) - 1) > 1e-9 or len({n for n, _ in league}) != len(league):
            raise ValueError('BOT_RL_LEAGUE_NAMES needs distinct names with shares summing to 1')
        return league
    if not spec:
        return _LEAGUE0
    shares = {k: float(v) for k, v in (t.split(':') for t in spec.split(','))}
    if set(shares) != {n for n, _ in _LEAGUE0} or abs(sum(shares.values()) - 1) > 1e-9:
        raise ValueError(f'BOT_RL_LEAGUE must give shares summing to 1 for exactly {[n for n, _ in _LEAGUE0]}')
    return tuple((n, shares[n]) for n, _ in _LEAGUE0)


LEAGUE = _league(os.environ.get('BOT_RL_LEAGUE', ''), os.environ.get('BOT_RL_LEAGUE_NAMES', ''))
OPP_IDS = {name: i for i, (name, _) in enumerate(LEAGUE)}
TOKEN_KEYS = ('ids', 'types', 'numeric', 'valid')


def check_bank(bank):
    assert bank > 0, 'set BOT_RL_BANK'
    from bot.fullpool.banks import reserved_eval_banks
    for base, span in (HEADLINE, TRAIN1) + tuple(reserved_eval_banks()):
        assert not (base - 10**9 < bank < base + span + 10**9), f'RL bank overlaps {base}'


def league_pick(g):
    u = int.from_bytes(hashlib.sha256(f'bot-rl-league|{g}'.encode()).digest()[:8], 'big') / 2**64
    acc = 0.
    for name, share in LEAGUE:
        acc += share
        if u < acc:
            return name, u
    return LEAGUE[-1][0], u


def env_pick(g):
    """(engine, levels, decks) of game g; independent of the league draw (own hash salt)."""
    if len(ENVS) == 1:
        return ENVS[0][:3]
    u = int.from_bytes(hashlib.sha256(f'bot-rl-env|{g}'.encode()).digest()[:8], 'big') / 2**64
    acc = 0.
    for e in ENVS:
        acc += e[3]
        if u < acc:
            return e[:3]
    return ENVS[-1][:3]


def make_opponent(rt, spec):
    from bot.eval.headline import make_player
    if spec == 'LIVE-K4CW-r16-fp':
        from bot.livediag.k4cw_fp import make_k4cw_fp
        if not K4CW_FAST:
            raise ValueError('LIVE-K4CW-r16-fp needs BOT_RL_K4CW_FAST (its fast-tier student spec)')
        return make_k4cw_fp(rt, K4CW_FAST)
    return make_player(rt, spec)


class RLPolicy:
    """Drop-in for s1 CachedPolicy inside V1Policy/StandalonePlayer: one forward per poll.

    deploy mode reproduces CachedPolicy(threshold) exactly; explore mode samples bot.rl.dist and keeps the
    poll's record in .last (features, sampled action, behaviour log-prob) for the player to keep or drop.
    """

    def __init__(self, base, tau, kappa=.5, temp=1., explore=True, generator=None):
        self.base, self.model, self.costs = base, base.model, base.costs
        self.tau, self.kappa, self.temp, self.explore = float(tau), float(kappa), float(temp), explore
        self.gen = generator
        self.last = None

    def sample(self, packet, d1, generator=None):
        import torch
        from imitation.model.inference import single_features
        from proposals import rank_actions
        from bot.rl import dist
        with torch.inference_mode():
            b = single_features(packet, d1, self.costs)
            raw = dist.forward(self.model, b)
            prob = dist.masked_log_softmax(raw['gate'], raw['gate_mask']).exp()[:, 1]
            card = dist.masked_log_softmax(raw['card'], raw['card_mask'])
            tile = dist.masked_log_softmax(raw['tile'], raw['tile_mask'])
            order = rank_actions((card[:, :, None] + tile).flatten(1)[0].numpy(), packet['action_mask'])
            deploy = int(order[0]) if len(order) and float(prob[0]) >= self.tau else 2304
            self.last = None
            if not self.explore or not len(order):
                return deploy
            d = dist.explore(raw, self.tau, self.kappa, self.temp)
            q = float(torch.sigmoid(d['z'][0]))
            play = bool(torch.rand((), generator=self.gen) < q)
            slot = tl = 0
            action = 2304
            if play:
                slot = int(torch.multinomial(d['card'][0].exp(), 1, generator=self.gen))
                tl = int(torch.multinomial(d['tile'][0, slot].exp(), 1, generator=self.gen))
                action = slot * 576 + tl
            lp = float(dist.log_prob(d, torch.tensor([play]), torch.tensor([slot]), torch.tensor([tl]))[0])
            self.last = dict(b={k: v[0].numpy().copy() for k, v in b.items()}, play=play, slot=slot, tile=tl,
                             logp=lp, p_play=float(prob[0]), q=q, deploy=deploy, action=action)
            return action


class RLPlayer:
    deadline_seconds = None

    def __init__(self, rt, base, tau, kappa, temp, explore, salt, name='rl'):
        self.rt, self.base, self.tau, self.kappa, self.temp = rt, base, tau, kappa, temp
        self.explore, self.salt, self.name = explore, salt, name
        self.records = []

    def start(self, ctx):
        import torch
        from policy import V1Policy
        from bot.players.policy import POLICY_SEED_OFFSET
        seed = int.from_bytes(hashlib.sha256(f'bot-rl-explore|{self.salt}|{ctx.seed}|{ctx.seat}'.encode())
                              .digest()[:8], 'big') >> 1
        self.rl = RLPolicy(self.base, self.tau, self.kappa, self.temp, self.explore,
                           torch.Generator().manual_seed(seed))
        self.poller = V1Policy(self.rl, self.rt.R.builder, self.rt.R.costs, ctx.seat, list(ctx.own_order),
                               ctx.seed + POLICY_SEED_OFFSET + ctx.seat)
        self.records = []

    def act(self, view):
        from bot.players.base import Decision, WAIT
        action = int(self.poller.poll(view.tick, view.reserved.packet, view.public_events))
        rec, self.rl.last = self.rl.last, None
        if rec is not None and view.can_act:
            rec['tick'] = view.tick
            self.records.append(rec)
        return Decision(action if action < WAIT else WAIT)

    def close(self):
        pass


def pack_records(records):
    """Ragged token arrays flattened with per-row counts; fixed-shape arrays stacked."""
    out = {}
    keys = records[0]['b'].keys()
    for k in keys:
        if k in TOKEN_KEYS:
            out['b_' + k] = np.concatenate([r['b'][k] for r in records], 0)
        else:
            out['b_' + k] = np.stack([r['b'][k] for r in records], 0)
    out['ntok'] = np.array([len(r['b']['ids']) for r in records], np.int32)
    for k, dt in (('play', bool), ('slot', np.int16), ('tile', np.int16), ('logp', np.float32),
                  ('p_play', np.float32), ('q', np.float32), ('deploy', np.int16), ('action', np.int16),
                  ('tick', np.int32)):
        out[k] = np.array([r[k] for r in records], dt)
    return out


def read_latest(run):
    p = run / 'policies' / 'LATEST'
    v, path = p.read_text().split()
    return int(v), path


def worker(w, a):
    os.environ.setdefault('PYTHONHASHSEED', '0')
    import torch
    torch.set_num_threads(1)
    from bot.players.runtime import Runtime
    from bot.players.ours import play_match
    from bot.exit import student as student_mod
    from bot.fullpool.banks import case as make_case, check_scope, select
    from bot.fullpool.models import install_from_env
    from bot.levels.match import max_levels
    rt = Runtime()
    install_from_env(rt)        # BOT_FULLPOOL_POLICIES (extended v1/R3a); unset = no-op
    belief = set()
    for _, _, decks in (e[:3] for e in ENVS):   # every environment must give the search players the same belief prior
        select(rt, decks)
        belief.add(getattr(rt, 'belief_prior', None))
        check_scope(rt, decks, 50, 0, RL_BANK)
    if len(belief) != 1:
        raise ValueError(f'BOT_RL_ENVS deck specs imply different belief priors {sorted(map(str, belief))}')
    vocab = None
    if any(e[0] != 'ours' for e in ENVS):
        from bot.players.royalesim_match import play_match as rsim_play_match
        if RSIM_VOCAB:
            vocab = json.loads(Path(RSIM_VOCAB).read_text())
        else:
            from bot.players.royalesim_vocab import load
            vocab = load(rt)
    from proposals import load_student
    run = a.run
    out = run / 'rollouts'
    summary = open(out / f'games-b{a.block}-w{w:03d}.jsonl', 'a', buffering=1)
    version, base = -1, None
    k = 0
    while not (run / 'STOP_ACTORS').exists():
        # back-pressure: do not run far ahead of the learner
        while len(list(out.glob('v*.npz'))) > a.max_backlog and not (run / 'STOP_ACTORS').exists():
            time.sleep(15)
        try:
            v, path = read_latest(run)
        except FileNotFoundError:       # fresh remote mirror before its first pointer: wait for the sync
            time.sleep(5)
            continue
        if v != version:
            try:
                base = load_student(path, TAU0)
            except FileNotFoundError:   # a pointer synced ahead of its file (remote hosts): keep the old policy
                if base is None:
                    time.sleep(5)
                    continue
                v = version             # this game is played (and labelled) by the policy actually loaded
            else:
                version = v
        g = a.block * 10**6 + k * a.workers + w
        k += 1
        if a.max_games and k > a.max_games:
            break
        opp, _ = league_pick(g)
        engine, levels, decks = env_pick(g)
        case = make_case(rt, g, RL_BANK, decks, opp_c56=OPP_C56 and opp.startswith(('K4', 'LIVE-K4')))   # 'x4s' -> x4s_setup(g, RL_BANK)
        opp_spec = LEAGUE_SPECS.get(opp, opp)
        if opp == 'it5s2':
            opp_spec = f'student:{IT5S2}@{TAU0}'
        elif opp == 'self':
            snaps = [s for s in (run / 'snapshots' / 'LIST').read_text().split()] if (run / 'snapshots' / 'LIST').exists() else []
            snap = snaps[int(hashlib.sha256(f'bot-rl-snap|{g}'.encode()).hexdigest(), 16) % len(snaps)] if snaps else SELF0
            opp_spec = f'student:{snap}@{TAU0}'
        # keep the per-process student cache to the models in use (snapshots would otherwise accumulate)
        keep = {str(Path(IT5S2).resolve()), str(Path(SELF0).resolve())}
        for s in [opp_spec, K4CW_FAST, *LEAGUE_SPECS.values()]:
            if s.startswith('student:'):
                keep.add(str(Path(s.split(':', 1)[1].rsplit('@', 1)[0]).resolve()))
        for key in list(student_mod._POLICIES):
            if key[0] not in keep:
                student_mod._POLICIES.pop(key)
        t0 = time.time()
        try:
            me = RLPlayer(rt, base, TAU0, a.kappa, a.temp, True, salt=f'{a.block}|{v}', name=f'rl-v{v}')
            players = {case['seat']: me, 1 - case['seat']: make_opponent(rt, opp_spec)}
            if engine == 'ours':
                lv = {} if levels == 'none' else dict(levels=dict(max_levels(MAX_LEVEL),   # as bot.eval.headline
                                                                  planner=os.environ.get('BOT_LEVEL_PLANNER', 'exact')))
                res = play_match(rt, players, seed=case['seed'], decks=case['decks'], **lv)
            else:
                lv = {} if levels == 'none' else dict(levels=[{c: MAX_LEVEL for c in d} for d in case['decks']],
                                                      tower_levels=[MAX_LEVEL, MAX_LEVEL])
                res = rsim_play_match(rt, players, seed=case['seed'], decks=case['decks'], vocab=vocab,
                                      client='16.402', **lv)
            # RoyaleSim: a card the translator vocab cannot map is silently dropped from the public rows, so the game
            # is not the one either player saw; record it as an error and keep no rollout (PF1's unmapped rule)
            unmapped = {k: v for k, v in (res.get('translator') or {}).items()
                        if v and ('unmapped' in k or 'missing' in k or k.startswith('no_template'))}
            if unmapped:
                raise ValueError(f'unmapped public rows {json.dumps(unmapped, default=str)[:300]} decks {case["decks"]}')
            wnr = res['winner']
            outcome = 0 if wnr is None or wnr == -1 else (1 if wnr == case['seat'] else -1)
            row = dict(g=g, version=v, opponent=opp, opponent_spec=opp_spec, seat=case['seat'], seed=case['seed'],
                       outcome=outcome, ticks=res['ticks'], towers=res['towers'], plays=res['plays'][case['seat']],
                       opp_plays=res['plays'][1 - case['seat']], decisions=len(me.records),
                       explore_plays=int(sum(r['play'] for r in me.records)),
                       deploy_plays=int(sum(r['deploy'] < 2304 for r in me.records)),
                       disagree=float(np.mean([r['action'] != r['deploy'] for r in me.records])) if me.records else 0.,
                       cpu_seconds=res['cpu_seconds'], wall_seconds=time.time() - t0, worker=w, block=a.block,
                       kappa=a.kappa, temp=a.temp, tau0=TAU0, engine=engine, levels=levels)
            if decks != 'x4s':
                row.update(decks=decks, deck_lists=case['decks'])
            if me.records:
                arrays = pack_records(me.records)
                arrays['meta'] = np.frombuffer(json.dumps(row).encode(), np.uint8)
                tmp = out / f'.v{v:05d}-g{g}.npz.partial'
                with open(tmp, 'wb') as fh:
                    np.savez_compressed(fh, **arrays)
                os.replace(tmp, out / f'v{v:05d}-g{g}.npz')
        except Exception as ex:  # recorded, never silently dropped
            import traceback
            row = dict(g=g, version=v, opponent=opp, engine=engine, decks=decks, error=repr(ex)[:500],
                       tb=traceback.format_exc()[-1500:])
        summary.write(json.dumps(row) + '\n')


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--run', required=True, type=Path)
    ap.add_argument('--workers', type=int, default=48)
    ap.add_argument('--block', type=int, required=True, help='game-index block; never reuse one')
    ap.add_argument('--kappa', type=float, default=.1)
    ap.add_argument('--temp', type=float, default=.1)
    ap.add_argument('--max-backlog', type=int, default=600)
    ap.add_argument('--max-games', type=int, default=0, help='per worker; 0 = until STOP_ACTORS')
    a = ap.parse_args(argv)
    check_bank(RL_BANK)
    (a.run / 'rollouts').mkdir(parents=True, exist_ok=True)
    blocks = a.run / 'rollouts' / 'BLOCKS'
    used = blocks.read_text().split() if blocks.exists() else []
    if str(a.block) in used:
        raise SystemExit(f'block {a.block} already used')
    with open(blocks, 'a') as fh:
        fh.write(f'{a.block}\n')
    (a.run / f'actor-b{a.block}.json').write_text(json.dumps(dict(
        args={k: str(v) for k, v in vars(a).items()}, bank=RL_BANK, decks=RL_DECKS, league=LEAGUE, pid=os.getpid(),
        tau0=TAU0, envs=ENVS, league_specs=LEAGUE_SPECS, k4cw_fast=K4CW_FAST, rsim_vocab=RSIM_VOCAB,
        started=time.time())))
    from multiprocessing import Process
    from bot.eval.headline import reap
    procs = [Process(target=worker, args=(w, a)) for w in range(a.workers)]
    for p in procs:
        p.start()
    reap(procs)
    bad = [p.exitcode for p in procs if p.exitcode]   # a crashed worker must fail the job (wrappers log rc)
    if bad:
        raise SystemExit(f'{len(bad)} worker process(es) failed, exit codes {bad[:8]}')


if __name__ == '__main__':
    main()
