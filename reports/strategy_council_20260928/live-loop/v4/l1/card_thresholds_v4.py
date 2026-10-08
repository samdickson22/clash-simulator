"""Per-card validation threshold proposals from a complete selected-epoch grid.

Pure helper, no file access or seal. The caller must authenticate the nine full
validation replays and the selected epoch through the formal grid driver first.
Thresholds are shared by native seats in EventFusion, so per-card support and
counts pool both seats. This does not refit the selected epoch or global default.
"""
from selection_matrix_v4 import counts
from scoring_v4 import select_threshold


def select_card_thresholds(sweep, *, global_threshold):
    sweep = list(sweep)
    grid = [i/10 for i in range(1, 10)]
    if (len(sweep) != 9 or sorted(r['threshold'] for r in sweep) != grid
            or isinstance(global_threshold, bool) or global_threshold not in grid):
        raise ValueError('Complete registered grid and selected global threshold required')
    epochs = {r['epoch'] for r in sweep}
    if len(epochs) != 1 or any(type(e) is not int or not 1 <= e <= 24 for e in epochs):
        raise ValueError('One selected formal epoch required')
    reference = sweep[0]
    body_threshold=reference.get('body_threshold')
    if type(body_threshold) not in (int,float) or body_threshold not in grid:
        raise ValueError('Explicit registered body threshold required')
    for row in sweep:
        if (row.get('schema') != 'clasher.v4.validation-score.v1'
                or row.get('replay_mode')!='grid' or row.get('event_thresholds')!={'default':row['threshold']}
                or row.get('heldout_payloads_opened') is not False
                or row.get('selection_seal') is not False
                or type(row.get('body_threshold')) not in (int,float)
                or any(row.get(k) != reference.get(k) for k in
                       ('readiness', 'validation_receipts', 'truth_payloads', 'sources','body_threshold'))):
            raise ValueError('Mixed validation evidence')
    tables, cards, truth_reference = {}, set(), None
    for row in sweep:
        score = row['point']
        if score['timing'] != 'point':
            raise ValueError('Point-time threshold objective required')
        table, total, opponent = {}, [0,0,0], [0,0,0]
        for entry in score['per_card_side']:
            card, side = entry['card'], entry['side']
            if (not isinstance(card, str) or not card or card == 'default'
                    or type(side) is not int or side not in (0,1) or (card,side) in table):
                raise ValueError('Invalid or duplicate card-side identity')
            count = counts(entry)
            table[card,side] = count
            total = [a+b for a,b in zip(total,count)]
            if side == 0: opponent = [a+b for a,b in zip(opponent,count)]
            cards.add(card)
        if tuple(total) != counts(score['all_sides']) or tuple(opponent) != counts(score['opponent']):
            raise ValueError('Card-side counts do not sum to full population')
        # Zero-truth false-positive cards can occur only at lower thresholds;
        # missing zero rows are equivalent. Nonzero truth must never disappear.
        truth = {key:value[0] for key,value in table.items() if value[0]}
        if truth_reference is not None and truth != truth_reference:
            raise ValueError('Per-card-side truth population changed')
        truth_reference = truth
        tables[row['threshold']] = table
    thresholds, support = {'default':global_threshold}, {}
    for card in sorted(cards):
        rows = []
        for threshold in grid:
            pooled = tuple(sum(tables[threshold].get((card,side),(0,0,0))[k] for side in (0,1))
                           for k in range(3))
            rows.append(dict(threshold=threshold, opponent=dict(zip(('truth','predictions','matched'),pooled))))
        n = rows[0]['opponent']['truth']
        eligible = n >= 10
        chosen = select_threshold(rows) if eligible else None
        if eligible: thresholds[card] = chosen['threshold']
        support[card] = dict(validation_events=n, eligible=eligible,
                             threshold=chosen['threshold'] if eligible else global_threshold,
                             fit='per_card' if eligible else 'global',
                             counts=chosen['opponent'] if eligible else None)
    return dict(schema='clasher.v4.card-thresholds.v1', epoch=next(iter(epochs)),
                body_threshold=body_threshold,
                thresholds=thresholds, support=support, objective='both native seats, card-play F1 at 500ms',
                selection_seal=False, heldout_opening_authorized=False,
                scope='pure proposal; authenticated final replay and calibration still required')
