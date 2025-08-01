import pytest
from src.clasher.engine import BattleEngine
from src.clasher.arena import Position
from src.clasher.data import CardDataLoader


def test_engine_creation():
    """Test basic engine creation"""
    engine = BattleEngine("gamedata.json")
    assert engine is not None


def test_battle_creation():
    """Test battle state creation"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    assert battle is not None
    assert len(battle.players) == 2
    assert battle.time == 0.0
    assert battle.tick == 0
    assert not battle.game_over


def test_card_loading():
    """Test card data loading"""
    loader = CardDataLoader("gamedata.json")
    cards = loader.load_cards()
    
    assert len(cards) > 0
    assert "Knight" in cards
    
    knight = loader.get_card("Knight")
    assert knight is not None
    assert knight.name == "Knight"
    assert knight.mana_cost > 0


def test_battle_step():
    """Test battle stepping"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    initial_time = battle.time
    initial_tick = battle.tick
    
    battle.step()
    
    assert battle.time > initial_time
    assert battle.tick > initial_tick


def test_card_deployment():
    """Test card deployment"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Try to deploy Knight for player 0
    position = Position(10.0, 5.0)  # Blue side
    result = battle.deploy_card(0, "Knight", position)
    
    # Should succeed if Knight exists and player has elixir
    if result:
        assert len(battle.entities) > 6  # 6 towers + 1 knight


def test_arena_bounds():
    """Test arena boundary checking"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Valid position for player 0 (blue)
    valid_pos = Position(16.0, 5.0)
    assert battle.arena.can_deploy_at(valid_pos, 0)
    
    # Invalid position for player 0 (red side)
    invalid_pos = Position(16.0, 15.0)
    assert not battle.arena.can_deploy_at(invalid_pos, 0)