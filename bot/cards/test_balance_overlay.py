"""balance_overlay on a small synthetic sample (no real gamedata or RoyaleSim tables in this file).

Covers the unit conversions (crown delta, damage on the unit or its projectile), rule 1 (16.402 wins), rule 2
(calibration only where RoyaleSim 15.535 == 16.402), rule 3 (uncertain / blank / default cells kept), structural
skips, the hold list, pass 2 (named projectiles, characters, buffs), determinism and the input JSON format.
"""
import copy
import json

from bot.cards import balance_overlay as bo


def unit(name, **kw):
    return dict(name=name, source='characters', **kw)


def troop(name, summon, **kw):
    return dict(name=name, source='spells_characters', manaCost=kw.pop('manaCost', 3), summonCharacterData=summon, **kw)


def spell(name, **kw):
    return dict(name=name, source='spells_other', manaCost=kw.pop('manaCost', 3), **kw)


def gamedata():
    spells = [
        troop('Knight', unit('Knight', hitpoints=100, damage=10, hitSpeed=1200, tidTarget='TID_TARGETS_GROUND',
                             areaDamageRadius=1000)),
        troop('Barbarians', unit('Barbarian', hitpoints=270, damage=75), summonNumber=5),
        troop('Bomber', unit('Bomber', hitpoints=150, projectileData=dict(name='BombProj', source='projectiles',
                                                                          damage=137, speed=500))),
        troop('Rascals', unit('RascalBoy', hitpoints=700, damage=80)),
        spell('Fireball', projectileData=dict(name='FireballSpell', source='projectiles', damage=269, radius=2500,
                                              crownTowerDamagePercent=-75)),
        spell('Zap', areaEffectObjectData=dict(name='Zap', source='area_effect_objects', damage=75, radius=2500,
                                               lifeDuration=1, crownTowerDamagePercent=-75)),
        spell('Lightning', areaEffectObjectData=dict(name='Lightning', source='area_effect_objects', hitSpeed=460,
                                                     radius=3500, lifeDuration=1500)),
        spell('BarbLog', projectileData=dict(
            name='BarbLogProjectile', source='projectiles', spawnProjectileData=dict(
                name='BarbLogRolling', source='projectiles', damage=91,
                spawnCharacterData=unit('Barbarian', hitpoints=270, damage=75)))),
        spell('DarkMagic', areaEffectObjectData=dict(
            name='DarkMagicAOE', source='area_effect_objects', radius=2500, onStartingAction=dict(
                classType='ActionGroup', subActions=[dict(classType='ActionPlayEffect'), dict(
                    classType='ActionLaserBall', onDetectedUnitActionList=[
                        # tiers listed in a different order from RoyaleSim's: matched by name, not index
                        dict(classType='ActionSpawn', spawnType='BuffType', spawnData=dict(
                            name='VoidLight', damagePerSecond=30, crownTowerDamagePerHit=1, hitFrequency=100)),
                        dict(classType='ActionSpawn', spawnType='BuffType', spawnData=dict(
                            name='VoidHeavy', damagePerSecond=130, crownTowerDamagePerHit=19, hitFrequency=100)),
                        dict(classType='ActionSpawn', spawnType='BuffType', spawnData=dict(
                            name='VoidOnlyOurs', damagePerSecond=5)),
                    ])]))),
        spell('Poison', areaEffectObjectData=dict(
            name='Poison', source='area_effect_objects', lifeDuration=8000, radius=3500,
            buffData=dict(name='Poison', source='character_buffs', crownTowerDamagePercent=-77, damagePerSecond=36))),
        dict(name='Hidden', source='spells_characters', notVisible=True, manaCost=1,
             summonCharacterData=unit('Hidden', hitpoints=1)),
    ]
    return dict(meta=dict(fingerprint='x'), items=dict(spells=spells, arenas=[]))


def calibration():
    g = gamedata()
    s = {x['name']: x for x in g['items']['spells']}
    s['Barbarians']['summonCharacterData']['hitpoints'] = 280                       # rule 2: RS 15 == 16 -> applied
    s['BarbLog']['projectileData']['spawnProjectileData']['spawnCharacterData']['hitpoints'] = 280
    s['Bomber']['summonCharacterData']['projectileData']['damage'] = 110            # RS 15 != 16 -> 16.402 wins
    s['Rascals']['summonDeployDelay'] = 100                                         # RS has no value -> not applied
    return g


def rs_card(name, **kw):
    return dict(name=name, kind=kw.pop('kind', 'troop'), elixir=kw.pop('elixir', 3), count=kw.pop('count', 1), **kw)


def royalesim(v16=True):
    """A RoyaleSim-shaped doc. v16=False gives the 15.535 table."""
    knight_hp = 110 if v16 else 100
    bomb = 118 if v16 else 110
    rolling = 84 if v16 else 91
    fire_crown = 23 if v16 else 25
    poison_crown = 22 if v16 else 23
    units = dict(
        Knight=dict(name='Knight', hitpoints=knight_hp, damage=10, hit_speed_ms=1200),
        Barbarian=dict(name='Barbarian', hitpoints=280, damage=75),
        Bomber=dict(name='Bomber', hitpoints=150, damage=bomb, projectile=dict(name='BombProj', speed=500)),
        RascalBoy=dict(name='RascalBoy', hitpoints=700, damage=80),
    )
    cards = [
        rs_card('Knight', summon_character='Knight', hitpoints=knight_hp, damage=10, hit_speed_ms=1200,
                attacks_air=True, area_damage_radius_milli=1500,
                defaults_applied=['area_damage_radius_milli']),
        rs_card('Barbarians', count=5, summon_character='Barbarian', hitpoints=280, damage=75),
        rs_card('Bomber', summon_character='Bomber', hitpoints=150, damage=bomb,
                projectile=dict(name='BombProj', speed=500, damage=bomb)),
        rs_card('Rascals', summon_character='RascalBoy', hitpoints=700, damage=80),
        rs_card('Fireball', kind='spell', damage=269, crown_tower_damage_percent=fire_crown,
                projectile=dict(name='FireballSpell', damage=269, crown_tower_damage_percent=fire_crown,
                                crown_tower_damage_percent_raw=fire_crown - 100)),
        rs_card('Zap', kind='spell', damage=75, crown_tower_damage_percent=100,
                spell=dict(area_effect_object=dict(name='Zap', damage=75, radius_milli=2500, life_duration_ms=1,
                                                   crown_tower_damage_percent=100,
                                                   crown_tower_damage_percent_raw=None))),
        rs_card('Lightning', kind='spell',
                spell=dict(area_effect_object=dict(name='Lightning', hit_speed_ms=500, radius_milli=3500,
                                                   life_duration_ms=1500))),
        rs_card('BarbLog', kind='spell'),
        rs_card('DarkMagic', kind='spell', elixir=5,
                spell=dict(area_effect_object=dict(name='DarkMagicAOE', radius_milli=2500, strike_area=dict(
                    kind='laser_ball', tiers=[
                        dict(buff=dict(name='VoidHeavy', damage_per_second=272, crown_tower_damage_per_hit=38,
                                       hit_frequency_ms=100)),
                        dict(buff=dict(name='VoidLight', damage_per_second=60 if v16 else 55,
                                       crown_tower_damage_per_hit=None, hit_frequency_ms=100))])))),
        rs_card('Poison', kind='spell',
                spell=dict(area_effect_object=dict(name='Poison', life_duration_ms=8000, radius_milli=3500))),
    ]
    return dict(
        version='synthetic-16' if v16 else 'synthetic-15', cards=cards, units=units,
        projectiles=dict(BombProj=dict(name='BombProj', damage=bomb, speed=500),
                         FireballSpell=dict(name='FireballSpell', damage=269, radius_milli=2500,
                                            crown_tower_damage_percent_raw=fire_crown - 100),
                         BarbLogRolling=dict(name='BarbLogRolling', damage=rolling)),
        area_effect_objects=dict(Zap=dict(name='Zap', damage=75, radius_milli=2500, life_duration_ms=1,
                                          crown_tower_damage_percent_raw=None),
                                 Poison=dict(name='Poison', life_duration_ms=8000, radius_milli=3500)),
        buffs=dict(Poison=dict(name='Poison', crown_tower_damage_percent=poison_crown, damage_per_second=36)))


def run_sample(tmp_path, name='out'):
    gd = tmp_path / 'gamedata.json'
    if not gd.exists():
        gd.write_text(json.dumps(gamedata(), indent=2, ensure_ascii=False) + '\n')
        (tmp_path / 'rs16.json').write_text(json.dumps(royalesim(True)))
        (tmp_path / 'rs15.json').write_text(json.dumps(royalesim(False)))
        (tmp_path / 'cal.json').write_text(json.dumps(calibration(), indent=2, ensure_ascii=False) + '\n')
    out = tmp_path / name / 'gamedata.json'
    receipt, detail = bo.run(gd, tmp_path / 'rs16.json', tmp_path / 'rs15.json', tmp_path / 'cal.json', out)
    return receipt, detail, json.loads(out.read_text()), out


def by_card(doc):
    return {s['name']: s for s in doc['items']['spells']}


def slot(detail, card, field, subject=None):
    hits = [d for d in detail if d.get('card') == card and d.get('field') == field
            and (subject is None or d['subject'] == subject)]
    assert len(hits) == 1, (card, field, hits)
    return hits[0]


def test_rule1_rs16_value_written(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Knight']['summonCharacterData']['hitpoints'] == 110
    assert slot(detail, 'Knight', 'hitpoints')['action'] == 'apply'
    assert receipt['comparer_check'] == dict(missing=[], extra=[])


def test_damage_goes_where_the_comparer_reads_it(tmp_path):
    # Bomber has no unit damage: the comparer reads (and the overlay writes) the projectile damage
    _, detail, out, _ = run_sample(tmp_path)
    bomber = by_card(out)['Bomber']['summonCharacterData']
    assert 'damage' not in bomber and bomber['projectileData']['damage'] == 118
    assert slot(detail, 'Bomber', 'damage')['path'] == '/summonCharacterData/projectileData/damage'


def test_crown_written_as_delta_from_100(tmp_path):
    _, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Fireball']['projectileData']['crownTowerDamagePercent'] == -77   # 23 % effective
    s = slot(detail, 'Fireball', 'crown tower damage percent', 'card')
    assert (s['ours'], s['rs16402'], s['written']) == (25, 23, -77)


def test_rule2_calibration_applied_when_rs_unchanged(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    s = slot(detail, 'Barbarians', 'hitpoints')
    assert s['action'] == 'calibration' and s['written'] == 280
    assert any(c['card'] == 'Barbarians' and c['action'] == 'calibration' for c in receipt['calibration_cases'])


def test_rule2_calibration_superseded_when_rs_changed(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    s = slot(detail, 'Bomber', 'damage')
    assert (s['calibration'], s['rs15535'], s['rs16402'], s['action'], s['written']) == (110, 110, 118, 'apply', 118)
    assert 'superseded' in s['reason']
    assert any(c['card'] == 'Bomber' and 'superseded' in c['reason'] for c in receipt['calibration_cases'])


def test_rule2_calibration_not_applied_without_rs_value(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    assert 'summonDeployDelay' not in by_card(out)['Rascals']
    assert slot(detail, 'Rascals', 'summon deploy delay (ms)')['action'] == 'keep-calibration-unconfirmed'
    cov = [c for c in receipt['calibration_paths'] if c['card'] == 'Rascals']
    assert cov and cov[0]['output'] is None


def test_rule3_blank_crown_cell_kept(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Zap']['areaEffectObjectData']['crownTowerDamagePercent'] == -75
    assert slot(detail, 'Zap', 'crown tower damage percent', 'card')['action'] == 'skip-uncertain'
    assert any(u[0] == 'Zap' for u in receipt['uncertain_kept'])


def test_rule3_comparer_caveat_kept(tmp_path):
    # Lightning hit speed carries a comparer caveat (balance_size.UNSURE_EXTRA): ours stays
    _, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Lightning']['areaEffectObjectData']['hitSpeed'] == 460
    assert slot(detail, 'Lightning', 'hit speed (ms)', 'card')['action'] == 'skip-uncertain'


def test_rule3_royalesim_default_kept(tmp_path):
    _, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Knight']['summonCharacterData']['areaDamageRadius'] == 1000
    assert slot(detail, 'Knight', 'area damage radius')['action'] == 'skip-uncertain'


def test_structural_and_hold(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    assert by_card(out)['Knight']['summonCharacterData']['tidTarget'] == 'TID_TARGETS_GROUND'
    assert slot(detail, 'Knight', 'attacks air')['action'] == 'skip-structural'
    assert by_card(out)['DarkMagic']['manaCost'] == 3
    assert slot(detail, 'DarkMagic', 'elixir')['action'] == 'skip-hold' and receipt['held']


def test_pass2_named_objects(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    rolling = by_card(out)['BarbLog']['projectileData']['spawnProjectileData']
    assert rolling['damage'] == 84                                         # named projectile, rule 1
    assert rolling['spawnCharacterData']['hitpoints'] == 280               # named character, rule 2
    assert slot(detail, 'BarbLog', 'hitpoints')['action'] == 'calibration'
    assert by_card(out)['Poison']['areaEffectObjectData']['buffData']['crownTowerDamagePercent'] == -78  # buff: 22 %
    assert receipt['actions_by_pass']['2']['apply'] >= 2


def test_only_applied_locations_change(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    before = gamedata()
    diffs = bo.bs.field_diff(by_card(before), by_card(out))
    applied = [d for d in detail if d.get('action') in ('apply', 'calibration')]
    assert len(diffs) == len(applied) == receipt['applied_slots']
    assert by_card(out)['Hidden'] == by_card(before)['Hidden']              # outside the pool: untouched
    assert set(out['meta']) == {'fingerprint', 'live16402_overlay'}


def test_deterministic_and_format_kept(tmp_path):
    r1, _, _, out1 = run_sample(tmp_path, 'a')
    r2, _, _, out2 = run_sample(tmp_path, 'b')
    assert out1.read_bytes() == out2.read_bytes()
    assert r1['output']['sha256'] == r2['output']['sha256']
    raw = out1.read_bytes()
    assert raw == (json.dumps(json.loads(raw), indent=2, ensure_ascii=False) + '\n').encode()


def test_receipt_has_no_stat_values_in_change_lists(tmp_path):
    receipt, _, _, _ = run_sample(tmp_path)
    for card, subject, fld in receipt['changed_fields']:
        assert isinstance(card, str) and isinstance(subject, str) and isinstance(fld, str)
    assert sum(receipt['changes_by_card'].values()) == receipt['applied_slots']


def test_decide_rule2_table():
    """decide() alone: calibration needs RoyaleSim 15.535 == 16.402 (both present)."""
    def d(ours, rs16, rs15, cal):
        return bo.decide(bo.Slot('A', 'card', 'damage', 'num', ours, rs16, bo.Loc({'d': ours}, 'd', '/d'),
                                 rs15=rs15, cal=cal))
    assert (d(10, 12, 12, 11).action, d(10, 12, 12, 11).value) == ('calibration', 11)
    assert (d(10, 12, 11, 11).action, d(10, 12, 11, 11).value) == ('apply', 12)
    assert (d(10, 12, None, 11).action, d(10, 12, None, 11).value) == ('apply', 12)
    assert d(10, None, None, 11).action == 'keep-calibration-unconfirmed'
    assert d(10, 10, 10, 10).action == 'agree'
    assert (d(10, 12, 10, 10).action, d(10, 12, 10, 10).value) == ('apply', 12)


def test_pass3_detection_action_tiers_by_name(tmp_path):
    receipt, detail, out, _ = run_sample(tmp_path)
    tiers = by_card(out)['DarkMagic']['areaEffectObjectData']['onStartingAction']['subActions'][1][
        'onDetectedUnitActionList']
    light, heavy, only = (t['spawnData'] for t in tiers)
    assert (heavy['damagePerSecond'], heavy['crownTowerDamagePerHit']) == (272, 38)    # rule 1, absolute crown
    assert light['damagePerSecond'] == 60                                               # 15.535 != 16.402: 16.402
    assert light['crownTowerDamagePerHit'] == 1                                         # blank RS cell: kept
    assert only == dict(name='VoidOnlyOurs', damagePerSecond=5)                        # no RS tier: no slot
    s = slot(detail, 'DarkMagic', 'crownTowerDamagePerHit', 'tier laser_ball VoidLight')
    assert s['action'] == 'skip-uncertain'
    assert receipt['actions_by_pass']['3']['apply'] == 3


def test_pass3_kind_must_match():
    card = dict(name='X', a=dict(classType='ActionBeam', onDetectedUnitActionList=[
        dict(spawnType='BuffType', spawnData=dict(name='B', damagePerSecond=1))]))
    rec = dict(spell=dict(strike_area=dict(kind='laser_ball', tiers=[dict(buff=dict(name='B', damage_per_second=2))])))
    assert bo._action_kind('ActionLaserBall') == 'laser_ball'
    assert set(bo._our_tier_buffs(card)) == {('beam', 'B')}
    assert set(bo._rs_tier_buffs(rec)) == {('laser_ball', 'B')}
