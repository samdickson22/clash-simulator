//! Serialized simultaneous recipients and per-hit status effects.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Multi {
    count: usize,
    fill_primary: bool,
    pub scale: f64,
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Buff {
    duration: f64,
    axes: (f64, f64, f64),
}

impl BattleState {
    pub(super) fn secondary_recipients(&self, i: usize, primary: usize) -> Vec<usize> {
        let a = &self.entities[i];
        let Some(spec) = &a.stats.multi_attack else { return Vec::new(); };
        if !self.entities[primary].alive { return Vec::new(); }
        let mut candidates: Vec<(usize,f64)> = self.entities.iter().enumerate().filter_map(|(j,e)| {
            (j != primary && e.owner != a.owner && e.alive && !e.hidden && !e.spirit && !e.underground
                && e.death_immunity.is_none() && e.stagger <= 1e-9 && e.stealth_until <= self.tick*50
                && (e.class == "Troop" || e.class == "Building")
                && (!a.stats.only_buildings || e.class == "Building")
                && a.can_hit_plane(e) && reach(a,e,0.0)).then_some((j,distance(a,e)))
        }).collect();
        let count = spec.count.saturating_sub(1);
        let mut selected = Vec::new();
        while !candidates.is_empty() && selected.len() < count {
            let minimum = candidates.iter().map(|(_,d)| *d).fold(f64::INFINITY,f64::min);
            let sign = if a.owner == 0 { 1.0 } else { -1.0 };
            let j = candidates.iter().filter(|(_,d)| *d <= minimum+1e-9).map(|(j,_)| *j).min_by(|&j,&k| {
                let b=&self.entities[j];let c=&self.entities[k];
                (sign*(b.x-9.0)).total_cmp(&(sign*(c.x-9.0)))
                    .then((sign*(b.y-16.0)).total_cmp(&(sign*(c.y-16.0))))
                    .then(b.id.cmp(&c.id))
            }).unwrap();
            selected.push(j);candidates.retain(|(k,_)| *k!=j);
        }
        if spec.fill_primary { selected.resize(count,primary); }
        selected
    }

    /// Batch C1 (cards/ronin.py RoninCounter.try_counter): a ready counter takes the direct hit of
    /// attacker `a` on Ronin `r` instead of its damage.
    pub(super) fn try_counter(&mut self, r: usize, a: usize, amount: f64) -> bool {
        let tick = self.tick;
        let e = &mut self.entities[r];
        if e.stats.counter_cooldown == 0 || !e.alive || tick < e.counter_ready { return false; }
        e.counter_ready = tick + e.stats.counter_cooldown;
        e.clock.stop();
        e.force_due = false;
        let id = self.entities[a].id;
        let e = &mut self.entities[r];
        e.counter_pending.push((tick + e.stats.counter_delay, id, amount * e.stats.counter_scalar as f64 / 100.0));
        let stop = e.stats.counter_stop;
        self.slow_target(a, stop, (0.0, 0.05, 0.0));
        true
    }
    pub(super) fn character_hit_buff(&mut self, i: usize, j: usize) {
        let Some(buff) = self.entities[i].stats.hit_buff.clone() else { return; };
        if buff.axes.0 <= 0.0 && buff.axes.1 <= 0.0 && buff.axes.2 <= 0.0 {
            self.stun_target(j,buff.duration);
        } else { self.slow_target(j,buff.duration,buff.axes); }
    }
}
