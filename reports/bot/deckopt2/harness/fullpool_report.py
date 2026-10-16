"""Passive true-deck paired analysis, kept separate from projected rows."""
import json
from pathlib import Path
from bot.deckopt2 import run as h
import metrics
from decision import decide
import fullpool_clean
import clean

GROUPS={'weak pool':('R3a','v1'),'strong opponent':('LIVE-K4CW-r16',),'pooled':('R3a','v1','LIVE-K4CW-r16')}

def render(root,statuses):
    d=root/'fullpool';p=d/'validation/bank.json'
    if not p.exists():return []
    bank=json.loads(p.read_text());meta=json.loads((d/'manifest.json').read_text())
    rows=[json.loads(p.read_text()) for p in (d/'validation/rows').glob('*.json')]
    expected=len(bank['cases'])*len(bank['candidates'])*len(bank['players'])
    errors=[r for r in rows if fullpool_clean.problems(r)]
    statuses.append(dict(stage='True Battle Log full-pool validation',rows=len(rows),expected=expected,errors=len(errors)))
    lines=['## True Battle Log full-pool validation\n',f"{len(rows)}/{expected} rows; {len(errors)} flagged. Fresh bank drawn {bank['created_utc']}; SHA `{h.sha(p)}`.\n",
           'Truth uses all original Battle Log cards, RoyaleSim16.402 with real levels; runtime live16402b-r3. Our owned C56 cards use the same frozen B upgrade vectors. Weak pool is full-pool R3a+v1; strong is the specified C56-belief/it5s2 opponent with extended R3a proposer. rext-bc n/a. Pooled weights each of the three policies equally. Both players use the approved serial no-wall configuration. Its cutoff rates are zero by construction; candidate-specific wall200 timing effects are unmeasured. The owner’s pinned wall timing is a separate bundle-level observation.\n']
    if errors:return lines+['Incomplete/unclean: no deck-change inference.\n']
    old=(h.PLAYERS,h.GROUPS,metrics.GROUPS,clean.problems)
    try:
        h.PLAYERS=bank['players'];h.GROUPS=metrics.GROUPS=GROUPS
        clean.problems=fullpool_clean.problems
        summary=h.summarize(d,'validation')
        diag=metrics.summarize_metrics(rows,bank['players'],bank['candidates'])
    finally:h.PLAYERS,h.GROUPS,metrics.GROUPS,clean.problems=old
    lines+=['|Player|Deck|Group|Paired n|Win%|Baseline%|Δ pp [95% CI]|','|---|---|---|---:|---:|---:|---|']
    for r in summary:
        if r['candidate']!='baseline':lines.append(f'|{r["player"]}|{r["candidate"]}|{r["group"]}|{r["n"]}|{100*r["win_rate"]:.1f}|{100*r["baseline_win_rate"]:.1f}|{100*r["delta"]:+.1f} [{100*r["delta_ci"][0]:+.1f}, {100*r["delta_ci"][1]:+.1f}]|')
    h.dump(d/'validation/metrics-summary.json',diag);lines.extend(metrics.markdown(diag))
    cuts=[]
    for player in bank['players']:
        for candidate in bank['candidates']:
            ds=[r['result']['public_diagnostics'][str(r['seat'])] for r in rows if r['player']==player and r['candidate']==candidate]
            count=sum(x['search_decisions'] for x in ds);hits=sum(x['cutoff_hits'] for x in ds)
            cuts.append(dict(player=player,candidate=candidate,decisions=count,hits=hits,rate=hits/count if count else None))
    flags=[]
    for x in cuts:
        base=next(b for b in cuts if b['player']==x['player'] and b['candidate']=='baseline')
        if x['rate'] is not None and base['rate'] is not None and abs(x['rate']-base['rate'])>.02:flags.append(x)
    h.dump(d/'validation/cutoff-summary.json',dict(arms=cuts,over_two_pp_flags=flags))
    lines+=['\n|Player|Deck|Cutoffs/search decisions|Rate|','|---|---|---:|---:|']
    for x in cuts:lines.append(f'|{x["player"]}|{x["candidate"]}|{x["hits"]}/{x["decisions"]}|'+('—|' if x['rate'] is None else f'{100*x["rate"]:.2f}%|'))
    if flags:lines.append('FLAG: candidate-baseline cutoff difference exceeds2percentagepoints; see cutoff-summary.json.\n')
    if len(rows)!=expected:return lines+['\nValidation is incomplete; partial deltas do not support a deck change.\n']
    decision=decide(summary,[n for n in bank['candidates'] if n!='baseline'],bank['players'])
    h.dump(d/'validation-decision.json',decision)
    recommended=decision['recommended'];safe=bool(decision['eligible'])
    variant=json.loads((root/'variant-B-full-budget.json').read_text());plan=variant['plans'][recommended]
    result=dict(created_utc=h.utc(),scenario='true Battle Log full-pool',recommended=recommended,deck_change_supported=safe,
                highest_pooled_candidate=decision['highest_pooled'],deck=variant['candidates'][recommended],levels=plan['levels'],
                remaining_order=plan['upgrade_order'],remaining_gold_spend=plan['gold'],committed_gold=1400,
                total_gold_from_original=plan['total_gold_from_original'],gold_left=8921-plan['gold'],
                wild_cards_left={r:n-plan['wild_cards_used'].get(r,0) for r,n in variant['wild_cards'].items()},gems_spent=0,
                bank_sha256=h.sha(p),variant_sha256=h.sha(root/'variant-B-full-budget.json'))
    assert result['gold_left']==10321-result['total_gold_from_original']
    h.dump(root/'FULLPOOL-PLAN.json',result)
    lines+=['## True-deck decision and ordered upgrade plan\n',f'**{recommended}**: '+', '.join(f'{c} L{plan["levels"][c]}' for c in result['deck'])+'.\n',
            ('Validation meets the registered per-player pooled/strong evidence bar.' if safe else 'Keep the baseline eight cards; no finalist meets the registered per-player pooled/strong evidence bar.')+' This true-deck result takes precedence if the full-pool bundle is deployed.\n',
            '|Order|Card|Level|Gold|Held copies|Wild cards|','|---:|---|---|---:|---:|---|']
    for i,s in enumerate(plan['upgrade_order'],1):lines.append(f'|{i}|{s["card"]}|{s["from_level"]}→{s["to_level"]}|{s["gold"]}|{s["held_copies"]}|{s["wild_cards"]} {s["rarity"]}|')
    lines.append(f'\nRemaining spend {plan["gold"]}gold; original-budget total {plan["total_gold_from_original"]}, including committed Fireball400+Giant1000; gold left {result["gold_left"]}. Gems spent0. Wilds left: {result["wild_cards_left"]}.\n')
    (root/'FULLPOOL-PLAN.md').write_text('\n'.join(lines)+'\n')
    return lines
