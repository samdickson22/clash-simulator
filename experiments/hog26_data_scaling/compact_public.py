"""Remove only entity storage masked for every decision of an audited game."""
import numpy as np
import torch
from scalar_dataset import PUBLIC_FIELDS
from scalar_models import PublicSequence


def compact_public(public):
    mask = np.asarray(public['entity_mask'])
    if mask.ndim != 2 or not len(mask) or mask.shape[1] == 0:
        raise ValueError('expected a nonempty game with entity storage')
    occupied = np.flatnonzero(mask.any(axis=0))
    width = max(1, int(occupied[-1]) + 1 if len(occupied) else 1)
    result = {}
    for key, value in public.items():
        if key.startswith('entity_'):
            if value.shape[:2] != mask.shape:
                raise ValueError('entity field shape differs from mask')
            if np.any(value[:, width:] != 0):
                raise ValueError('discarded entity storage must be zero padding')
            result[key] = value[:, :width].copy()
        else:
            result[key] = value
    return result


def compact_public_batch(games):
    """Recreate the original batch padding for variable-width audited games."""
    if not games:
        raise ValueError('empty batch')
    lengths = torch.tensor([len(g.public['entity_ids']) for g in games], dtype=torch.long)
    max_time = int(lengths.max())
    width = max(1, max((int(np.flatnonzero(g.public['entity_mask'].any(axis=0))[-1]) + 1
                        if g.public['entity_mask'].any() else 1) for g in games))
    tensors = {}
    for key in PUBLIC_FIELDS:
        first = games[0].public[key]
        shape = (width, *first.shape[2:]) if key.startswith('entity_') else first.shape[1:]
        values = np.zeros((len(games), max_time, *shape), dtype=first.dtype)
        for index, game in enumerate(games):
            incoming = game.public[key]
            if key.startswith('entity_'):
                incoming = incoming[:, :width]
                values[index, :len(incoming), :incoming.shape[1]] = incoming
            else:
                values[index, :len(incoming)] = incoming
        tensors[key] = torch.from_numpy(values)
    return PublicSequence(**tensors), lengths
