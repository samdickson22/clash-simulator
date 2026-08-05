from clasher.data import CardDataLoader


def test_level_multipliers_match_game_tables():
    knight = CardDataLoader().get_card("Knight")
    assert knight is not None
    assert knight.get_scaled_stat(690, level=11) == 1766
    assert knight.get_scaled_stat(690, level=12) == 1938
    assert knight.get_scaled_stat(690, level=16) == 2822


def test_cached_definitions_still_create_loader_local_compatibility_stats():
    first = CardDataLoader().get_card("Knight")
    second = CardDataLoader().get_card("Knight")
    assert first is not None and second is not None
    assert first is not second

    original_damage = second.damage
    first.damage = -1
    assert second.damage == original_damage


def test_level_11_snapshot_stats_use_game_multiplier():
    loader = CardDataLoader()
    queen = loader.get_card("ArcherQueen")
    balloon = loader.get_card("Balloon")
    assert queen is not None and balloon is not None
    assert (queen.scaled_hitpoints, queen.scaled_damage) == (1000, 225)
    assert balloon.scaled_damage == 640


def test_current_balance_layer_updates_enabled_base_cards():
    loader = CardDataLoader()
    expected = {
        "Minions": (230, 107, 1200),
        "Wallbreakers": (330, 350, 1200),
        "MagicArcher": (529, 143, 1100),
        "MiniPekka": (1390, 755, 1600),
        "DartGoblin": (261, 151, 800),
        "Giant": (3968, 253, 1500),
        "Balloon": (1676, 640, 2000),
        "Bats": (81, 81, 1200),
        "ElectroDragon": (1049, 192, 2100),
        "ElectroWizard": (714, 117, 1800),
        "Cannon": (824, 202, 1000),
        "DarkPrince": (1200, 266, 1400),
        "Tesla": (1182, 220, 1100),
        "BabyDragon": (1152, 168, 1500),
        "IceGolem": (1315, 84, 2500),
        "Pekka": (3760, 842, 1800),
    }
    for name, values in expected.items():
        card = loader.get_card(name)
        assert card is not None
        assert (card.scaled_hitpoints, card.scaled_damage, card.hit_speed) == values

    assert loader.get_card("Prince").charge_range == 250
    assert {
        name: loader.get_card(name).charge_speed_multiplier
        for name in ("Prince", "DarkPrince", "BattleRam")
    } == {"Prince": 200, "DarkPrince": 200, "BattleRam": 200}
    assert loader.get_card("RoyalGhost")._raw_entry["summonCharacterData"][
        "buffWhenNotAttackingTime"
    ] == 2000
    assert loader.get_card("ArcherQueen")._raw_entry["summonCharacterData"][
        "abilityData"
    ]["castTime"] == 933
    assert loader.get_card("Firecracker").projectile_speed == 500
    assert loader.get_card("Firecracker").sight_range == 8.0
    assert loader.get_card("InfernoDragon").projectile_start_radius == 0.45
    assert loader.get_card("IceWizard").projectile_data["homing"] is True
    assert loader.get_card("Xbow").projectile_data["homing"] is True
    assert loader.get_card("Tesla").lifetime_ms == 25000
    assert loader.get_card("SpearGoblins").summon_radius == 0.8
    assert loader.get_card("DarkPrince").scaled_damage_special == 532
    assert (loader.get_card("BattleRam").load_time, loader.get_card("BattleRam").first_hit_time) == (
        350,
        50,
    )
    assert loader.get_card("BattleRam").death_spawn_radius == 0.6
    assert loader.get_card("BattleRam").spawn_angle_shift == 180
    skeleton_barrel = loader.get_card("SkeletonBarrel")
    assert skeleton_barrel.range == 0.35
    assert skeleton_barrel.kamikaze_time == 500
    royal_hogs = loader.get_card("RoyalHogs")
    assert royal_hogs.summon_width == 3.5
    assert royal_hogs.deploy_w_tile_margin == 2
    assert loader.get_card("Miner").can_deploy_on_enemy_side
    mega_knight = loader.get_card("MegaKnight")._raw_entry["summonCharacterData"]
    assert (
        mega_knight["dashCooldown"],
        mega_knight["dashConstantTime"],
        mega_knight["dashLandingTime"],
        mega_knight["dashPushBack"],
        mega_knight["dashRadius"],
    ) == (900, 800, 300, 1000, 2200)


def test_current_hidden_combat_timings_and_nested_character_balance():
    loader = CardDataLoader()
    expected = {
        # name: (hit time ms, first hit ms, range tiles)
        "Skeletons": (1100, 500, 0.5),
        "Minions": (1200, 500, 2.5),
        "Miner": (1300, 500, 1.2),
        "DartGoblin": (800, 350, 6.5),
        "Bats": (1200, 600, 1.2),
        "DarkPrince": (1400, 400, 1.2),
        "SpearGoblins": (1700, 500, 5.0),
    }
    for name, values in expected.items():
        card = loader.get_card(name)
        assert card is not None
        assert (card.hit_speed, card.first_hit_time, card.range) == values

    lumberjack = loader.get_card("Lumberjack")
    rage_buff = lumberjack._raw_entry["summonCharacterData"]["deathSpawnCharacterData"][
        "deathAreaEffectData"
    ]["buffData"]
    assert rage_buff["hitSpeedMultiplier"] == 130
    assert rage_buff["speedMultiplier"] == 130


def test_load_time_encodes_first_hit_and_overloaded_retarget_timings():
    loader = CardDataLoader()
    xbow = loader.get_card("Xbow")
    inferno_dragon = loader.get_card("InfernoDragon")
    inferno_tower = loader.get_card("InfernoTower")
    assert xbow is not None and inferno_dragon is not None and inferno_tower is not None

    # Missing loadTime means a complete preload, not an arbitrary one-second
    # value. X-Bow therefore begins ready after its deployment window.
    assert (xbow.hit_speed, xbow.load_time, xbow.first_hit_time) == (300, 300, 0)

    # An explicit load time above hit speed is the generic retarget form used
    # by ramping weapons: first lock is one hit, target changes cost the excess.
    for card in (inferno_dragon, inferno_tower):
        assert (card.hit_speed, card.load_time) == (400, 1200)
        assert card.first_hit_time == 400
        assert card.retarget_time == 800
