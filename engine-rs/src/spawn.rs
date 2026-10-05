//! Native character production and serialized spawn hooks.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    interval: f64,
    first: Option<f64>,
    intra: f64,
    count: usize,
    angle: i64,
    maximum: i64,
    radius: f64,
    gated: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    elapsed: f64,
    waves: i64,
    pending: usize,
    unit_elapsed: f64,
    wave_spawned: usize,
}

impl BattleState {
    fn spawn_push_hook(&mut self, i: usize) {
        if self.entities[i].spawn_push_done { return; }
        self.entities[i].spawn_push_done = true;
        let Some((distance,radius,air,ground)) = self.entities[i].stats.spawn_push else { return; };
        let a = &self.entities[i]; let center = (a.x,a.y);
        let victims: Vec<usize> = self.entities.iter().enumerate().filter_map(|(j,e)| {
            (e.alive && e.owner!=a.owner && e.class=="Troop" && !e.spirit
                && !e.underground && e.stagger<=1e-9
                && (if e.stats.air { air } else { ground })
                && Self::in_area(e,a.x,a.y,radius)).then_some(j)
        }).collect();
        for j in victims { self.radial_knockback(j,center,distance,true,false,None); }
    }
    pub(super) fn spawn_hook(&mut self, i: usize) {
        self.leap_spawn(i);
        self.spawn_push_hook(i);
        if self.entities[i].spawn_area_done {
            return;
        }
        self.entities[i].spawn_area_done = true;
        if let Some(template) = self.config.spawn_areas.get(&self.entities[i].stats.name) {
            let parent = &self.entities[i];
            let mut area = template.clone();
            area.id = self.next_id as i32;
            self.next_id += 1;
            area.x = parent.x;
            area.y = parent.y;
            area.owner = parent.owner;
            area.birth = self.tick;
            self.entities.push(area);
        }
    }
    fn child_spawn_valid(&self, x: i64, y: i64, r: i64) -> bool {
        if x - r < 0 || y - r < 0 || x + r >= 18000 || y + r >= 32000 {
            return false;
        }
        for tx in (x - r) / 500..=(x + r - 1) / 500 {
            for ty in (y - r) / 500..=(y + r - 1) / 500 {
                if self.config.water[(ty * 36 + tx) as usize] {
                    return false;
                }
            }
        }
        true
    }
    pub(super) fn child_position_without_radius(
        &self, parent: &Entity, child: &Entity, direct: bool,
    ) -> (i64, i64) {
        let (px, py) = (units(parent.x), units(parent.y));
        let d = if direct { 0 } else { units(parent.stats.radius + child.stats.radius) };
        for (mut dx, mut dy) in [(0, d), (-d, 0), (0, -d), (d, 0)] {
            if parent.x > 9.0 { dx = -dx; }
            if parent.owner == 1 { dy = -dy; }
            if self.child_spawn_valid(px + dx, py + dy, units(child.stats.radius)) {
                return (px + dx, py + dy);
            }
        }
        (px + 1, py)
    }
    fn production_child(&mut self, i: usize, index: usize, count: usize, spec: &Spec) {
        let parent = &self.entities[i];
        let mut child = self.config.production_children[&parent.stats.name].clone();
        let (px, py) = (units(parent.x), units(parent.y));
        let (x, y) = if spec.radius > 0.0 {
            let base = if spec.angle != 0 {
                self.vector_angle(parent.facing.0, parent.facing.1) + spec.angle
            } else {
                0
            };
            let angle = (base + ((count - 1 - index) * 360 / count) as i64).rem_euclid(360);
            let (cos, sin) = self.config.rotations[angle as usize];
            let radius = units(spec.radius);
            (px + cos * radius / 1024, py + sin * radius / 1024)
        } else {
            self.child_position_without_radius(parent, &child, false)
        };
        child.id = self.next_id as i32;
        self.next_id += 1;
        child.x = x.clamp(250, 17750) as f64 / 1000.0;
        child.y = y.clamp(250, 31750) as f64 / 1000.0;
        child.lane = if child.x < 9.0 { 1 } else { 2 };
        child.owner = parent.owner;
        child.facing = (0, if parent.owner == 0 { 1000 } else { -1000 });
        child.birth = self.tick;
        self.entities.push(child);
    }
    pub(super) fn production_tick(&mut self, i: usize) {
        if self.entities[i].stun > 1e-9 {
            return;
        }
        let spec = self.entities[i].stats.spawner.clone().unwrap();
        if spec.gated {
            let a = &self.entities[i];
            let nearby = self.entities.iter().any(|e| {
                e.alive
                    && e.owner != a.owner
                    && (e.class == "Troop" || e.class == "Building")
                    && !e.spirit
                    && !e.underground
                    && !e.hidden
                    && e.death_immunity.is_none()
                    && e.stagger <= 1e-9
                    && e.stealth_until <= self.tick * 50
                    && ((e.x - a.x).powi(2) + (e.y - a.y).powi(2)).sqrt() <= 6.0 + e.stats.radius
            });
            if !nearby {
                let state = self.entities[i].production.as_mut().unwrap();
                state.elapsed = 0.0;
                state.waves = 0;
                return;
            }
        }
        let mut budget = self.entities[i].spawn_work();
        if budget <= 0.0 {
            return;
        }
        let mut state = self.entities[i].production.take().unwrap();
        loop {
            if state.pending > 0 {
                let needed = (spec.intra - state.unit_elapsed).max(0.0);
                if budget < needed {
                    state.unit_elapsed += budget;
                    break;
                }
                budget -= needed;
                state.unit_elapsed = 0.0;
                self.production_child(i, state.wave_spawned, spec.count.max(1), &spec);
                state.wave_spawned += 1;
                state.pending -= 1;
                if state.pending == 0 {
                    state.waves += 1;
                    state.wave_spawned = 0;
                    state.elapsed = 0.0;
                }
                if budget == 0.0 {
                    break;
                }
                continue;
            }
            if spec.maximum != -1 && state.waves >= spec.maximum {
                break;
            }
            let threshold = if state.waves == 0 {
                spec.first.unwrap_or(spec.interval)
            } else {
                spec.interval
            };
            let needed = (threshold - state.elapsed).max(0.0);
            if budget < needed {
                state.elapsed += budget;
                break;
            }
            budget -= needed;
            state.elapsed = 0.0;
            let count = spec.count.max(1);
            if spec.intra > 0.0 && count > 1 {
                self.production_child(i, 0, count, &spec);
                state.wave_spawned = 1;
                state.pending = count - 1;
                state.unit_elapsed = 0.0;
            } else {
                for index in 0..count {
                    self.production_child(i, index, count, &spec);
                }
                state.waves += 1;
            }
            if budget == 0.0 {
                break;
            }
        }
        self.entities[i].production = Some(state);
    }
}
