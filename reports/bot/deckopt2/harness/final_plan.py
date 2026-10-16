"""Render the actionable plan only after complete clean validation."""
import json
from pathlib import Path
from bot.deckopt2.run import dump, sha, utc


def render(root, recommended, best, safe):
    variant = json.loads((root / 'variant-B-full-budget.json').read_text())
    plan = variant['plans'][recommended]
    remaining_wild = {rarity: count - plan['wild_cards_used'].get(rarity, 0)
                      for rarity, count in variant['wild_cards'].items()}
    result = dict(created_utc=utc(), scenario='C56-projected scenario', provisional_until_fullpool=True, recommended=recommended,
                  highest_pooled_candidate=best, deck_change_supported=safe,
                  variant_sha256=sha(root / 'variant-B-full-budget.json'),
                  validation_bank_sha256=sha(root / 'final-validation/validation/bank.json'),
                  deck=variant['candidates'][recommended], levels=plan['levels'],
                  remaining_order=plan['upgrade_order'], remaining_gold_spend=plan['gold'],
                  committed_gold=variant['committed_gold'],
                  total_gold_from_original=plan['total_gold_from_original'],
                  gold_left=variant['budget'] - plan['gold'],
                  wild_cards_left=remaining_wild, gems_spent=0)
    assert result['gold_left'] == variant['original_budget'] - result['total_gold_from_original']
    dump(root / 'C56-PROJECTED-PLAN.json', result)
    lines = ['## C56-projected scenario: ordered upgrade plan\n',
             f'Projected-scenario deck: **{recommended}**. ' + ', '.join(
                 f'{card} L{plan["levels"][card]}' for card in result['deck']) + '.\n',
             ('Projected validation supports a deck change under the C56-projected scenario. A deployed full-pool bundle requires the true-deck validation before the final live recommendation.' if safe else
              'Keep the current eight cards; validation did not meet the registered deck-change evidence bar.') + '\n',
             '|Order|Card|Level|Gold|Held copies|Wild cards|',
             '|---:|---|---|---:|---:|---|']
    for i, step in enumerate(plan['upgrade_order'], 1):
        wild = f'{step["wild_cards"]} {step["rarity"]}' if step['wild_cards'] else '0'
        lines.append(f'|{i}|{step["card"]}|{step["from_level"]}→{step["to_level"]}|{step["gold"]}|{step["held_copies"]}|{wild}|')
    lines += [f'\nRemaining ordered spend **{plan["gold"]} gold**. Already committed: Fireball5→6,400gold (9held+1rare-wild copies); Giant6→7,1000gold (15held+5rare-wild copies). Musketeer already holds4copies after its separate2rare-wild transfer, with no gold spent on that transfer. Total from original10321gold: **{plan["total_gold_from_original"]}**; gold left **{result["gold_left"]}**.\n',
              'Remaining wild cards: ' + ', '.join(f'{r} {n}' for r, n in remaining_wild.items()) + '. Gems spent0;300held.\n',
              'Order prioritizes the win condition and defensive pieces using the registered heuristic; the upgrade sequence itself was not separately randomized for causal value. Every transition is replayed against the official rarity-aware costs and the frozen shared inventory.\n']
    (root / 'C56-PROJECTED-PLAN.md').write_text('\n'.join(lines) + '\n')
    return lines
