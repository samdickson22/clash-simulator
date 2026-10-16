"""Select by the registered split before touching any episode directory."""
import hashlib
import json
from pathlib import Path

DATA = Path('/mpac/sdicks02/repos/clasher-bot-data')
# Same immutable registration as bot.live.real_replay / live.perception.common.
SPLIT_SHA = '3edbd25bdae8e9b9efd6f0b4341e2caf5214854a74de56d250e81290653b5258'


class SplitGuard:
    def __init__(self, split_path=DATA / 't1-split.json'):
        raw = Path(split_path).read_bytes()
        if hashlib.sha256(raw).hexdigest() != SPLIT_SHA:
            raise ValueError('not the registered T1 split; refusing')
        self.registration = json.loads(raw)
        self.entries = {m['episode']: m for m in self.registration['matches']
                        if m['split'] in ('train', 'validation')}

    def select(self, split):
        if split not in ('train', 'validation'):
            raise ValueError('only train or validation may be selected')
        # Never enumerate the dataset root (or heldout names).
        return sorted((e for e in self.entries.values() if e['split'] == split),
                      key=lambda e: e['episode'])

    def check(self, episode, split):
        if split not in ('train', 'validation'):
            raise ValueError('only train or validation may be loaded')
        entry = self.entries.get(episode)
        if entry is None or entry['split'] != split:
            raise ValueError('episode is outside the requested registered split')
        if Path(episode).name != episode or episode in ('.', '..'):
            raise ValueError('invalid episode name')
        return entry

    def load(self, rt, episode, split, root=DATA / 't1-trainval'):
        entry = self.check(episode, split)
        from bot.live.replay import T1Match
        return T1Match(rt, Path(root) / episode, entry, seat=0)
