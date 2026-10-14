"""Load a T1 Phase A native recording as a replay fixture.

A fixture is the SCRIPT (decks, the initial hand/cycle order, every accepted card
play at its native execution tick and tap tile) plus the TRUTH (per observed tick,
every native unit: towers, troops and buildings, i.e. objects that carry hp).

Only train/validation episodes may be loaded. The split comes from the registered
split.json; anything else (heldout, smoke, unknown) is refused before any of its
files are opened.
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from pathlib import Path

ALLOWED_SPLITS = frozenset({"train", "validation"})
TOWER_BODIES = {"KingTower": "king", "PrincessTower": "princess"}


@dataclass(frozen=True)
class Play:
    side: int
    card: str  # name as recorded (Clasher naming)
    card_id: int  # native card id
    kind: str
    tile: tuple[float, float]  # tap tile centre, tiles
    exec_tick: int  # native tick on which the play executed
    command_tick: int
    slot: int


@dataclass
class TruthUnit:
    key: int  # native object id
    side: int
    root: int  # native card id of the card whose play put it there (-1 tower)
    tower_slot: int | None
    first_tick: int
    # tick -> (x, y, hp) in native units (1000 per tile)
    rows: dict[int, tuple[int, int, int]] = field(default_factory=dict)


@dataclass
class Fixture:
    episode: str
    split: str
    decks: list[list[str]]
    deck_ids: list[list[int]]
    initial_order: list[list[int]]  # per side: 4 hand card ids (hand index order) + 4 cycle card ids
    start_tick: int
    end_tick: int
    plays: list[Play]
    ticks: list[int]  # observed truth ticks, ascending
    units: dict[int, TruthUnit]
    initial_elixir: list[float]

    def units_alive_at(self, tick: int):
        for u in self.units.values():
            r = u.rows.get(tick)
            if r is not None:
                yield u, r


def load_split(split_json: Path) -> dict[str, str]:
    data = json.loads(Path(split_json).read_text())
    return {m["episode"]: m["split"] for m in data["matches"]}


def load_fixture(match_dir: Path, splits: dict[str, str]) -> Fixture:
    match_dir = Path(match_dir)
    episode = match_dir.name
    split = splits.get(episode)
    if split not in ALLOWED_SPLITS:
        raise PermissionError(f"{episode}: split {split!r} is not train/validation; refusing to open it")
    setup = json.loads((match_dir / "setup.json").read_text())
    entry = setup["entry"]
    if entry["split"] != split:
        raise ValueError(f"{episode}: setup split {entry['split']} != registered {split}")

    # Initial hand and cycle (privileged, used only to make the replayed hands match).
    with gzip.open(match_dir / "evaluation-only.jsonl.gz", "rt") as fh:
        first = json.loads(fh.readline())["observation"]
    initial_order, deck_ids, elixir = [], [], []
    for side in (0, 1):
        p = next(pl for pl in first["players"] if pl["owner"] == side)
        hand = [h["cardId"] for h in sorted(p["hand"], key=lambda h: h["handIndex"])]
        cyc = [c["cardId"] for c in sorted(p["cycle"], key=lambda c: c["cycleIndex"])]
        initial_order.append(hand + cyc)
        deck_ids.append([d["cardId"] for d in sorted(p["deck"], key=lambda d: d["deckSlot"])])
        elixir.append(float(p["elixir"]))

    plays = []
    for line in (match_dir / "events.jsonl").read_text().splitlines():
        e = json.loads(line)
        if not e.get("accepted") or e.get("exec_tick") is None:
            continue
        plays.append(Play(
            side=int(e["side"]), card=e["card"], card_id=int(e["card_id"]), kind=e["kind"],
            tile=(float(e["tile"][0]), float(e["tile"][1])), exec_tick=int(e["exec_tick"]),
            command_tick=int(e["command_tick"]), slot=int(e.get("slot", -1)),
        ))
    plays.sort(key=lambda p: (p.exec_tick, p.side, p.slot))

    units: dict[int, TruthUnit] = {}
    per_tick: dict[int, list] = {}
    with gzip.open(match_dir / "objects.jsonl.gz", "rt") as fh:
        for line in fh:
            r = json.loads(line)
            per_tick[int(r["tick"])] = r["objects"]  # last observation of a tick wins
    for tick in sorted(per_tick):
        for o in per_tick[tick]:
            hp = o.get("hp")
            if hp is None or hp <= 0:
                continue  # projectiles, spell areas, death bombs carry no hp
            key = int(o["native_id"])
            u = units.get(key)
            if u is None:
                body = o.get("body_name")
                tower_slot = None
                if o["card_id"] == -1 and body in TOWER_BODIES:
                    tower_slot = 0 if body == "KingTower" else (1 if int(o["x"]) < 9000 else 2)
                u = units[key] = TruthUnit(key=key, side=int(o["owner"]), root=int(o["card_id"]),
                                           tower_slot=tower_slot, first_tick=tick)
            u.rows[tick] = (int(o["x"]), int(o["y"]), int(hp))
    # Drop cardless non-tower hp objects (none expected); keep towers and rooted units.
    units = {k: u for k, u in units.items() if u.root != -1 or u.tower_slot is not None}
    return Fixture(
        episode=episode, split=split, decks=entry["decks"], deck_ids=deck_ids,
        initial_order=initial_order, start_tick=int(entry["start_tick"]),
        end_tick=max(per_tick), plays=plays, ticks=sorted(per_tick), units=units,
        initial_elixir=elixir,
    )
