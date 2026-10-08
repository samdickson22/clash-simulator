"""T7 fit-evidence checks before validation replay; no I/O or heldout admission.

The future replay driver must authenticate completion/admission files, recompute
source and checkpoint hashes, and read checkpoint metadata before calling this
helper. Caller declarations alone never constitute a selection seal.
"""
import math
import re
from formal_guard import SPLIT_SHA


def _sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def validate_t7_fit(manifest, complete, inventory, training_rows, *,
                    admitted_train_receipts, checkpoints, measured_source_hashes):
    """Reject pilots/partial runs, population drift, and incomplete epoch sets."""
    expected = dict(seed=6108, device='cuda', precision='bf16', compile=False,
                    epochs=24, steps=400, max_matches=0, windows_per_match=32,
                    loader_workers=6, heldout_opened=False)
    for key, value in expected.items():
        if type(manifest.get(key)) is not type(value) or manifest[key] != value:
            raise ValueError(f'Not registered full T7 configuration: {key}')
    if manifest.get('engineering_only',False):raise ValueError('Engineering fit cannot enter formal selection')
    if not manifest.get('pixel_cache'):
        raise ValueError('Formal T7 cache required')
    if complete.get('steps_completed') != 9600 or complete.get('heldout_opened') is not False:
        raise ValueError('T7 fit incomplete or invalid heldout status')
    if complete.get('manifest') != manifest:
        raise ValueError('Completion and training manifest disagree')
    if not _sha(complete.get('checkpoint_sha256')):
        raise ValueError('Final checkpoint hash missing')
    source = manifest.get('source_hashes', {})
    if not source or source != measured_source_hashes or not all(_sha(v) for v in source.values()):
        raise ValueError('Measured runtime/training sources disagree')
    if inventory.get('split') != 'train' or inventory.get('split_sha256') != manifest.get('split_sha256'):
        raise ValueError('Training inventory split mismatch')
    if manifest.get('split_sha256') != SPLIT_SHA:
        raise ValueError('Frozen split hash changed')
    if not admitted_train_receipts or not all(_sha(v) for v in admitted_train_receipts.values()):
        raise ValueError('Authenticated full training admission required')
    observed = {}
    for row in inventory['matches']:
        ep = row['episode']
        if ep in observed or row['split'] != 'train':
            raise ValueError('Duplicate or non-training inventory entry')
        observed[ep] = row['receipt_sha256']
    if observed != admitted_train_receipts or manifest.get('training_matches') != len(observed):
        raise ValueError('Full admitted training population differs')
    indices = manifest.get('cache_index_sha256', {})
    if set(indices) != set(observed) or not all(_sha(v) for v in indices.values()):
        raise ValueError('Incomplete cache provenance')
    for key in ('cards', 'bodies'):
        vocab = manifest.get(key)
        if (not isinstance(vocab, list) or not vocab or any(not isinstance(x, str) or not x for x in vocab)
                or len(set(vocab)) != len(vocab)):
            raise ValueError('Invalid label vocabulary')
    if inventory.get('cards') != manifest['cards']:
        raise ValueError('Inventory card vocabulary differs')
    rows = list(training_rows)
    if len(rows) != 9600:
        raise ValueError('Training log must contain exactly 9600 unique contiguous steps')
    for step, row in enumerate(rows, 1):
        if type(row.get('step')) is not int or row['step'] != step:
            raise ValueError('Training log has missing/duplicate/reordered steps')
        loss = row.get('loss')
        if isinstance(loss, bool) or not isinstance(loss, (float, int)) or not math.isfinite(loss):
            raise ValueError('Nonfinite or missing training loss')
    if set(checkpoints) != set(range(1, 25)):
        raise ValueError('All 24 epoch checkpoints required before selection')
    for epoch, ckpt in checkpoints.items():
        if type(epoch) is not int or type(ckpt.get('step')) is not int or ckpt['step'] != epoch*400:
            raise ValueError('Epoch checkpoint step mismatch')
        if any(ckpt.get(k) != manifest[k] for k in ('cards', 'bodies')) or not _sha(ckpt.get('sha256')):
            raise ValueError('Epoch checkpoint vocabulary/hash mismatch')
    return dict(validated=True, scope='fit evidence only; authenticated replay driver still required',
                training_matches=len(observed), steps=9600, epochs=24,
                selection_seal=False, heldout_opening_authorized=False)
