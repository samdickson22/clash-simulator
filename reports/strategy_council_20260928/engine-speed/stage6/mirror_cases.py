"""History-aware focused fixture; unchanged source engine and comparator."""
from stage2 import *

def focused_case(focus, case, cfg, ticks=2200, trace_tick=None):
    cards = (focus,) + tuple(c for c in CARDS if c != focus)
    b = initial(21000 + case, cards=cards)
    for p in b.players:
        # High-cost focused cards must actually enter play in this fixture.
        # Real-game gates retain the reference's ordinary starting elixir.
        p.elixir = max(p.elixir, cfg["cards"][focus]["cost"])
        p.deck = (list(cards) * 2)[:8]
        p.hand = list(cards[:4])
        p.cycle_queue = deque((list(cards) * 2)[4:8])
    r = clasher_core.BattleState(snapshot(b, cfg))
    actions = []
    coverage = dict(jump_ticks=0, stun_ticks=0, push_ticks=0, hidden_ticks=0)
    pcpu = rcpu = 0.0
    for t in range(trace_tick or ticks):
        if b.game_over:
            break
        if t % 80 == 0:
            for seat in (0, 1):
                p = b.players[seat]
                card = next(
                    (
                        c
                        for c in cards
                        if c in p.hand and b.resolve_card_play(seat,c) is not None
                        and p.elixir + 1e-9 >= b.resolve_card_play(seat,c)[1].mana_cost
                    ),
                    None,
                )
                if card:
                    x = (4.5, 13.5)[(t // 80 + seat + case) % 2]
                    if case >= 6:
                        x = (8.5, 9.5)[(t // 80 + seat + case) % 2]
                    # Keep troop fixtures unchanged; building footprints need deeper forward anchors.
                    y = (
                        (10.5 - case % 3 if seat == 0 else 21.5 + case % 3)
                        if cfg["cards"][focus]["footprint"] == 0
                        else (10.5 + case % 3 if seat == 0 else 21.5 - case % 3)
                    )
                    if cfg["cards"][card].get("spell") and not cfg["cards"][card][
                        "spell"
                    ].get("requires_territory"):
                        targets = [
                            e
                            for e in b.entities.values()
                            if e.player_id != seat
                            and e.is_alive
                            and type(e).__name__ == "Troop"
                        ]
                        if targets:
                            target = targets[(case + t // 80) % len(targets)]
                            x, y = target.position.x, target.position.y
                        else:
                            x, y = 3.5, 25.5 if seat == 0 else 6.5
                    pa = b.deploy_card(seat, card, Position(x, y))
                    ra = r.apply_action(seat, card, x, y)
                    actions.append([t, seat, card, x, y, pa, ra])
                    if pa != ra or battle_digest(b) != r.digest():
                        return dict(
                            ok=False,
                            kind="action",
                            tick=t,
                            actions=actions,
                            **detail(b, r),
                        )
        if trace_tick and t == trace_tick - 1:
            return phase_step(b, r)
        start = time.process_time()
        b.step()
        pcpu += time.process_time() - start
        start = time.process_time()
        r.step()
        rcpu += time.process_time() - start
        for field, attr in [
            ("jump_ticks", "_river_jump_active"),
            ("stun_ticks", "stun_timer"),
            ("push_ticks", "_knockback_target"),
            ("hidden_ticks", "_hidden_building"),
        ]:
            coverage[field] += any(
                bool(getattr(e, attr, False)) for e in b.entities.values()
            )
        words, index = r.rng_state()
        if (
            battle_digest(b) != r.digest()
            or tuple(words) + (index,) != b.rng.getstate()[1]
        ):
            return dict(
                ok=False, kind="tick", tick=b.tick, actions=actions, **detail(b, r)
            )
    return dict(
        ok=any(a[2] == focus and a[-1] for a in actions),
        focal_accepted=sum(a[2] == focus and a[-1] for a in actions),
        ticks=b.tick,
        game_over=b.game_over,
        python_cpu=pcpu,
        rust_cpu=rcpu,
        digest=battle_digest(b),
        coverage=coverage,
        actions=len(actions),
        accepted=sum(a[-1] for a in actions),
    )

