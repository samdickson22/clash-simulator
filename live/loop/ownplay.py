"""Own-play de-duplication for the live loop (applied to each perception record before LiveSession.step).

Our own plays reach the translator twice: LiveSession._confirm_pending adds an own play event once the raw HUD shows the
tapped card left its slot (tick = poll, x/y = our target tile), and ~1 s later perception's temporal play head reports
the same deploy landing (owner 0, its own tick and position). LiveTranslator.accept_events de-duplicates on (owner,
card, tick, x, y), so the second copy was accepted as ANOTHER own play: the card is no longer in the tracked hand, so
OwnTracker.play re-anchored it into "the first slot the HUD disagrees on" and played it there — shifting the tracked
hand by one card (s12-m02 n666: Musketeer counted twice, slot 0 Valkyrie -> Archers; n844/n864 then tapped Skeletons /
MiniPekka while believing MiniPekka / Musketeer). The reverse order (perception first) is already handled by
_confirm_pending. A real second play of the same card within WINDOW is impossible: the card goes to the back of the
4-card queue.
"""
WINDOW = 60                     # ticks (3 s)


def dedupe_own_events(rec, sess, window=WINDOW):
    """Drop owner-0 events of a card our session already played within `window` ticks. Returns the number dropped."""
    evs = rec.get('events') or []
    if not evs or not getattr(sess, 'started', False):
        return 0
    now = sess.last_poll if sess.last_poll is not None else 0
    recent = {name for t, name in sess.tr.plays[0] if t >= now - window}
    if not recent:
        return 0
    keep = [e for e in evs if not (int(e.get('owner', 1)) == 0 and str(e.get('card')) in recent)]
    dropped = len(evs) - len(keep)
    if dropped:
        rec['events'] = keep
        sess.tr.stats['own_event_dup_dropped'] += dropped
    return dropped
