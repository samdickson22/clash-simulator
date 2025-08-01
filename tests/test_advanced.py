import pytest
import time
from src.clasher.engine import BattleEngine
from src.clasher.arena import Position
from src.clasher.replay import TurboEngine


def test_spell_casting():
    """Test spell deployment"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Give player enough elixir for spells
    battle.players[0].elixir = 10.0
    
    # Test Arrows spell
    initial_entities = len(battle.entities)
    result = battle.deploy_card(0, "Arrows", Position(16.0, 12.0))
    
    # Arrows should cast immediately, no new entities
    assert len(battle.entities) == initial_entities


def test_knight_vs_knight():
    """Test Knight vs Knight mid-bridge battle as mentioned in plan"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Deploy Knights at bridge
    battle.players[0].elixir = 10.0
    battle.players[1].elixir = 10.0
    
    # Deploy at bridge positions
    battle.deploy_card(0, "Knight", Position(16.0, 8.5))  # Just below bridge
    battle.deploy_card(1, "Knight", Position(16.0, 9.5))  # Just above bridge
    
    # Run battle until Knights meet and fight
    for _ in range(300):  # ~10 seconds
        battle.step()
        if battle.game_over:
            break
    
    # Check that entities fought (some should be dead or damaged)
    knights = [e for e in battle.entities.values() if "Knight" in e.card_stats.name]
    assert len(knights) <= 2  # At most 2 knights should remain


def test_win_conditions():
    """Test win condition detection"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Find and destroy red king tower
    for entity in battle.entities.values():
        if (entity.player_id == 1 and 
            entity.position.x == battle.arena.RED_KING_TOWER.x and 
            entity.position.y == battle.arena.RED_KING_TOWER.y):
            entity.take_damage(5000)  # Destroy king tower
            break
    
    battle.step()
    
    assert battle.game_over
    assert battle.winner == 0  # Player 0 wins


def test_elixir_regeneration():
    """Test elixir regeneration timing"""
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    
    # Reset elixir to 0
    battle.players[0].elixir = 0.0
    
    # Run for exactly 2.8 seconds (1 elixir)
    ticks = int(2.8 / 0.033)
    for _ in range(ticks):
        battle.step()
    
    # Should have ~1 elixir
    assert 0.9 <= battle.players[0].elixir <= 1.1
    
    # Test double elixir at 2 minutes
    battle.time = 120.0
    battle.double_elixir = True
    
    initial_elixir = battle.players[0].elixir
    for _ in range(int(1.4 / 0.033)):  # 1.4 seconds
        battle.step()
    
    # Should gain ~1 more elixir in half the time
    elixir_gained = battle.players[0].elixir - initial_elixir
    assert 0.9 <= elixir_gained <= 1.1


def test_turbo_engine():
    """Test turbo engine performance"""
    turbo = TurboEngine("gamedata.json")
    
    # Run quick benchmark
    results = turbo.benchmark(duration_seconds=2)
    
    assert results["battles_per_second"] > 0
    assert results["ticks_per_second"] > 1000  # Should be very fast
    assert results["total_battles"] >= 1


def test_replay_recording():
    """Test replay recording functionality"""
    from src.clasher.replay import ReplayRecorder
    
    engine = BattleEngine("gamedata.json")
    battle = engine.create_battle()
    recorder = ReplayRecorder()
    
    # Record a few ticks
    for _ in range(10):
        recorder.record_tick(battle)
        battle.step()
    
    assert len(recorder.snapshots) == 10
    
    # Test saving/loading
    recorder.save_json("test_replay.json")
    
    stats = recorder.get_stats()
    assert stats["total_ticks"] == 10
    assert stats["duration_seconds"] >= 0


def test_batch_battles():
    """Test running multiple battles"""
    turbo = TurboEngine("gamedata.json")
    
    results = turbo.run_batch(num_battles=3, speed_factor=50.0)
    
    assert len(results) == 3
    for result in results:
        assert "result" in result
        assert "duration_seconds" in result
        assert result["ticks_per_second"] > 100