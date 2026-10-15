"""Make the pinned native's name-keyed config/metadata lookups total (skip the effect when the entry is absent).
usage: python patch_total.py ENGINE_RS_DIR   (edits src/*.rs in place; every replacement must match exactly once)"""
import sys
from pathlib import Path

E = [
    # (file, old, new)
    ('c56.rs',
     '''            let target = &self.entities[j];
            let mut chain = self.config.cards[source.stats.key()].chain.clone().unwrap();
            chain.owner = source.owner;
            chain.id = self.next_id as i32;
            self.next_id += 1;
            chain.x = target.x;
            chain.y = target.y;
            chain.chain_origin = (target.x, target.y);
            chain.chain_remaining = source.stats.chain_count.saturating_sub(1);
            chain.hit_ids = vec![target.id];
            chain.birth = self.tick;
            self.entities.push(chain);
        }''',
     '''            // A source whose card (or chain template) is absent from the config keeps its hit and death.
            if let Some(mut chain) = self.config.cards.get(source.stats.key()).and_then(|c| c.chain.clone()) {
                let target = &self.entities[j];
                chain.owner = source.owner;
                chain.id = self.next_id as i32;
                self.next_id += 1;
                chain.x = target.x;
                chain.y = target.y;
                chain.chain_origin = (target.x, target.y);
                chain.chain_remaining = source.stats.chain_count.saturating_sub(1);
                chain.hit_ids = vec![target.id];
                chain.birth = self.tick;
                self.entities.push(chain);
            }
        }'''),
    ('c56.rs',
     '''        let spell = self.config.cards[&area.spell_name].spell.clone().unwrap();
        let duration = area.effect_duration;''',
     '''        let Some(spell) = self.config.cards.get(&area.spell_name).and_then(|c| c.spell.clone()) else {
            if area.effect_age >= area.effect_duration - 1e-9 { self.entities[i].alive = false; }
            return;
        };
        let duration = area.effect_duration;'''),
    ('c56.rs',
     '''        let card = self.config.cards[&source.spell_name].clone();
        let spell = card.spell.as_ref().unwrap();''',
     '''        let Some(card) = self.config.cards.get(&source.spell_name).filter(|c| c.spell.is_some()).cloned() else {
            self.entities[i].alive = false;
            return;
        };
        let spell = card.spell.as_ref().unwrap();'''),
    ('c56.rs',
     '''        let spell = self.config.cards[&area.spell_name].spell.clone().unwrap();
        let deadline = area.effect_age.min(area.effect_duration);''',
     '''        let Some(spell) = self.config.cards.get(&area.spell_name).and_then(|c| c.spell.clone()) else {
            if area.effect_age >= area.effect_duration - 1e-9 { self.entities[i].alive = false; }
            return;
        };
        let deadline = area.effect_age.min(area.effect_duration);'''),
    ('lib.rs',
     '''        let spell = self.config.cards[&name].spell.clone().unwrap();
        let e = &mut self.entities[i];''',
     '''        let Some(spell) = self.config.cards.get(&name).and_then(|c| c.spell.clone()) else {
            self.entities[i].alive = false;
            return;
        };
        let e = &mut self.entities[i];'''),
    ('lib.rs',
     '''            let spawns = self.config.cards[&cast.name].spawns[owner].clone();''',
     '''            let spawns = self.config.cards.get(&cast.name).map(|c| c.spawns[owner].clone()).unwrap_or_default();'''),
    ('lib.rs',
     '''            let spell = self.config.cards[&cast.name].spell.clone().unwrap();
            self.direct_spell(&cast, &spell, None);''',
     '''            let Some(spell) = self.config.cards.get(&cast.name).and_then(|c| c.spell.clone()) else { continue; };
            self.direct_spell(&cast, &spell, None);'''),
    ('lib.rs',
     '''                            let spell = self.config.cards[&name].spell.clone().unwrap();
                            let cast = Cast {
                                player: self.entities[i].owner as usize,
                                name,
                                x: self.entities[i].aim.0,
                                y: self.entities[i].aim.1,
                            };
                            self.grouped_spell(
                                &cast,
                                &spell,
                                Some((self.entities[i].x, self.entities[i].y)),
                                self.entities[i].damage_group,
                            );
                        } else if''',
     '''                            if let Some(spell) = self.config.cards.get(&name).and_then(|c| c.spell.clone()) {
                                let cast = Cast {
                                    player: self.entities[i].owner as usize,
                                    name,
                                    x: self.entities[i].aim.0,
                                    y: self.entities[i].aim.1,
                                };
                                self.grouped_spell(
                                    &cast,
                                    &spell,
                                    Some((self.entities[i].x, self.entities[i].y)),
                                    self.entities[i].damage_group,
                                );
                            }
                        } else if'''),
    ('scope.rs',
     '''        let mut child = self.config.cards[&area.spell_name].spawns[area.owner as usize][0].clone();''',
     '''        let Some(mut child) = self.config.cards.get(&area.spell_name)
            .and_then(|c| c.spawns[area.owner as usize].first().cloned()) else { return; };'''),
    ('scope.rs',
     '''if let Some(template) = self.config.cards[&area.spell_name].spawns[area.owner as usize].first() {''',
     '''if let Some(template) = self.config.cards.get(&area.spell_name).and_then(|c| c.spawns[area.owner as usize].first()) {'''),
    ('spawn.rs',
     '''        let mut child = self.config.production_children[parent.stats.key()].clone();''',
     '''        let Some(mut child) = self.config.production_children.get(parent.stats.key()).cloned() else { return; };'''),
    ('champions.rs',
     '''        let mut bomb = self.config.ability_bombs[e.stats.key()].clone();
        bomb.id = self.next_id as i32;
        self.next_id += 1;
        bomb.owner = e.owner;
        bomb.x = e.x;
        bomb.y = e.y;
        bomb.facing = (0, if e.owner == 0 { 1000 } else { -1000 });
        bomb.birth = self.tick;''',
     '''        let mut bomb = self.config.ability_bombs.get(e.stats.key()).cloned();
        if let Some(bomb) = bomb.as_mut() {
            bomb.id = self.next_id as i32;
            self.next_id += 1;
            bomb.owner = e.owner;
            bomb.x = e.x;
            bomb.y = e.y;
            bomb.facing = (0, if e.owner == 0 { 1000 } else { -1000 });
            bomb.birth = self.tick;
        }'''),
    ('champions.rs',
     '''        e.reset_ramp();
        self.entities.push(bomb);''',
     '''        e.reset_ramp();
        if let Some(bomb) = bomb { self.entities.push(bomb); }'''),
    # NativeScripts
    ('c56_scripts.rs',
     '''            let m = &self.meta.cards[name];''',
     '''            let Some(m) = self.meta.cards.get(name) else { continue; };'''),
    ('scripts.rs',
     '''        let card=&b.config.cards[name];''',
     '''        let Some(card)=b.config.cards.get(name) else { return true; };'''),
    ('scripts.rs',
     '''            let m = &self.meta.bodies[&e.stats.name];''',
     '''            let Some(m) = self.meta.bodies.get(&e.stats.name) else { continue; };'''),
    ('scripts.rs',
     '''.map(|s| s.as_ref().map_or(0, |s| self.meta.cards[s].token))''',
     '''.map(|s| s.as_ref().and_then(|s| self.meta.cards.get(s)).map_or(0, |m| m.token))'''),
    ('scripts.rs',
     '''            } else { &self.meta.cards[name] };''',
     '''            } else { let Some(m) = self.meta.cards.get(name) else { continue; }; m };'''),
    ('scripts.rs',
     '''            let m = &self.meta.cards[name];''',
     '''            let Some(m) = self.meta.cards.get(name) else { continue; };''', 2),
    ('scripts.rs',
     '''                    let sp = b.config.cards[name].spell.as_ref().unwrap();''',
     '''                    let Some(sp) = b.config.cards.get(name).and_then(|c| c.spell.as_ref()) else { continue; };'''),
    ('scripts.rs',
     '''.is_none_or(|n| self.meta.cards[n].cost > elixir + 1e-6)''',
     '''.is_none_or(|n| self.meta.cards.get(n).is_none_or(|m| m.cost > elixir + 1e-6))'''),
    ('public_mask_v2.rs',
     '''                let c=&b.config.cards[name];''',
     '''                let Some(c)=b.config.cards.get(name) else { return false; };'''),
    ('leaf.rs',
     '''            e.stats.leaf_elixir_share.expect("C56 leaf metadata is required")
        } else {
            let m = &self.meta.bodies[&e.stats.name];
            m.cost.max(0.0) / m.count.max(1.0)
        };''',
     '''            e.stats.leaf_elixir_share.unwrap_or(0.0)
        } else {
            self.meta.bodies.get(&e.stats.name).map_or(0.0, |m| m.cost.max(0.0) / m.count.max(1.0))
        };'''),
] + [
    (f, '''            let cost = self.meta.cards[&card].cost;''',
     '''            let cost = self.meta.cards.get(&card)
                .ok_or_else(|| PyValueError::new_err("submitted card absent from metadata"))?.cost;''')
    for f in ('delay_commands.rs', 'e1_commands.rs', 'wait_screen8.rs')
]

src = Path(sys.argv[1]) / 'src'
for item in E:
    f, old, new = item[:3]
    n = item[3] if len(item) > 3 else 1
    p = src / f
    t = p.read_text()
    assert t.count(old) == n, (f, t.count(old), old[:80])
    p.write_text(t.replace(old, new))
    print('patched', f, n, old.strip().splitlines()[0][:90])
