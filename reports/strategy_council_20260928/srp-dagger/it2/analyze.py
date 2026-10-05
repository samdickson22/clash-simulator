"""Behavior and matched evaluation statistics without changing the evaluator."""
import sys,json
from pathlib import Path
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import kit
from kit import np
OUT=Path(__file__).resolve().parent

def behavior(folder):
    rows=[];games=[]
    for p in sorted(folder.glob('*.decisions.json')):
        cell=p.name.split('.decisions')[0]
        for r in json.loads(p.read_text()):r['cell']=cell;rows.append(r)
    for p in sorted(folder.glob('*.games.json')):games+=json.loads(p.read_text())
    plays=[r for r in rows if not r['is_no_op'] and not r['is_ability']];playable=[r for r in rows if r['legal_action_count']>1]
    cards=Counter(r['hand'][r['slot']] for r in plays)
    def entropy(counts):
        p=np.asarray(list(counts.values()),float);p/=p.sum();return float(-(p*np.log(p)).sum())
    tiles=Counter(r['candidate_action']%576 for r in plays)
    return dict(games=len(games),decisions=len(rows),plays=len(plays),plays_per_game=len(plays)/len(games),plays_per_1000_ticks=len(plays)/sum(g['ticks'] if 'ticks' in g else 0 for g in games)*1000 if games and 'ticks' in games[0] else None,playable_decisions=len(playable),wait_rate_when_playable=sum(r['is_no_op'] for r in playable)/len(playable),location_entropy_nats=entropy(tiles),location_entropy_definition='empirical sampled canonical tile histogram, conditional on play',per_card_location_entropy={c:entropy(Counter(r['candidate_action']%576 for r in plays if r['hand'][r['slot']]==c)) for c in cards},card_counts=dict(cards),card_mix={c:n/len(plays) for c,n in cards.items()},elixir_at_play_mean=float(np.mean([r['elixir'] for r in plays])),elixir_at_play_median=float(np.median([r['elixir'] for r in plays])),win_count=sum(g['outcome']=='win' for g in games))

def compare(oldfolder,newfolder,n):
    cells=[];pairs=[];win0=win1=0
    for role in ('holdout','hog26'):
        for style in ('balanced','pressure','defense'):
            cell=f'{role}-nominal-{style}';old=json.loads((oldfolder/f'{cell}.games.json').read_text());new=json.loads((newfolder/f'{cell}.games.json').read_text());assert len(old)==len(new)==n
            sa=json.loads((oldfolder/f'{cell}.json').read_text());sb=json.loads((newfolder/f'{cell}.json').read_text())
            for key in ('seed','decision_interval_ticks','max_ticks','deterministic','gamedata_sha256','model_config_sha256','public_contract_version','public_script_style','opponent_mode','opponent_strategy','opponent_checkpoint_sha256','reward_profile','level_mode','sampling_temperature','paired_asymmetric_matchups','mirror_match','location_lookahead','candidate_sampling_decks_sha256','opponent_sampling_decks_sha256'):assert sa[key]==sb[key],(cell,key)
            assert sa['checkpoint_sha256']==kit.sha(kit.INITIAL); assert sb['checkpoint_sha256']==kit.sha(OUT/'student.pt')
            diffs=[]
            for a,b in zip(old,new):
                for key in ('game','matchup','matchup_seed','candidate_player','candidate_deck','opponent_deck','candidate_card_levels','opponent_card_levels','candidate_tower_level','opponent_tower_level'):assert a[key]==b[key],(cell,key)
                assert a['terminated'] and b['terminated'] and not a['truncated'] and not b['truncated']
                score={'win':1.,'draw':.5,'loss':0.};diffs.append(score[b['outcome']]-score[a['outcome']])
            w0=sum(g['outcome']=='win' for g in old);w1=sum(g['outcome']=='win' for g in new);win0+=w0;win1+=w1
            cells.append(dict(cell=cell,initial_wins=w0,final_wins=w1,games=n,score_difference=float(np.mean(diffs))))
            pairs.extend(np.asarray(diffs).reshape(-1,2).mean(-1).tolist())
    pairs=np.asarray(pairs);rng=np.random.default_rng(980034);boots=pairs[rng.integers(0,len(pairs),(20000,len(pairs)))].mean(-1)
    counts={0:1}
    for mag in np.rint(np.abs(pairs)*4).astype(int):
        nxt={}
        for v,count in counts.items():
            for sign in (-1,1):nxt[v+sign*int(mag)]=nxt.get(v+sign*int(mag),0)+count
        counts=nxt
    observed=abs(round(pairs.sum()*4));p=sum(count for v,count in counts.items() if abs(v)>=observed)/2**len(pairs)
    return dict(cells=cells,initial_wins=win0,final_wins=win1,games=6*n,score_difference=float(pairs.mean()),paired_bootstrap_95ci=np.quantile(boots,[.025,.975]).tolist(),paired_exact_sign_flip_p=p,matchup_pairs=len(pairs),gate_passed=bool(pairs.mean()>=0 and win1>=win0))

def diagnosis():
    d=json.loads((OUT/'diagnostics.json').read_text());b={name:behavior(OUT/'evaluation'/folder) for name,folder in [('initial','diagnostic-initial'),('it1','diagnostic-it1')]};kit.write_json(OUT/'behavior.json',b)
    first,last=d['initial']['heldout'],d['it1']['heldout'];fmt=lambda key:f"{first[key]['mean']:.6g} -> {last[key]['mean']:.6g}"
    lines=['# Pilot regression diagnosis','',
    'The hard-label fit made the student play earlier and spend on cheap cards while learning little of the teacher\'s placement rule. The top-1 wait metric hid this change because the single wait action could remain the largest individual logit even after most probability mass moved to hundreds of play actions. Both evaluation and collection sample the distribution.',
    '', '## Label provenance', '',
    'Across 9,565 labels: 4,229 no-op labels, 1,722 script-choice/top-4 play labels, and 3,614 random-candidate play labels. Of 5,336 play labels, 32.27% came from the script and 67.73% from the random sample; no-op contributes 0% of play labels. Random provenance refers to the exact selected slot/tile action, including tiles independently sampled for different slots. Script membership includes the script\'s own choice and top four. Classification follows the planner\'s script-first deduplication. Reconstructed public packets were passed to the original script ranker for every labelled row. All chosen IDs occurred in stored root candidates.',
    '', '## Student probabilities and placement', '',
    'Held-out teacher-play rows, n=1,126. All metrics replay complete executed histories, including unsupervised context.', '',
    '| Metric | Initial -> fitted |','|---|---|',
    *[f'| {label} | {fmt(key)} |' for key,label in [('teacher_probability','Teacher action probability'),('wait_probability','Wait probability'),('teacher_slot_probability','Teacher card/slot marginal probability'),('argmax_slot_agreement','Full joint argmax card/slot agreement'),('conditional_play_slot_agreement','Card/slot agreement conditional on play'),('best_play_tile_distance','Best legal play tile distance, Euclidean tiles'),('teacher_slot_tile_distance','Best tile within teacher slot distance, Euclidean tiles')]],'',
    'The literal joint argmax is almost always wait, so its tile distance is undefined. The table reports the best legal play and the teacher-slot conditional tile distances instead. Hand slots hold distinct cards here, so slot and card agreement coincide. Median teacher-action probability rises from %.8f to %.8f.'%(first['teacher_probability']['median'],last['teacher_probability']['median']),
    '', '## Traced behavior', '',
    'Fresh canonical 24-game traced evaluation per checkpoint, four games in each of the six existing cells, seed base 770031. Counts are sampled submitted plays. Location entropy is empirical entropy of sampled canonical tiles, conditional on playing; it is not the policy distribution\'s entropy.', '',
    '| Metric | Initial | Fitted |','|---|---:|---:|',
    *[f'| {key} | {b["initial"][key]:.6g} | {b["it1"][key]:.6g} |' for key in ('win_count','plays_per_game','wait_rate_when_playable','location_entropy_nats','elixir_at_play_mean','elixir_at_play_median')], '',
    '| Card | Initial plays | Fitted plays | Initial share | Fitted share |','|---|---:|---:|---:|---:|',
    *[f'| {c} | {b["initial"]["card_counts"].get(c,0)} | {b["it1"]["card_counts"].get(c,0)} | {b["initial"]["card_mix"].get(c,0):.2%} | {b["it1"]["card_mix"].get(c,0):.2%} |' for c in sorted(set(b['initial']['card_counts'])|set(b['it1']['card_counts']))], '',
    'Cheap-card spending crowded out win conditions and support. Hog Rider fell from 8.65% to 1.46% of plays and Musketeer from 15.53% to 4.14%; the fitted student never played Giant or Prince in these 24 games. Teacher-play labels were at mean 2.451 elixir, median 2.250. The original fit label-weighted KL rose from 0.254 in epoch 1 to 1.675 nats in epoch 3. At coefficient 0.1 this contributed only 0.168 to the final-epoch average objective, versus CE 3.430.', '',
    '## Alignment and cause', '',
    d['tick_alignment'],
    'Eight teacher play labels were rerun live across both seats. Stored ticks, hands, public global features, teacher action IDs and decoded world tiles matched exactly. Saved labels round-trip through the environment\'s decode/encode. The same action IDs enter the native rollout and policy target. The previous full-game Python/native receipt also matched every label and action, with maximum leaf-score discrepancy 1.61e-5. No indexing, seat rotation, observation-tick or recurrent-history pipeline bug was found.', '',
    'Full-action hard CE treats each sampled winning random tile as the only correct action. It rewards increasing total play probability even when precise placement remains uncertain. Wait probability on teacher-play states fell by 59 percentage points and teacher card probability rose roughly twenty-fold, while tile distance improved by less than half a tile. The weak 0.1 anchor allowed this large behavioral change. The mixed teacher/student collection visits low-elixir states unlike the student\'s preferred timing; matching privileged greedy rollout decisions at those states changes spending behavior. Random-candidate label noise and unavailable privileged information limit the deterministic public mapping. The measurements support these mechanisms but do not individually isolate them causally.', '',
    'Evidence: it2/diagnostics.json, it2/behavior.json and it2/evaluation/diagnostic-{initial,it1}/. Original pilot fresh evaluation regressed 88/192 to 16/192, paired exact sign-flip p=1.38e-14. Iteration 2 tests candidate-conditioned soft targets with a full-distribution anchor and an advantage filter; it does not establish which intervention matters alone.'
    ]
    (kit.HERE/'DIAGNOSIS.md').write_text('\n'.join(lines)+'\n')
    return b
if __name__=='__main__':print(json.dumps(diagnosis(),indent=2))
