"""
Test suite for card mechanics implementations.

Tests the special mechanics of cards like Bandit, Electro Wizard, Bomb Tower, and Princess.
"""

import pytest
import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from clasher.cards.bandit import BanditDash
from clasher.cards.electro_wizard import ElectroWizardSpawnZap, ElectroWizardStunAttack
from clasher.cards.bomb_tower import BombTowerDeathBomb, BombTowerBomb
from clasher.cards.princess import PrincessLongRange, PrincessAreaArrows, PrincessMultiShot


class MockPosition:
    """Mock position class for testing"""
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def distance_to(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5

    def copy(self):
        return MockPosition(self.x, self.y)


class MockEntity:
    """Mock entity class for testing"""
    def __init__(self, player_id=0, damage=100, range=1000):
        self.player_id = player_id
        self.damage = damage
        self.range = range
        self.position = MockPosition()
        self.is_alive = True
        self.attack_cooldown = 0.0
        self.target_id = None
        self._bandit_dashing = False
        self._bandit_invulnerable_until = 0
        self._bandit_dash_timer = 0.0
        self._bandit_dash_origin = None
        self._bandit_dash_target = None
        self._princess_first_attack = True
        self._princess_arrow_count = 5

    def take_damage(self, damage):
        self.damage_taken = damage

    def apply_stun(self, duration):
        self.stun_duration = duration


class MockBattleState:
    """Mock battle state for testing"""
    def __init__(self):
        self.entities = {}
        self.time = 0.0

    def add_entity(self, entity):
        entity_id = len(self.entities)
        self.entities[entity_id] = entity
        return entity_id


class TestBanditDash:
    """Test Bandit dash mechanics"""

    def test_bandit_dash_init(self):
        """Test BanditDash initialization"""
        dash = BanditDash()
        assert dash.dash_distance == 500.0
        assert dash.dash_min_range == 3.5
        assert dash.dash_max_range == 6.0
        assert dash.dash_duration_ms == 800
        assert dash.invincibility_duration_ms == 800
        assert not dash.is_dashing

    def test_bandit_dash_on_attach(self):
        """Test BanditDash on_attach"""
        entity = MockEntity()
        dash = BanditDash()
        dash.on_attach(entity)

        assert not entity._bandit_dashing
        assert entity._bandit_invulnerable_until == 0
        assert entity._bandit_dash_timer == 0.0
        assert entity._bandit_dash_origin is None
        assert entity._bandit_dash_target is None

    def test_bandit_dash_range_check(self):
        """Test Bandit dash range conditions"""
        entity = MockEntity()
        target = MockEntity()
        dash = BanditDash()

        # Set up entity with battle state
        entity.battle_state = MockBattleState()
        entity.battle_state.time = 2.0  # 2 seconds have passed (enough for dash cooldown)
        entity.position = MockPosition(0, 0)
        target.position = MockPosition(4000, 0)  # 4 tiles away

        # Should dash at 4 tiles (within 3.5-6 range)
        entity.target_id = 1
        entity.battle_state.entities[1] = target

        # Mock can_attack_target
        def can_attack_target(t):
            return True
        entity.can_attack_target = can_attack_target

        dash.on_tick(entity, 100)

        # Should initiate dash
        assert entity._bandit_dashing


class TestElectroWizard:
    """Test Electro Wizard mechanics"""

    def test_spawn_zap_init(self):
        """Test ElectroWizardSpawnZap initialization"""
        zap = ElectroWizardSpawnZap()
        assert zap.radius_tiles == 4.0
        assert zap.stun_duration_ms == 500
        assert zap.damage_scale == 0.5

    def test_spawn_zap_on_spawn(self):
        """Test Electro Wizard spawn zap"""
        entity = MockEntity(damage=200)
        enemy = MockEntity(player_id=1)

        battle_state = MockBattleState()
        battle_state.entities[0] = entity
        battle_state.entities[1] = enemy

        entity.battle_state = battle_state
        entity.position = MockPosition(0, 0)
        enemy.position = MockPosition(2000, 0)  # 2 tiles away

        zap = ElectroWizardSpawnZap()
        zap.on_spawn(entity)

        # Enemy should take damage and be stunned
        assert hasattr(enemy, 'damage_taken')
        assert enemy.damage_taken == 100  # 50% of 200
        assert hasattr(enemy, 'stun_duration')
        assert enemy.stun_duration == 0.5

    def test_stun_attack_init(self):
        """Test ElectroWizardStunAttack initialization"""
        stun = ElectroWizardStunAttack()
        assert stun.stun_duration_ms == 500
        assert stun.chain_targets == 2

    def test_stun_attack_on_hit(self):
        """Test Electro Wizard stun on attack hit"""
        entity = MockEntity()
        target = MockEntity(player_id=1)

        entity.battle_state = MockBattleState()
        entity.battle_state.entities[0] = entity
        entity.battle_state.entities[1] = target

        stun = ElectroWizardStunAttack()
        stun.on_attack_hit(entity, target)

        # Target should be stunned
        assert hasattr(target, 'stun_duration')
        assert target.stun_duration == 0.5


class TestBombTower:
    """Test Bomb Tower mechanics"""

    def test_death_bomb_init(self):
        """Test BombTowerDeathBomb initialization"""
        bomb = BombTowerDeathBomb()
        assert bomb.explosion_radius_tiles == 3.0
        assert bomb.explosion_delay_ms == 3000
        assert bomb.damage_scale == 1.0

    def test_death_bomb_on_death(self):
        """Test Bomb Tower death bomb"""
        tower = MockEntity(damage=150)
        tower.battle_state = MockBattleState()

        bomb = BombTowerDeathBomb()
        bomb.on_death(tower)

        # Should create a death bomb entity
        assert len(tower.battle_state.entities) > 0

        # The created entity should be a bomb with explosion capability
        bomb_entities = [e for e in tower.battle_state.entities.values() if hasattr(e, 'explosion_damage')]
        assert len(bomb_entities) == 1
        assert bomb_entities[0].explosion_damage == 150  # Full damage for death bomb

    def test_bomb_projectile_init(self):
        """Test BombTowerBomb initialization"""
        bomb = BombTowerBomb()
        assert bomb.bomb_lifetime_ms == 2000
        assert bomb.explosion_radius_tiles == 2.0


class TestPrincess:
    """Test Princess mechanics"""

    def test_long_range_init(self):
        """Test PrincessLongRange initialization"""
        range_mechanic = PrincessLongRange()
        assert range_mechanic.range_bonus_tiles == 9.0
        assert range_mechanic.first_attack_speed_bonus == 0.5

    def test_long_range_on_attach(self):
        """Test Princess range bonus on attach"""
        entity = MockEntity(range=2000)  # 2 tiles
        range_mechanic = PrincessLongRange()
        range_mechanic.on_attach(entity)

        # Range should be increased to 9 tiles
        assert entity.range == 9000  # 9 tiles in game units
        assert entity._princess_first_attack

    def test_area_arrows_init(self):
        """Test PrincessAreaArrows initialization"""
        arrows = PrincessAreaArrows()
        assert arrows.arrow_count == 5
        assert arrows.arrow_spread_radius_tiles == 1.5
        assert arrows.area_damage_radius_tiles == 1.0

    def test_multi_shot_init(self):
        """Test PrincessMultiShot initialization"""
        multi_shot = PrincessMultiShot()
        assert multi_shot.initial_arrow_count == 1
        assert multi_shot.subsequent_arrow_count == 5
        assert multi_shot.is_first_attack

    def test_first_attack_single_arrow(self):
        """Test Princess first attack shoots single arrow"""
        entity = MockEntity()
        target = MockEntity(player_id=1)

        multi_shot = PrincessMultiShot()
        multi_shot.on_attack_start(entity, target)

        # Should set up for single arrow
        assert entity._princess_arrow_count == 1
        assert not multi_shot.is_first_attack

    def test_subsequent_attack_multi_arrow(self):
        """Test Princess subsequent attacks shoot multiple arrows"""
        entity = MockEntity()
        target = MockEntity(player_id=1)

        multi_shot = PrincessMultiShot()
        multi_shot.is_first_attack = False  # Simulate after first attack
        multi_shot.on_attack_start(entity, target)

        # Should set up for multiple arrows
        assert entity._princess_arrow_count == 5

    def test_princess_projectile_creation(self):
        """Test Princess creates correct number of projectiles with scaled damage"""
        entity = MockEntity(damage=500)  # 500 damage
        target = MockEntity(player_id=1)

        # Set up battle state with next_entity_id
        entity.battle_state = MockBattleState()
        entity.battle_state.next_entity_id = 100
        entity.battle_state.entities[0] = entity
        entity.battle_state.entities[1] = target

        multi_shot = PrincessMultiShot()
        multi_shot.is_first_attack = False  # 5 arrow attack
        multi_shot.on_attack_start(entity, target)

        # Mock the add_entity method to capture created projectiles
        created_projectiles = []
        def add_entity(proj):
            created_projectiles.append(proj)
        entity.battle_state.add_entity = add_entity

        # Simulate attack hit
        multi_shot.on_attack_hit(entity, target)

        # Should create 5 projectiles
        assert len(created_projectiles) == 5

        # Each projectile should have 1/5 of the total damage (100 damage each)
        for projectile in created_projectiles:
            assert projectile.damage == 100  # 500 / 5 = 100
            assert projectile.source_name == "Princess"
            assert projectile.travel_speed == 1200
            assert projectile.splash_radius == 300

    def test_princess_first_attack_single_projectile(self):
        """Test Princess first attack creates single projectile with full damage"""
        entity = MockEntity(damage=500)  # 500 damage
        target = MockEntity(player_id=1)

        # Set up battle state with next_entity_id
        entity.battle_state = MockBattleState()
        entity.battle_state.next_entity_id = 100
        entity.battle_state.entities[0] = entity
        entity.battle_state.entities[1] = target

        multi_shot = PrincessMultiShot()
        multi_shot.on_attack_start(entity, target)  # Should be first attack (1 arrow)

        # Mock the add_entity method to capture created projectiles
        created_projectiles = []
        def add_entity(proj):
            created_projectiles.append(proj)
        entity.battle_state.add_entity = add_entity

        # Simulate attack hit
        multi_shot.on_attack_hit(entity, target)

        # Should create 1 projectile
        assert len(created_projectiles) == 1

        # Single projectile should have full damage
        projectile = created_projectiles[0]
        assert projectile.damage == 500  # Full damage for single arrow
        assert projectile.source_name == "Princess"


if __name__ == "__main__":
    # Run tests manually if pytest is not available
    import unittest

    # Create test suite
    suite = unittest.TestSuite()

    # Add Bandit tests
    suite.addTest(unittest.FunctionTestCase(TestBanditDash().test_bandit_dash_init))
    suite.addTest(unittest.FunctionTestCase(TestBanditDash().test_bandit_dash_on_attach))

    # Add Electro Wizard tests
    suite.addTest(unittest.FunctionTestCase(TestElectroWizard().test_spawn_zap_init))
    suite.addTest(unittest.FunctionTestCase(TestElectroWizard().test_spawn_zap_on_spawn))
    suite.addTest(unittest.FunctionTestCase(TestElectroWizard().test_stun_attack_init))
    suite.addTest(unittest.FunctionTestCase(TestElectroWizard().test_stun_attack_on_hit))

    # Add Bomb Tower tests
    suite.addTest(unittest.FunctionTestCase(TestBombTower().test_death_bomb_init))
    suite.addTest(unittest.FunctionTestCase(TestBombTower().test_death_bomb_on_death))
    suite.addTest(unittest.FunctionTestCase(TestBombTower().test_bomb_projectile_init))

    # Add Princess tests
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_long_range_init))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_long_range_on_attach))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_area_arrows_init))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_multi_shot_init))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_first_attack_single_arrow))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_subsequent_attack_multi_arrow))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_princess_projectile_creation))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_princess_first_attack_single_projectile))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    if result.wasSuccessful():
        print("\n✅ All tests passed!")
    else:
        print(f"\n❌ {len(result.failures)} test(s) failed!")
        for failure in result.failures:
            print(f"FAILURE: {failure[0]}")
            print(failure[1])