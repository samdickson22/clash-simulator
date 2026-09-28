"""Native command-origin deployment anchors for Bandit and Mega Knight."""
import json
from pathlib import Path

import pytest

from clasher.arena import Position
from clasher.battle import BattleState

REFERENCE = json.loads(
    (Path(__file__).parent / 'fixtures/native_dash_deploy_15_535_86.json').read_text()
)


@pytest.mark.parametrize('fast_path', [False, True])
@pytest.mark.parametrize('case', REFERENCE['cases'])
def test_native_dash_card_deployment_anchor(fast_path, case):
    battle = BattleState(fast_path=fast_path)
    for _ in range(200):
        battle.step()
    player = battle.players[case['owner']]
    player.elixir = 10
    player.hand = [case['name']]
    before = set(battle.entities)
    assert battle.deploy_card(
        case['owner'], case['name'], Position(*(v / 1000 for v in case['command']))
    )
    troop = battle.entities[(set(battle.entities) - before).pop()]
    battle.step()
    assert [round(troop.position.x * 1000), round(troop.position.y * 1000)] == case['position']
