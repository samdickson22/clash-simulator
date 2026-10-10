"""V6 column serialization using gate (c)'s public-only serving adapter."""
import hashlib
import json
from pathlib import Path
import numpy as np
from imitation.evaluation.d1 import model_packet
from imitation.model.features import ENTITY_COLUMNS, build_row

WAIT = 2304


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for part in iter(lambda: f.read(1 << 20), b''):
            h.update(part)
    return h.hexdigest()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.partial')
    tmp.write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')
    tmp.replace(path)


def observation(packet, mask, d1, builder=None):
    p = model_packet(packet, mask)
    active = p['entity_mask']
    row = {k: np.asarray(p[k]).copy() for k in
           ('hand_ids', 'hand_levels', 'global_features', 'opponent_seen_card_ids', 'champion_button')}
    obs=packet.observation
    row['hand_ids']=row['hand_ids'].astype(np.int16)
    row['hand_levels']=row['hand_levels'].astype(np.int8)
    row['opponent_seen_card_ids']=row['opponent_seen_card_ids'].astype(np.int16)
    row['opponent_history_ids']=obs.opponent_history_ids.astype(np.int16)
    row['opponent_history_ages']=obs.opponent_history_ages.astype(np.float32)
    row['board_rotated']=np.int8(-1 if obs.board_rotated is None else int(obs.board_rotated))
    row['terminal_status']=np.int8(-1 if obs.terminal is None else int(obs.terminal))
    accepted=obs.own_last_play
    row['own_last_play_ids']=np.int16(0 if accepted is None else builder.token_id(accepted.card_name,namespace='card_action'))
    row['own_last_play_features']=np.array([float(accepted is not None),0. if accepted is None else accepted.elixir_cost/10],np.float32)
    row.update({k: np.asarray(v).copy() for k, v in d1.items()})
    row.update(entity_counts=np.int16(active.sum()),
               flat_entity_ids=p['entity_ids'][active].astype(np.int16),
               flat_entity_levels=p['entity_levels'][active].astype(np.int8),
               flat_entity_features=p['entity_features'][active][:, ENTITY_COLUMNS].astype(np.float32),
               packed_mask=np.packbits(mask))
    return row


def feature_bytes(row, costs):
    p = {k: row[k] for k in ('hand_ids', 'hand_levels', 'global_features',
                             'opponent_seen_card_ids', 'champion_button')}
    p.update(action_mask=np.unpackbits(row['packed_mask'])[:2306].astype(bool),
             entity_ids=row['flat_entity_ids'], entity_levels=row['flat_entity_levels'],
             entity_features=row['flat_entity_features'],
             entity_mask=np.ones(int(row['entity_counts']), bool))
    return build_row(p, row, costs)


def seal(directory, rows, score_rows, receipt):
    """One completed game = one mmap shard; ragged scores preserve timed WAIT IDs."""
    directory = Path(directory)
    role = directory/'train'
    role.mkdir(parents=True, exist_ok=False)
    n = len(rows)
    arrays = {}
    for key in rows[0]:
        if key == 'packed_mask':
            continue
        arrays[key] = (np.concatenate([r[key] for r in rows]) if key.startswith('flat_entity_')
                       else np.asarray([r[key] for r in rows]))
    masks, inverse = np.unique(np.asarray([r['packed_mask'] for r in rows]), axis=0, return_inverse=True)
    arrays['mask_index'] = inverse.astype(np.int32)
    arrays['entity_offsets'] = np.r_[0, np.cumsum(arrays['entity_counts'], dtype=np.int64)]
    arrays['row_ids'] = np.arange(n, dtype=np.int64)
    arrays['perspective_ids'] = np.full(n, receipt['seed'], np.int64)
    arrays['episode_ids'] = np.zeros(n,np.int32)
    arrays['episode_starts'] = np.arange(n) == 0
    arrays['wait_ipw'] = np.where(arrays['expert_actions'] == WAIT, 4., 1.).astype(np.float32)
    arrays['weights'] = np.ones(n, np.float32)
    arrays['recorded_outcome'] = np.full(n, receipt['outcome'], np.int8)
    arrays['previous_actions']=np.r_[WAIT,arrays['expert_actions'][:-1]].astype(np.int16)
    arrays['source_unit']=np.zeros(n,np.int16)
    arrays['source_row']=np.arange(n,dtype=np.int32)
    arrays['source_mask_index']=arrays['mask_index'].copy()
    arrays['label_projection_distance']=np.zeros(n,np.float32)
    arrays['tower_clamped']=np.zeros(n,bool)
    arrays['overshoot_frac']=np.zeros(n,np.float32)
    arrays['intent_deck_index'] = np.full(n, -1, np.int8)
    arrays['intent_delay_ticks'] = np.zeros(n, np.int32)
    arrays['intent_censored'] = np.ones(n, bool)
    arrays['root_offsets'] = np.r_[0, np.cumsum([len(s['candidates']) for s in score_rows], dtype=np.int64)]
    arrays['root_actions'] = np.asarray([a for s in score_rows for a in s['candidates']], np.int16)
    arrays['root_scores'] = np.asarray([0. if v is None else v for s in score_rows for v in s['scores']], np.float64)
    arrays['root_valid'] = np.asarray([v is not None for s in score_rows for v in s['scores']], bool)
    for name, value in arrays.items():
        np.save(role/(name+'.npy'), value, allow_pickle=False)
    np.save(directory/'mask_table.npy', masks, allow_pickle=False)
    write_json(role/'manifest.json', dict(role='train', rows=n, entities=int(arrays['entity_offsets'][-1]),
        arrays={k: dict(dtype=str(v.dtype), shape=list(v.shape), sha256=sha(role/(k+'.npy'))) for k,v in arrays.items()}))
    write_json(directory/'receipt.json', receipt)
    files = [p for p in directory.rglob('*') if p.is_file() and not p.name.endswith('.partial')]
    write_json(directory/'manifest.json', dict(schema='clasher.exit-r1.teacher-v6.v1', complete=True,
        rows=n, outcome=receipt['outcome'], files={str(p.relative_to(directory)): sha(p) for p in files},
        fair_information='gate-c public v5 + event-derived D1 + own opening order; independent search belief/RNG'))
