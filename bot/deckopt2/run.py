"""Exploration deck evaluation. All mutations and results stay in the specified job directory.

prepare: freeze population, real own levels, candidates and an urandom screening bank.
run: fork isolated games (paired across candidates/players), partition by stable job index.
select: require a complete clean screen, freeze two finalists, THEN draw a fresh validation bank.
report: paired within-policy bootstrap; screen and validation never combined.
"""
from __future__ import annotations
import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import time
import traceback

REPO = Path(__file__).resolve().parents[2]
PLAYERS = ('LD-K4L-R-gs-rw', 'LD-K4L-R-gs-rw-res')
OPPONENTS = ('R3a', 'v1', 'LIVE-K4CW-r16', 'rext-bc')
GROUPS = {'weak pool': ('R3a', 'v1'), 'strong opponent': ('LIVE-K4CW-r16',), 'rext-bc': ('rext-bc',), 'pooled': OPPONENTS}


def utc():
    return subprocess.check_output(['date', '-u', '+%Y-%m-%dT%H:%M:%SZ'], text=True).strip()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, data, exclusive=False):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        with path.open('x') as f:
            json.dump(data, f, indent=2, sort_keys=True)
        return
    tmp = path.with_suffix('.tmp.' + str(os.getpid()))
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    tmp.replace(path)


def bootstrap_data(rows):
    # Count observed levels as a population only; never retain the sampled log row's levels in a case.
    counts = Counter(lv for r in rows for lv in r.get('opp_levels', []) if lv is not None)
    assert counts
    return sorted(counts.items())


def bank(root, rt, meta, stage, n, names):
    from bot.levels.profile import rarity, clamp, RARE_OFFSET
    path = root / stage / 'bank.json'
    assert not path.exists(), f'refusing to replace {path}'
    entropy = os.urandom(16).hex()
    rng = random.Random(int(entropy, 16))
    levels, weights = zip(*meta['opponent_common_prior'])
    cases = []
    for oi, opponent in enumerate(OPPONENTS):
        for i in range(n):
            seed = rng.randrange(1 << 48)
            case_rng = random.Random(seed)
            source_index = case_rng.randrange(len(meta['population']))
            population = meta['population'][source_index]
            deck = list(population['projected_deck'])
            case_rng.shuffle(deck)
            order = list(range(8))
            case_rng.shuffle(order)
            lrng = random.Random(seed ^ 0x1E7E1)
            opp_levels = {c: clamp(rarity(rt, c), lrng.choices(levels, weights=weights)[0] - RARE_OFFSET.get(rarity(rt, c), 1)) for c in deck}
            cases.append(dict(id=f'{oi}-{i:04d}', opponent=opponent, index=i, seed=seed,
                              seat=i % 2, source_index=source_index, opponent_deck=deck,
                              opponent_levels=opp_levels, own_permutation=order))
    data = dict(stage=stage, created_utc=utc(), entropy_hex=entropy, cases=cases, candidates=names,
                players=PLAYERS, cases_per_policy=n, own_levels=meta['own_levels'], own_tower=meta['own_tower'],
                collection_sha256=meta['collection_sha256'], manifest_sha256=sha(root/'manifest.json'))
    if stage == 'validation':
        old = json.loads((root/'screen/bank.json').read_text())
        assert not {c['seed'] for c in cases} & {c['seed'] for c in old['cases']}
        data['selection_sha256'] = sha(root/'selection.json')
    dump(path, data, exclusive=True)
    print(f'{stage} bank {sha(path)} created {data["created_utc"]}, {len(cases)} cases', flush=True)


def prepare(root, rt, args):
    from bot.fullpool.cards import C56, engine_name
    from bot.levels.bank import project
    collection = json.loads((root/'collection.json').read_text())
    assert sha(root/'collection.json').startswith('294eaf5b')
    assert sha(root/'opponent-decks.jsonl').startswith('3a7c4e78')
    rows = [json.loads(x) for x in (root/'opponent-decks.jsonl').read_text().splitlines()]
    assert len(rows) == 91
    old = json.loads((root/'prior-search-manifest.json').read_text())
    candidates = {n: old['candidates'][n]['cards'] for n in old['active_candidates']}
    own = {engine_name(c): int(v['level']) for c, v in collection.items()}
    for deck in candidates.values():
        assert len(set(deck)) == len(deck) == 8
        assert set(deck) <= set(own) & set(C56)
    catalog = [d for d in rt.PRIOR['decks'] if set(d['cards']) <= set(C56)]
    population = []
    for r in rows:
        d, overlap = project(r['opp_deck'], catalog)
        population.append(dict(run=r['run'], original_deck=r['opp_deck'], projected_deck=d, overlap=overlap,
                               opp_trophies=r['opp_trophies'], arena=r['arena']))
    meta = dict(created_utc=utc(), source_commit=args.source_commit, card_scope=args.card_scope,
                candidates=candidates, own_levels=own, own_tower=6, opponent_tower=6,
                collection_sha256=sha(root/'collection.json'), population_sha256=sha(root/'opponent-decks.jsonl'),
                opponent_common_prior=bootstrap_data(rows), population=population,
                planner='deployed all-L11 planning, unmodified LD live twins; no ExactLevelRoot',
                pins=rt.pins, runtime=str(rt.root), runtime_pin=os.environ['CLASHER_BOT_RUNTIME_PINS'],
                source_sha256=source_hashes(), simulator=sim_identity(),
                environment={k: os.environ.get(k) for k in ('PYTHONHASHSEED','NUMPY_MADVISE_HUGEPAGE','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')})
    if args.engine != 'rsim16402':
        meta['engine'] = args.engine
    dump(root/'manifest.json', meta, exclusive=True)
    bank(root, rt, meta, 'screen', args.n, list(candidates))


def source_hashes():
    return {str(p.relative_to(REPO)): sha(p) for folder in ('bot', 'reports/explore/x4s')
            for p in sorted((REPO/folder).rglob('*.py'))}


def sim_identity():
    from bot.levels.placement_probe import installed_identity
    return installed_identity()


def install_compat(rt):
    """Existing public static placement adapter, installed on each actual policy poller.

    Wrap the canonical V1Policy constructor so the LivePlayer fast and search pollers,
    strong search and standalone policies all receive the same simulator compatibility.
    No planner roots, belief, candidate scores or oracle masks change.
    """
    from bot.levels.placement import install_runtime, _wrap
    install_runtime(rt)
    from policy import V1Policy
    if getattr(V1Policy, '_deckopt_placement', False):
        return
    original = V1Policy.__init__
    def init(self, *args, **kw):
        original(self, *args, **kw)
        _wrap(self.player, rt.R.builder)
    V1Policy.__init__ = init
    V1Policy._deckopt_placement = True


def game(rt, vocab, root, stage, meta, case, candidate, player_name, out):
    from bot.eval.headline import make_player
    from bot.livediag.variants import make_variant
    from bot.players.royalesim_match import play_match
    from bot.search.lopp import FAILURES
    started = time.monotonic()
    row = dict(case, stage=stage, candidate=candidate, player=player_name, host=os.uname().nodename,
               started_utc=utc(), bank_sha256=sha(root/stage/'bank.json'))
    players = {}
    try:
        own = [meta['candidates'][candidate][i] for i in case['own_permutation']]
        seat = case['seat']
        decks = [own, case['opponent_deck']] if seat == 0 else [case['opponent_deck'], own]
        own_levels = {c: meta['own_levels'][c] for c in own}
        levels = [own_levels, case['opponent_levels']] if seat == 0 else [case['opponent_levels'], own_levels]
        player = make_variant(rt, player_name)
        opponent = make_player(rt, case['opponent'])
        if case['opponent'] == 'rext-bc':
            opponent.evaluation_clients = ('15.535.29', '16.402')
        players = {seat: player, 1-seat: opponent}
        assert all(p.deadline_seconds is None for p in players.values())
        before = Counter(FAILURES)
        towers = [meta['own_tower'] if s == seat else meta['opponent_tower'] for s in (0,1)]
        if meta.get('engine', 'rsim16402') == 'ours':
            # Our engine at the same true levels (bot/levels/match.py); planners stay all-L11 as on RoyaleSim.
            from bot.players.ours import play_match as ours_match
            from bot.levels.match import from_lists
            result = ours_match(rt, players, seed=case['seed'], decks=decks, verbose=True,
                                levels=from_lists(levels, towers, planner='l11'))
        else:
            result = play_match(rt, players, seed=case['seed'], decks=decks, vocab=vocab, client='16.402',
                                verbose=True, levels=levels, tower_levels=towers)
        logs = result.pop('play_log')
        result.pop('command_events', None)
        row.update(result=result, win=int(result['winner']==seat), draw=int(result['winner'] is None),
                   score=.5 if result['winner'] is None else float(result['winner']==seat),
                   card_plays=dict(Counter(c for _,c,_,ok in logs[seat] if ok)), failures=dict(Counter(FAILURES)-before))
        row['live_errors'] = {s: [d for d in getattr(p,'decisions',[]) if 'error' in d or d.get('native_failures')] for s,p in players.items()}
        issues = []
        if not result['terminal']: issues.append('nonterminal')
        if row['failures']: issues.append('native failures')
        if any(row['live_errors'].values()): issues.append('live errors')
        if any(c['rejected'] for c in result['channels'].values()): issues.append('command rejections')
        row['issues'] = issues
    except BaseException as ex:
        row.update(error=repr(ex), traceback=traceback.format_exc())
    row['wall_seconds'] = time.monotonic()-started
    dump(out, row)


def jobs_for(data):
    return [(c,n,p) for c in data['cases'] for n in data['candidates'] for p in data['players']]


def run(root, rt, args):
    from bot.players.royalesim_vocab import load
    meta = json.loads((root/'manifest.json').read_text())
    assert meta['source_sha256'] == source_hashes(), 'source changed'
    assert meta['pins'] == json.loads(json.dumps(rt.pins)), 'planning runtime pins changed'
    assert meta['simulator'] == sim_identity(), 'simulator identity changed'
    data = json.loads((root/args.stage/'bank.json').read_text())
    meta = dict(meta, own_levels=data['own_levels'], own_tower=data['own_tower'])
    install_compat(rt)
    vocab = load(rt)
    # Preload common weights before any fork.
    rt.STUDENT
    from bot.live.player import load_fast
    load_fast(rt)
    selected = [(i,j) for i,j in enumerate(jobs_for(data)) if i % args.shards == args.shard]
    active = {}
    def path(i): return root/args.stage/'rows'/f'{i:06d}.json'
    for i, job in selected:
        dest = path(i)
        if dest.exists():
            old = json.loads(dest.read_text())
            assert 'error' not in old and not old.get('issues'), f'failed row must be investigated: {dest}'
            assert old['bank_sha256'] == sha(root/args.stage/'bank.json')
            continue
        while len(active) >= args.workers:
            pid,status = os.wait()
            finished = active.pop(pid)
            if status or not path(finished).exists(): raise RuntimeError(f'child failed: {finished}: {status}')
            result = json.loads(path(finished).read_text())
            if 'error' in result or result.get('issues'): raise RuntimeError(f'unclean row: {finished}: {result}')
        if (root/'STOP').exists(): raise RuntimeError('operator STOP')
        pid = os.fork()
        if pid == 0:
            try:
                game(rt,vocab,root,args.stage,meta,*job,dest)
            finally:
                os._exit(0)
        active[pid] = i
    while active:
        pid,status = os.wait()
        i = active.pop(pid)
        assert status == 0 and path(i).exists()
        row = json.loads(path(i).read_text())
        assert 'error' not in row and not row.get('issues'), row
    dump(root/args.stage/f'finished-{args.shard}.json',dict(utc=utc(), jobs=len(selected)))


def read_rows(root, stage, complete=False):
    data = json.loads((root/stage/'bank.json').read_text())
    rows = [json.loads(p.read_text()) for p in sorted((root/stage/'rows').glob('*.json'))]
    assert all('error' not in r and not r.get('issues') for r in rows), 'unclean rows'
    if complete: assert len(rows)==len(jobs_for(data)), (len(rows), len(jobs_for(data)))
    keys = [(r['id'],r['candidate'],r['player']) for r in rows]
    assert len(keys)==len(set(keys))
    return data, rows


def summarize(root, stage, complete=False):
    import numpy as np
    data, rows = read_rows(root,stage,complete)
    lookup={(r['id'],r['candidate'],r['player']):r for r in rows}
    summaries=[]
    for p in PLAYERS:
        for n in data['candidates']:
            for group,opps in GROUPS.items():
                rng=np.random.default_rng(0)
                bmeans=[]; cmeans=[]; sizes=[]; wins=basewins=draws=0
                for opp in opps:
                    cases=[c for c in data['cases'] if c['opponent']==opp and
                           (c['id'],n,p) in lookup and (c['id'],'baseline',p) in lookup]
                    if not cases: continue
                    a=np.array([lookup[c['id'],n,p]['win'] for c in cases],dtype=float)
                    b=np.array([lookup[c['id'],'baseline',p]['win'] for c in cases],dtype=float)
                    ix=rng.integers(0,len(cases),(20000,len(cases)))
                    cmeans.append(a[ix].mean(1)); bmeans.append(b[ix].mean(1)); sizes.append(len(cases))
                    wins+=int(a.sum()); basewins+=int(b.sum())
                    draws+=sum(lookup[c['id'],n,p]['draw'] for c in cases)
                if not sizes: continue
                cs=np.average(cmeans,axis=0,weights=sizes); bs=np.average(bmeans,axis=0,weights=sizes)
                total=sum(sizes)
                summaries.append(dict(player=p,candidate=n,group=group,n=total,wins=wins,draws=draws,
                                      win_rate=wins/total,baseline_win_rate=basewins/total,delta=(wins-basewins)/total,
                                      delta_ci=np.quantile(cs-bs,[.025,.975]).tolist(),win_ci=np.quantile(cs,[.025,.975]).tolist()))
    dump(root/stage/'summary.json',summaries)
    return summaries


def select(root,rt,args):
    summary=summarize(root,'screen',True)
    data=json.loads((root/'screen/bank.json').read_text())
    ranking=[]
    for n in data['candidates']:
        if n=='baseline': continue
        rows=[r for r in summary if r['candidate']==n and r['group']=='pooled']
        ranking.append((sum(r['delta'] for r in rows)/len(rows),n))
    ranking.sort(reverse=True)
    import numpy as np
    _, screen_rows=read_rows(root,'screen',True)
    lookup={(r['id'],r['candidate'],r['player']):r['win'] for r in screen_rows}
    second,third=ranking[1][1],ranking[2][1]
    differences=np.array([sum(lookup[c['id'],second,p]-lookup[c['id'],third,p] for p in PLAYERS)/len(PLAYERS)
                          for c in data['cases']])
    boundary_se=float(differences.std(ddof=1)/np.sqrt(len(differences)))
    take=3 if ranking[1][0]-ranking[2][0] <= boundary_se else 2
    names=['baseline']+[n for _,n in ranking[:take]]
    dump(root/'selection.json',dict(created_utc=utc(),rule='top2 mean pooled delta; also top3 if third within1SE of second; casecluster across players; no validation outcomes',
                                  boundary_se=boundary_se,ranking=ranking,selected=names,screen_bank_sha256=sha(root/'screen/bank.json')),exclusive=True)
    meta=json.loads((root/'manifest.json').read_text())
    if args.validation_collection is not None:
        from bot.fullpool.cards import engine_name
        collection=json.loads(args.validation_collection.read_text())
        own={engine_name(c):int(v['level']) for c,v in collection.items()}
        assert all(set(meta['candidates'][n]) <= set(own) for n in names)
        meta=dict(meta,own_levels=own,collection_sha256=sha(args.validation_collection))
    meta['own_tower']=args.tower_level
    bank(root,rt,meta,'validation',150,names)


def report(root,args):
    meta=json.loads((root/'manifest.json').read_text())
    sections=['# Real-level paired deck search\n',f'Updated {utc()}. Exploration; current live deck is baseline.\n',
              'Planner: deployed LD twins, all-L11 planning assumption, live belief; no ExactLevelRoot B. Truth: RoyaleSim16.402, actual owned card levels, tower6/6 (account King scenario from levels pilot; BOT LEAD confirmation pending). Opponent true levels are independent population draws; never passed to planners.\n',
              f'Runtime `{meta["runtime_pin"]}`, native SHA `{meta["pins"]["native_sha256"]}`. Simulator SHA `{meta["simulator"]["binary_sha256"]}`.\n',
              'Population: all91 Battle Log rows uniformly sampled, nearest C56 catalog by overlap/frequency/literal tuple; projected deck and opening shuffled independently of the source row. Level prior: all observed common levels, with rare/epic offset1 and rarity floors from bot.levels.profile. These are population assumptions, never per-match log truth.\n',
              f'Collection SHA `{meta["collection_sha256"]}`. Opponent population SHA `{meta["population_sha256"]}`.\n',
              'rext-bc is INTERNAL EVAL ONLY. Explicit balance transfer from its15.535 training to16.402 truth; frozen old observation normalization/weights. All players share existing simulator static placement compatibility. Our planning remains all11; this is not an eval of level-aware search. No wall deadline on deterministic twins; no claim of live wall200 latency equivalence.\n']
    for stage in ('screen','validation'):
        if not (root/stage/'bank.json').exists():
            sections.append(f'## {stage}\n\nNot started. No validation claim.\n'); continue
        data, rows=read_rows(root,stage)
        expected=len(jobs_for(data))
        summary=summarize(root,stage)
        sections.append(f'## {stage}\n\n{len(rows)}/{expected} clean rows; bank created{data["created_utc"]}, SHA `{sha(root/stage/"bank.json")}`.\n')
        sections.append(f'Own levels: {data["own_levels"]}; King {data["own_tower"]}; collection SHA `{data["collection_sha256"]}`.\n')
        sections.append('|Player|Deck|Group|Paired n|Win%|Baseline%|Δ pp [95% CI]|\n|---|---|---|---:|---:|---:|---|')
        for r in summary:
            sections.append(f'|{r["player"]}|{r["candidate"]}|{r["group"]}|{r["n"]}|{100*r["win_rate"]:.1f}|{100*r["baseline_win_rate"]:.1f}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|')
        if len(rows)<expected: sections.append('\nINCOMPLETE: no deck recommendation.\n')
    sections.append('\n## Candidate levels\n')
    for n,d in meta['candidates'].items():
        sections.append(f'- {n}: '+', '.join(f'{c} L{meta["own_levels"][c]}' for c in d))
    sections.append('\nLevel risk: Arrows L1, Goblins L1, Knight L3; simulated at these levels. Projection bias, opponent rarity assumption and frozen learned level features remain outside bootstrap intervals.\n\nActual wins primary (draws nonwins), draws retained. 20,000 percentile paired bootstrap replicates resample same cases for baseline/candidate within each policy. Pooled mixture is equal policy weights (weak group gets two policies). Pointwise CIs, selection handled by fresh independent validation; no screen outcomes enter validation. Recommend only with positive pooled lowerCI and nonnegative strong estimate for bothplayers; a negative strong CI lowerbound remains inconclusive safety evidence.\n')
    (root/'REPORT.md').write_text('\n'.join(sections)+'\n')


def main():
    a=argparse.ArgumentParser()
    a.add_argument('command',choices=['prepare','run','select','report'])
    a.add_argument('--root',type=Path,required=True)
    a.add_argument('--stage',choices=['screen','validation'],default='screen')
    a.add_argument('--workers',type=int,default=8)
    a.add_argument('--shard',type=int,default=0)
    a.add_argument('--shards',type=int,default=4)
    a.add_argument('--n',type=int,default=16)
    a.add_argument('--card-scope',choices=['c56'],default='c56',help='full pool later requires live16402b-r3 and fresh bank')
    a.add_argument('--source-commit',default='c04196523')
    a.add_argument('--validation-collection',type=Path)
    a.add_argument('--tower-level',type=int,default=6)
    a.add_argument('--engine',choices=['rsim16402','ours'],default='rsim16402',
                   help="true game: RoyaleSim 16.402 (default) or our engine at the same levels (bot/levels/match.py)")
    args=a.parse_args()
    assert os.environ['PYTHONHASHSEED']=='0' and os.environ['NUMPY_MADVISE_HUGEPAGE']=='0'
    assert 1<=args.workers<=40 and 0<=args.shard<args.shards
    if args.command=='report': report(args.root,args); return
    from bot.players.runtime import Runtime
    rt=Runtime()
    if args.command=='prepare': prepare(args.root,rt,args)
    if args.command=='run': run(args.root,rt,args)
    if args.command=='select': select(args.root,rt,args)

if __name__=='__main__': main()
