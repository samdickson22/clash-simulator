"""Unit tests for imitation.hp1.lagshift on hand-built rows (no store needed).

    python -m pytest imitation/hp1/test_lagshift.py -q
"""
import numpy as np
import pytest

from imitation.hp1.lagshift import WAIT, check_layout, compute_overlay, legal_bits


def masks(legal_sets):
    """mask_table rows (big-endian packbits) from lists of legal actions; WAIT always legal unless stated."""
    rows = []
    for legal in legal_sets:
        bits = np.zeros(2306, bool)
        bits[list(legal)] = True
        rows.append(np.packbits(np.concatenate([bits, np.zeros(2312 - 2306, bool)]), bitorder='big'))
    return np.stack(rows)


def build(rows):
    """rows: list of dicts(ep, tick, action, hand(4 cards + next), legal(list), s122=False, ok=True, w=1.)."""
    table = masks([r['legal'] for r in rows])
    return dict(expert_actions=np.array([r['action'] for r in rows], np.int16),
                expert_action_supervision_valid=np.array([r.get('ok', True) for r in rows], bool),
                weights=np.array([r.get('w', 1.) for r in rows], np.float32),
                episode_ids=np.array([r['ep'] for r in rows], np.int32),
                submitted_ticks=np.array([r['tick'] for r in rows], np.int64),
                hand_ids=np.array([r['hand'] for r in rows], np.int16),
                mask_index=np.arange(len(rows), dtype=np.int32), mask_table=table,
                corpus_s122=np.array([r.get('s122', False) for r in rows], bool))


HAND = [11, 12, 13, 14, 15]          # card 13 sits in slot 2


def episode(ep, n, play_at, legal_from_tick, tile=100, slot=2, start=0, hand_at=None, extra=None):
    rows = []
    for i in range(n):
        t = start + 5 * i
        hand = (hand_at or {}).get(t, HAND)
        s = hand.index(13) if 13 in hand[:4] else None
        legal = [WAIT] + ([s * 576 + tile] if s is not None and t >= legal_from_tick else [])
        rows.append(dict(ep=ep, tick=t, action=WAIT, hand=hand, legal=legal))
    i = (play_at - start) // 5
    rows[i]['action'] = slot * 576 + tile
    rows[i]['legal'] = sorted(set(rows[i]['legal']) | {slot * 576 + tile})
    return rows


def test_bit_order_matches_packbits_big():
    t = masks([[0, 7, 8, 2304, 2305]])
    got = legal_bits(t, np.zeros(6, int), [0, 7, 8, 9, 2304, 2305])
    assert got.tolist() == [True, True, True, False, True, True]


def test_shift_to_earliest_legal_within_30_ticks_and_busy_rows():
    rows = episode(1, 20, play_at=60, legal_from_tick=0)
    a, ok, w, s = compute_overlay(build(rows))
    # earliest legal within 30 ticks before tick 60 is tick 30 (row 6); play row 12 becomes WAIT
    assert a[6] == 2 * 576 + 100 and a[12] == WAIT and ok[6] and ok[12]
    assert not ok[7:12].any() and ok[:6].all() and ok[13:].all()
    assert s['shifted_earlier'] == 1 and s['dt_ticks'] == {'30': 1} and s['supervised_plays_after'] == 1


def test_affordability_limits_the_shift():
    rows = episode(1, 20, play_at=60, legal_from_tick=45)      # only legal from tick 45
    a, ok, _, s = compute_overlay(build(rows))
    assert a[9] == 2 * 576 + 100 and a[12] == WAIT and s['dt_ticks'] == {'15': 1}
    # submitted at 45, due 72: ticks 50..70 are busy, including the original play row (tick 60)
    assert not ok[10:15].any() and ok[15]


def test_card_not_in_hand_keeps_original_row():
    other = [11, 12, 14, 16, 13]                             # 13 only in the next-card slot before tick 60
    rows = episode(1, 20, play_at=60, legal_from_tick=0, hand_at={t: other for t in range(0, 60, 5)})
    a, ok, _, s = compute_overlay(build(rows))
    assert a[12] == 2 * 576 + 100 and s['unshifted'] == 1 and ok[:13].all()
    assert not ok[13:18].any() and ok[18:].all()            # due 87: ticks 65..85 busy


def test_slot_is_remapped_when_the_card_moved():
    moved = [13, 11, 12, 14, 15]                             # 13 in slot 0 before tick 50
    rows = episode(1, 20, play_at=60, legal_from_tick=0, hand_at={t: moved for t in range(0, 50, 5)})
    a, ok, _, s = compute_overlay(build(rows))
    assert a[6] == 0 * 576 + 100 and s['dt_ticks'] == {'30': 1}


def test_previous_play_bounds_the_next_shift():
    rows = episode(1, 30, play_at=60, legal_from_tick=0)
    rows[14]['action'] = 2 * 576 + 100                        # a second play of the same card at tick 70
    rows[14]['legal'] = [WAIT, 2 * 576 + 100]
    a, ok, _, s = compute_overlay(build(rows))
    # first play -> tick 30 (due 57). The second may start at 57; tick 60 is the first play's own row (not a free
    # WAIT row in the labels), so its earliest legal row is tick 65 (dt 5), due 92: ticks 70..90 are busy.
    assert a[6] == 2 * 576 + 100 and a[12] == WAIT and a[13] == 2 * 576 + 100 and a[14] == WAIT
    assert s['dt_ticks'] == {'5': 1, '30': 1}
    assert ok[12] and ok[13] and not ok[14:19].any() and not ok[7:12].any()


def test_command_still_pending_delays_the_next_play():
    # Sol r1 regression: play 1 at tick 50 is legal only from 45 -> submitted 45, due 72. Play 2 at tick 70 cannot be
    # submitted before 72, so it is delayed to the next free legal row (tick 75), never placed inside the busy window.
    rows = episode(1, 30, play_at=50, legal_from_tick=45)
    rows[14]['action'] = 2 * 576 + 100
    a, ok, _, s = compute_overlay(build(rows))
    assert a[9] == 2 * 576 + 100 and a[10] == WAIT and a[15] == 2 * 576 + 100 and a[14] == WAIT
    assert s['delayed'] == 1 and s['dt_ticks'] == {'-5': 1, '5': 1}
    assert not ok[10:15].any() and ok[15] and not ok[16:21].any()     # second busy window ticks 80..100


def test_play_dropped_when_no_free_legal_row():
    rows = episode(1, 30, play_at=50, legal_from_tick=45)
    rows[14]['action'] = 2 * 576 + 100
    for r in rows[15:]:
        r['legal'] = [WAIT]                                      # never legal again after tick 70
    a, ok, _, s = compute_overlay(build(rows))
    assert s['dropped'] == 1 and not ok[14] and s['supervised_plays_after'] == 1


def test_perspective_boundary_and_thinned_rows():
    first = episode(1, 4, play_at=15, legal_from_tick=0)
    second = episode(2, 20, play_at=60, legal_from_tick=0)
    second = [r for r in second if r['tick'] not in (30, 35)]  # thinned waits: the row 30 ticks back is missing
    a, ok, _, s = compute_overlay(build(first + second))
    # first: play at tick 15 of perspective 1 can only move to tick 0 (dt 15), never into another perspective
    assert a[0] == 2 * 576 + 100 and a[3] == WAIT
    # second: earliest stored row within 30 ticks is tick 40 (dt 20)
    assert s['dt_ticks'] == {'15': 1, '20': 1}


def test_unsupervised_rows_are_never_targets():
    rows = episode(1, 20, play_at=60, legal_from_tick=0)
    for i in range(6, 9):
        rows[i]['ok'] = False
    a, ok, _, s = compute_overlay(build(rows))
    assert s['dt_ticks'] == {'15': 1} and a[9] == 2 * 576 + 100


def test_layout_checks():
    with pytest.raises(ValueError):
        check_layout(np.array([1, 1, 2, 1]), np.array([0, 5, 0, 10]))
    with pytest.raises(ValueError):
        check_layout(np.array([1, 1]), np.array([5, 5]))


def test_weights_follow_the_play():
    rows = episode(1, 20, play_at=60, legal_from_tick=0)
    rows[12]['w'] = 0.5; rows[6]['w'] = 2.0
    _, _, w, _ = compute_overlay(build(rows))
    assert w[6] == 0.5 and w[12] == 0.5


def test_long_delay_masks_the_whole_busy_window():
    rows = episode(1, 40, play_at=60, legal_from_tick=0)
    a, ok, _, s = compute_overlay(build(rows), max_shift=30, delay=100)
    # submitted at 30, due 130: every row with 30 < tick < 130 is busy
    assert a[6] == 2 * 576 + 100 and not ok[7:26].any() and ok[26]


def test_long_shift_reaches_the_earliest_legal_row():
    rows = episode(1, 40, play_at=150, legal_from_tick=0)
    a, ok, _, s = compute_overlay(build(rows), max_shift=100, delay=27)
    assert a[10] == 2 * 576 + 100 and s['dt_ticks'] == {'100': 1}


def test_unsupported_parameters_and_cadence_rejected():
    rows = episode(1, 10, play_at=30, legal_from_tick=0)
    with pytest.raises(ValueError):
        compute_overlay(build(rows), max_shift=200)
    with pytest.raises(ValueError):
        check_layout(np.array([1, 1]), np.array([0, 3]))


def test_final_unsupervised_terminal_row_may_be_off_cadence():
    rows = episode(1, 20, play_at=60, legal_from_tick=0)
    rows.append(dict(ep=1, tick=rows[-1]['tick'] + 2, action=WAIT, hand=HAND, legal=[WAIT], ok=False))
    rows += episode(2, 10, play_at=20, legal_from_tick=0)
    a, ok, _, s = compute_overlay(build(rows))
    assert s['shifted_earlier'] == 2
    bad = episode(1, 20, play_at=60, legal_from_tick=0)
    bad.append(dict(ep=1, tick=bad[-1]['tick'] + 2, action=WAIT, hand=HAND, legal=[WAIT], ok=True))   # supervised
    with pytest.raises(ValueError):
        compute_overlay(build(bad))
    mid = episode(1, 20, play_at=60, legal_from_tick=0)
    mid[5]['tick'] = mid[4]['tick'] + 2                                                      # not the last row
    with pytest.raises(ValueError):
        compute_overlay(build(mid))
