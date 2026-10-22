"""Read-only authentication of registered evaluation evidence. No engine imports."""
import copy
import json
import math
from pathlib import Path

from . import rl_schedule as S


def read(path):
    return json.loads(Path(path).read_text())


def authenticate_run(config, out):
    from . import rl_driver as D
    out = Path(out)
    S.require(config.get('qualification_only', False) is False and config.get('test_only', False) is False
              and not (out/'qualification.json').exists(), 'qualification/test evidence is not registered')
    scope = dict(scope='registered-experiment', counted_registered_prefix=True, maximum_updates=32,
                 minimum_qualification_seconds=None, checkpoint_or_data_promotion_allowed=False, test_only=False)
    S.require(read(out/'scope.json') == scope, 'registered scope mismatch')
    # Recompute gates and all pinned inputs. Saved admission is evidence, never authority.
    admission = D.audit(config)
    S.require(admission['status'] == 'GO', 'registered admission failed: '+repr(admission['failures']))
    S.require(read(out/'admission.json') == admission, 'saved admission/source/config mismatch')
    runtime = dict(D.make_manifest(config), scope='registered-experiment')
    S.require(read(out/'runtime.json') == runtime, 'saved registered runtime mismatch')
    return runtime


def learner(config, runtime):
    from . import rl_learner as L
    return L.Learner(S.pinned(config['anchor']), anchor_sha256=config['anchor']['sha256'],
        model_cfg=read(S.pinned(config['model_cfg'])), runtime_manifest=runtime,
        config=L.LearnerConfig(seed=config['seed'], size=config['size'], precision=config['precision'],
                              microbatch=128, precision_registration=config['precision_registration_id']), device='cpu')


# joint_kl/joint_terms explicitly cast logits to float32, including FP64 runs.
# Allow cancellation near zero in their two log-softmax/reduction levels, with
# a conservative 64-epsilon budget scaled by log(5)+log(576)+1. This is only a
# serialized-statistic roundoff allowance; the learner's >0.5 stop stays exact.
KL_ROUNDOFF = 64*2**-23*(1+math.log(5)+math.log(576))


def verify_metrics(proof, state, version, policy, previous_high_kl_streak):
    """Validate retained statistics, without reconstructing deleted poll arrays."""
    metrics = state['last_metrics']
    if version == 0:
        S.require(metrics is None and type(state['high_kl_streak']) is int
                  and state['high_kl_streak'] == 0, 'update00 has learner progress')
        return metrics
    integers = dict(update=version, version=version, generated_steps=state['generated_steps'],
                    trained_steps=state['trained_steps'], optimizer_steps=state['optimizer_steps'],
                    polls=proof.config.steps_per_update, legal_action_checks=proof.config.steps_per_update,
                    cadence_checks=proof.config.steps_per_update)
    counts = {'actor_polls', 'forced_polls', 'busy_polls', 'boundary_declined_steps', 'high_kl_streak'}
    numbers = {'old_logp_max_error', 'old_value_max_error', 'mean_entropy', 'mean_kl', 'p95_kl'}
    fields = set(integers) | counts | numbers | {'warmup', 'policy_sha256', 'halted_reason',
                                               'per_opponent_kl', 'plays_per_300s', 'play_rates_reported'}
    S.require(isinstance(metrics, dict) and set(metrics) == fields, 'checkpoint learner metric fields missing/unsupported')
    for key, expected in integers.items():
        S.require(type(metrics[key]) is int and metrics[key] == expected,
                  'checkpoint learner progress mismatch: '+key)
    S.require(all(type(metrics[k]) is int and metrics[k] >= 0 for k in counts),
              'checkpoint learner metric count type/bounds mismatch')
    n, actor, forced = metrics['polls'], metrics['actor_polls'], metrics['forced_polls']
    # Busy implies no legal slot. A declined boundary row can also be busy;
    # neither the sum of these counts nor equality with forced is implied.
    S.require(actor+forced == n and metrics['busy_polls'] <= forced
              and metrics['boundary_declined_steps'] <= forced, 'checkpoint learner forced/busy accounting mismatch')
    S.require(type(metrics['warmup']) is bool and metrics['warmup'] == (version <= 3)
              and metrics['policy_sha256'] == policy and metrics['halted_reason'] is None,
              'checkpoint learner warmup/policy/halt mismatch')
    finite = lambda x: type(x) in (int, float) and math.isfinite(x)
    S.require(all(finite(metrics[k]) for k in numbers), 'checkpoint learner metric numeric/finite mismatch')
    S.require(all(0 <= metrics[k] <= 2e-6 for k in ('old_logp_max_error', 'old_value_max_error')),
              'checkpoint learner strict parity error mismatch')
    # There are at most 1+4*576 joint actions. No fixed upper KL threshold
    # follows from that cardinality: anchor probabilities can be arbitrarily small.
    S.require(0 <= metrics['mean_entropy'] <= math.log(1+4*576)+KL_ROUNDOFF
              and (actor > 0 or metrics['mean_entropy'] == 0), 'checkpoint learner entropy bounds mismatch')

    def kl_stats(mean, p95, polls):
        # KL rows are finite float32 values, aggregated/quantiled in float64.
        S.require(finite(mean) and finite(p95) and -KL_ROUNDOFF <= mean <= 3.4028234663852886e38
                  and -KL_ROUNDOFF <= p95 <= 3.4028234663852886e38,
                  'checkpoint learner KL numeric/finite/bounds mismatch')
        # numpy's linear q=.95 needs at least n-ceil(.95*(n-1)) rows
        # at or above q. Their mass bounds q from the mean and row lower bound.
        tail = polls-math.ceil(.95*(polls-1))
        S.require(p95 <= -KL_ROUNDOFF+(mean+KL_ROUNDOFF)*polls/tail+KL_ROUNDOFF,
                  'checkpoint learner KL mean/quantile mismatch')
        if polls == 1:
            S.require(math.isclose(mean, p95, rel_tol=1e-12, abs_tol=1e-12),
                      'checkpoint learner one-poll KL mismatch')

    kl_stats(metrics['mean_kl'], metrics['p95_kl'], n)
    opponents = metrics['per_opponent_kl']
    S.require(isinstance(opponents, dict) and 0 < len(opponents) <= n,
              'checkpoint learner per-opponent KL missing')
    for name, stats in opponents.items():
        S.require(isinstance(name, str) and 0 < len(name) <= 256 and isinstance(stats, dict)
                  and set(stats) == {'mean', 'p95', 'polls'} and type(stats['polls']) is int
                  and 0 < stats['polls'] <= n, 'checkpoint learner per-opponent KL fields/count mismatch')
        kl_stats(stats['mean'], stats['p95'], stats['polls'])
    S.require(sum(s['polls'] for s in opponents.values()) == n,
              'checkpoint learner per-opponent KL poll accounting mismatch')
    # These means use float64 numpy reductions over the same float32 rows.
    # 1e-12 covers regrouping roundoff, not a tolerance on scientific KL limits.
    weighted = math.fsum(s['mean']*(s['polls']/n) for s in opponents.values())
    S.require(math.isclose(weighted, metrics['mean_kl'], rel_tol=1e-12, abs_tol=1e-12),
              'checkpoint learner per-opponent KL mean accounting mismatch')
    if len(opponents) == 1:
        S.require(next(iter(opponents.values()))['p95'] == metrics['p95_kl'],
                  'checkpoint learner per-opponent KL quantile mismatch')
    if not actor:
        S.require(abs(metrics['mean_kl']) <= KL_ROUNDOFF and abs(metrics['p95_kl']) <= KL_ROUNDOFF
                  and all(abs(s['mean']) <= KL_ROUNDOFF and abs(s['p95']) <= KL_ROUNDOFF
                          for s in opponents.values()),
                  'checkpoint learner forced-only KL mismatch')
    rates = metrics['plays_per_300s']
    S.require(isinstance(rates, dict) and len(rates) <= n
              and all(isinstance(k, str) and 0 < len(k) <= 256 and finite(v) and 15 <= v <= 80
                      for k, v in rates.items()) and metrics['play_rates_reported'] is bool(rates),
              'checkpoint learner play-rate metric mismatch')
    S.require(type(previous_high_kl_streak) is int and 0 <= previous_high_kl_streak < 3,
              'checkpoint previous KL streak already halted/invalid')
    streak = 0 if version <= 3 or metrics['mean_kl'] <= .5 else previous_high_kl_streak+1
    S.require(type(state['high_kl_streak']) is int and state['high_kl_streak'] == metrics['high_kl_streak'] == streak,
              'checkpoint learner KL streak recurrence mismatch')
    S.require(streak < 3, 'checkpoint learner KL streak requires mandatory halt')
    return metrics


def verify_checkpoint(proof, path, version, previous_masks=(), *, previous_high_kl_streak=0):
    """Check serialized learner state on CPU without restoring CUDA/process RNGs."""
    import torch
    from . import rl_learner as L
    state = torch.load(path, map_location='cpu', weights_only=False)
    for key, value in dict(format=1, config=proof.config.record(), model_cfg=proof.model.cfg,
            feature_hash=proof.feature_hash, anchor_sha256=proof.anchor_sha256, selection=proof.selection,
            anchor_state_sha256=proof._anchor_state_sha256, runtime_manifest=proof.runtime_manifest,
            provenance_sha256=proof.provenance_sha256, update_index=version, halted_reason=None,
            generated_steps=version*proof.config.steps_per_update, trained_steps=version*proof.config.steps_per_update,
            optimizer_steps=version*proof.config.record()['optimizer_steps_per_update']).items():
        S.require(state.get(key) == value, 'checkpoint '+key+' mismatch')
    for key, model in (('model', proof.model), ('anchor', proof.anchor)):
        expected, actual = model.state_dict(), state[key]
        S.require(set(actual) == set(expected) and all(isinstance(actual[k], torch.Tensor)
                  and actual[k].dtype == t.dtype and actual[k].shape == t.shape
                  and bool(torch.isfinite(actual[k]).all()) for k, t in expected.items()),
                  'checkpoint '+key+' keys/dtypes/shapes/finite mismatch')
        model.load_state_dict(actual, strict=True)
    S.require(L.policy_sha256(proof.anchor, proof.feature_hash) == proof._anchor_state_sha256,
              'checkpoint anchor state hash mismatch')
    policy = L.policy_sha256(proof.model, proof.feature_hash)
    S.require(policy == state['policy_sha256'], 'checkpoint policy state hash mismatch')
    # Reuse the core's participation/shuffle derivation, without resuming a run.
    counters = proof._checkpoint_optimizer_counters(state)
    masks = state['optimizer_resume']['ppo_actor_masks']
    S.require(masks[:len(previous_masks)] == list(previous_masks),
              'checkpoint optimizer eligibility history changed')
    stored = state['optimizer']
    expected = proof.optimizer.state_dict()
    S.require(stored['param_groups'] == expected['param_groups'], 'checkpoint optimizer configuration mismatch')
    S.require(all(type(pid) is int for pid in stored['state']) and set(stored['state']) == set(counters),
              'checkpoint optimizer initialized parameter set mismatch')
    parameters = dict(zip(expected['param_groups'][0]['params'], proof.model.parameters()))
    for pid, values in stored['state'].items():
        S.require(set(values) == {'step', 'exp_avg', 'exp_avg_sq'}, 'checkpoint optimizer state keys mismatch')
        parameter = parameters[pid]
        for key in ('exp_avg', 'exp_avg_sq'):
            value = values[key]
            S.require(isinstance(value, torch.Tensor) and value.dtype == parameter.dtype
                      and value.shape == parameter.shape and bool(torch.isfinite(value).all()),
                      'checkpoint optimizer moment dtype/shape mismatch')
        S.require(bool((values['exp_avg_sq'] >= 0).all()), 'checkpoint optimizer negative second moment')
        step = values['step']
        S.require(isinstance(step, torch.Tensor) and step.dtype == torch.float32 and step.ndim == 0
                  and float(step) == counters[pid], 'checkpoint optimizer step counter mismatch')
    metrics = verify_metrics(proof, state, version, policy, previous_high_kl_streak)
    if version and masks:
        S.require(metrics['actor_polls'] == sum(byte.bit_count() for byte in masks[-1]),
                  'checkpoint learner eligibility count mismatch')
    return policy, masks, metrics


def verify_progress(config, ledger, prior, names, contents, metrics):
    """Replay the retained coordinator receipts, not a caller's claimed totals.

    Acknowledged queue arrays are deleted by the coordinator. These are checks
    of its retained boundary evidence, not a replay of engine games or training.
    """
    from . import rl_coordinator as C
    version = ledger['version']
    workers = config['workers']
    S.require(type(workers) is int and workers > 0 and 262144 % workers == 0,
              'checkpoint actor topology mismatch')
    quotas = {f'actor-{i:02d}': 262144//workers for i in range(workers)}
    budgets = {k: n*32 for k, n in quotas.items()}
    S.require(ledger.get('quotas') == quotas and ledger.get('budgets') == budgets,
              'checkpoint quotas/budgets mismatch')
    empty = dict(generated=0, observed=0, accepted=0, trained=0, sequence=0,
                 reported_until=0, unpublished_reported=0, reported_ranges=[], update_rows=0,
                 boundary_declined=0, completed=0, chain='0'*64, last=None,
                 discarded=0, games_sha256=S.digest([]))
    actors = {k: copy.deepcopy(empty if prior is None else prior['actors'][k]) for k in quotas}
    for actor in actors.values():
        actor['update_rows'] = 0
    games = [] if prior is None else list(prior['games'])
    S.require(isinstance(ledger.get('actors'), dict) and set(ledger['actors']) == set(quotas)
              and isinstance(ledger.get('games'), list) and isinstance(ledger.get('receipts'), list),
              'checkpoint actors/games/receipts missing')
    seen_games = {k: {g['game_id'] for g in games if g['actor_id'] == k} for k in quotas}
    last_bindings = {}
    for binding in ledger['receipts']:
        S.require(version > 0 and set(binding) == {'actor_id', 'receipt', 'boundary', 'publication', 'previous', 'sha256'},
                  'checkpoint receipt binding mismatch')
        key = binding['actor_id']
        S.require(key in actors, 'checkpoint receipt actor mismatch')
        a, r, b, p = actors[key], binding['receipt'], binding['boundary'], binding['publication']
        S.require(set(r) == {'name', 'manifest_sha256', 'bytes', 'rows', 'version', 'generated_steps'}
                  and set(b) == {'reason', 'generated_steps', 'remaining_budget', 'remaining_quota',
                                 'terminal', 'unfinished', 'boundary_declined_steps'}
                  and set(p) == {'sequence', 'game_id', 'game_sequence', 'engine_tick', 'terminal', 'completed'},
                  'checkpoint receipt/context fields mismatch')
        S.require(all(type(r[k]) is int for k in ('bytes', 'rows', 'version', 'generated_steps'))
                  and 0 < r['rows'] == r['generated_steps'] <= config['chunk_rows']
                  and r['version'] == version-1 and 0 < r['bytes'] <= C.queue_capacity(r['rows'])[1],
                  'checkpoint receipt rows/version/bytes mismatch')
        S.require(isinstance(r['name'], str) and r['name'].startswith('chunk-')
                  and isinstance(r['manifest_sha256'], str) and len(r['manifest_sha256']) == 64
                  and all(c in '0123456789abcdef' for c in r['manifest_sha256'])
                  and r['name'] not in names and r['manifest_sha256'] not in contents,
                  'checkpoint duplicate/invalid receipt identity')
        names.add(r['name']); contents.add(r['manifest_sha256'])
        S.require(binding['previous'] == a['chain']
                  and binding['sha256'] == S.digest({k: v for k, v in binding.items() if k != 'sha256'}),
                  'checkpoint actor receipt chain mismatch')
        S.require(all(type(b[k]) is int for k in ('generated_steps', 'remaining_budget', 'remaining_quota',
                                                 'boundary_declined_steps'))
                  and all(type(p[k]) is int for k in ('sequence', 'game_sequence', 'engine_tick'))
                  and type(b['terminal']) is type(b['unfinished']) is type(p['terminal']) is bool,
                  'checkpoint integer/boolean receipt context mismatch')
        total, rows = a['accepted']+r['rows'], a['update_rows']+r['rows']
        reason = 'budget' if total == budgets[key] else 'quota' if rows == quotas[key] else 'terminal' if p['terminal'] else 'chunk'
        declined = b['boundary_declined_steps']-a['boundary_declined']
        S.require(total <= budgets[key] and rows <= quotas[key] and b['generated_steps'] == total
                  and b['remaining_budget'] == budgets[key]-total and b['remaining_quota'] == quotas[key]-rows
                  and declined in (0, 1) and b['reason'] == reason
                  and b['terminal'] == p['terminal'] and b['unfinished'] == (reason == 'budget' and not p['terminal']),
                  'checkpoint receipt progress/quota/budget mismatch')
        last = a['last']
        S.require(p['sequence'] == a['sequence'] and C.text(p['game_id']) and p['game_sequence'] >= 0,
                  'checkpoint publication sequence mismatch')
        if last is None or last['terminal']:
            S.require(p['game_id'] not in seen_games[key]
                      and p['game_sequence'] == (0 if last is None else last['game_sequence']+1),
                      'checkpoint game replay/sequence mismatch')
            first = 90
        else:
            S.require(not last['declined'] and p['game_id'] == last['game_id']
                      and p['game_sequence'] == last['game_sequence'], 'checkpoint game continuity mismatch')
            first = last['tick']+5
        tick = first+(r['rows']-1)*5
        S.require(not declined or tick in (3600, 6000), 'checkpoint boundary-decline tick mismatch')
        S.require(tick <= p['engine_tick'] <= tick+5 if p['terminal'] else p['engine_tick'] == tick+5,
                  'checkpoint game engine tick mismatch')
        S.require((p['completed'] is not None) == p['terminal'], 'checkpoint completed game evidence mismatch')
        if p['terminal']:
            rate = p['completed']
            S.require(set(rate) == {'game_id', 'accepted_plays', 'seconds'} and rate['game_id'] == p['game_id']
                      and type(rate['accepted_plays']) is int and rate['accepted_plays'] >= 0
                      and type(rate['seconds']) in (int, float) and math.isfinite(rate['seconds']) and rate['seconds'] > 0
                      and 15 <= 300*rate['accepted_plays']/rate['seconds'] <= 80,
                      'checkpoint completed game play rate mismatch')
            S.require(len(ledger['games']) > len(games), 'checkpoint missing completed game')
            game = ledger['games'][len(games)]
            expected = dict(actor_id=key, game_id=p['game_id'], game_sequence=p['game_sequence'],
                            accepted_plays=rate['accepted_plays'], seconds=rate['seconds'], engine_tick=p['engine_tick'])
            S.require(set(game) == set(expected) | {'terminal_reward'}
                      and all(game[k] == v for k, v in expected.items())
                      and type(game['terminal_reward']) in (float, int) and game['terminal_reward'] in (-1, 0, 1),
                      'checkpoint completed game/publication mismatch')
            games.append(game)
            seen_games[key].add(p['game_id'])
            a['completed'] += 1
        # The receipt does not retain bootstrap/opponent scalars. Check those
        # in the last actor snapshot below; the ticks are derivable from rows.
        a.update(generated=total, observed=total, accepted=total, sequence=a['sequence']+1,
                 update_rows=rows, boundary_declined=b['boundary_declined_steps'], chain=binding['sha256'],
                 last=dict(game_id=p['game_id'], game_sequence=p['game_sequence'], tick=tick,
                           terminal=p['terminal'], version=version-1, declined=bool(declined)))
        last_bindings[key] = binding
    S.require(S.encoded(ledger['games']) == S.encoded(games), 'checkpoint cumulative games mismatch')
    for key, a in actors.items():
        a['trained'] = version*quotas[key]
        a['games_sha256'] = S.digest([g for g in games if g['actor_id'] == key])
        S.require(a['generated'] == a['accepted'] == a['trained'] == version*quotas[key]
                  and a['update_rows'] == (quotas[key] if version else 0), 'checkpoint actor progress mismatch')
        if key in last_bindings:
            actual = ledger['actors'][key]['last']
            S.require(isinstance(actual, dict) and set(actual) == set(a['last']) | {'bootstrap', 'opponent_id'}
                      and all(actual[k] == v for k, v in a['last'].items())
                      and type(actual['bootstrap']) in (float, int) and math.isfinite(actual['bootstrap'])
                      and abs(actual['bootstrap']) <= 1
                      and (not actual['terminal'] or actual['bootstrap'] == 0) and C.text(actual['opponent_id']),
                      'checkpoint actor last game mismatch')
            a['last'] = actual
        S.require(S.encoded(ledger['actors'][key]) == S.encoded(a), 'checkpoint actor accounting mismatch')
    if version:
        declined = sum(a['boundary_declined'] for a in actors.values())-sum(
            a['boundary_declined'] for a in prior['actors'].values())
        rates = {S.digest([g['actor_id'], g['game_id']]): 300*g['accepted_plays']/g['seconds']
                 for g in games[len(prior['games']):]}
        S.require(metrics['boundary_declined_steps'] == declined and metrics['plays_per_300s'] == rates
                  and metrics['play_rates_reported'] is bool(rates),
                  'checkpoint learner/receipt progress mismatch')


def phase_manifest(config, out, runtime, version, cases, policy):
    from . import rl_driver as D
    checkpoint = Path(out)/f'checkpoints/update-{version:02d}.pt'
    return dict(assigned=list(range(len(cases))), bank_sha256=S.digest(cases), policy_sha256=policy,
                runtime_manifest=runtime, source_sha256=D.source_digest(),
                config_sha256=D.registration_identity(config), version=version,
                checkpoint=dict(path=str(checkpoint.resolve()), sha256=S.file_sha(checkpoint)))


def authenticate_checkpoints(config, out, runtime, versions, *, completed):
    """Authenticate every serialized boundary; return only requested policies."""
    out = Path(out)
    expected = learner(config, runtime)
    initial_policy = expected.policy_sha256
    versions = set(versions) | {0}
    last = 32 if completed else max(versions)
    S.require(all(type(v) is int and 0 <= v <= 32 for v in versions), 'checkpoint version out of budget')
    previous, ledgers, policies, masks = None, {}, {}, []
    names, contents, high_kl_streak = set(), set(), 0
    for version in range(last+1):
        directory = out/'checkpoints'
        path = directory/f'update-{version:02d}.pt'
        ledger = read(path.with_suffix('.json'))
        for key, value in dict(schema=1, test_only=False, version=version,
                config=dict(wait_seconds=config['wait_seconds'], test_only=False),
                learner_config=expected.config.record(), anchor_sha256=expected.anchor_sha256,
                model_cfg=expected.model.cfg, model_cfg_sha256=S.digest(expected.model.cfg),
                feature_hash=expected.feature_hash, runtime_manifest=runtime,
                provenance_sha256=expected.provenance_sha256, previous_checkpoint_sha256=previous,
                engine_resume_qualified=False).items():
            S.require(ledger.get(key) == value, f'checkpoint ledger {version} {key} mismatch')
        S.require(ledger['learner_checkpoint'] == dict(file=path.name, sha256=S.file_sha(path)),
                  'checkpoint file/ledger mismatch')
        # Verify raw state before load_state_dict can silently cast its dtype.
        policy, masks, metrics = verify_checkpoint(expected, path, version, masks,
                                                 previous_high_kl_streak=high_kl_streak)
        high_kl_streak = 0 if metrics is None else metrics['high_kl_streak']
        S.require(policy == ledger['policy_sha256'], 'checkpoint policy/version mismatch')
        if version == 0:
            S.require(policy == initial_policy, 'update00 is not the verified own BC start')
        verify_progress(config, ledger, ledgers.get(version-1), names, contents, metrics)
        ledgers[version] = ledger
        previous = S.digest(ledger)
        if version in versions:
            policies[version] = policy
    if completed:
        final = read(out/'checkpoints/final-manifest.json')
        saved = read(out/'completed.json')
        S.require(saved['status'] == 'training_complete' and saved['optimizer_resume_proof'] is True
                  and saved['final'] == final, 'completion record/final ledger mismatch')
        # finalize() snapshots after resetting per-update rows and receipts.
        boundary = copy.deepcopy(ledgers[32])
        boundary.pop('learner_checkpoint')
        boundary['previous_checkpoint_sha256'] = previous
        boundary['receipts'] = []
        for actor in boundary['actors'].values():
            actor['update_rows'] = 0
        boundary.update(generated=8388608, accepted=8388608, trained=8388608, discarded=0, updates=32,
                        completed_games=len(boundary['games']), unfinished_games=sum(
                            not a['last']['terminal'] for a in boundary['actors'].values()),
                        games_sha256=S.digest(boundary['games']), checkpoint_sha256=previous)
        S.require(boundary['games'] and S.encoded(final) == S.encoded(boundary),
                  'final checkpoint accounting/identity mismatch')
        S.require(saved.get('generated_counts') == final['budgets'] and saved.get('engine_resume_qualified') is False,
                  'completion generated actor totals mismatch')
        S.require(final['checkpoint_sha256'] == previous and final['generated'] == final['accepted'] ==
                  final['trained'] == 8388608 and final['discarded'] == 0 and final['updates'] == 32,
                  'unequal/incomplete training budget or final checkpoint chain')
    return policies


def validate_origins(origins, config):
    """Validate retained module locations against pinned file bytes, without importing them."""
    from . import rl_driver as D
    required = {'bot', 'clasher', 'bot.pretrain_v1', 'bot.pretrain_v1.rl_evaluate',
                'bot.pretrain_v1.rl_driver', 'bot.pretrain_v1.sim_ours', 'bot.pretrain_v1.model',
                'bot.players.ours', 'bot.rl.actor'}
    S.require(isinstance(origins, dict) and required <= set(origins), 'missing evaluation module origins')
    lineage = read(S.pinned(config['runtime_manifest']))
    candidate = D.ROOT/'bot/pretrain_v1'
    candidate_files = {str(p.relative_to(candidate)): S.file_sha(p) for p in candidate.rglob('*.py')}
    for name, value in origins.items():
        S.require(isinstance(value, str), 'invalid evaluation module origin')
        if name == 'clasher' or name.startswith('clasher.'):
            root, files = Path(config['runtime']).resolve(), lineage['files']
        elif name == 'bot.pretrain_v1' or name.startswith('bot.pretrain_v1.'):
            root, files = candidate, candidate_files
        else:
            S.require(name == 'bot' or name.startswith('bot.'), 'unexpected module origin')
            root, files = Path(config['actor_source']).resolve(), lineage['source_files']
        path = Path(value).resolve()
        S.require(path.is_relative_to(root), 'evaluation module outside registered root: '+name)
        relative = str(path.relative_to(root))
        S.require(relative in files and S.file_sha(path) == files[relative], 'unregistered evaluation module: '+name)
        module = name.removeprefix('bot.pretrain_v1.').replace('.', '/') if root == candidate else name.replace('.', '/')
        if name == 'clasher' or name.startswith('clasher.'):
            module = 'src/'+module
        if name == 'bot.pretrain_v1':
            module = ''
        allowed = {module+'.py', module+'/__init__.py'} if module else {'__init__.py'}
        S.require(relative in allowed or path.suffix == '.so' and str(Path(relative).parent) == str(Path(module).parent)
                  and path.name.startswith(Path(module).name+'.'), 'evaluation module name/path mismatch: '+name)
