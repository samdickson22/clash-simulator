"""T3 frequency baseline in float64, including its exact zero-mass convention.

Do not turn zero training count into a pseudo-count through logit clipping.
T3 clips the FINAL probability at 1e-300 for NLL, not counts at 1e-30.
Only tile histograms receive the specified add-one smoothing.
"""
import numpy as np


def frequency_rows(store, indices, counts):
    ix = np.asarray(indices); a = store.arrays; n = len(ix)
    valid = a['expert_action_supervision_valid'][ix].astype(bool)
    action = a['expert_actions'][ix].astype(np.int64)
    hand = a['hand_ids'][ix, :4]
    if 'action_mask' in a:
        mask = a['action_mask'][ix].astype(bool)
    else:
        mask = np.unpackbits(a['mask_table'][a['mask_index'][ix]], axis=1,
                             bitorder=getattr(store, 'mask_bitorder', 'little'))[:, :2306].astype(bool)
    if not mask[:, 2304].all():
        raise ValueError('T3 baseline convention requires legal wait')
    placements = mask[:, :2304].reshape(n, 4, 576); legal = placements.any(2)
    ticks = a['submitted_ticks'][ix]
    phase = np.where(ticks<2400, 0, np.where(ticks<3600, 1, 2))
    bucket = phase*11+np.clip(np.floor(a['global_features'][ix, 5]*10+1e-5), 0, 10).astype(np.int64)
    gate = counts['gate'][bucket].astype(np.float64)
    gate[:, 1] *= legal.any(1); gate[:, 2] *= mask[:, 2305]
    empty = gate.sum(1)==0
    gate[empty] = counts['gate'].sum(0)
    gate[empty, 1] *= legal[empty].any(1); gate[empty, 2] *= mask[empty, 2305]
    if (gate.sum(1)==0).any(): raise ValueError('no legal global frequency mass')
    gate /= gate.sum(1, keepdims=True)
    play = valid & (action<2304); row = np.flatnonzero(play)
    slot, tile = action[row]//576, action[row]%576
    cp = counts['cards'][hand[row]].astype(np.float64)*legal[row]
    empty = cp.sum(1)==0; cp[empty] = legal[row][empty]
    cp /= cp.sum(1, keepdims=True)
    # The frozen T3 implementation conditions card on the labelled slot.
    if len(row) and (np.diff(np.sort(hand[row], axis=1), axis=1)==0).any():
        raise ValueError('duplicate hand token would break baseline/spec alignment')
    hist = (counts['tiles'][hand[row, slot]]+1).astype(np.float64)*placements[row, slot]
    tile_probability = hist[np.arange(len(row)), tile]/hist.sum(1)
    gate_y = np.where(action==2304, 0, np.where(action==2305, 2, 1))
    joint = -np.log(gate[np.arange(n), gate_y].clip(1e-300, 1))
    card_nll = -np.log(cp[np.arange(len(row)), slot].clip(1e-300, 1))
    tile_nll = -np.log(tile_probability.clip(1e-300, 1))
    joint[row] += card_nll+tile_nll
    binary = np.where(action==2304, gate[:, 0], gate[:, 1:].sum(1))
    result = {'joint_nll': np.where(valid, joint, np.nan),
              'play_wait_nll': np.where(valid & legal.any(1), -np.log(binary.clip(1e-300, 1)), np.nan),
              'card_nll': np.full(n, np.nan), 'tile_nll': np.full(n, np.nan)}
    result['card_nll'][row] = card_nll; result['tile_nll'][row] = tile_nll
    return result


if __name__ == '__main__':
    import argparse
    import json
    from pathlib import Path
    import time
    from imitation.model.store import PackedStore
    from .guards import write_once, sha
    p = argparse.ArgumentParser(description='Dev-only alignment check; no model inference')
    for key in ('store', 'assets', 'counts', 'reference', 'output'):
        p.add_argument('--'+key, required=True)
    a = p.parse_args(); start = time.monotonic()
    store = PackedStore(a.store, 'dev', a.assets)
    with np.load(a.counts, allow_pickle=False) as z:
        counts = {k: z[k] for k in ('gate','cards','tiles')}
    reference = json.loads(Path(a.reference).read_text())
    if reference['role']!='dev' or reference['count_sha256']!=sha(a.counts):
        raise ValueError('baseline dev/count provenance mismatch')
    sums = {}; nums = {}
    for start_row in range(0, len(store), 8192):
        rows = frequency_rows(store, np.arange(start_row, min(len(store), start_row+8192)), counts)
        for key, v in rows.items():
            sums[key] = sums.get(key, 0.)+np.nansum(v, dtype=np.float64)
            nums[key] = nums.get(key, 0)+int(np.isfinite(v).sum())
    checks = {}
    for key in sums:
        field = 'play_wait_nll_playable' if key=='play_wait_nll' else key
        value = sums[key]/nums[key]; expected = reference['metrics'][field]
        if abs(value-expected)>1e-10: raise ValueError((key,value,expected))
        checks[key] = {'value': value, 'T3_value': expected, 'rows': nums[key]}
    write_once(a.output, {'passed': True, 'role': 'dev', 'model_inference': False,
                         'counts_sha256': sha(a.counts), 'reference_sha256': sha(a.reference),
                         'checks': checks, 'wall_seconds': time.monotonic()-start})
