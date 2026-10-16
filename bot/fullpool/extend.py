"""Checkpoint converters: C56-trained models -> full-pool models, bit-identical on C56 inputs (exploration).

    # policy nets (v1 main02.pt, R3a.pt, it5s2, RL r5 snapshots: any imitation/exit_r3 SetPolicy checkpoint)
    python -m bot.fullpool.extend policy --in CKPT --out OUT.pt [--init row|input]
    # K4L learned rollout opponent (.npz from bot/search/lopp_train.py); card tokens from the r1-cards1 R.meta
    python -m bot.fullpool.extend meta-tokens --out META.json        # under CLASHER_BOT_RUNTIME_PINS=r1-cards1
    python -m bot.fullpool.extend lopp --in pool.npz --out poolfp.npz --meta META.json

Policy nets (SetPolicy, vocab 360 = the contract-v5 token walk over all 122 cards). The shape already covers every
card; rows of tokens that only non-C56 cards produce were never trained (weight decay only: R3a and RL r5 v10 rows
of all 223 such tokens moved by exactly the decay factor, see reports/bot/fullpool/INVENTORY.md). The converter
overwrites only those rows:
  card token of each new card      <- card token row of its proxy card (bot/cards/proxy_table NAMED.proxy_card)
  each body in the card's body_map <- token row of the proxy body (when the body token is new-card-only)
  every other new-only token (projectiles, buffs, areas) is left as is.
--init row (default) copies card_embed rows; the token keeps its own descriptor/cost buffers (true stats).
--init input copies the full input embedding: E[new] = E[proxy] + D(desc[proxy]) - D(desc[new]), so the new card
encodes exactly as its proxy. A row is overwritten only if its token is owned by no C56 card, so a C56-only input
indexes only untouched rows: outputs are identical by construction (embedding = gather), and the parity test
(bot/fullpool/parity.py) checks it on recorded roots. Shapes, keys and loaders are unchanged.

K4L (.npz): vocab = [pad] + C56 meta tokens. New cards are APPENDED (never renumbered): emb/tem rows and the card
logit columns copy the proxy card's; meta_cost = the runtime's config cost. The new logit columns are stored as
Wv_x/bv_x and computed by their own matmul (lopp_feat.NumpyOpponent.heads), so the C56 columns are the same BLAS call
as before. Only hand-slot logits are ever read, so C56 hands give identical decisions.

Every output gets OUT.fullpool.json (input/output sha256, row map, mode) and, for policies, the input's
.calibration.json copied next to it (student:OUT reads its threshold from there).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np

from bot.fullpool.cards import C56, EXCLUDED, NEW, body_proxies, engine_name, proxy_card, vocab_name


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def token_owners(builder):
    """{token id: set of ENGINE card names whose contract-v5 token walk produces it} (structured_obs walk)."""
    from clasher.rl.structured_obs import _walk_named_payloads
    owners = {}
    for card in builder.card_vocab:
        stats = builder.loader.get_card(card)
        raw = getattr(stats, '_raw_entry', {}) or {}
        for name in {card, *_walk_named_payloads(raw)}:
            owners.setdefault(int(builder.token_id(name)), set()).add(engine_name(card))
    return owners


def policy_rowmap(builder):
    """[(dst token, src token, why)] and skipped [(token, why)] for the policy-net extension."""
    owners = token_owners(builder)
    names = list(builder.token_names)
    unknown = int(builder.token_id(None))
    new_only = {t for t, cs in owners.items() if not cs & set(C56)}
    rows, skipped, taken = [], [], {}

    def add(dst, src, why):
        if dst in (0, unknown):
            skipped.append((dst, f'{why}: pad/unknown token'))
        elif dst not in new_only:
            skipped.append((dst, f'{why}: {names[dst]} is also produced by a C56 card ({sorted(owners.get(dst, ()))[:3]})'))
        elif src in new_only or src in (0, unknown):
            skipped.append((dst, f'{why}: source {names[src]} is not a C56 token'))
        elif dst in taken:
            if taken[dst] != src:
                skipped.append((dst, f'{why}: already mapped from {names[taken[dst]]}'))
        else:
            taken[dst] = src
            rows.append((dst, src, why))

    for card in NEW + EXCLUDED:
        proxy = proxy_card(card)
        add(int(builder.token_id(vocab_name(card))), int(builder.token_id(proxy)), f'card {card} <- {proxy}')
        for body, pbody in sorted(body_proxies(card).items()):
            if pbody is None:
                continue
            add(int(builder.token_id(body)), int(builder.token_id(pbody)), f'body {body} ({card}) <- {pbody}')
    return rows, skipped, sorted(new_only)


def extend_policy(src, dst, builder, init='row'):
    import torch
    ck = torch.load(src, map_location='cpu', weights_only=True)
    rows, skipped, new_only = policy_rowmap(builder)
    dsts = [d for d, _, _ in rows]
    srcs = [s for _, s, _ in rows]
    done = set()
    for key in ('ema', 'model'):
        sd = ck.get(key)
        if sd is None:
            continue
        E = sd['card_embed.weight']
        if E.data_ptr() in done:      # bot.rl.learner saves one state dict as both ema and model
            continue
        done.add(E.data_ptr())
        with torch.no_grad():
            if init == 'row':
                E[dsts] = E[srcs]
            elif init == 'input':
                W = sd['descriptor.weight'].double()                    # Linear(descriptors -> width), no bias
                desc = sd['descriptors'].double()
                E[dsts] = (E[srcs].double() + desc[srcs] @ W.T - desc[dsts] @ W.T).to(E.dtype)
            else:
                raise ValueError(init)
    ck.setdefault('args', {})
    ck['fullpool'] = dict(kind='policy', init=init, source_sha256=sha256(src), rows=len(rows))
    tmp = Path(str(dst) + '.partial')
    torch.save(ck, tmp)
    tmp.replace(dst)
    cal = Path(str(src) + '.calibration.json')
    if cal.exists():
        shutil.copyfile(cal, str(dst) + '.calibration.json')
    names = list(builder.token_names)
    receipt = dict(kind='policy', source=str(src), source_sha256=sha256(src), output=str(dst), output_sha256=sha256(dst),
                   init=init, tokens_sha256=builder.pinned_tokens.sha256 if hasattr(builder, 'pinned_tokens') else None,
                   new_only_tokens=len(new_only),
                   rows=[dict(dst=d, dst_name=names[d], src=s, src_name=names[s], why=w) for d, s, w in rows],
                   skipped=[dict(token=t, name=names[t], why=w) for t, w in skipped])
    Path(str(dst) + '.fullpool.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def meta_tokens(R):
    cards = R.meta['cards'] if isinstance(R.meta, dict) else json.loads(R.meta)['cards']
    return {name: dict(token=int(c['token']), cost=float(c['cost'])) for name, c in sorted(cards.items())}


def extend_lopp(src, dst, meta):
    """meta: {engine name: {token, cost}} of the r1-cards1 R.meta (meta_tokens)."""
    z = dict(np.load(src, allow_pickle=False))
    if 'Wv_x' in z:
        raise ValueError(f'{src} is already extended')
    vocab = [int(t) for t in z['meta_vocab']]
    index = {t: i for i, t in enumerate(vocab)}
    c56_tokens = {meta[c]['token'] for c in C56}
    if set(vocab[1:]) != c56_tokens:
        raise ValueError(f'{src}: vocab tokens != the C56 meta tokens of this runtime (PYTHONHASHSEED must be 0): '
                         f'{sorted(set(vocab[1:]) ^ c56_tokens)}')
    new = sorted((meta[c]['token'], c) for c in NEW if c in meta)
    missing = [c for c in NEW if c not in meta]
    rows = []
    for tok, card in new:
        if tok in index:
            raise ValueError(f'{card}: token {tok} already in the vocab')
        rows.append((tok, card, proxy_card(card), index[meta[proxy_card(card)]['token']]))
    src_idx = np.array([r[3] for r in rows], np.int64)
    out = dict(z)
    out['emb'] = np.concatenate([z['emb'], z['emb'][src_idx]])
    out['tem'] = np.concatenate([z['tem'], z['tem'][src_idx]])
    out['Wv_x'] = np.ascontiguousarray(z['Wv'][:, src_idx])
    out['bv_x'] = z['bv'][src_idx].copy()
    out['meta_vocab'] = np.concatenate([z['meta_vocab'], np.array([r[0] for r in rows], z['meta_vocab'].dtype)])
    out['meta_cost'] = np.concatenate([z['meta_cost'], np.array([meta[r[1]]['cost'] for r in rows], z['meta_cost'].dtype)])
    tmp = Path(str(dst) + '.partial.npz')
    np.savez(tmp, **out)
    tmp.replace(dst)
    receipt = dict(kind='lopp', source=str(src), source_sha256=sha256(src), output=str(dst), output_sha256=sha256(dst),
                   base_vocab=len(vocab), vocab=len(out['meta_vocab']), missing_from_meta=missing,
                   rows=[dict(token=t, card=c, proxy=p, proxy_index=int(i)) for t, c, p, i in rows])
    Path(str(dst) + '.fullpool.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('policy'); p.add_argument('--in', dest='src', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path); p.add_argument('--init', default='row', choices=['row', 'input'])
    m = sub.add_parser('meta-tokens'); m.add_argument('--out', required=True, type=Path)
    k = sub.add_parser('lopp'); k.add_argument('--in', dest='src', required=True, type=Path)
    k.add_argument('--out', required=True, type=Path); k.add_argument('--meta', required=True, type=Path)
    a = ap.parse_args(argv)
    if a.cmd == 'lopp':
        r = extend_lopp(a.src, a.out, json.loads(a.meta.read_text()))
    else:
        from bot.players.runtime import Runtime
        rt = Runtime(verify=False)
        if a.cmd == 'policy':
            r = extend_policy(a.src, a.out, rt.R.builder, a.init)
        else:
            r = dict(meta=meta_tokens(rt.R), pins=rt.pins, root=str(rt.root),
                     card_scope=getattr(rt.R, 'card_scope', 'c56'))
            a.out.write_text(json.dumps(r['meta'], indent=1) + '\n')
            Path(str(a.out) + '.receipt.json').write_text(json.dumps({k: v for k, v in r.items() if k != 'meta'}, indent=1, default=str) + '\n')
    print(json.dumps({k: v for k, v in r.items() if k not in ('rows', 'skipped', 'meta')}, indent=1, default=str))
    if 'rows' in r:
        print(len(r['rows']), 'rows;', len(r.get('skipped', [])), 'skipped')


if __name__ == '__main__':
    main()
