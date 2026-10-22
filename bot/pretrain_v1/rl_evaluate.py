"""Snapshot DEV/audit and paired final-versus-BC evaluation in the pinned engine.

Every assigned case gets one attempt. Raw failures remain in the denominator;
only true terminal, identity-valid results supply wins, draws or losses.
"""
from __future__ import annotations

import json
from pathlib import Path
import time

from . import rl_schedule as S


def paired_bootstrap(a, b, *, draws=20000, seed=2026102023):
    """The BC comparison's PCG64 case bootstrap and all-assigned bounds.

    Inputs are assigned-index maps with validated wins or missing observations.
    This endpoint uses wins, so a terminal draw contributes zero.
    """
    import numpy as np
    from .compare_arms import estimate
    S.require(set(a) == set(b) and bool(a), 'paired assignment mismatch')
    generator = np.random.Generator(np.random.PCG64(seed))
    result = dict(assigned=len(a), a_missing=sum(v is None for v in a.values()),
                  b_missing=sum(v is None for v in b.values()))
    for label, fa, fb in (('complete_pairs', None, None), ('all_assigned_lower', 0., 1.),
                          ('all_assigned_upper', 1., 0.)):
        diffs = []
        for key in sorted(a):
            x, y = a[key] if a[key] is not None else fa, b[key] if b[key] is not None else fb
            if x is not None and y is not None:
                diffs.append(x-y)
        if diffs:
            point, ci = estimate({'live': diffs}, ['live'], generator, draws)
            result[label] = dict(n=len(diffs), delta=point, ci95=ci)
        else:
            result[label] = dict(n=0, delta=None, ci95=None)
    cp, lower = result['complete_pairs'], result['all_assigned_lower']
    result['a_wins_by_registered_rule'] = bool(cp['ci95'] is not None and cp['ci95'][0] > 0 and lower['delta'] > 0)
    return result


def validate_result(row, case, *, policy, bank, runtime):
    """Require complete assignment and runtime identities before counting an outcome."""
    S.require(row['case'] == case and row['case_sha256'] == S.digest(case)
              and row['policy_sha256'] == policy and row['bank_sha256'] == bank
              and row['runtime_manifest'] == runtime, 'evaluation provenance mismatch')
    if row.get('error'):
        return None
    game = row['result']
    S.require(game['terminal'] is True and (game['winner'] is None or
              type(game['winner']) is int and game['winner'] in (0, 1)), 'nonterminal/invalid outcome')
    seat, winner = case['seat'], game['winner']
    S.require(game['seed'] == case['seed'] and game['decks'] == case['decks'], 'evaluation engine case mismatch')
    if 'levels' in case:
        expected = case['levels']
        actual = game['levels']
        S.require(actual['cards'] == [expected['cards'][str(s)] if str(s) in expected['cards']
                  else expected['cards'][s] for s in (0, 1)]
                  and actual['towers'] == expected['towers'], 'evaluation engine level mismatch')
    win = int(winner == seat) if winner is not None else 0
    draw = int(winner is None)
    S.require(row['win'] == win and row['draw'] == draw and row['score'] == win+.5*draw,
              'evaluation outcome mismatch')
    return win


def evaluate(config, out, rt):
    import torch
    from . import rl_driver as D, rl_coordinator as C, operational_rejections as O, stream_actor as A
    from .sim_ours import PolicyOursPlayer, bind_matches
    from .model import PolicyV1
    from . import probe_roots as P
    from bot.players.ours import play_match
    from bot.fullpool.models import install_from_env
    from bot.fullpool.banks import select
    D.guard()
    out = Path(out)
    S.require((out/'completed.json').exists(), 'successful full training finalization required')
    root = out/'evaluation'
    root.mkdir()  # Preserve failed attempts. No resume or retries.
    banks = S.validate_banks(json.loads(S.pinned(config['banks']).read_text()), config['seed'])
    for key, value in config['live']['environment'].items():
        import os
        os.environ[key] = value
    install_from_env(rt)
    select(rt, config['live']['belief_spec'])
    cfg = json.loads(S.pinned(config['model_cfg']).read_text())
    dtype = {'float32': torch.float32, 'float64': torch.float64}[config['precision']]
    model = PolicyV1(**cfg).to(dtype=dtype).eval()
    initial = torch.load(out/'checkpoints/update-00.pt', map_location='cpu', weights_only=False)
    model.load_state_dict(initial['model'], strict=True)
    opponents = D.Opponents(rt, model, config, out/'checkpoints')
    runtime = json.loads((out/'runtime.json').read_text())
    primary_scores, rejection_records, rejection_baselines = {}, {}, {}
    phases = [(f'dev-{v}', int(v), rows) for v, rows in banks['dev'].items()]
    phases += [('primary-bc', 0, banks['primary']), ('primary-final', 32, banks['primary'])]
    for phase, version, cases in phases:
        model = opponents.snapshot(version)
        policy = A.policy_sha256(model)
        assigned = list(range(len(cases)))
        bank = S.digest(cases)
        directory = root/phase
        directory.mkdir()
        C.durable_json(directory/'manifest.json', dict(assigned=assigned, policy_sha256=policy, bank_sha256=bank,
            source_sha256=D.source_digest(), config_sha256=D.registration_identity(config), runtime_manifest=runtime))
        scores, records, rows = {}, {}, []
        for index, case in enumerate(cases):
            D.guard()
            row = dict(index=index, case=case, case_sha256=S.digest(case), policy_sha256=policy,
                       bank_sha256=bank, runtime_manifest=runtime)
            started = time.monotonic()
            try:
                own = D.bounded_policy_player(model)
                opponent, _ = opponents.make(dict(case, league='live'), version)
                players = {case['seat']: own, 1-case['seat']: opponent}
                def observer(view, decision):
                    D.guard()
                    D.execution_ok(decision.stats or {})
                with bind_matches(players):
                    game = play_match(rt, players, seed=case['seed'], decks=case['decks'], levels=case['levels'],
                                      verbose=True, observer=observer)
                counts = O.game_counts(game, case['seat'])
                row['module_origins_after'] = D.module_origins(config)
                S.require(game['terminal'], 'evaluation did not reach true terminal')
                winner = game['winner']
                win, draw = int(winner == case['seat']) if winner is not None else 0, int(winner is None)
                row.update(result=game, win=win, draw=draw, score=win+.5*draw, operational_rejections=counts,
                           actions=dict(own.counts))
                records[index] = counts
            except Exception as ex:
                # Assigned evaluation errors stay explicit missing observations.
                # No failed game is retried or replaced. Training has ended.
                row['error'] = repr(ex)
            row['wall_seconds'] = time.monotonic()-started
            C.durable_json(directory/f'{index:04d}.json', row)
            scores[index] = validate_result(row, case, policy=policy, bank=bank, runtime=runtime)
            rows.append(row)
        summary = dict(assigned=len(cases), attempted=len(rows), valid=sum(v is not None for v in scores.values()),
                       wins=sum(v for v in scores.values() if v is not None),
                       draws=sum(r.get('draw', 0) for r in rows), failures=sum(v is None for v in scores.values()),
                       operational_rejections=O.aggregate(records.values()))
        C.durable_json(directory/'summary.json', summary)
        family = 'primary' if phase.startswith('primary') else 'dev'
        if version == 0:
            rejection_baselines[family] = (records, policy, bank)
        baseline_records, baseline_policy, baseline_bank = rejection_baselines[family]
        S.require(bank == baseline_bank, 'rejection baseline must use the same assignments')
        matched = sorted(set(records) & set(baseline_records))
        alert = O.aggregate([records[i] for i in matched],
            baseline=O.aggregate([baseline_records[i] for i in matched]))
        C.durable_json(directory/'rejections-vs-bc.json', dict(baseline_policy_sha256=baseline_policy,
            bank_sha256=bank, scope=family, assigned=len(cases), matched_valid_cases=len(matched),
            partial=len(matched) != len(cases), counts=alert))
        if phase.startswith('primary'):
            primary_scores[phase] = scores
            rejection_records[phase] = records
        if phase.startswith('dev') or phase == 'primary-final':
            # Use the exact existing audit logic with an explicit model, so no
            # checkpoint loader can silently convert precision or dropout.
            S.require(S.pinned(banks['audits']['defense']) == (P.DEF/'events.json').resolve()
                      and S.pinned(banks['audits']['spell']) == (P.SPELL/'opportunities.json').resolve(),
                      'audit roots differ from frozen registered inputs')
            C.durable_json(directory/'roots.json', P.evaluate(model, ckpt=str(out/f'checkpoints/update-{version:02d}.pt')))
    comparison = paired_bootstrap(primary_scores['primary-final'], primary_scores['primary-bc'])
    matched = sorted(set(rejection_records['primary-bc']) & set(rejection_records['primary-final']))
    baseline = O.aggregate([rejection_records['primary-bc'][i] for i in matched])
    comparison['operational_rejections'] = O.aggregate(
        [rejection_records['primary-final'][i] for i in matched], baseline=baseline)
    comparison['operational_rejection_matched_cases'] = len(matched)
    comparison.update(seed=config['seed'], size=config['size'], bank_sha256=S.digest(banks['primary']))
    C.durable_json(root/'final-vs-bc.json', comparison)
    return comparison
