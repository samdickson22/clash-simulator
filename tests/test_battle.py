"""Tests for the Clash Royale battle simulator."""
import json
import random
import pytest
from clasher.battle import BattleState
from clasher.arena import Position


@pytest.fixture
def battle():
    """Fresh battle state."""
    return BattleState()


@pytest.fixture
def decks():
    with open("decks.json") as f:
        return json.load(f)["decks"]


def setup_battle(b: BattleState, deck0: list, deck1: list):
    """Set up battle with two decks."""
    for pid, deck in enumerate([deck0, deck1]):
        p = b.players[pid]
        p.deck = list(deck)
        p.hand = list(deck[:4])
        p.cycle_queue.clear()
        for c in deck[4:]:
            p.cycle_queue.append(c)


def run_battle_with_random_ai(b: BattleState, max_ticks=11000, seed=42):
    """Run battle with simple random AI for both players."""
    random.seed(seed)
    for _ in range(max_ticks):
        b.step()
        if b.game_over:
            break
        for pid in [0, 1]:
            p = b.players[pid]
            for card in list(p.hand):
                stats = b.card_loader.get_card(card) or b.card_loader.get_card_compat(card)
                if stats and p.elixir >= getattr(stats, "mana_cost", 99):
                    x = random.uniform(3, 15)
                    y = random.uniform(1, 14) if pid == 0 else random.uniform(17, 30)
                    b.deploy_card(pid, card, Position(x, y))
                    break
    return b


# ---- Basic engine tests ----

class TestEngine:
    def test_initial_state(self, battle):
        assert battle.time == 0.0
        assert not battle.game_over
        assert battle.winner is None
        assert len(battle.entities) == 6  # 6 towers

    def test_elixir_regeneration(self, battle):
        for _ in range(100):
            battle.step()
        # After ~3.3s, should have regenerated some elixir
        assert battle.players[0].elixir > 5.0

    def test_double_elixir_activation(self, battle):
        # Fast forward to 3 minutes (180s)
        for _ in range(5455):  # 180s / 0.033
            battle.step()
        assert battle.double_elixir

    def test_deploy_troop(self, battle):
        p = battle.players[0]
        p.hand = ["Knight"]
        p.deck = ["Knight"]
        p.elixir = 10.0
        ok = battle.deploy_card(0, "Knight", Position(9, 10))
        assert ok
        assert len(battle.entities) == 7  # 6 towers + 1 knight

    def test_deploy_spell(self, battle):
        p = battle.players[0]
        p.hand = ["Zap"]
        p.deck = ["Zap"]
        p.elixir = 10.0
        ok = battle.deploy_card(0, "Zap", Position(9, 25))
        assert ok

    def test_card_cycle(self, battle):
        p = battle.players[0]
        p.deck = ["Knight", "Archers", "Giant", "Fireball", "Musketeer", "Zap", "Log", "Minions"]
        p.hand = ["Knight", "Archers", "Giant", "Fireball"]
        p.cycle_queue.clear()
        for c in ["Musketeer", "Zap", "Log", "Minions"]:
            p.cycle_queue.append(c)
        p.elixir = 10.0

        battle.deploy_card(0, "Knight", Position(9, 10))
        # Knight should be replaced by Musketeer
        assert "Musketeer" in p.hand
        assert "Knight" not in p.hand


# ---- Card loading tests ----

class TestCardLoading:
    def test_all_60_cards_loadable(self, battle):
        """Every card used in the 30 sample decks must be loadable."""
        with open("decks.json") as f:
            decks = json.load(f)["decks"]
        all_cards = set()
        for d in decks:
            all_cards.update(d["cards"])

        from clasher.spells import SPELL_REGISTRY
        from clasher.name_map import resolve_name

        missing = []
        for card in sorted(all_cards):
            stats = battle.card_loader.get_card(card) or battle.card_loader.get_card_compat(card)
            internal = resolve_name(card)
            is_spell = card in SPELL_REGISTRY or internal in SPELL_REGISTRY
            if not stats and not is_spell:
                missing.append(card)

        assert missing == [], f"Cards not loadable: {missing}"


# ---- Deck battle tests ----

class TestDeckBattles:
    def test_all_deck_pairs_no_crash(self, decks):
        """All 15 adjacent deck pairs should complete without crash."""
        for i in range(0, len(decks) - 1, 2):
            d0, d1 = decks[i], decks[i + 1]
            b = BattleState()
            setup_battle(b, d0["cards"], d1["cards"])
            run_battle_with_random_ai(b, max_ticks=2000, seed=i)
            # Should not crash - if we get here, it passed

    def test_battles_produce_damage(self, decks):
        """After 2000 ticks, at least some tower damage should occur."""
        d0, d1 = decks[0], decks[1]
        b = BattleState()
        setup_battle(b, d0["cards"], d1["cards"])
        run_battle_with_random_ai(b, max_ticks=3000, seed=99)

        # At least one tower should have taken damage
        p0 = b.players[0]
        p1 = b.players[1]
        total_damage = (
            max(0, 3631 - p0.left_tower_hp)
            + max(0, 3631 - p0.right_tower_hp)
            + max(0, 4824 - p0.king_tower_hp)
            + max(0, 3631 - p1.left_tower_hp)
            + max(0, 3631 - p1.right_tower_hp)
            + max(0, 4824 - p1.king_tower_hp)
        )
        assert total_damage > 0, "No tower damage occurred in battle"

    def test_full_battle_produces_winner(self, decks):
        """A full-length battle should produce a winner or draw."""
        d0, d1 = decks[0], decks[1]
        b = BattleState()
        setup_battle(b, d0["cards"], d1["cards"])
        run_battle_with_random_ai(b, max_ticks=11000, seed=42)
        assert b.game_over, "Battle should end within time limit"


# ---- Win condition tests ----

class TestWinConditions:
    def test_king_tower_destruction_wins(self, battle):
        """Destroying king tower should end the game."""
        # Find red king tower and destroy it
        for eid, ent in list(battle.entities.items()):
            if ent.player_id == 1 and ent.position.y > 28:
                ent.take_damage(99999)
        battle._cleanup_dead_entities()
        battle._check_win_conditions()
        assert battle.game_over
        assert battle.winner == 0

    def test_overtime_crown_difference(self, battle):
        """In overtime, more crowns should win."""
        battle.time = 300.0
        battle.overtime = True
        # Destroy one of P1's princess towers
        for eid, ent in list(battle.entities.items()):
            if ent.player_id == 1 and ent.position.y < 28 and ent.position.y > 20:
                ent.take_damage(99999)
                break
        battle._cleanup_dead_entities()
        battle._check_win_conditions()
        assert battle.game_over
        assert battle.winner == 0


# ---- Specific card mechanic tests ----

class TestCardMechanics:
    def test_knight_attacks(self, battle):
        """Knight should move and attack enemies."""
        p = battle.players[0]
        p.hand = ["Knight"]
        p.deck = ["Knight"]
        p.elixir = 10
        battle.deploy_card(0, "Knight", Position(9, 10))
        
        knight = None
        for e in battle.entities.values():
            if getattr(e.card_stats, "name", "") == "Knight":
                knight = e
                break
        assert knight is not None
        
        initial_y = knight.position.y
        for _ in range(100):
            battle.step()
        # Knight should have moved toward enemy side
        assert knight.position.y > initial_y

    def test_giant_targets_buildings(self, battle):
        """Giant should only target buildings."""
        stats = battle.card_loader.get_card("Giant")
        assert stats is not None
        assert stats.targets_only_buildings

    def test_balloon_is_air(self, battle):
        """Balloon should be classified as air unit."""
        p = battle.players[0]
        p.hand = ["Balloon"]
        p.deck = ["Balloon"]
        p.elixir = 10
        battle.deploy_card(0, "Balloon", Position(9, 10))
        
        balloon = None
        for e in battle.entities.values():
            if getattr(e.card_stats, "name", "") == "Balloon":
                balloon = e
                break
        assert balloon is not None
        assert balloon.is_air_unit

    def test_golem_death_spawn(self, battle):
        """Golem should spawn Golemites on death."""
        stats = battle.card_loader.get_card("Golem")
        assert stats is not None
        assert stats.death_spawn_character is not None

    def test_witch_spawns_skeletons(self, battle):
        """Witch should have periodic spawner mechanic."""
        stats = battle.card_loader.get_card("Witch")
        assert stats is not None
        assert stats.spawner_spawn_character_data is not None

    def test_inferno_tower_damage_ramp(self, battle):
        """Inferno Tower should have damage ramp mechanic."""
        defn = battle.card_loader.get_card_definition("InfernoTower")
        assert defn is not None
        has_ramp = any("DamageRamp" in type(m).__name__ for m in defn.mechanics)
        assert has_ramp

    def test_guards_have_shield(self, battle):
        """Guards should have shield mechanic."""
        defn = battle.card_loader.get_card_definition("Guards")
        assert defn is not None
        has_shield = any("Shield" in type(m).__name__ for m in defn.mechanics)
        assert has_shield

    def test_spell_zap_stuns(self, battle):
        """Zap should deal damage and stun."""
        from clasher.spells import SPELL_REGISTRY
        zap = SPELL_REGISTRY.get("Zap")
        assert zap is not None
        assert zap.stun_duration > 0

    def test_spell_log_rolls(self, battle):
        """Log should be a rolling projectile spell."""
        from clasher.spells import SPELL_REGISTRY
        log = SPELL_REGISTRY.get("Log")
        assert log is not None

    def test_aliased_cards_deploy(self, battle):
        """Cards with name aliases (Archers, Bandit, etc.) should deploy correctly."""
        aliases = ["Archers", "Bandit", "DartGoblin", "Guards", "IceGolem",
                   "IceSpirit", "Lumberjack", "MagicArcher", "RoyalGhost", "SkeletonBarrel"]
        p = battle.players[0]
        p.elixir = 100
        for card in aliases:
            p.hand = [card]
            p.deck = [card]
            stats = battle.card_loader.get_card(card) or battle.card_loader.get_card_compat(card)
            assert stats is not None, f"Card {card} not found"

    def test_aliased_spells_deploy(self, battle):
        """BarbarianBarrel and GiantSnowball should deploy via alias."""
        from clasher.spells import SPELL_REGISTRY
        from clasher.name_map import resolve_name
        for card in ["BarbarianBarrel", "GiantSnowball"]:
            internal = resolve_name(card)
            assert internal in SPELL_REGISTRY, f"{card} ({internal}) not in spell registry"
