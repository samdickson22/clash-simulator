"""Aggregate passive public diagnostics; never used by selection or a player."""
import numpy as np
GROUPS={'weak pool':('R3a','v1'),'strong opponent':('LIVE-K4CW-r16',),'pooled':('R3a','v1','LIVE-K4CW-r16')}


def summarize_metrics(rows, players, candidates):
    out = []
    for player in players:
        for candidate in candidates:
            for group, opponents in GROUPS.items():
                selected = [r for r in rows if r['player'] == player and
                            r['candidate'] == candidate and r['opponent'] in opponents]
                ds = [r['result'].get('public_diagnostics', {}).get(str(r['seat']))
                      for r in selected]
                ds = [d for d in ds if d is not None]
                if not ds:
                    continue
                reactions = [s for d in ds for s in d['reaction_s']]
                giant_reactions = [s for d in ds for s in d['reaction_giant_s']]
                pushes = sum(d['giant_pushes'] for d in ds)
                undefended = sum(d['undefended_before_contact'] for d in ds)
                median_search = [(d.get('search_wall_ms') or {})['p50'] for d in ds
                                 if (d.get('search_wall_ms') or {}).get('p50') is not None]
                defence_reactions = [push['def_minus_cross_s'] for d in ds
                                     for push in d['giant_push_details']
                                     if push.get('def_minus_cross_s') is not None]
                contacts = sum(push.get('t_contact') is not None for d in ds
                               for push in d['giant_push_details'])
                def quantiles(values):
                    return np.quantile(values, [.5, .9]).tolist() if values else [None, None]
                out.append(dict(player=player, candidate=candidate, group=group,
                                games=len(ds), available_games=len(selected),
                                reaction_events=len(reactions), reaction_p50_p90_s=quantiles(reactions),
                                giant_reaction_events=len(giant_reactions),
                                giant_reaction_p50_p90_s=quantiles(giant_reactions),
                                giant_pushes=pushes, contact_pushes=contacts, undefended=undefended,
                                defence_minus_cross_p50_p90_s=quantiles(defence_reactions),
                                undefended_contact_share=undefended / contacts if contacts else None,
                                undefended_share=undefended / pushes if pushes else None,
                                median_game_search_p50_ms=float(np.median(median_search)) if median_search else None))
    return out


def markdown(rows):
    def num(value):
        return '—' if value is None else f'{value:.2f}'
    lines = ['\nPublic reaction/defence diagnostics (descriptive, separate from win-rate inference):\n',
             '|Player|Deck|Group|Games|Enemy-play reaction p50/p90 s|Enemy Giant reaction p50/p90 s|Giant defence minus crossing p50/p90 s|Undefended Giant pushes|Median game search p50 ms|',
             '|---|---|---|---:|---|---|---|---|---:|']
    for r in rows:
        reaction = '/'.join(num(v) for v in r['reaction_p50_p90_s'])
        giant = '/'.join(num(v) for v in r['giant_reaction_p50_p90_s'])
        defence = '/'.join(num(v) for v in r['defence_minus_cross_p50_p90_s'])
        share = ('—' if r['undefended_share'] is None else
                 f'{r["undefended"]}/{r["giant_pushes"]} ({100*r["undefended_share"]:.1f}%)')
        lines.append(f'|{r["player"]}|{r["candidate"]}|{r["group"]}|{r["games"]}|{reaction}|{giant}|{defence}|{share}|{num(r["median_game_search_p50_ms"])}|')
    lines.append('\nReaction is accepted enemy play to next own submitted play in simulator seconds; terminal enemy plays without a later own play are unobserved. An own play need not defend that threat. Percentiles pool observed events. Undefended share is the existing live_metrics enemy Giant lane-track proxy: no same-lane defence before contact, divided by observed Giant pushes. Defence-minus-crossing is signed time to first qualifying defence (negative means before river crossing), conditional on any defence observed. Contact-only denominators are also in metrics-summary.json. These proxies do not attribute damage causally. Search milliseconds are host-load-dependent measurements of the unbounded twin, not deployed wall200 latency.\n')
    return lines
