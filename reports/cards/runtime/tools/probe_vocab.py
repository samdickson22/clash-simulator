"""Pool names vs C56 aliases vs builder.card_vocab (light)."""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))
from bot.players.runtime import Runtime
rt = Runtime.__new__(Runtime)
rt.root = Path('/mpac/sdicks02/repos/clasher-bot-runtime/r1'); rt.native_dir = Path('/mpac/sdicks02/repos/clasher-bot-runtime/native-total-r1')
rt._bootstrap_paths()
sys.path.insert(0, str(REPO / 'reports/cards/tools'))
from pool import ladder_pool
import c56_controller
from clasher.rl.contract_v5 import ContractV5ObservationBuilder
from clasher.card_aliases import resolve_card_name
b = ContractV5ObservationBuilder()
C56 = c56_controller.CARDS
canon56 = {resolve_card_name(n): n for n in C56}
pool = [c['name'] for c in ladder_pool(rt.root / 'gamedata.json')]
alias = {n: canon56[resolve_card_name(n)] for n in pool if n not in C56 and resolve_card_name(n) in canon56}
print('pool aliases of C56', alias)
extra = sorted(n for n in pool if resolve_card_name(n) not in canon56)
print('extra', len(extra))
vocab = list(b.card_vocab)
vr = {resolve_card_name(n): n for n in vocab}
print('card_vocab', len(vocab), 'token count', len(b.token_names))
print('extra not in card_vocab', [n for n in extra if resolve_card_name(n) not in vr])
print('extra vocab name differs', {n: vr[resolve_card_name(n)] for n in extra if resolve_card_name(n) in vr and vr[resolve_card_name(n)] != n})
print('extra no loader stats', [n for n in extra if b.loader.get_card(n) is None])
print('extra card_action tokens', {n: b.token_id(n, namespace='card_action') for n in extra})
print('c56 resolve', {n: resolve_card_name(n) for n in C56 if resolve_card_name(n) != n})
