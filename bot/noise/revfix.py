"""Evidence-ranked revealed set, evaluated in the harness (bot lead noise worker, exploration).

bot/live is NOT edited. bot/noise/livefix/{translate,resync,revealed}.py are copies of the proposed bot/live files
(only the bot.live.* -> bot.noise.livefix.* imports differ; `python -m bot.noise.revfix --diff` prints the exact
proposed bot/live patch). This wrapper swaps that translator into the deployed PercPlayer, same noise stream:

    'PERCR<tag>-<arm>:<player>'     e.g. 'PERCRe2b3-emp-sr1u50:LIVED-K4L-R-gs-rw-fc'

  <tag>   'off'       patched code, eviction disabled (must equal the unpatched PERC-<arm> bit for bit)
          'oracle'    DIAGNOSTIC (reads truth): the revealed set IS the opponent's true revealed set (cards it has
                      really played so far); play acceptance and the board sanitizer both use it, all else noisy
          e<n>b<n>[k<k>n<n>][p<k>][w<m>][c<n>]   eviction on (defaults = the proposal, 'e2b10' = e2 b10 k3n4
                      p1 w0 c1): newcomer needs n plays (accepted+rejected) or n persistent board records (c<n> plays
                      against a contradicted victim); persistence k of n records; a non-contradicted victim needs
                      <= p plays and <= w board records.
"""
from __future__ import annotations

import re

DEFAULT = dict(events_need=2, board_need=10, persist=(3, 4), weak_plays=1, weak_board=0, contra_need=1, contra_plays=2)


def parse(tag):
    if tag in ('off', 'oracle'):
        return tag
    m = re.fullmatch(r'e(\d+)b(\d+)(?:k(\d+)n(\d+))?(?:p(\d+))?(?:w(\d+))?(?:c(\d+))?', tag)
    if m is None:
        raise ValueError(f'bad PERCR tag {tag!r}')
    cfg = dict(DEFAULT, events_need=int(m[1]), board_need=int(m[2]))
    if m[3]:
        cfg['persist'] = (int(m[3]), int(m[4]))
    if m[5]:
        cfg['weak_plays'] = int(m[5])
    if m[6]:
        cfg['weak_board'] = int(m[6])
    if m[7]:
        cfg['contra_need'] = int(m[7])
    return cfg


def oracle_set():
    from bot.noise.livefix.revealed import RevealedSet

    class OracleRevealed(RevealedSet):
        """Diagnostic only: membership = the opponent's TRUE revealed cards (set each poll by the harness)."""
        truth = frozenset()

        def members(self):
            return set(self.truth)

        def allows(self, card):
            return card in self.truth

        def observe_board(self, tick, cards, frame=None, synthetic=False):
            return []

        def victim(self, newcomer, tick):
            return None
    return OracleRevealed


def make_percr(rt, name, fallback):
    from bot.live.perc import PercPlayer
    from bot.noise.livefix.resync import ResyncTranslator
    m = re.fullmatch(r'PERCR([a-z0-9]+)-([^:]+):(.+)', name)
    if m is None:
        raise ValueError(name)
    cfg, arm, inner = parse(m[1]), m[2], m[3]

    class Fixed(PercPlayer):
        def start(self, ctx):
            super().start(ctx)
            if self.noise is not None or self.plays_from != 'events':
                raise ValueError('PERCR: empirical events arms only')
            tr = ResyncTranslator(self.rt, list(ctx.own_order), plays_from=self.plays_from)
            tr.set_own_order(ctx.own_order)
            if cfg == 'off':
                tr.revealed.evict = False
            elif cfg == 'oracle':
                tr.revealed = oracle_set()(tr.public_events, tr.plays[1], stats=tr.stats)
            else:
                for k, v in cfg.items():
                    setattr(tr.revealed, k if k != 'persist' else 'persist_k', v if k != 'persist' else v[0])
                if 'persist' in cfg:
                    from collections import deque
                    tr.revealed.window = deque(maxlen=cfg['persist'][1])
            self.tr = tr

        def act(self, view):
            if cfg == 'oracle':
                opp = 1 - view.seat
                self.tr.revealed.truth = frozenset(e['name'] for e in view.public_events
                                                   if e.get('kind', 'card') == 'card' and e['seat'] == opp)
            return super().act(view)
    p = Fixed(rt, arm, fallback(rt, inner))
    p.name = name
    return p


def proposed_diff():
    """The exact bot/live patch these copies implement (imports mapped back to bot.live)."""
    import difflib
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    out = []
    for f in ('translate.py', 'resync.py', 'revealed.py', 'test_revealed.py'):
        src = root / ('bot/noise' if f.startswith('test_') else 'bot/noise/livefix') / f
        new = src.read_text().replace('bot/noise/livefix = the proposed bot/live patch; ', '').replace(
            'bot/noise/test_revealed.py', 'bot/live/test_revealed.py')
        new = new.replace('\nProposed as bot/live/test_revealed.py with `bot.noise.livefix.` -> `bot.live.`.\n', '')
        new = new.replace('bot.noise.livefix.', 'bot.live.').replace(
            "parents[2] / 'players/royalesim_vocab.json'", "parents[1] / 'players/royalesim_vocab.json'")
        old_p = root / 'bot/live' / f
        old = old_p.read_text() if old_p.exists() else ''
        out += difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                    f'a/bot/live/{f}' if old else '/dev/null', f'b/bot/live/{f}')
    return ''.join(out)


if __name__ == '__main__':
    import sys
    if sys.argv[1:] == ['--diff']:
        sys.stdout.write(proposed_diff())
