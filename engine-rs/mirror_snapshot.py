"""Level-specific native payload tables for the unchanged Mirror resolver."""


def payload_key(name, level):
    return name if level == 11 else f'level{level}:{name}'


def extend(output, cards):
    from differential import config, initial
    probe = initial(cards=('Mirror', 'Knight', 'Zap', 'Archers'))
    supported = []
    for name in cards:
        if name == 'Mirror': continue
        probe.players[0].last_played_card = name
        probe.players[0].last_played_card_cost = probe.card_loader.get_card(name).mana_cost
        if probe.resolve_card_play(0, 'Mirror') is not None:
            supported.append(name)
    names = tuple(supported)
    mirrored = config(names, level=12, mirror_templates=False)

    def qualify(value):
        if isinstance(value, dict):
            if value.get('spell_name') in names:
                value['spell_name'] = payload_key(value['spell_name'], 12)
            for child in value.values(): qualify(child)
        elif isinstance(value, list):
            for child in value: qualify(child)

    qualify(mirrored)
    for table in ('cards', 'death_areas', 'death_objects', 'death_children',
                  'spirit_areas', 'production_children', 'spawn_areas',
                  'ability_bombs', 'bomb_children'):
        for name, value in mirrored.get(table, {}).items():
            output.setdefault(table, {})[payload_key(name, 12)] = value


def live_spell_key(entity, name, cfg):
    if not name or name not in cfg['cards']:
        return name
    level = getattr(entity.card_stats, 'level', getattr(entity, 'spawn_level', None))
    if level is not None:
        key = payload_key(name, level)
        return key if key in cfg['cards'] else name
    key = payload_key(name, 12)
    if key not in cfg['cards']:
        return name
    normal = cfg['cards'][name].get('spell') or {}
    mirrored = cfg['cards'][key].get('spell') or {}
    # Projectile carriers have no CardStats or level field. Their immutable
    # serialized damage distinguishes the captured effective spell payload.
    for field in ('damage', 'crown_tower_damage'):
        actual = getattr(entity, field, None)
        if mirrored.get(field) != normal.get(field) and actual == mirrored.get(field):
            return key
    return name
