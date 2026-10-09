"""Opt-in fair public candidate filter; no physical or hypothetical oracle input."""
import math

WAIT = 2304
THREAT_RADIUS = 6.


def filter_candidates(candidates, packet, catalog, opponent_elixir, *, enabled=False):
    if not enabled:
        return candidates
    obs = packet.observation
    balance = float(obs.global_features[5])*10
    if opponent_elixir < 5:
        return candidates
    # Canonical public actor coordinates. Own live crown towers are static token names.
    bodies = obs.entity_features[obs.entity_mask]
    ids = obs.entity_ids[obs.entity_mask]
    towers = [(float(f[0])*18,float(f[1])*32) for f, token in zip(bodies, ids)
              if f[2] > .5 and f[9] > 0 and catalog['bodies'].get(str(int(token)),{}).get('name','').rsplit(':',1)[-1] in ('Tower','KingTower')]
    threats = []
    for f in bodies:
        x,y = float(f[0])*18,float(f[1])*32
        if f[3] > .5 and f[4] > .5 and f[9] > 0 and (
                y <= 16 or any(math.hypot(x-tx,y-ty) <= THREAT_RADIUS for tx,ty in towers)):
            threats.append((x,y))
    result=[]
    for a in candidates:
        if a >= WAIT:
            result.append(a); continue
        name = catalog['token_names'][int(obs.hand_ids[a//576])]
        card = catalog['cards'][name]
        x,y = a%576%18+.5,a%576//18+.5
        # "Response" is a frozen geometry proxy: own-half same-lane placement
        # within six tiles of a visible qualifying hostile troop. Applies to
        # troops/buildings/spells equally, avoiding hidden target/path information.
        defensive = y <= 16 and any((x>=9)==(tx>=9) and
            math.hypot(x-tx,y-ty) <= THREAT_RADIUS for tx,ty in threats)
        if defensive or balance-card['cost'] >= 4-1e-6:
            result.append(a)
    assert WAIT in result
    return result
