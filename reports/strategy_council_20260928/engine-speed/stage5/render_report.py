"""Publish the completed fixed evaluation and its qualification receipts."""
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from qualify import write

HERE=Path(__file__).resolve().parent
r=json.loads((HERE/'result.json').read_text());assert r['complete']
p=json.loads((HERE/'parity-r3.json').read_text())['results']
g=json.loads((HERE/'native-games-scoped.json').read_text())['games']
d=json.loads((HERE/'derived-games.json').read_text())['games']
a=json.loads((HERE/'abilities.json').read_text())['results']
manifest=json.loads((HERE/'evaluation-manifest.json').read_text())
scoped=json.loads((HERE/'scoped-sources.json').read_text())
ci=lambda row:f"{row['score']:.6f} [{row['ci'][0]:.6f}, {row['ci'][1]:.6f}]"
status='GO' if r['statistical_pass'] and r['timing']['pass_budget'] else 'NO-GO'
lines=[f'# Stage 5: {status} for srp-pub-mix-C56', '',
    'Implementation and the registered256-game evaluation are complete. Python remains the default and the byte-identity reference.', '',
    f"Statistical gate: {'PASS' if r['statistical_pass'] else 'FAIL'}. Strict250ms wall gate: {'PASS' if r['timing']['pass_budget'] else 'FAIL'}. These verdicts are independent. No confirmation outcome was used to retune the player, schedule or gate.", '',
    '## Registered evaluation', '',
    f"Pooled: {ci(r['pooled'])},256 games. Required score >=0.55 and lower95% bound >0.50.",
    f"Defense: {ci(r['styles']['defense'])},{r['styles']['defense']['games']} games. The same thresholds apply.", '',
    '| Family | Games | Wins | Draws | Score | Matchup95% CI | Abilities accepted |',
    '| --- | ---: | ---: | ---: | ---: | --- | ---: |']
for name,c in r['families'].items():
    lines.append(f"| {name} | {c['games']} | {c['wins']} | {c['draws']} | {c['score']:.4f} | [{c['ci'][0]:.4f}, {c['ci'][1]:.4f}] | {c['ability_accepted']} |")
lines+=['','| Opponent style | Games | Score and95% CI |','| --- | ---: | --- |']
for name,c in r['styles'].items():lines.append(f"| {name} | {c['games']} | {ci(c)} |")
lines+=['', 'Intervals use10000 percentile bootstrap resamples of paired matchup means, RNG40404041. Both seats stay together. Family intervals are descriptive. The fixed schedule has128 matchups with swapped planning seats, role-held-out eval/eval_ood human planning perspectives, and train-frequency opponents. Common deck identities can occur in both train and eval roles; this is role holdout, not a claim of deck-identity holdout. Both actions are selected before fixed seat0/seat1 application.', '',
    'PREREG-C56.md predates every confirmation game. schedule.json fixes all decks/styles/seeds. The initial audit scanned915788 historical seed fields and3945 NPZ archives; the embedded-metadata supplement checked1924 seed occurrences from1922 archives plus textual report matches, with no collision. Pickled roots are covered through their JSON plan/gate provenance. All256 receipts are present; no outcome was excluded.', '',
    '## Timing and abilities', '',
    f"One execution thread per game process, nice10, pregame initialization/warmup excluded. Whole decisions include public sensor conversion, history assimilation, candidates, reconstructed root and native search. {r['timing']['decisions']} decisions/{r['timing']['searches']} searches. All-decision p99 {r['timing']['p99']:.9f}s, max {r['timing']['max']:.9f}s. Searched p99 {r['timing']['search_p99']:.9f}s, max {r['timing']['search_max']:.9f}s. Overruns: {r['timing']['overruns']}. Three independent evaluation processes shared the host with unrelated jobs; quiet-core isolation was not established.", '',
    'Eight development games on the final driver passed the observed budget before confirmation: p99 0.119796398s, searched p99 0.164559547s, max 0.242517875s. They are not part of strength estimates and do not override confirmation timing.', '',
    '| Champion | Legal decision opportunities | Attempts | Accepted |','| --- | ---: | ---: | ---: |']
for name,c in r['abilities'].items():lines.append(f"| {name} | {c['opportunities']} | {c['attempts']} | {c['accepted']} |")
lines += ['',f"Rejected non-no-op commands: planner {r['rejected'][0]}, opponent {r['rejected'][1]}; all outcomes retained. Script opponents retain their declared rule of never activating abilities. Legal opportunities count decisions where the own active champion could activate; they are not independent cooldown windows.",'',
    '## Native parity and public-state accuracy','',
    f"All200 searchable C56 roots match selected actions,ordered candidates,exact scores,continuation digests and full624-word MT state plus index: {sum(x['candidates'] for x in p)} candidates,{sum(x['rollouts'] for x in p)} three-style rollouts,{sum(x['ticks'] for x in p)} ticks,{sum(x['continuation_actions'] for x in p)} continuation actions. Six additional roots exercise AQ/MM/Goblinstein in both seats,36 rollouts; each ability also activates in the public reconstructed model.",
    f"Eight full native-searched core games match Python every tick,action and MT state: {sum(x['ticks'] for x in g)} ticks,{sum(x['searches'] for x in g)} searches,{sum(x['abilities'] for x in g)} accepted abilities. These core qualification games use full model roots and are not the fair evaluation. Current Stage4 regression discovery88/88 and P16 backend/regressions9/9 pass.",
    f"The public tracker passes8 C56 full games/{sum(x['checks'] for x in d)} checks with exact elixir equality,{sum(x['hand_determined'] for x in d)} determined-hand and{sum(x['cycle_determined'] for x in d)} determined-cycle checks,9 abilities. A separate full Collector/Heal/champion game passes12002 checks,8 resource grants,3 abilities and38 Heal plays. Champion cycling is the reference engine's ordinary four-card cycle. Heal has no elixir effect. Confirmation adds{r['derived_checks']} truth checks,{r['hand_determined']} determined-hand and{r['cycle_determined']} determined-cycle checks,all exact by assertion.", '',
    'The prior reconstructs2925 train decks weighted by69380 human perspectives. The posterior removes unobservable hand-slot permutations and retains exact hand multisets/queue order. Known quantities are never resampled. Hidden hand/cycle/elixir/RNG poisoning leaves the public sensor and model unchanged. Public template coverage passes1232 samples across all56 cards.', '',
    'The fair player accepts only a v5 public packet, own HUD and timestamped public events. Unobserved combat clocks,targets,shields and deployment phases use deterministic synthetic defaults. This is a public model, not exact recovery of hidden combat state. Only unresolved cards/order and independent rollout RNG are sampled. Card metadata and missing carrier templates come from isolated fixed demonstrations, not the real battle.', '',
    '## Implementation and evidence', '',
    'New src/clasher/rl/c56_rollout_planner.py provides explicit Python/native C56 backends. Root candidates are balanced script choice/top4,no-op,legal ability and16 sampled public-legal placements. There is no qualified C56 policy in this run. Every candidate averages balanced/pressure/defense opponent-model rollouts at160/10 ticks, with balanced own continuation, defense-v2 plus elixir and terminal+2/-2/0. Search runs every second5-tick decision starting at tick90. Native continuations do not call Python.', '',
    'The development differential found one native physics omission. Stunned pushback skipped the frozen path reached-node update, diverging on RoyalHogs at tick588 after a route difference at580. Rust now matches entities.py:391-410. failure19.pkl,phase19.json,routephase19.json and engine-rs/test_stage5_search.py retain the reduction. C56 leaf metadata now imports per-entity cost/formation share and respects movement modifiers. C56 action2305 is supported; C56 script behavior is unchanged.', '',
    'An unrelated job changed vision/l1_training.py while the original aggregate fingerprint included vision. No historical receipt was relabelled. replay_qualified.py reproduces all200 recorded Python trace hashes under the final scoped runtime pins, and eight core games were rerun under those pins. scoped-sources.json verifies read-back invariance. Python oracle sources outside that unrelated vision work,canonical gamedata and the original Stage4 active native library remain entry-identical. Stage5 uses a private extension.', '',
    f"Evaluation manifest SHA256: {r['manifest']}. Receipt aggregate SHA256: {r['receipts_sha256']}. Final scoped runtime fingerprint: {scoped['fingerprint']}.", '',
    'Changed files: src/clasher/rl/c56_rollout_planner.py; engine-rs/differential.py; engine-rs/src/lib.rs,scripts.rs,leaf.rs; engine-rs/test_stage5_search.py; engine-speed/PREREG-C56.md,STAGE5.md,PROGRESS.md and stage5/ implementation,drivers,receipts,private library. No Python engine/C56 script behavior, forbidden evidence directory or unrelated process was changed. No git commit or destructive git operation was performed. Build intermediates were cleaned while idle; Stage5 outputs remain below1GiB.', '',
    '## Open issues', '']
if not r['timing']['pass_budget']:lines.append('The registered hard250ms wall limit failed. This player has no one-core budget admission; preflight timing and percentile results cannot erase the measured maxima. A future performance change needs its own pinned validation.')
if not r['statistical_pass']:lines.append('The registered statistical gate failed. Do not retune on these confirmation outcomes or represent the run as a strength pass. A new configuration needs a new preregistration and fresh seeds.')
lines.append('Public combat-state reconstruction remains approximate, and quiet-core timing is unverified. Native support is an optional local extension rather than a packaged wheel.')
report='\n'.join(lines)+'\n'
report=re.sub(r',(?=\S)', ', ', report)
for old,new in {
'registered256':'registered 256','Strict250ms':'Strict 250 ms','>=0.55':'>= 0.55','lower95%':'lower 95%','>0.50':'> 0.50',
'Matchup95%':'Matchup 95%','and95%':'and 95%','use10000':'use 10,000','RNG40404041':'RNG 40404041','has128':'has 128',
'seat0/seat1':'seat 0/seat 1','scanned915788':'scanned 915,788','and3945':'and 3,945','checked1924':'checked 1,924','from1922':'from 1,922',
'All256':'All 256','nice10':'nice 10','209575 decisions/22913 searches':'209,575 decisions / 22,913 searches',
'All200':'All 200','all200':'all 200','full624-word':'full 624-word','Stage4':'Stage 4','Stage5':'Stage 5',
'discovery88/88':'discovery 88/88','regressions9/9':'regressions 9/9','passes8':'passes 8','passes12002':'passes 12,002',
'and38 Heal':'and 38 Heal','adds209575':'adds 209,575','and202757':'and 202,757','and70598':'and 70,598',
'reconstructs2925':'reconstructs 2,925','by69380':'by 69,380','passes1232':'passes 1,232','all56':'all 56',
'choice/top4':'choice/top 4','and16':'and 16','at160/10':'at 160/10','terminal+2':'terminal +2','second5-tick':'second 5-tick',
'tick90':'tick 90','tick588':'tick 588','at580':'at 580','action2305':'action 2305','below1GiB':'below 1 GiB','hard250ms':'hard 250 ms',
}.items():report=report.replace(old,new)
report=re.sub(r'(?<=\d)s\b',' s',report)
report=report.replace('\nEight full native-searched','\n\nEight full native-searched').replace('\nThe public tracker','\n\nThe public tracker')
report=report.replace('Evaluation manifest SHA256:', 'The sealed analyzer required a JSON-only adapter for NumPy scalar booleans. analyze_serialize.py converts those scalars to native JSON values without changing the sealed statistical code, bootstrap draws or results. analysis-serialization.json pins both files.\n\nEvaluation manifest SHA256:')
report=report.replace('A future performance change needs its own pinned validation.', 'Recorded overruns also exceed 250 ms of process CPU time; scheduler delay alone does not explain the failure. A future performance change needs its own pinned validation.')
(HERE.parent/'STAGE5.md').write_text(report)
write(HERE/'completion.json',dict(complete=True,statistical_pass=r['statistical_pass'],budget_pass=r['timing']['pass_budget'],status=status,report_sha256=hashlib.sha256((HERE.parent/'STAGE5.md').read_bytes()).hexdigest(),stage5_bytes=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())))
print(status, 'report written')
