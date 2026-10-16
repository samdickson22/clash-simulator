"""Token names + entity stats names for given cards (light)."""
import sys, random
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from bot.players.runtime import Runtime
rt = Runtime.__new__(Runtime)
rt.root = Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1'); rt.native_dir = Path('/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1')
rt._bootstrap_paths()
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from differential import initial, Position
b = ContractV5ObservationBuilder()
for t in map(int, sys.argv[1].split(',')):
    print(t, b.token_names[t])
for card in sys.argv[2].split(','):
    d = initial(seed=1, cards=(card, 'Knight', 'Archers', 'Fireball')); d.players[0].elixir = 10
    old = set(d.entities); d.deploy_card(0, card, Position(4.5, 10.5))
    for i in sorted(set(d.entities) - old):
        e = d.entities[i]; tok, row = b._entity_row(e, 0)
        print(card, type(e).__name__, e.card_stats.name, tok, b.token_names[tok])
