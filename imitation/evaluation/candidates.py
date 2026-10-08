"""Pure matched-count proposal replacement."""
import numpy as np


def replacement_candidates(base, baseline, proposals, mask, rng):
    """Keep A's exact post-dedup count, including random/script collisions.

    Stage 5b samples 16 before deduplication. Its actual unique quota can be
    smaller. B fills that identical quota; it never adds eight extra candidates.
    """
    result = list(base)
    target = len(baseline)
    for a in proposals:
        a = int(a)
        if not 0 <= a < 2304 or not mask[a]:
            raise ValueError(f'illegal imitation proposal: {a}')
        if a not in result and len(result) < target:
            result.append(a)
    # Reuse A's draw/order for common-random-number coupling where possible.
    for a in baseline:
        if a not in result and len(result) < target:
            result.append(a)
    if len(result) < target:
        pool = np.array([a for a in np.flatnonzero(mask[:2304]) if a not in result])
        result.extend(map(int, rng.choice(pool, target-len(result), replace=False)))
    assert len(result) == len(baseline) == len(set(result))
    return result

