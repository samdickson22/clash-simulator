"""Select among validated decks subject to the registered per-player safety bar."""


def decide(summary, candidates, players):
    scores = {name: sum(r['win_rate'] for r in summary if r['candidate'] == name
                       and r['group'] == 'pooled') / len(players) for name in candidates}
    eligible = []
    checks = {}
    for name in candidates:
        rs = [r for r in summary if r['candidate'] == name]
        pooled = [r for r in rs if r['group'] == 'pooled']
        strong = [r for r in rs if r['group'] == 'strong opponent']
        assert {r['player'] for r in pooled} == set(players)
        assert {r['player'] for r in strong} == set(players)
        passed = (all(r['delta_ci'][0] > 0 for r in pooled) and
                  all(r['delta_ci'][0] >= 0 for r in strong))
        checks[name] = dict(eligible=passed, pooled=pooled, strong=strong)
        if passed:
            eligible.append(name)
    ranking = sorted(candidates, key=lambda name: (-scores[name], name))
    eligible = [name for name in ranking if name in eligible]
    return dict(highest_pooled=ranking[0], eligible=eligible,
                recommended=eligible[0] if eligible else 'baseline', checks=checks,
                rule='Among candidates with pooled lower95%CI>0 and strong lower95%CI>=0 for BOTH players, choose highest mean pooled win rate; otherwise keep baseline.')
