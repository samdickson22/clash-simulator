"""Rebuild the measured summary and cause index from completed game evidence."""
from collections import Counter
import hashlib
import html
import itertools
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

SPECS=[
 dict(key='inferno-retarget',scope='C56 card; mixed context',card='Inferno Tower',
      mechanic='Retarget/reload delay: native emits a 43-damage beam early',
      games=[202,291,377,429,440,458,498,533],
      values='Miner HP 1210 / 1167; Inferno cooldown before tick 0.410 / 0.010 s',
      rust='engine-cards/src/lib.rs:combat_one (non-ordinary building retarget/preload)',
      note='The native retarget-reset branch applies to Troop but skips non-ordinary Building. Python reset_attack_windup applies the building retarget delay. Mixed-game victims include C56 bodies and new-card bodies; C56-only status is not assumed without a reproduction.'),
 dict(key='xbow-clock',scope='C56 card; mixed context',card='X-Bow',
      mechanic='Attack clock/acquisition: an extra projectile is created one tick early',
      games=[124,317,361,373,520],values='next_id 236 / 237; X-Bow load remaining 50 / 300 ms after the tick',
      rust='engine-cards/src/lib.rs:combat_one; engine-cards/src/clock.rs:advance_with_load',
      note='Public projectile birth is the first difference. The equal prefix already has a 50 ms hit-timeline offset; native creates a shot while Python still has 50 ms loading work. Some contexts include stun, and some a first acquisition; these are grouped by the observed clock failure, not asserted to be one proven source-code fix.'),
 dict(key='dash-target-movement',scope='New-card interaction',card='Boss Bandit × Mighty Miner / Monk',
      mechanic='Movement keeps advancing toward a target that has just entered dash travel',
      games=[22,245,274,323],values='Mighty Miner y 19.628 / 19.568 (one extra 0.060-tile step)',
      rust='engine-cards/src/lib.rs:tick_once movement loop; dash.rs:dash_combat',
      note='Boss Bandit changes to travel in combat after another actor committed its movement target. Python revalidates that target in the movement component and stops; native spends the committed travel. Monk/Ice Spirit collision displacement also follows from this extra movement.'),
 dict(key='dragon-invalid-impact',scope='New-card interaction',card='Electro Dragon',
      mechanic='Chain hit hook fires for a launched Spirit or a primary killed earlier in the object phase',
      games=[16,86,336,460],values='Furnace HP 727 / 517; next_id 63 / 64',
      rust='engine-cards/src/lib.rs:tick_once projectile impact; c56.rs:dragon_chain_hit',
      note='Native checks the start-of-object-phase alive set before calling the hook. Python only notifies the source for a primary in the actual impact recipient set. The extra chain can damage a secondary or die immediately, leaving only a next_id difference.'),
 dict(key='mirror-barrel-level',scope='New-card interaction',card='Mirror × Skeleton Barrel',
      mechanic='Mirrored death-container children lose their level',games=[133,509],
      values='Seven Skeletons: HP 89 / 81 each',
      rust='engine-cards/src/c56.rs:bomb_tick (bomb_children lookup by bomb.stats.name)',
      note='Mirror exports level12:SkeletonBalloon child templates, but bomb_tick looks up the unqualified stats.name. It selects ordinary level-11 children instead of the mirrored payload key.'),
 dict(key='mega-long-distance',scope='New-card interaction',card='Mega Knight',
      mechanic='Normal melee splash is discarded at long distance despite the dash-capable exemption',
      games=[189,415],values='Little Prince HP 0 / 161; Royal Hogs differ by 268 HP in game 415',
      rust='engine-cards/src/lib.rs:combat_one (cancel-distance branch)',
      note='Both weapon clocks fire on the same tick; leap phase is idle. Python exempts direct area damage and dashCooldown characters from its long-distance discard. Native applies the generic distance cancellation and drops the normal melee payload. This is not a jump-landing-damage discrepancy.'),
 dict(key='poison-dash',scope='New-card interaction',card='Poison × Boss Bandit / Bandit',
      mechanic='Poison installs/refreshes slow and periodic damage while the target is dash-invulnerable',
      games=[75,416],values='Boss Bandit (x,y) (13.712,19.625) / (13.711,19.611); slow 1.00 / 0.85',
      rust='engine-cards/src/c56.rs:area_targets, c56_area_tick, periodic_tick',
      note='area_targets omits the dash-travel effect guard before installing area slows and periodic buffs. In game 75 Python has no slow while native retains 0.85 movement; game 416 later receives a native-only 92-damage Poison tick (Bandit HP 286 / 194).'),
 dict(key='valk-preload',scope='C56 card; mixed context',card='Valkyrie',
      mechanic='Legacy attack preload/retarget clock releases a melee hit early',games=[344],
      values='Goblin HP 202 / 0; Valkyrie cooldown before tick 0.200 / 0.050 s',
      rust='engine-cards/src/lib.rs:combat_one (legacy preload/retarget)',
      note='The moving Valkyrie has no ordinary clock in either adapter. Native has already preloaded to 0.1 s while Python is still reducing legacy cooldown; the native hit kills a Goblin before Python attacks. New units exist in the surrounding mixed game, so this is not silently labeled C56-only.'),
 dict(key='freeze-dash-charge',scope='New-card interaction',card='Ice Spirit × Boss Bandit; Heal collision',
      mechanic='Non-interrupting Spirit freeze cancels native dash wind-up',games=[548],
      values='Boss Bandit (x,y) (3.229,18.983) / (3.231,18.893); Python charging / native idle',
      rust='engine-cards/src/c56.rs:stun_target_mode (unconditional dash_cancel); lib.rs:spirit_tick',
      note='The Ice Spirit path calls stun_target_mode with interrupt=false, but native still cancels the dash. Python preserves anticipation for this non-interrupting freeze. The latent state difference becomes public after thaw, also displacing the nearby Heal Spirit differently.'),
]


def main():
    rows=[json.loads(p.read_text()) for p in sorted((ROOT/'games').glob('game-*.json'))]
    by_id={r['game']['game']:r for r in rows}
    assert len(rows)==600 and len(by_id)==600
    ice=[]
    for r in rows:
        if r.get('first') and any((e.get('python') or {}).get('spell_name')=='FreezeIceGolemite'
            for e in r['first']['detail']['entities'].values()):ice.append(r['game']['game'])
    specs=SPECS+[dict(key='icegolemite-alias',scope='Known C56 baseline',card='Ice Golem (IceGolemite)',
        mechanic='Death freeze area missing from imported config',games=ice,
        values='Death effect entity 19 present / absent; next_id 20 / 19',
        rust='engine-cards/src/lib.rs:death_effects; exporter differential.py:config, IceGolem branch',
        note='Pool uses IceGolemite; config exports its death area only when the requested alias is IceGolem. Rust death_effects consumes an absent death_areas entry. This is the known probe divergence, reproduced here with all-C56 decks as well.')]
    assigned=[i for s in specs for i in s['games']]
    mismatches=[r['game']['game'] for r in rows if r['status']=='mismatch']
    assert len(set(assigned))==len(assigned) and sorted(assigned)==sorted(mismatches)
    for s in specs:
        s['count']=len(s['games'])
        s['first_game']=min(s['games'])
        s['first_tick']=by_id[s['first_game']]['first']['tick']
        s['phase']=__import__('inspect_results').summary(by_id[s['first_game']])['phase']
    specs.sort(key=lambda s:(-s['count'],s['key']))
    (ROOT/'causes.json').write_text(json.dumps(specs,indent=1)+'\n')
    (ROOT/'game-causes.json').write_text(json.dumps({str(i):s['key'] for s in specs for i in s['games']},indent=1,sort_keys=True)+'\n')
    statuses=Counter(r['status'] for r in rows)
    acceptance=[a for r in rows for a in r['actions'] if a[5]!=a[6]]
    primary=dict(games=600,statuses=dict(statuses),mismatch_rate=104/600,
        ticks=sum(r['ticks'] for r in rows),panics=statuses['panic'],exceptions=statuses['exception'],
        replay_errors=sum('triage_error' in r for r in rows),
        action_first_divergences=sum((r.get('first')or{}).get('kind')=='action' for r in rows),
        post_divergence_action_disagreements=len(acceptance),
        new_interaction_games=sum(s['count'] for s in specs if s['scope']=='New-card interaction'),
        c56_mixed_clock_games=sum(s['count'] for s in specs if s['scope']=='C56 card; mixed context'),
        known_c56_games=len(ice))
    plan=json.loads((ROOT/'plan.json').read_text())
    appearances, deployed, prefix, plays = Counter(), Counter(), Counter(), Counter()
    mechanic_types, mechanic_pairs, card_pairs = set(), set(), set()
    for r in rows:
        appearances.update(set(sum(r['game']['decks'],[])))
        deployed.update({a[2] for a in r['actions'] if a[5] and a[6]})
        bound=(r.get('first')or{}).get('tick',10000)
        prefix.update({a[2] for a in r['actions'] if a[5] and a[6] and a[0]<bound})
        plays.update(a[2] for a in r['actions'] if a[5] and a[6])
        mechanic_types.update(r['seen_mechanics'])
        mechanic_pairs.update(map(tuple,r['nearby_mechanics']))
        card_pairs.update(map(tuple,r['nearby_cards']))
    cov=dict(games=len(rows),total_ticks=primary['ticks'],first_kinds={'digest':104},
       cards={c:dict(scope='C56' if c in plan['c56'] else 'new',
                     appearances=appearances[c],deployed_games=deployed[c],
                     equal_prefix_deployed_games=prefix[c],successful_plays=plays[c])
              for c in sorted(plan['kinds'])},
       mechanic_types=sorted(mechanic_types),nearby_mechanic_pairs=sorted(mechanic_pairs),
       nearby_card_pairs_count=len(card_pairs),
       missing_mechanic_proximity_pairs=[list(p) for p in itertools.combinations(sorted(mechanic_types),2)
                                        if p not in mechanic_pairs])
    pairs=set(map(tuple,cov['nearby_mechanic_pairs']))
    for p in (ROOT/'mechanics').glob('game-*.json'):
        pairs.update(map(tuple,json.loads(p.read_text())['nearby_mechanics']))
    cov['with_focused_games_missing_pairs']=[list(p) for p in itertools.combinations(cov['mechanic_types'],2) if p not in pairs]
    cov['with_focused_games_cross_pairs']=sum(a!=b for a,b in pairs)
    (ROOT/'coverage.json').write_text(json.dumps(cov,indent=1)+'\n')
    (ROOT/'metrics.json').write_text(json.dumps(primary,indent=1)+'\n')
    text=['# Native mixed-deck differential — pinned build 681b5f2c', '',
      '**600 mixed games: 104 mismatches (17.33%), 496 matches. 1,842,169 ticks.**',
      '**Native panics: 0. Python engine exceptions: 0. First-tick replay failures: 0.**', '',
      'The 104 first divergences separate into 75 known IceGolemite config failures, '
      '15 new-card interactions, and 14 timing failures in C56 cards inside mixed contexts. '
      'Those 14 are not assumed to be C56-only: the surrounding new cards may trigger '
      'the state that exposes the clock difference. Counts are first causes per game; '
      'later independent failures in the same game are masked by the first divergence.', '',
      '| Scope | Card | Mechanic | Games | First game / tick / phase | Python / native evidence | Rust consumer / function |',
      '|---|---|---|---:|---|---|---|']
    for s in specs:
        text.append(f"| {s['scope']} | {s['card']} | {s['mechanic']} | {s['count']} | "
                    f"[game {s['first_game']:04d}](games/game-{s['first_game']:04d}.json) / {s['first_tick']} / {s['phase']} | "
                    f"{s['values']} | `{s['rust']}` |")
    text += ['', '**Coverage and method.**', '',
      'Two weighted random eight-card decks per primary game, seed 6812026, level 11, '
      '3,600 ticks or Python game over. Both seats start at 10 elixir and then regenerate naturally. '
      'Cards are chosen by least prior successful play count, saving elixir for expensive cards. '
      'Three deployment depths, both lanes, cluster/tower spell targeting, defensive buildings, '
      'Mirror after valid history, Heal Spirit near friendly troops. The primary game script uses '
      'only deploy_card / apply_action to change battle state after initialization. It records all '
      'acceptances/rejections and compares es_common.battle_digest(b) with native.digest() every tick.', '',
      'All 66 non-C56 cards appear in **77–80** primary games, actually deploy successfully in '
      '**72–79** games, and deploy while the public trajectories still agree in **66–78** games. '
      'Mirror deploys in 79 games (220 plays); Heal in 76 (215 plays). All **7,381** unordered '
      'card pairs co-occur in primary decks. The primary games observe 31 mechanic classes '
      'and 453/465 distinct class pairs within six tiles at 40-tick sample points. Twelve focused '
      'supplemental games close all 12 gaps: **465/465** distinct observed mechanic-class pairs '
      'have proximity opportunities. This is an encounter proxy, not proof that every pair of '
      'effects fired. No champion abilities are activated, and instantaneous spell effects are '
      'not exhaustively covered by the mechanic-class proximity metric. Pair coverage is exploratory.', '',
      'All 104 first differing ticks are found by exhaustive per-tick comparison, then the equal '
      'prefix is replayed and diagnostics.phase_step captures before/start/combat/movement/objects/'
      'cleanup/complete. diagnostics.detail records differing entities, targets and sources. '
      'The 29 non-IceGolemite cases also retain 13-frame focused histories in triage/. '
      'All first divergences are digest differences; none starts with action rejection disagreement. '
      'There are 111 later action disagreements in 13 already-diverged games; they are recorded '
      'and are not counted as separate causes. Comparisons after the first divergence are '
      'diagnostic only. The digest does not cover every private timer, so matching games do '
      'not imply private-state equivalence.', '',
      '**Supplemental controls.**', '',
      '24 all-C56 controls: 12/12 without IceGolemite match; 12/12 with IceGolemite diverge '
      'at the missing death area. The 12 focused mechanic-pair games all match (41,078 ticks). '
      'The initial two smoke games match but are excluded: their affordable-card policy starved '
      'expensive cards and was corrected before the measured batch. Seven small all-C56 '
      'public-action clock probes also match; they do not reproduce the 14 mixed-context timing failures. '
      'Supplemental setup assertions from an earlier probe attempt were caused by occupied tower '
      'tiles, corrected before those seven valid probes, and are not engine exceptions. '
      'An optional 64-game C56 extension never started because its lease requests remained '
      'queued; both pending requests were cancelled by exact PID. It contributes no results.', '',
      '**Cause notes and attribution limits.**', '']
    for s in specs:
        text.append(f"- **{s['card']} ({s['count']}):** {s['note']}")
    text += ['', '**Reproduction and provenance.**', '',
      'Worktree: /mpac/sdicks02/repos/clasher-cards. Host: 127x08. '
      'Host job root: /mpac/sdicks02/jobs/clasher/cards/native-diff/. '
      'Run from /mpac/sdicks02/jobs/clasher/cards/root with '
      'PYTHONPATH=../out-total:engine-rs:src and /mpac/sdicks02/repos/clasher-bot/.venv/bin/python -B. '
      'See PROGRESS.md and run_batch.sh for lease, exact PIDs and restart commands. '
      'The primary launcher is 1886743; all 16 worker PIDs are explicitly waited, all exit 0. '
      'Every batch uses setsid, nice 15 and BOT LEAD cpu_job.sh, never more than 16 workers.', '',
      'Native SHA-256: `681b5f2c866ba3df1aa9903d1bf40d565e21feb6f541319bef84ee493c72066b`. '
      'Python reference is read-only clasher-bot-runtime/r1/src, not the newer worktree src. '
      'The source difference is intentional and recorded in provenance.json. Native source, '
      'differential.py and diagnostics.py match engine-cards/ byte for byte. No engine edits, '
      'builds, commits or pushes were made. No source game-data tables or imported config '
      'are included in this report directory; sanitize_results.py strips them from host evidence.', '',
      'One atomic result per primary game in games/. causes.json and game-causes.json '
      'map every mismatch exactly once; coverage.json and metrics.json hold aggregate counts. '
      'Full raw snapshots and config remain on the host; worktree evidence is sanitized. '
      'A repeat can skip already-completed files, or use a fresh output directory to force replay.', '']
    (ROOT/'RESULTS.md').write_text('\n'.join(text))
    ordered=sorted(specs,key=lambda s:(s['scope']!='New-card interaction',-s['count'],s['key']))
    table=''.join(f'<tr><td><strong>{html.escape(s["card"])}</strong><small>{html.escape(s["mechanic"])}</small><details><summary>Evidence and Rust location</summary><p>{html.escape(s["values"])}</p><code>{html.escape(s["rust"])}</code></details></td><td>{s["count"]}</td><td>{s["first_game"]} / {s["first_tick"]}<small>{html.escape(s["scope"])}</small></td></tr>' for s in ordered)
    doc='''<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>
body{font-family:var(--font-sans,system-ui);color:var(--foreground,#ddd);font-size:14px}p{line-height:1.5} .metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:0 0 18px}.metrics strong{display:block;font-size:25px}.metrics span,small{color:var(--muted-foreground,#999)}small{display:block;line-height:1.45;margin-top:5px}table{width:100%;border-collapse:collapse}th{text-align:left;font-size:12px;color:var(--muted-foreground,#999)}td,th{border-bottom:1px solid var(--border,#444);padding:12px 8px 12px 0;vertical-align:top}td:first-child{width:70%}details{margin-top:8px;font-size:12px}summary{cursor:pointer;color:var(--muted-foreground,#999)}code{word-break:break-word} .note{font-size:12px;color:var(--muted-foreground,#999)}@media(max-width:450px){.metrics{grid-template-columns:repeat(2,1fr)}td:first-child{width:62%}}
</style></head><body><div class="metrics"><div><strong>600</strong><span>mixed games</span></div><div><strong>17.33%</strong><span>104 first divergences</span></div><div><strong>0</strong><span>panics / exceptions</span></div><div><strong>1.84M</strong><span>ticks compared</span></div></div><p>15 new-card interactions · 14 C56-card timing failures in mixed contexts · 75 known Ice Golem failures. New-card causes appear first below.</p><table><thead><tr><th>Card and first cause</th><th>Games</th><th>Example game / tick</th></tr></thead><tbody>'''+table+'''</tbody></table><p class="note">Every new card deployed in at least 72 games; 465/465 observed mechanic-class pairs have proximity opportunities after 12 focused games. Proximity does not prove every effect combination fired. Native build 681b5f2c; Python runtime r1. No engine changes.</p></body></html>'''
    (ROOT/'results.html').write_text(doc)
    print(json.dumps(primary,indent=1))


if __name__=='__main__':main()
