"""
Test suite for card mechanics implementations.

Tests the special mechanics of cards like Bandit, Electro Wizard, and Princess.
"""

import pytest

from clasher.cards.bandit import BanditDash
from clasher.cards.archer_queen import ArcherQueenCloak
from clasher.cards import CARD_MECHANICS
from clasher.cards.electro_wizard import ElectroWizardSpawnZap
from clasher.cards.electro_dragon import ElectroDragonChainLightning
from clasher.cards.electro_spirit import ElectroSpiritChain
from clasher.cards.firecracker import AttackRecoil
from clasher.cards.princess import PrincessLongRange
from clasher.cards.royal_ghost import InvisibilityWhenNotAttacking
from clasher.cards.tesla import HideWhenIdle
from clasher.cards.mega_knight import MegaKnightSlam
from clasher.cards.miner import UndergroundDeployment
from clasher.cards.battle_ram import BattleRamCharge
from clasher.cards.ice_spirit import IceSpiritFreeze
from clasher.cards.wallbreakers import WallBreakersDemolition
from clasher.factory.mechanic_detector import detect_mechanics_from_data
from clasher.mechanics.shared import MultipleTargetAttack, SerializedOnHitBuff
from clasher.rl.deck_pool import load_deck_pool
from clasher.card_aliases import resolve_card_name


class MockPosition:
    """Mock position class for testing"""
    def __init__(self, x=0, y=0):
        self.x = x
        self.y = y

    def distance_to(self, other):
        return ((self.x - other.x)**2 + (self.y - other.y)**2)**0.5

    def copy(self):
        return MockPosition(self.x, self.y)


def test_enabled_mechanics_do_not_depend_on_card_name_registry():
    enabled_names = {
        name
        for deck in load_deck_pool()
        for card_name in deck
        for name in (card_name, resolve_card_name(card_name))
    }

    assert enabled_names.isdisjoint(CARD_MECHANICS)


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

    def apply_stun(self, duration, **_kwargs):
        self.stun_duration = duration

    def apply_slow(
        self,
        duration,
        movement_multiplier,
        *,
        attack_speed_multiplier=None,
        spawn_speed_multiplier=None,
        **_kwargs,
    ):
        self.slow_effect = (
            duration,
            movement_multiplier,
            attack_speed_multiplier,
            spawn_speed_multiplier,
        )

    def get_collision_radius(self):
        return 0.5

    def native_target_distance_to(self, target):
        return self.position.distance_to(target.position)

    def native_dash_range_edge_distance(
        self,
        target,
        minimum_range,
        maximum_range,
    ):
        distance = self.native_target_distance_to(target)
        target_edge_distance = distance - target.get_collision_radius()
        edge_gap = target_edge_distance - self.get_collision_radius()
        if edge_gap >= minimum_range and target_edge_distance <= maximum_range:
            return target_edge_distance
        return None

    def intersects_native_area(self, area_center, area_radius):
        return self.position.distance_to(area_center) < (
            self.get_collision_radius() + area_radius
        )

    def can_receive_area_damage(self, *_args, **_kwargs):
        return True


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
        dash.on_attach(entity)

        # Set up entity with battle state
        entity.battle_state = MockBattleState()
        entity.battle_state.time = 2.0  # 2 seconds have passed (enough for dash cooldown)
        entity.position = MockPosition(0, 0)
        target.position = MockPosition(4.6, 0)  # 3.6 tiles edge-to-edge

        # The inner dash boundary measures the gap between both bodies.
        entity.target_id = 1
        entity.battle_state.entities[1] = target

        # Mock can_attack_target
        def can_attack_target(t):
            return True
        entity.can_attack_target = can_attack_target

        dash.on_tick(entity, 100)

        # The target enters the interruptible charge phase first; movement is
        # governed separately by jumpSpeed after the 0.8 s wind-up.
        assert entity._bandit_charging
        assert not entity._bandit_dashing


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
        enemy.position = MockPosition(2.0, 0)  # 2 tiles away

        zap = ElectroWizardSpawnZap()
        zap.on_spawn(entity)

        # Enemy should take damage and be stunned
        assert hasattr(enemy, 'damage_taken')
        assert enemy.damage_taken == 100  # 50% of 200
        assert hasattr(enemy, 'stun_duration')
        assert enemy.stun_duration == 0.5

    def test_stun_attack_init(self):
        """Test the shared multi-target attack defaults."""
        stun = MultipleTargetAttack()
        assert stun.target_count == 2

    def test_stun_attack_on_hit(self):
        """Test Electro Wizard stun on attack hit"""
        entity = MockEntity()
        target = MockEntity(player_id=1)

        entity.battle_state = MockBattleState()
        entity.battle_state.entities[0] = entity
        entity.battle_state.entities[1] = target

        stun = SerializedOnHitBuff(
            duration_ms=500,
            movement_multiplier=0.0,
            attack_multiplier=0.0,
            spawn_multiplier=0.0,
        )
        stun.on_attack_hit(entity, target)

        # Target should be stunned
        assert hasattr(target, 'stun_duration')
        assert target.stun_duration == 0.5

    def test_serialized_multi_target_attack_is_detected_without_card_name(self):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericSplitter",
                "summonCharacterData": {
                    "multipleTargets": 3,
                    "allTargetsHit": True,
                },
            }
        )

        assert sum(isinstance(item, MultipleTargetAttack) for item in mechanics) == 1

    def test_multi_target_on_hit_buff_preserves_independent_slow_axes(self):
        entity = MockEntity()
        target = MockEntity(player_id=1)
        mechanic = SerializedOnHitBuff(
            duration_ms=2500,
            movement_multiplier=0.7,
            attack_multiplier=0.8,
            spawn_multiplier=0.9,
        )

        mechanic.on_attack_hit(entity, target)

        assert target.slow_effect == (2.5, 0.7, 0.8, 0.9)

    def test_secondary_hit_uses_committed_damage_and_outgoing_modifiers(self):
        class DoubleDamage:
            @staticmethod
            def modify_outgoing_damage(_entity, _target, damage):
                return damage * 2

        entity = MockEntity(damage=100)
        secondary = MockEntity(player_id=1)
        secondary.id = 2
        battle = MockBattleState()
        battle.entities[secondary.id] = secondary
        mechanic = MultipleTargetAttack(
            _secondary_target_ids=(secondary.id,),
        )
        entity.mechanics = [mechanic, DoubleDamage()]

        mechanic.resolve_secondary_attack_hits(
            entity,
            MockEntity(player_id=1),
            250,
            battle,
        )

        assert secondary.damage_taken == 500

    def test_hide_when_idle_is_detected_without_building_name(self):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericRetractableBuilding",
                "summonCharacterData": {
                    "hidesWhenNotAttacking": True,
                    "hideTimeMS": 800,
                    "upTimeMS": 800,
                },
            }
        )

        assert sum(isinstance(item, HideWhenIdle) for item in mechanics) == 1

    def test_attack_recoil_is_detected_without_character_name(self):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericRecoilAttacker",
                "summonCharacterData": {
                    "attackPushback": 1250,
                },
            }
        )

        assert sum(isinstance(item, AttackRecoil) for item in mechanics) == 1

    def test_inactivity_invisibility_is_detected_without_character_name(self):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericFadingAttacker",
                "summonCharacterData": {
                    "buffWhenNotAttackingData": {
                        "name": "Invisibility",
                    },
                    "buffWhenNotAttackingTime": 1500,
                    "buffWhenNotAttackingUseAttackRange": True,
                },
            }
        )

        assert (
            sum(
                isinstance(item, InvisibilityWhenNotAttacking)
                for item in mechanics
            )
            == 1
        )

    @pytest.mark.parametrize(
        ("extra_fields", "expected_type"),
        (
            (
                {
                    "jumpSpeed": 500,
                    "dashImmuneToDamageTime": 100,
                },
                BanditDash,
            ),
            (
                {
                    "jumpSpeed": 250,
                    "dashConstantTime": 800,
                    "dashLandingTime": 300,
                    "dashRadius": 2200,
                    "dashPushBack": 1000,
                },
                MegaKnightSlam,
            ),
        ),
    )
    def test_dash_variant_is_detected_from_payload_shape(
        self,
        extra_fields,
        expected_type,
    ):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericDashAttacker",
                "summonCharacterData": {
                    "dashDamage": 100,
                    "dashMinRange": 3500,
                    "dashMaxRange": 6000,
                    **extra_fields,
                },
            }
        )

        assert sum(isinstance(item, expected_type) for item in mechanics) == 1

    @pytest.mark.parametrize(
        ("character_fields", "projectile_fields", "expected_type"),
        (
            (
                {},
                {"chainedHitCount": 3, "chainedHitRadius": 4000},
                ElectroDragonChainLightning,
            ),
            (
                {"kamikaze": True},
                {"chainedHitCount": 9, "chainedHitRadius": 4000},
                ElectroSpiritChain,
            ),
            (
                {"kamikaze": True},
                {
                    "radius": 1500,
                    "targetBuffData": {"name": "Freeze"},
                },
                IceSpiritFreeze,
            ),
            (
                {
                    "kamikaze": True,
                    "deathSpawnCount": 2,
                    "deathSpawnCharacterData": {"name": "GenericRider"},
                },
                {},
                BattleRamCharge,
            ),
            (
                {
                    "kamikaze": True,
                    "areaDamageRadius": 1500,
                },
                {"radius": 1500},
                WallBreakersDemolition,
            ),
        ),
    )
    def test_kamikaze_and_chain_variant_is_detected_from_payload_shape(
        self,
        character_fields,
        projectile_fields,
        expected_type,
    ):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericPayloadAttacker",
                "summonCharacterData": {
                    **character_fields,
                    "projectileData": projectile_fields,
                },
            }
        )

        assert sum(isinstance(item, expected_type) for item in mechanics) == 1

    @pytest.mark.parametrize(
        ("character_fields", "expected_type"),
        (
            (
                {
                    "abilityData": {
                        "tid": "TID_ABILITY_INVISIBILITY_RUSH",
                        "buffData": {
                            "hitSpeedMultiplier": 280,
                            "speedMultiplier": -25,
                        },
                    },
                },
                ArcherQueenCloak,
            ),
            (
                {
                    "spawnPathfindSpeed": 650,
                },
                UndergroundDeployment,
            ),
        ),
    )
    def test_ability_and_deployment_variant_is_detected_without_card_name(
        self,
        character_fields,
        expected_type,
    ):
        mechanics = detect_mechanics_from_data(
            {
                "name": "GenericSpecialCharacter",
                "summonCharacterData": character_fields,
            }
        )

        assert sum(isinstance(item, expected_type) for item in mechanics) == 1


class TestPrincess:
    """Test Princess's real single-projectile, nine-tile range mechanic."""

    def test_long_range_init(self):
        """Test PrincessLongRange initialization"""
        range_mechanic = PrincessLongRange()
        assert range_mechanic.range_tiles == 9.0

    def test_long_range_on_attach(self):
        """Test Princess range bonus on attach"""
        entity = MockEntity(range=2.0)
        range_mechanic = PrincessLongRange()
        range_mechanic.on_attach(entity)

        assert entity.range == 9.0


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

    # Add Princess tests
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_long_range_init))
    suite.addTest(unittest.FunctionTestCase(TestPrincess().test_long_range_on_attach))

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
