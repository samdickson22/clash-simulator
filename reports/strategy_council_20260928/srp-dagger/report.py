"""Paired analysis fixed before fine-tuned evaluation outcomes are available."""
import json
import numpy as np
from kit import HERE, COUNCIL, INITIAL, FINAL, sha, write_json, config, budget, source_hashes, sources_match


def comparison():
    folder = COUNCIL/'human-prior-p16/evaluation'
    cells, pairs, initial_wins, final_wins = [], [], 0, 0
    for role in ('holdout', 'hog26'):
        for style in ('balanced','pressure','defense'):
            name = f'{role}-nominal-{style}'
            old = json.loads((folder/'srp-dagger-initial-s2902'/f'{name}.games.json').read_text())
            new = json.loads((folder/'srp-dagger-it1-s2902'/f'{name}.games.json').read_text())
            assert len(old) == len(new) == 32
            old_summary = json.loads((folder/'srp-dagger-initial-s2902'/f'{name}.json').read_text())
            new_summary = json.loads((folder/'srp-dagger-it1-s2902'/f'{name}.json').read_text())
            assert old_summary['checkpoint_sha256'] == sha(INITIAL)
            assert new_summary['checkpoint_sha256'] == sha(FINAL)
            for key in ('seed','decision_interval_ticks','max_ticks','deterministic','gamedata_sha256',
                        'model_config_sha256','public_contract_version','public_script_style',
                        'opponent_mode','opponent_strategy','opponent_checkpoint_sha256','reward_profile',
                        'level_mode','sampling_temperature','paired_asymmetric_matchups','mirror_match','location_lookahead',
                        'candidate_sampling_decks_sha256','opponent_sampling_decks_sha256'):
                assert old_summary[key] == new_summary[key], (name,key)
            assert not old_summary['deterministic']
            diffs = []
            for a,b in zip(old,new):
                for key in ('game','matchup','matchup_seed','candidate_player','candidate_deck','opponent_deck',
                            'candidate_card_levels','opponent_card_levels','candidate_tower_level','opponent_tower_level'):
                    assert a[key] == b[key], (name,key)
                assert a['terminated'] and b['terminated'] and not a['truncated'] and not b['truncated']
                score = {'win':1., 'draw':.5, 'loss':0.}
                diffs.append(score[b['outcome']] - score[a['outcome']])
            iw = sum(x['outcome']=='win' for x in old)
            fw = sum(x['outcome']=='win' for x in new)
            initial_wins += iw; final_wins += fw
            pairs.extend(np.asarray(diffs).reshape(16,2).mean(1).tolist())
            cells.append(dict(cell=name, initial_wins=iw, final_wins=fw, games=32,
                              initial_noop_when_playable=old_summary['metrics']['candidate_noop_when_playable'],
                              final_noop_when_playable=new_summary['metrics']['candidate_noop_when_playable'],
                              score_difference=float(np.mean(diffs))))
    pairs = np.asarray(pairs)
    rng = np.random.default_rng(880034)
    boots = np.mean(pairs[rng.integers(0, len(pairs), (20000,len(pairs)))],axis=1)
    # Exact two-sided paired randomization, swapping model identity within each
    # matchup/seat-pair cluster. Differences are multiples of one quarter.
    magnitudes = np.rint(np.abs(pairs)*4).astype(int)
    counts = {0:1}
    for magnitude in magnitudes:
        nxt = {}
        for total,n in counts.items():
            for sign in (-1,1): nxt[total+sign*magnitude] = nxt.get(total+sign*magnitude,0)+n
        counts = nxt
    observed = abs(int(round(pairs.sum()*4)))
    pvalue = sum(n for total,n in counts.items() if abs(total)>=observed) / 2**len(pairs)
    return dict(cells=cells, initial_wins=initial_wins, final_wins=final_wins, games=192,
        matchup_pairs=len(pairs), score_difference=float(pairs.mean()),
        paired_bootstrap_95ci=np.quantile(boots,[.025,.975]).tolist(),
        paired_exact_sign_flip_p=pvalue)


def main():
    cfg = config()
    if not sources_match(json.loads((HERE/'preflight.json').read_text())['sources']):
        raise RuntimeError('unreviewed source drift before final reporting')
    games = [json.loads((HERE/'games'/f'game-{g:03d}.json').read_text()) for g in range(cfg.games)]
    canonical = json.loads((HERE/'canonical-data.json').read_text())
    assert all(g['gamedata_sha256'] == canonical['gamedata_sha256'] and g['backend'] == 'native' for g in games)
    fit = json.loads((HERE/'fit.json').read_text())
    evaluation_cost = json.loads((HERE/'evaluation-cost-final.json').read_text())
    baseline_cost = json.loads((HERE/'evaluation-cost-initial.json').read_text())
    labels = sum(g['labels'] for g in games)
    cpu = sum(g['planner_cpu_s'] for g in games)
    native = [g for g in games if g.get('backend', 'python') == 'native']
    assert native and json.loads((HERE/'native-parity.json').read_text())['passed']
    native_calls = sum(g['labels'] for g in native)
    native_cpu = sum(g['planner_cpu_s'] for g in native)
    native_per_call = native_cpu/native_calls
    native_other_per_decision = sum(g['total_cpu_s']-g['planner_cpu_s'] for g in native)/sum(g['decisions'] for g in native)
    parity = json.loads((HERE/'native-parity.json').read_text())
    score_error = max((abs(d['python']-d['native']) for d in parity['root_score_differences']), default=0.)
    projected_planner_cpu = native_per_call*labels/len(games)*300
    projected_collection_cpu = projected_planner_cpu + native_other_per_decision*sum(g['decisions'] for g in games)/len(games)*300
    results = dict(games=len(games), labels=labels,
        decisions=sum(g['decisions'] for g in games), planner_cpu_s=cpu,
        planner_core_s_per_call=cpu/labels, labels_per_game=labels/len(games),
        backend_counts=dict(python=len(games)-len(native), native=len(native)),
        native_planner_cpu_s=native_cpu, native_labels=native_calls,
        native_planner_core_s_per_call=native_per_call,
        projected_300_game_planner_core_hours=projected_planner_cpu/3600,
        projected_300_game_collection_core_hours=projected_collection_cpu/3600,
        projection_assumptions='native-only cost per call and other CPU per decision at the 40-game query/decision rate; same beta/decks/cadence; QA replay excluded',
        fit_cpu_s=fit['cpu_s'], final_evaluation_cpu_s=evaluation_cost['cpu_s'],
        initial_evaluation_cpu_s=baseline_cost['cpu_s'],
        projected_300_core_hours_with_cached_baseline=(projected_collection_cpu
            + fit['cpu_s']*300/len(games) + evaluation_cost['cpu_s'])/3600,
        projected_300_core_hours_with_two_evaluations=(projected_collection_cpu
            + fit['cpu_s']*300/len(games) + evaluation_cost['cpu_s'] + baseline_cost['cpu_s'])/3600,
        full_projection_assumptions='linear collection and BC scaling; measured initial/final evaluation CPU',
        projected_300_at_200_calls_core_hours=native_per_call*200*300/3600,
        native_parity=parity, native_root_score_max_abs_difference=score_error,
        canonical_data=canonical,
        heldout_initial=fit['curves'][0]['heldout'], heldout_final=fit['curves'][-1]['heldout'],
        evaluation=comparison(), initial_sha256=sha(INITIAL), final_sha256=sha(FINAL),
        workspace_sources_unchanged=source_hashes()==json.loads((HERE/'preflight.json').read_text())['sources'],
        p16_source_guard_passed=sources_match(json.loads((HERE/'preflight.json').read_text())['sources']),
        prior_invalid_run='archive/noncanonical-3d99987c/INVALID.json; excluded from all pilot metrics',
        artifact_bytes=budget())
    write_json(HERE/'results.json',results)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    curves = fit['curves']
    fig, axes = plt.subplots(1,2,figsize=(10,4),layout='constrained')
    for split in ('train','heldout'):
        axes[0].plot([c['epoch'] for c in curves], [c[split]['ce'] for c in curves], marker='o',label=split)
        axes[1].plot([c['epoch'] for c in curves], [c[split]['agreement'] for c in curves], marker='o',label=split)
    axes[0].set(ylabel='Cross-entropy',xlabel='Epoch',title='Teacher label loss')
    axes[1].set(ylabel='Exact action agreement',xlabel='Epoch',title='Student top-1 vs privileged teacher',ylim=(0,1))
    for ax in axes: ax.legend(); ax.grid(alpha=.2)
    fig.savefig(HERE/'fit-curves.png',dpi=160)
    plt.close(fig)
    outcome = results['evaluation']
    first, last = results['heldout_initial'], results['heldout_final']
    ci = outcome['paired_bootstrap_95ci']
    lines = [
        '# SRP DAgger pilot result', '',
        f"One iteration from s2902 at 1M: {len(games)} complete games, {labels:,} privileged SRP labels, "
        'beta 0.5, public-v4 student inputs, 32/8 game split. Three epochs of recurrent CE plus '
        '0.1 KL(student || initial), learning rate 1e-5. Full-prefix BC was used because the '
        'TBPTT report leaves learning-quality acceptance unproven.', '',
        f"Held-out CE: {first['ce']:.4f} → {last['ce']:.4f}. Exact top-1 agreement: "
        f"{first['agreement']:.2%} → {last['agreement']:.2%} on {last['labels']:,} labels. "
        f"Final play agreement is {last['play_agreement']:.2%}; wait agreement is {last['wait_agreement']:.2%}. "
        'Lower CE alone does not establish successful action imitation.', '',
        f"Fresh paired evaluation (seed base 770031): initial {outcome['initial_wins']}/192 wins; "
        f"fine-tuned {outcome['final_wins']}/192. Mean match-score change {outcome['score_difference']:+.2%}, "
        f"95% paired bootstrap interval [{ci[0]:+.2%}, {ci[1]:+.2%}]. "
        f"Exact two-sided sign-flip p={outcome['paired_exact_sign_flip_p']:.6g}, clustered over 96 deck/seat pairs. "
        'These are matched games against public scripts, not student head-to-head games.', '',
        '| Cell | Initial wins | Fine-tuned wins | Games |',
        '|---|---:|---:|---:|',
        *[f"| {c['cell']} | {c['initial_wins']} | {c['final_wins']} | 32 |" for c in outcome['cells']], '',
        f"Completed-label planner cost was {cpu:,.1f} core-seconds across {len(native)} native games. "
        f"The native sample contains {native_calls} calls at {native_per_call:.5f} core-seconds/call. "
        f"A 300-game iteration projects to {projected_planner_cpu/3600:.2f} planner core-hours, "
        f"{projected_collection_cpu/3600:.2f} total collection core-hours, and "
        f"{results['projected_300_core_hours_with_cached_baseline']:.2f} core-hours including linearly scaled BC "
        f"and one 192-game evaluation ({results['projected_300_core_hours_with_two_evaluations']:.2f} "
        'with a newly evaluated baseline). These are CPU estimates, not wall-time guarantees. '
        'QA replay and all archived noncanonical work are excluded from pilot timing.', '',
        'Game 032 initially stopped at the strict source-hash guard after the native backend was added. '
        'The unchanged Python methods were audited and the retry completed. The coordinator later found '
        'two noncanonical P16 data values. The entire previous cohort, fit and evaluations were archived '
        'and excluded. This replacement pilot uses canonical data and native collection throughout; '
        'both initial and final evaluations were regenerated.', '',
        f"The canonical complete-game backend check matched {results['native_parity']['labels']} teacher labels, "
        f"{results['native_parity']['decisions']} mixed-policy actions, public observations and masks. "
        f"Root score differences: {len(parity['root_score_differences'])}, maximum absolute difference {score_error:.8g}. "
        'Only hard labels were used; any score mismatch remains open for future soft targets. '
        'SRP remains privileged, and this one-seed, 40-game pilot is limited evidence.', '',
        '![Fit curves](fit-curves.png)', '',
        'Receipts: results.json, fit.json, fit-curves.json, fit-batches.jsonl, verification.json, '
        'native-parity.json, native-runtime.json and completion.json. Exact commands and owned PIDs are in PROGRESS.md.',
    ]
    (HERE/'RESULTS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(results,indent=2),flush=True)

if __name__ == '__main__': main()
