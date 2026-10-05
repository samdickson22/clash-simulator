"""Analyze only a complete registered evaluation; preserve unknown acceptance."""
import bisect,gzip,hashlib,json,time
from pathlib import Path
import numpy as np
H=Path(__file__).resolve().parent

def load(path):return json.loads(path.read_text())
def rows(path):
    with (gzip.open(path,'rt') if path.suffix=='.gz' else path.open()) as f:return [json.loads(l) for l in f]
def summary(a):
    a=[x for x in a if x is not None]
    return dict(n=len(a),p50=float(np.quantile(a,.5)),p95=float(np.quantile(a,.95)),p99=float(np.quantile(a,.99)),max=float(max(a))) if a else dict(n=0)
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n')
def ci(d,schedule):
    rng=np.random.default_rng(1967100103);sums=np.zeros(10000)
    for family in sorted({x['family'] for x in schedule}):
        inds=np.array([i for i,x in enumerate(schedule) if x['family']==family])
        sums+=np.asarray(d)[rng.choice(inds,(10000,len(inds)),replace=True)].sum(axis=1)
    return np.quantile(sums/len(d),[.025,.975]).tolist()

def perception_audit(ds, pub, truth, folder, names, loader):
    """Descriptive time-aligned diagnostics, separate from registered outcomes.

    Native objects have no visibility labels. Unmatched objects therefore are
    missing from predictions, not proven visible-object detector misses.
    """
    from scipy.optimize import linear_sum_assignment
    frames={p['frame_id']:p for p in pub};times=[t['time'] for t in truth]
    counts=dict(aligned_decisions=0,unaligned_decisions=0,hand_slots=0,
        wrong_hand_slots=0,unknown_hand_slots=0,body_truth=0,body_predictions=0,
        body_matches=0,body_identity_disagreements=0,body_identity_unresolved=0,
        body_hp_missing=0,king_predictions=0,king_hp_missing=0)
    elixir=[];hp=[]
    body_names={i:(loader.get_card(n)._raw_entry.get('summonCharacterData') or {}).get('name',loader.get_card(n).name)
                for i,n in names.items()}
    for d in ds:
        j=bisect.bisect_right(times,d['capture_received_mono'])-1
        if j<0 or d['capture_received_mono']-times[j]>.25:
            counts['unaligned_decisions']+=1;continue
        counts['aligned_decisions']+=1
        frame=frames[d['frame_id']]['public'];state=truth[j]['observation']
        own=next(p for p in state['players'] if p['owner']==1)
        actual={c['handIndex']:names.get(c['cardId']) for c in own['hand']}
        for slot,card in enumerate(frame['own_hand']):
            if slot not in actual:continue
            counts['hand_slots']+=1
            if not card:counts['unknown_hand_slots']+=1
            elif card!=actual[slot]:counts['wrong_hand_slots']+=1
        if frame['own_elixir'] is not None:elixir.append(abs(frame['own_elixir']-own['elixir']))
        for e in frame['entities']:
            if e['card']=='KingTower':
                counts['king_predictions']+=1;counts['king_hp_missing']+=e['hp_fraction'] is None
        predicted=[e for e in frame['entities'] if e['card'] not in ('Tower','KingTower') and e['kind'] in ('troop','building')]
        objects=[o for o in state['objects'] if o['cardId']!=-1 and o['hp'] is not None and o['hp']>0]
        counts['body_truth']+=len(objects);counts['body_predictions']+=len(predicted)
        costs=np.full((len(predicted),len(objects)),1e6)
        for i,e in enumerate(predicted):
            for k,o in enumerate(objects):
                distance=float(np.hypot(e['x_tiles']-o['x']/1000,e['y_tiles']-o['y']/1000))
                if e['player_id']==o['owner'] and distance<=1:costs[i,k]=distance
        if costs.size:
            ii,jj=linear_sum_assignment(costs)
            for i,k in zip(ii,jj):
                if costs[i,k]>=1e6:continue
                e,o=predicted[i],objects[k];counts['body_matches']+=1
                expected=body_names.get(o['cardId'])
                if expected is None:counts['body_identity_unresolved']+=1
                elif e['card']!=expected:counts['body_identity_disagreements']+=1
                if e['hp_fraction'] is None:counts['body_hp_missing']+=1
                elif o['maxHp'] and o['maxHp']>0:hp.append(abs(e['hp_fraction']-o['hp']/o['maxHp']))
    counts['body_unmatched_truth']=counts['body_truth']-counts['body_matches']
    counts['body_unmatched_predictions']=counts['body_predictions']-counts['body_matches']
    counts['own_elixir_absolute_errors']=elixir;counts['body_hp_absolute_errors']=hp
    # Use the same conservative 500 ms event window as L1, on evaluator time
    # brackets. No per-frame truth was fed back into the running actor.
    origin=float(np.median([d['capture_received_mono']-frames[d['frame_id']]['timestamp_ms']/1000 for d in ds])) if ds else None
    predicted_events=[(origin+f['timestamp_ms']/1000,e['card']) for f in pub for e in f['public']['play_events'] if e['player_id']==0] if origin is not None else []
    opfile=folder/'opponent-actions.jsonl';ops=rows(opfile) if opfile.exists() else []
    ticks=[t['observation']['tick'] for t in truth];events=[];unknown=failed=0
    for op in ops:
        receipt=op['receipt']
        if receipt['state']!='succeeded':failed+=1;continue
        tick=receipt['executeTick'];j=bisect.bisect_left(ticks,tick)
        if j==0 or j>=len(ticks):unknown+=1;continue
        events.append((times[j-1],times[j],op['card']))
    costs=np.full((len(predicted_events),len(events)),1e6)
    for i,(t,card) in enumerate(predicted_events):
        for j,(lo,hi,actual) in enumerate(events):
            if card==actual and t>=hi and t-lo<=.5:costs[i,j]=t-lo
    matches=0
    if costs.size:
        ii,jj=linear_sum_assignment(costs);matches=sum(costs[i,j]<1e6 for i,j in zip(ii,jj))
    counts.update(opponent_successes_bracketed=len(events),opponent_successes_unbracketed=unknown,
        opponent_failed_receipts=failed,opponent_event_predictions=len(predicted_events),
        opponent_events_matched_500ms=int(matches),opponent_events_missed_500ms=len(events)-int(matches))
    return counts

def main():
    schedule=load(H/'schedule.json')['matches'];native=[];sim=[];decisions=[];audit=[];examples=[];derived=[];gaps=[];frame_count=0;frame_seconds=0.;observation_skips=[];skip_episodes=[];perception=[]
    assert len(schedule)==48 and {e['pair'] for e in schedule}==set(range(48))
    for ep in schedule:
        name=f"pair-{ep['pair']:02d}";n=load(H/'native'/f'{name}.json');s=load(H/'simulator'/f'{name}.json')
        assert n['terminal'] and s['terminal'] and n['seed']==s['seed']==ep['seed']
        assert n['decks']==s['decks']==ep['decks']
        allowed_manifests={hashlib.sha256(p.read_bytes()).hexdigest() for p in [H/'manifest.json',*list((H/'manifests').glob('*.json'))] if 'files' in load(p)}
        assert n['source_manifest'] in allowed_manifests and s['source_manifest'] in allowed_manifests
        native.append(n);sim.append(s)
        folder=H/'native'/name;dp=folder/'decisions.jsonl';ds=rows(dp) if dp.exists() else []
        sp=folder/'observation-skips.jsonl'
        skipped=rows(sp) if sp.exists() else []
        observation_skips.extend(skipped)
        if skipped:skip_episodes.append(ep['pair'])
        assert len(ds)==n['decisions']
        decisions.extend(ds)
        truth=rows(folder/'evaluation-only.jsonl.gz');times=[o['time'] for o in truth]
        pub=rows(folder/'public-frames.jsonl.gz');frames={p['frame_id']:p for p in pub}
        gaps.extend(b['timestamp_ms']-a['timestamp_ms'] for a,b in zip(pub,pub[1:]));frame_count+=len(pub);frame_seconds+=(pub[-1]['timestamp_ms']-pub[0]['timestamp_ms'])/1000
        moves=[d for d in ds if d['action']<2304]
        # Names come from registered deck data and public card metadata, never prediction matching.
        import sys,os
        sys.path.insert(0,str(H/'runtime/src'));os.environ['CLASHER_ROOT']=str(H.parents[3])
        from clasher.data import CardDataLoader
        loader=CardDataLoader();names={loader.get_card(c)._raw_entry['id']:c for deck in ep['decks'] for c in deck}
        perception.append(dict(pair=ep['pair'],**perception_audit(ds,pub,truth,folder,names,loader)))
        for i,d in enumerate(moves):
            before_time=d['action_submit_mono']-d['tap_ms']/1000
            pi=bisect.bisect_right(times,before_time)-1
            ai=bisect.bisect_left(times,d['action_submit_mono']+.15)
            next_time=(moves[i+1]['action_submit_mono']-moves[i+1]['tap_ms']/1000) if i+1<len(moves) else float('inf')
            result='unknown';wrong=None;actual=None;unaffordable=None;reason='missing unambiguous bracket'
            if pi>=0 and ai<len(truth) and times[ai]<next_time and before_time-times[pi]<.75:
                before=truth[pi]['observation'];after=truth[ai]['observation']
                bp=next(p for p in before['players'] if p['owner']==1);ap=next(p for p in after['players'] if p['owner']==1)
                bc=next((c for c in bp['hand'] if c['handIndex']==d['slot']),None)
                ac=next((c for c in ap['hand'] if c['handIndex']==d['slot']),None)
                if bc is not None:
                    actual=names.get(bc['cardId'],str(bc['cardId']));wrong=actual!=d['chosen_card'];unaffordable=bp['elixir']<bc['cost']
                    changed=ac is None or ac['cardId']!=bc['cardId']
                    regen=sum(int(500/(.93 if t>4800 else 1.4 if t>2400 else 2.8))/10000 for t in range(before['tick']+1,after['tick']+1))
                    spend=bp['elixir']+regen-ap['elixir']
                    if changed and spend>=bc['cost']-.1:result='confirmed';reason='slot changed and cost paid'
                    elif not changed and spend<.1 and after['tick']>=before['tick']+4:result='rejected';reason='slot unchanged and no cost paid after native advance'
                    else:reason='conflicting slot/cost evidence'
                    if (wrong or unaffordable) and len(examples)<15:
                        f=frames[d['frame_id']]['public']
                        examples.append(dict(pair=ep['pair'],family=ep['family'],frame=d['frame_id'],action=d['action'],tile=d['tile'],
                            chosen_card=d['chosen_card'],actual_slot_card=actual,predicted_elixir=f['own_elixir'],actual_pre_tap_elixir=bp['elixir'],
                            actual_cost=bc['cost'],result=result,wrong_card=wrong,unaffordable=unaffordable,
                            artifact=str(folder.relative_to(H)),interpretation='temporal association, not a causal counterfactual'))
            audit.append(dict(pair=ep['pair'],frame=d['frame_id'],result=result,reason=reason,wrong_card=wrong,actual_card=actual,unaffordable=unaffordable))
        for d in ds:
            if 'opponent' not in d['diag']:continue
            j=bisect.bisect_right(times,d['capture_received_mono'])-1
            if j<0:continue
            actual=next(p for p in truth[j]['observation']['players'] if p['owner']==0)['elixir'];est=d['diag']['opponent'];lo,hi=est['elixir_interval_90']
            derived.append(dict(error=abs(actual-est['elixir_mean']),covered=lo<=actual<=hi,width=hi-lo))
    nw=np.array([r['win'] for r in native]);sw=np.array([r['win'] for r in sim]);delta=nw-sw
    ns=np.array([r['score'] for r in native]);ss=np.array([r['score'] for r in sim])
    acts=[d for d in decisions if d['action']<2304]
    rejection={k:sum(r['result']==k for r in audit) for k in ['confirmed','rejected','unknown']}
    measured=rejection['confirmed']+rejection['rejected']
    pixel_known=[n for n in native if n['pixel_result']['winner']!='unknown']
    stats=dict(pairs=len(native),native=dict(wins=int(nw.sum()),draws=sum(r['winner'] is None for r in native),win_rate=float(nw.mean()),score=float(ns.mean())),
        simulator=dict(wins=int(sw.sum()),draws=sum(r['winner'] is None for r in sim),win_rate=float(sw.mean()),score=float(ss.mean())),
        paired_win_difference=float(delta.mean()),paired_win_ci95=ci(delta,schedule),paired_score_difference=float((ns-ss).mean()),paired_score_ci95=ci(ns-ss,schedule),
        latency_all_ms=summary([d['production_to_action_ms'] for d in decisions]),latency_deploy_ms=summary([d['production_to_action_ms'] for d in acts]),
        receive_latency_all_ms=summary([d['receive_to_action_ms'] for d in decisions]),receive_latency_deploy_ms=summary([d['receive_to_action_ms'] for d in acts]),tap_ms=summary([d['tap_ms'] for d in acts]),
        recorded_search_ms=summary([d['diag']['search_ms'] for d in decisions if 'search_ms' in d['diag']]),
        search_over_200_ms=sum(d['diag'].get('search_ms',0)>200 for d in decisions),
        attempts=len(acts),rejection=rejection,rejection_rate_known=rejection['rejected']/measured if measured else None,
        wrong_slot_card=sum(x['wrong_card'] is True for x in audit),unaffordable=sum(x['unaffordable'] is True for x in audit),
        attempts_per_game_minute=len(acts)/(sum(n['native_tick'] for n in native)/1200),
        attempts_per_wall_minute=len(acts)/(sum(n['seconds'] for n in native)/60),
        pixel_end_detected=sum(n['pixel_end_detected'] for n in native),pixel_result_known=len(pixel_known),
        pixel_result_correct=sum(n['pixel_result']['winner']==n['winner'] for n in pixel_known),
        opponent_elixir=dict(n=len(derived),mae=float(np.mean([d['error'] for d in derived])),coverage=float(np.mean([d['covered'] for d in derived])),mean_interval_width=float(np.mean([d['width'] for d in derived]))) if derived else None,
        opponent_observation_skips=len(observation_skips),opponent_skip_episodes=skip_episodes,maximum_coherent_state_gap_s=max([x['seconds_without_coherent_state'] for x in observation_skips],default=0.),processed_fps=frame_count/frame_seconds,frame_gaps_ms=summary(gaps),temporal_reset_gaps=sum(g>300 for g in gaps),observed_native_ticks_per_wall_second=summary([(n['native_tick']-220)/n['seconds'] for n in native]),native_ticks=sum(n['native_tick'] for n in native),families={},styles={},L3_ready=False,
        qualification='whole adapted pixel-loop comparison across different engines; no pure perception causal claim')
    for key,target in [('family','families'),('style','styles')]:
        for v in sorted({e[key] for e in schedule}):
            inds=[i for i,e in enumerate(schedule) if e[key]==v]
            stats[target][v]=dict(n=len(inds),native_wins=int(nw[inds].sum()),sim_wins=int(sw[inds].sum()),difference=float(delta[inds].mean()))
    diagnostic={k:sum(p[k] for p in perception) for k in perception[0] if k not in ('pair','own_elixir_absolute_errors','body_hp_absolute_errors')}
    for key in ('own_elixir_absolute_errors','body_hp_absolute_errors'):
        values=[v for p in perception for v in p[key]]
        diagnostic[key]=dict(**summary(values),mean=float(np.mean(values)) if values else None)
    diagnostic['method']='Descriptive only: previous coherent observation within 250 ms of frame reception; same-owner body matching within one tile. Native visibility is unknown. Identity uses native card summon metadata, which can alias spawned or transformed bodies. Events require prediction after the upper observed execution-time bound and within 500 ms of the lower bound.'
    stats['perception_audit']=diagnostic
    for arm in ('native','simulator'):stats[arm]['losses']=len(native)-stats[arm]['wins']-stats[arm]['draws']
    stats['gates']=dict(full_pairs=len(native)==48,noninferiority=stats['paired_win_ci95'][0]>=-.10,
        latency_p99=stats['latency_all_ms']['p99']<=400,search_deadline=stats['search_over_200_ms']==0,
        pixel_lifecycle=stats['pixel_end_detected']==48 and stats['pixel_result_known']==48 and stats['pixel_result_correct']==48,
        calibrated_uncertainty_interface=False,L1_certification=False)
    write(H/'metrics.json',stats);write(H/'action-audit.json',audit);write(H/'failure-examples.json',examples);write(H/'perception-audit.json',diagnostic)
    pins=load(H/'manifest.json')['files'];drift=[]
    for p,want in pins.items():
        with open(p,'rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=want:drift.append(p)
    retained=load(H/'recovery-t3-restart/completed-receipt-pins.json')
    retained_drift=[p for p,want in retained.items() if hashlib.sha256((H/p).read_bytes()).hexdigest()!=want]
    assert not retained_drift,retained_drift
    assert load(H/'native/pair-17/opening-replay-check.json')['equal'] is True
    write(H/'final-audit.json',dict(pins=len(pins),drift=drift,pairs=48,manifest_sha256=hashlib.sha256((H/'manifest.json').read_bytes()).hexdigest(),
        retained_receipts_verified=len(retained),retained_receipt_drift=retained_drift,
        new_output_bytes=sum(p.stat().st_size for p in H.rglob('*') if p.is_file()),completed=time.time()))
    assert not drift,drift
    def fmt(d):return ' / '.join(f"{d[k]:.1f}" for k in ['p50','p95','p99','max'])
    text=f'''# L2 results

L3 readiness: NOT READY.

All {len(native)} registered native matches and {len(sim)} clean simulator matches reached terminal states. The actor consumed sanitized pixels only. ADB taps used the existing touch hook's 1080x1920 input mapping on the 1080x2280 display. The scripted opponent used probe action submission; probe observations were restricted to opponent control and segregated evaluator evidence.

## Paired outcomes

Pixel wins {int(nw.sum())}/48 ({nw.mean():.1%}); simulator wins {int(sw.sum())}/48 ({sw.mean():.1%}). Draws: {stats['native']['draws']} native, {stats['simulator']['draws']} simulator. Losses: {stats['native']['losses']} native, {stats['simulator']['losses']} simulator. Paired win-rate difference {delta.mean():+.1%}, 95% family-stratified paired bootstrap CI [{stats['paired_win_ci95'][0]:+.1%}, {stats['paired_win_ci95'][1]:+.1%}]. The registered noninferiority margin is -10 percentage points. Score counting draws as half: {ns.mean():.4f} native versus {ss.mean():.4f} simulator.

Seeds, decks and native opening hand/queue order are paired. Native and simulator engines/RNG, transport delay, opponent sensor conversion and command lead differ. The estimate measures the full L2 adaptation and these execution differences; it cannot isolate perception error causally. Family/style splits are in metrics.json. The clean C56 prior is the three registered deck multisets; the pixel posterior uses its broader public card roster. This additional belief-model difference is part of the adapter comparison, not a controlled perception-only ablation.

## Latency and actions

Screenshot-production-to-submission p50 / p95 / p99 / max, all decisions: {fmt(stats['latency_all_ms'])} ms. Deployments only: {fmt(stats['latency_deploy_ms'])} ms. Capture reception to submission, all decisions: {fmt(stats['receive_latency_all_ms'])} ms; deployments: {fmt(stats['receive_latency_deploy_ms'])} ms. The existing L1 timestamp measures screenshot production and is not certified compositor-to-native-tick timing. Explicit pregame perception warmup is excluded; any remaining policy/search first-use cost stays in the measured decisions. Wait decisions remain in the all-decision denominator. Observed native progress, despite nominal speed 1, had median {stats['observed_native_ticks_per_wall_second']['p50']:.2f} and p95 {stats['observed_native_ticks_per_wall_second']['p95']:.2f} ticks per wall second. Slower native progress changes game-time control cadence relative to the simulator's ten-tick decisions and is another execution limitation.

{len(acts)} deployment attempts, {stats['attempts_per_game_minute']:.2f} per native game minute and {stats['attempts_per_wall_minute']:.2f} per wall minute. Evaluator slot-change plus cost evidence confirms {rejection['confirmed']}, rejects {rejection['rejected']}, and leaves {rejection['unknown']} unknown. Unknown windows are not accepted or discarded. Known-window rejected fraction: {stats['rejection_rate_known']:.1%}. Search p50 / p95 / p99 / max: {fmt(stats['recorded_search_ms'])} ms. Deployment tap time: {fmt(stats['tap_ms'])} ms. Search exceeded its cooperative 200 ms deadline on {stats['search_over_200_ms']} recorded decisions.

## Failure analysis and readiness

Processed perception cadence was {stats['processed_fps']:.2f} FPS, with {stats['temporal_reset_gaps']} frame gaps above 300 ms. The v3 temporal detector clears its short image history across such gaps. Capture runs concurrently, but perception, search and tapping share the actor loop, so this is a concrete integration cost compared with L1's standalone stream evaluation. No causal loss attribution is claimed.

{stats['wrong_slot_card']} audited attempts disagreed with the native pre-tap slot identity. This can include card-classification error, refill/render lag and capture-to-action staleness; it is not a classifier-only error count. {stats['unaffordable']} attempts were unaffordable in the pre-tap observation. failure-examples.json links predicted card/elixir, actual slot/cost and rejection evidence. These are temporal associations, not proven counterfactual causes of a loss. Derived opponent-elixir diagnostics are in metrics.json; no recalibration used these games.

The descriptive perception audit aligned {diagnostic['aligned_decisions']} decisions to a coherent native observation no more than 250 ms old. Across {diagnostic['hand_slots']} compared hand slots, {diagnostic['wrong_hand_slots']} disagreed and {diagnostic['unknown_hand_slots']} abstained. Own-elixir absolute error averaged {diagnostic['own_elixir_absolute_errors']['mean']:.3f}. Snapshot lag remains part of these measurements.

Same-owner spatial matching within one tile left {diagnostic['body_unmatched_truth']}/{diagnostic['body_truth']} native body instances unmatched across sampled decision frames. Of {diagnostic['body_matches']} matched bodies, {diagnostic['body_identity_disagreements']} disagreed with native summon-card metadata, {diagnostic['body_identity_unresolved']} lacked a resolved identity, and {diagnostic['body_hp_missing']} had no predicted HP. These counts repeat persistent objects across frames. Native visibility is not labeled, so unmatched bodies are not certified visible-object misses. Spawned or transformed bodies can also alias native card metadata. King HP was absent on {diagnostic['king_hp_missing']}/{diagnostic['king_predictions']} King predictions. HP error summaries and the matching definition are in perception-audit.json.

The audit matched {diagnostic['opponent_events_matched_500ms']}/{diagnostic['opponent_successes_bracketed']} bracketed successful opponent deployments to same-card public events within the conservative 500 ms window, leaving {diagnostic['opponent_events_missed_500ms']} missed or late. Another {diagnostic['opponent_successes_unbracketed']} successful receipts lacked a time bracket and remain unscored. This uses evaluator execution-time brackets and frame reception, not certified render timing; it is a descriptive failure diagnostic.

The opponent/evaluator had {stats['opponent_observation_skips']} coherent-read timeouts across {len(skip_episodes)} matches; maximum logged gap {stats['maximum_coherent_state_gap_s']:.2f} seconds. The unchanged coherence fence rejected those reads. Retrying them delayed opponent opportunities, so this is an explicit confound in the native-versus-simulator comparison and cannot support a clean noninferiority claim by itself.

Pixel end detection fired for {stats['pixel_end_detected']}/48 matches. The provisional pixel result reader returned a result for {len(pixel_known)}/48 and was correct on {stats['pixel_result_correct']}; equal-count/tiebreak states remain unknown. Native terminal labels are evaluator outcomes, not actor inputs. This fails the complete pixel lifecycle/result requirement.

The unmodified public scripts require certain inputs. L2 scored a declared conditional point model while retaining measured confidence in original frame logs. Missing HP uses a last-value/full-health prior; L1 never reads King HP. Own unseen queues are modeled; opponent state uses the noisy v3 posterior. This interface is an experimental adaptation and has not become a calibrated uncertainty-aware controller. L1's failed event, placement and frame-timing gates remain unresolved. No official-client readiness is established. Individual gate results are recorded in metrics.json; all gates are required, and passing a strength gate alone cannot change this verdict.

## Evidence and preservation

PREREG.md, schedule.json, seed-audit.json and manifest.json precede the replacement evaluation. interrupted-r1 preserves one native terminal, two simulator terminals and a partial native game from the first transport attempt. It stopped on adb SIGABRT before any aggregate strength inspection; the posix_spawn repair and fresh replacement seeds were registered before run 2. During run 2, an externally lost adb forward interrupted pair 5 after five completed native games. recovery-forward preserves that partial trajectory; the completed pairs were retained, and the same incomplete seed was replayed after a preregistered read-only reconnect repair. manifests/ retains the source versions. A subsequent startup-only attempt had three intro frames and zero decisions; the start-before-end lifecycle guard was corrected prospectively, with that attempt preserved in recovery-startup. recovery-observation preserves a later incomplete two-second read-window timeout; the prospective bounded read-retry amendment keeps the original coherence fence and reports missed opponent opportunities. Exact opening equality is recorded for the technical replay. recovery-wall-time preserves a 400-second attempt stopped at tick 4155 while the clock still showed 1:33 overtime; the wall allowance alone was extended to 1200 seconds before the same incomplete seed was replayed. A T3 restart on October 5 also killed the emulator and workers during native pair 17. recovery-t3-restart preserves that valid but incomplete trajectory, old launch receipts, completed-receipt hashes and the incident audit. All 17 native and 18 simulator completed receipts were retained. The offline emulator restarted with the same settings and pinned attestation, IPv4/IPv6 UID blocking and dedicated adb server port 5041. Native pair 17 passed exact opening equality before its same-seed replay. No completed outcome was replaced. native/ contains compressed PublicVisionFrame and evaluator-only streams, action timestamps, limited sanitized images and terminal receipts. simulator/ holds the clean full-game receipts. Four actor-boundary checks cover masked-HUD invariance, confidence preservation, denied file/socket reads during actor decisions and seed balance/disjointness. Five additional recovery checks cover owned-forward handling, mutation replay safety and the start-before-end guard. final-audit.json checks all pinned sources and the output cap.

All task writes are confined to live-loop/l2, including a frozen local Python source copy with a relocated helper root. Shared engine, gamedata, engine-rs, pilot and c56 sources were not edited. One owned offline emulator was used with app UID networking rejected; no official client or foreign process was touched. See PROGRESS.md for excluded smoke attempts and completion/cleanup receipts.
'''
    (H/'RESULTS.md').write_text(text)
    print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
