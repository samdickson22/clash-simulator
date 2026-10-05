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

def main():
    schedule=load(H/'schedule.json')['matches'];native=[];sim=[];decisions=[];audit=[];examples=[];derived=[]
    for ep in schedule:
        name=f"pair-{ep['pair']:02d}";n=load(H/'native'/f'{name}.json');s=load(H/'simulator'/f'{name}.json')
        assert n['terminal'] and s['terminal'] and n['seed']==s['seed']==ep['seed']
        assert n['decks']==s['decks']==ep['decks'] and n['source_manifest']==s['source_manifest']
        native.append(n);sim.append(s)
        folder=H/'native'/name;ds=rows(folder/'decisions.jsonl');decisions.extend(ds)
        truth=rows(folder/'evaluation-only.jsonl.gz');times=[o['time'] for o in truth]
        pub=rows(folder/'public-frames.jsonl.gz');frames={p['frame_id']:p for p in pub}
        moves=[d for d in ds if d['action']<2304]
        ids={c['d'] for deck in load(folder/'setup-evaluation-only.json')['config']['battle'].values() if isinstance(deck,dict) for c in deck.get('sp',[])}
        # Names come from registered deck data and public card metadata, never prediction matching.
        import sys,os
        sys.path.insert(0,str(H/'runtime/src'));os.environ['CLASHER_ROOT']=str(H.parents[3])
        from clasher.data import CardDataLoader
        loader=CardDataLoader();names={loader.get_card(c)._raw_entry['id']:c for deck in ep['decks'] for c in deck}
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
                    elif not changed and spend<.1:result='rejected';reason='slot unchanged and no cost paid'
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
        receive_latency_all_ms=summary([d['receive_to_action_ms'] for d in decisions]),tap_ms=summary([d['tap_ms'] for d in acts]),
        recorded_search_ms=summary([d['diag']['search_ms'] for d in decisions if 'search_ms' in d['diag']]),
        search_over_200_ms=sum(d['diag'].get('search_ms',0)>200 for d in decisions),
        attempts=len(acts),rejection=rejection,rejection_rate_known=rejection['rejected']/measured if measured else None,
        wrong_slot_card=sum(x['wrong_card'] is True for x in audit),unaffordable=sum(x['unaffordable'] is True for x in audit),
        attempts_per_game_minute=len(acts)/(sum(n['native_tick'] for n in native)/1200),
        attempts_per_wall_minute=len(acts)/(sum(n['seconds'] for n in native)/60),
        pixel_end_detected=sum(n['pixel_end_detected'] for n in native),pixel_result_known=len(pixel_known),
        pixel_result_correct=sum(n['pixel_result']['winner']==n['winner'] for n in pixel_known),
        opponent_elixir=dict(n=len(derived),mae=float(np.mean([d['error'] for d in derived])),coverage=float(np.mean([d['covered'] for d in derived])),mean_interval_width=float(np.mean([d['width'] for d in derived])) if derived else None,
        native_ticks=sum(n['native_tick'] for n in native),families={},styles={},L3_ready=False,
        qualification='whole adapted pixel-loop comparison across different engines; no pure perception causal claim')
    for key,target in [('family','families'),('style','styles')]:
        for v in sorted({e[key] for e in schedule}):
            inds=[i for i,e in enumerate(schedule) if e[key]==v]
            stats[target][v]=dict(n=len(inds),native_wins=int(nw[inds].sum()),sim_wins=int(sw[inds].sum()),difference=float(delta[inds].mean()))
    write(H/'metrics.json',stats);write(H/'action-audit.json',audit);write(H/'failure-examples.json',examples)
    pins=load(H/'manifest.json')['files'];drift=[]
    for p,want in pins.items():
        with open(p,'rb') as f:
            if hashlib.file_digest(f,'sha256').hexdigest()!=want:drift.append(p)
    write(H/'final-audit.json',dict(pins=len(pins),drift=drift,pairs=48,manifest_sha256=hashlib.sha256((H/'manifest.json').read_bytes()).hexdigest(),
        new_output_bytes=sum(p.stat().st_size for p in H.rglob('*') if p.is_file()),completed=time.time()))
    assert not drift,drift
    def fmt(d):return ' / '.join(f"{d[k]:.1f}" for k in ['p50','p95','p99','max'])
    text=f'''# L2 results

L3 readiness: NOT READY.

All {len(native)} registered native matches and {len(sim)} clean simulator matches reached terminal states. The actor consumed sanitized pixels only. ADB taps used the existing touch hook's 1080x1920 input mapping on the 1080x2280 display. The scripted opponent used probe action submission; probe observations were restricted to opponent control and segregated evaluator evidence.

## Paired outcomes

Pixel wins {int(nw.sum())}/48 ({nw.mean():.1%}); simulator wins {int(sw.sum())}/48 ({sw.mean():.1%}). Draws: {stats['native']['draws']} native, {stats['simulator']['draws']} simulator. Paired win-rate difference {delta.mean():+.1%}, 95% family-stratified paired bootstrap CI [{stats['paired_win_ci95'][0]:+.1%}, {stats['paired_win_ci95'][1]:+.1%}]. The registered noninferiority margin is -10 percentage points. Score counting draws as half: {ns.mean():.4f} native versus {ss.mean():.4f} simulator.

Seeds, decks and native opening hand/queue order are paired. Native and simulator engines/RNG, transport delay, opponent sensor conversion and command lead differ. The estimate measures the full L2 adaptation and these execution differences; it cannot isolate perception error causally. Family/style splits are in metrics.json.

## Latency and actions

Screenshot-production-to-submission p50 / p95 / p99 / max, all decisions: {fmt(stats['latency_all_ms'])} ms. Deployments only: {fmt(stats['latency_deploy_ms'])} ms. Capture reception to submission: {fmt(stats['receive_latency_all_ms'])} ms. The existing L1 timestamp measures screenshot production and is not certified compositor-to-native-tick timing. Pregame model warmup is excluded. Wait decisions remain in the all-decision denominator.

{len(acts)} deployment attempts, {stats['attempts_per_game_minute']:.2f} per native game minute and {stats['attempts_per_wall_minute']:.2f} per wall minute. Evaluator slot-change plus cost evidence confirms {rejection['confirmed']}, rejects {rejection['rejected']}, and leaves {rejection['unknown']} unknown. Unknown windows are not accepted or discarded. Known-window rejected fraction: {stats['rejection_rate_known']:.1%}. Search exceeded its cooperative 200 ms deadline on {stats['search_over_200_ms']} recorded decisions.

## Failure analysis and readiness

{stats['wrong_slot_card']} audited attempts chose a perceived card different from the actual tapped slot. {stats['unaffordable']} attempts were unaffordable in the pre-tap observation. failure-examples.json links predicted card/elixir, actual slot/cost and rejection evidence. These are temporal associations, not proven counterfactual causes of a loss. Derived opponent-elixir diagnostics are in metrics.json; no recalibration used these games.

Pixel end detection fired for {stats['pixel_end_detected']}/48 matches. The provisional pixel result reader returned a result for {len(pixel_known)}/48 and was correct on {stats['pixel_result_correct']}; equal-count/tiebreak states remain unknown. Native terminal labels are evaluator outcomes, not actor inputs. This fails the complete pixel lifecycle/result requirement.

The unmodified public scripts require certain inputs. L2 scored a declared conditional point model while retaining measured confidence in original frame logs. Missing HP uses a last-value/full-health prior; L1 never reads King HP. Own unseen queues are modeled; opponent state uses the noisy v3 posterior. This interface is an experimental adaptation and has not become a calibrated uncertainty-aware controller. L1's failed event, placement and frame-timing gates remain unresolved. No official-client readiness is established.

## Evidence and preservation

PREREG.md, schedule.json, seed-audit.json and manifest.json precede evaluation. native/ contains compressed PublicVisionFrame and evaluator-only streams, action timestamps, limited sanitized images and terminal receipts. simulator/ holds the clean full-game receipts. Four boundary checks cover masked-HUD invariance, confidence preservation, denied file/socket reads during actor decisions and seed balance/disjointness. final-audit.json checks all pinned sources and the output cap.

All task writes are confined to live-loop/l2, including a frozen local Python source copy with a relocated helper root. Shared engine, gamedata, engine-rs, pilot and c56 sources were not edited. One owned offline emulator was used with app UID networking rejected; no official client or foreign process was touched. See PROGRESS.md for excluded smoke attempts and completion/cleanup receipts.
'''
    (H/'RESULTS.md').write_text(text)
    print(json.dumps(stats,indent=2))
if __name__=='__main__':main()
