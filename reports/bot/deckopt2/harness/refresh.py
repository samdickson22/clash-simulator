"""Light, local result refresh; no simulator or Runtime imports."""
from pathlib import Path
import json
from collections import Counter
from types import SimpleNamespace
from bot.deckopt2.run import report,read_rows,summarize,utc,sha
import clean
from metrics import summarize_metrics,markdown
from final_plan import render as render_final_plan
from decision import decide
clean.install()
ROOT=Path('/mpac/sdicks02/jobs/clasher/bot-deckopt2')

text=['# Real-level deck search 2 — C56-projected scenario\n',f'Updated {utc()}. Exploration; no live deployment performed. Full-pool true-Battle-Log validation has an independently registered bank; it takes precedence for the live recommendation if deployed.\n',
      'King L6 confirmed on the live home screen (3312 HP). Both players retain deployed all-L11 planning; only simulator truth uses real levels. Each stage is registered independently.\n']
smoke_path=ROOT/'fullpool/smoke-result.json'
if smoke_path.exists():
    smoke=json.loads(smoke_path.read_text());diag=smoke['diagnostics']['0']
    text += ['## Full-pool true-deck variant\n',
             f"Real-level actual-wall200 reserve-bundle smoke passed {smoke['utc']}: terminal{smoke['result']['ticks']}ticks,0ownrefusals,0unmapped rows,no native/live errors,packet checks clean. This single preflight is not validation.\n",
             f"Unpinned, loaded-01 wall smoke cutoff **{diag['cutoff_hits']}/{diag['search_decisions']} = {100*diag['cutoff_hit_rate']:.1f}%**; default {100*diag['default_rate']:.1f}%. This R3a smoke used one Runtime. It is a separate setup/timing observation, not an efficacy row. The owner’s later package timing on pinned cores reports cutoff3.5% non-res (6games) and2.7% res (8games), versus C56base4.4% (5games); these are separate fleet observations (BUNDLE.md b8d41879), updated from the earlier3.1–3.2% partial snapshot. No additional wall200 rows are planned without quiet dedicated cores.\n",
             'BOT LEAD cleared the gate (strong+0.150,R3a+0.054,v1+0.028) and approved serial no-wall c4 validation: set_deadline(None,1), native_threads1, pool_size0, chunks4, live deadline cleared, f1a2 explicit. Versus K4L-R-gs-rw-fc-c4-mk1a1, the fallback differs: f1a2 rather than R3a. A duplicate-case command-hash proof is required before locking the bank. Strong remains current C56 LiveBelief+it5s2, threads1, extended R3a proposer, scoped separate Runtime. Each side logs belief and fast tier at start. rext-bc is n/a for this variant.\n']
    text.append('The first serial repeat exposed a harness-only stale Recorder deadline: its cached200ms value caused wall-lateness despite inner no-wall settings. Failed preflight rows are retained; the wrapper now clears/asserts the effective deadline and the duplicate-case proof is rerun before locking validation. The projected harness already asserts all effective deadlinesNone.\n')
    if (ROOT/'fullpool/release-reconciliation.json').exists():
        text.append('Deployment package reconciled with owner BUNDLE.md (main2fa5d496, docb8d41879): f1a2 regression check passed and its pinned model/calibration files match our copies. Evaluation source1a65dcd1 differs only by the package’s added, inactive Mac runtime-pin entry; active Linux r3 code is unchanged. Full details: fullpool/release-reconciliation.json.\n')
    replay_path=ROOT/'fullpool/repeat-proof.json'
    if replay_path.exists():
        replay=json.loads(replay_path.read_text())
        text.append(f"Serial duplicate-case proof passed {replay['utc']}; identical command SHA `{replay['command_sha256']}`.\n")
parity_path=ROOT/'projected-parity/receipt.json'
if parity_path.exists():
    parity=json.loads(parity_path.read_text())
    text += ['## Projected implementation parity receipt\n', f"Requested five projected-validation cases per player, including two strong-opponent cases, completed {parity['utc']}. All command/state/terminal comparisons identical: {parity['passed']}; reserve activity confirmed in both implementations on the required res strong cases: {parity['reserve_fired']}. Selected implementation: {'fc-c4 serial fast reduction' if parity['passed'] else 'original LD'}. Receipt SHA `{sha(parity_path)}`. These games are implementation checks and are excluded from validation counts; no outcomes were used for selection.\n"]
text.append('Full-pool diagnostic correction: pinned royalesim_vocab.py declares SpearGoblin_Dummy in NO_COUNTERPART (Goblin Hut garrison sprite), and royalesim_translate._lazy_unit intentionally drops it. Its raw counter is misleadingly named unmapped_unit. The full harness initially stopped on this expected counter. fullpool_clean.py exempts only that predeclared visual row; all other missing/unmapped rows and genuine failures remain flags. Every raw row and bank stays unchanged. Recovery verifies original producer exit, preserves row hashes, resumes only missing arms, and keeps partial cases on their original host. The frozen game worker, player settings and observation mapping are unchanged. Full provenance is in fullpool/resume-manifest.json once recovery is registered.\n')
text.append('BOT LEAD protocol update: the full-pool bundle is scheduled live00:00Z, so the true-deck4500-game bank governs the decision. Projected6000-game validation is optional only after true validation finishes and CPU is idle; otherwise it is recorded not run. Its fresh bank and5/5-per-player fc-c4 parity receipt remain available. An interim read freezes225complete paired cases with actual per-policy n, paired CIs and completion-time-bias caveat; it is not a decision. No extra01/03capacity is admitted beyond4workers each.\n')
statuses=[]
for label,root,stage in [('Original ten-deck screen',ROOT,'screen'),('Gold-budget 32-deck screen',ROOT/'new-cards','screen'),('Fresh validation',ROOT/'final-validation','validation')]:
    if not (root/stage/'bank.json').exists():
        text.append(f'## {label}\n\nNot started.\n');continue
    meta=json.loads((root/'manifest.json').read_text())
    data=json.loads((root/stage/'bank.json').read_text())
    paths=list((root/stage/'rows').glob('*.json'))
    rows=[json.loads(p.read_text()) for p in paths]
    errors=[r for r in rows if clean.problems(r)]
    expected=len(data['cases'])*len(data['candidates'])*len(data['players'])
    statuses.append(dict(stage=label,rows=len(rows),expected=expected,errors=len(errors)))
    text += [f'## {label}\n',f'{len(rows)}/{expected} rows; {len(errors)} unclean. Bank drawn {data["created_utc"]}; SHA `{sha(root/stage/"bank.json")}`.\n',
             f'Collection SHA `{data["collection_sha256"]}`; King {data["own_tower"]}. True owned levels: '+', '.join(f'{c} L{l}' for c,l in sorted(data['own_levels'].items()))+'.\n']
    if errors:
        text.append('Evidence is INCOMPLETE/UNCLEAN; investigate errors before selection or recommendation.\n');continue
    summary=summarize(root,stage)
    text.append('|Player|Deck|Opponent group|Paired n|Win%|Baseline%|Δ pp [95% CI]|\n|---|---|---|---:|---:|---:|---|')
    for r in summary:
        if r['candidate']=='baseline':continue
        text.append(f'|{r["player"]}|{r["candidate"]}|{r["group"]}|{r["n"]}|{100*r["win_rate"]:.1f}|{100*r["baseline_win_rate"]:.1f}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|')
    if meta.get('candidate_plans'):
        diagnostics=summarize_metrics(rows,data['players'],data['candidates'])
        (root/stage/'metrics-summary.json').write_text(json.dumps(diagnostics,indent=2))
        text.extend(markdown(diagnostics))
    if len(rows)<expected:text.append('\nINCOMPLETE; partial screening deltas do not support a deck change.\n')
    text.append('\nCandidate decks:\n')
    for n in data['candidates']:
        text.append(f'- {n}: '+', '.join(f'{c} L{meta.get("candidate_plans",{}).get(n,{}).get("levels",data["own_levels"])[c]}' for c in meta['candidates'][n]))
    text.append('')
    if stage=='validation' and len(rows)==expected:
        candidates=[n for n in data['candidates'] if n!='baseline']
        decision=decide(summary,candidates,data['players'])
        (ROOT/'validation-decision.json').write_text(json.dumps(decision,indent=2))
        best=decision['highest_pooled'];recommended=decision['recommended'];safe=bool(decision['eligible'])
        text += ['## C56-projected scenario decision\n',f'Highest mean pooled validation win rate across the two players: **{best}**.\n',
                 ('Recommend **'+recommended+'** under the C56-projected scenario: pooled lower95%CI>0 and strong lower95%CI>=0 for bothplayers. Among eligible decks choose highest mean pooled win rate.' if safe else 'No supported deck-change recommendation: no finalist meets positive pooled lower95%CI and nonnegative strong lower95%CI for bothplayers.')+'\n']
        text.extend(render_final_plan(ROOT,recommended,best,safe))
from fullpool_report import render as render_fullpool
text.extend(render_fullpool(ROOT,statuses))
from fullpool_interim import maybe as interim_read
text.extend(interim_read(ROOT))
text += ['## Protocol and limits\n',
         'Clean rule clarified by BOT LEAD2026-10-16: opponent policy deploy refusals are ordinary opponent behavior and retained as clean. Our own refusals, native failures, live errors and nonterminal/error games remain flagged. Raw rows, including their original diagnostic tags, are unchanged. No case is excluded for an opponent refusal.\n',
         'Only validation supports the claim. Actual wins are primary, draws count as nonwins and remain in raw rows. The paired percentile bootstrap uses20,000 replicates and the same resampled case indices for candidate/baseline within each opponent policy. Pointwise intervals; no multiplicity adjustment. Degenerate all-win/all-loss bootstrap intervals do not prove true rates of0/100%.\n',
         'Weak pool = R3a+v1 only. Strong LIVE-K4CW-r16 and internal-only rext-bc each have separate rows. Overall pooled uses equal weights across the four policies, so weak contributes half; rext never enters weak pool. Both deterministic LD twins have no wall deadline; wall200 live timing equivalence is not claimed.\n',
         'Truth: RoyaleSim16.402 /0.1.34; native simulator SHA97e03055332faeb986c91a12aa64c6e22ca65948b68351803d914e0a84eb43bb. Planning pin live16402b-r2/native de11f12401da396b309cd2e5d3ea422cfa1c94f462a4e3250fd51d89a62887b1; frozen deployed roots/weights/live belief, no ExactLevelRoot B. Simulator public static placement compatibility is shared by every V1Policy poller and scripted candidates.\n',
         'All91 Battle Log rows uniformly sampled; nearest C56 catalog projection uses overlap, frequency, literal card tuple. Opponent levels are independent population draws from the250observed values {2:7,3:17,4:61,5:110,6:53,7:2}, with existing rare/epic offset1 and rarity floors (common1/rare3/epic6/legendary9/champion11). No sampled log row level is treated as per-match truth or passed to a planner. Projection retains all8cards for11/91rows; overlap counts are3cards:12rows,4:31,5:33,6:4,8:11. Thus80/91decks are changed by nearest-catalog mapping. Projection bias and rarity assumptions are outside the confidence intervals. Opponent towers6scenario.\n',
         'rext-bc was trained on15.535.29; explicit harness opt-in evaluates it on16.402 without retraining or changing its old observation normalization. This balance/level distribution shift limits interpretation; internal eval only.\n',
         'Own level risk: low-level new Wizard3/InfernoTower3/FireSpirits1, plus Knight3/Goblins1 in original candidates. Both screens disclose their exact collection snapshot; only final post-upgrade levels enter validation. Card scope C56 only; no non-C56 recommendation.\n',
         'Resource receipts retain admission attempts and the03backoff: all unscored missing cases are resumed using fixed seeds, with no completed outcome discarded. Shared cpu_job admission uses per-check flock (main b8ad5e222, cpu_job md5 prefix3103e8a4093e, cpu_room0e8577911a23; supersedes the earlier wait-held lock), each partition in a distinct detached session; nice15, CPU-only, required deterministic env. Compute on01/03/04 under the later explicit04authorization;05light aggregation.\n']
text += ['## Upgrade-budget search\n',
         'Copies-only variant A locked32distinct candidate decks. Official source:127x03:/mpac/sdicks02/repos/clasher-bot-runtime/live16402c/gamedata.json, SHAa7de3e93eb4320c48775da97cd0e5113fb793ea57782ba0eb006af0bd6eb0ccb. Fields items.rarities.upgradeMaterialCount/upgradeCost, indexed absolute current level minus relativeLevel minus1; common starts1,rare3,epic6,legendary9. Current needed counts agree with the collection. Fireball400/Giant1000 match committed gold spending; Musketeer4→5 matches the in-game150gold/4copies read. BOT LEAD approved this official table; later differences trigger a final-plan affordability recheck.\n',
         'Held-copy maxima: Arrows1→6,625gold; Goblins1→6,625; Skeletons5→7,1400; Wizard3→7,1600; InfernoTower3→7,1600; FireSpirits1→4,75. All ownedC56 maxima total5925gold (below10321); each deck spends only on its own cards, at most4600 in the32-deck A set. This is the original copies-only reference. Variant B includes the subsequent committed Fireball/Giant upgrades and Musketeer wild-card transfer.\n',
         'Variant B frozen after20:37:55Z: Fireball5→6 (400gold,9held+1rare-wild copies) and Giant6→7 (1000gold,15held+5rare-wild copies) already committed in every deck. Two further rare wilds are already applied to Musketeer: L4,4heldcopies. Remaining shared resources:8921gold,59common/2rare wildcards; gems300 excluded. All32 decks optimize only their own remaining upgrades under a registered weighted-strength heuristic, not measured upgrade value. Exact sequential replay verifies gold, held copies and shared wilds. Variant-B-full-budget.json SHA190e15df6ecea88da441ef29f2c45da56316558a5174516054997191dc5de968. All32 target vectors match pre-Musketeer-transfer B; only remaining resource accounting changed. The derived collection matches the20:37:55Z ACCOUNT-LOG entry, independently checked20:46:27Z (log snapshot SHAe66cbca5dd339b7fae73d662bf6909f65f23cc45e30c9c228a406caf48f1d78d); standalone updated collection remains pending. Baseline remaining order: Musketeer4→5,150gold/4heldcopies; Minions5→6,400gold/50common-wild copies. Remaining550gold; total1950from original10321 including1400committed. Only-res screens8cases/policy; both players validate150/policy. No account spending by this worker.\n']
(ROOT/'REPORT.md').write_text('\n'.join(text)+'\n')
(ROOT/'status.json').write_text(json.dumps(dict(updated_utc=utc(),stages=statuses),indent=2))
print(json.dumps(statuses))
