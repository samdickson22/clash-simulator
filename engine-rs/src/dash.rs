//! Bandit wind-up, committed dash and damage-only landing immunity.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct Spec {
    minimum: f64,
    maximum: f64,
    windup: f64,
    speed: i64,
    damage: f64,
    tail: i64,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct State {
    pub phase: String,
    timer: f64,
    target: Option<i32>,
    destination: Option<(f64,f64)>,
    pub immunity: i64,
    consumed: bool,
}
impl Entity {
    pub(super) fn clock_projection_ms(&self) -> i64 {
        if self.force_due { 0 }
        else if self.clock.finish != 0 || self.clock.timeline == 0 {
            self.clock.remaining+self.clock.interval-self.clock.load
        } else { self.clock.interval-self.clock.timeline.rem_euclid(self.clock.interval) }
    }
    pub(super) fn consume_clock_reseed(&mut self) {
        let remaining=self.clock_reseed.take();
        if self.stats.ordinary { self.clock_initialized=true; }
        let Some(remaining)=remaining else {return;};
        let finish = self.clock.finish;
        self.clock.stop();self.force_due=remaining==0;
        let first=self.clock.interval-self.clock.load;
        if remaining>0 && remaining<first {
            self.clock.timeline=self.clock.interval-remaining;self.clock.remaining=0;
        } else { self.clock.remaining=self.clock.load.min((remaining-first).max(0)); }
        self.clock.finish=finish;
    }
    pub(super) fn cancel_dash_for_hook(&mut self) {
        if let Some(s)=&mut self.dash {
            s.phase="idle".into();s.timer=0.0;s.target=None;s.destination=None;s.immunity=0;s.consumed=false;
        }
    }
    pub(super) fn dash_active(&self) -> bool {
        self.dash.as_ref().is_some_and(|s| s.phase != "idle" || s.consumed)
    }
    pub(super) fn dash_travel(&self) -> bool {
        self.dash.as_ref().is_some_and(|s| s.phase == "travel")
    }
    pub(super) fn dash_cancel(&mut self) {
        if let Some(s) = &mut self.dash {
            if s.phase == "charging" {
                s.phase = "idle".into(); s.timer = 0.0;
                s.target = None; s.consumed = true;
            }
        }
    }
}
impl BattleState {
    fn dash_band(&self, i: usize, j: usize, spec: &Spec) -> bool {
        let a = &self.entities[i]; let b = &self.entities[j];
        let (dx,dy) = (units(a.x-b.x),units(a.y-b.y));
        let square = (dx*dx+dy*dy - b.stats.distance_discount.round_ties_even() as i64).max(0);
        let inner = units(spec.minimum)+units(a.stats.radius)+units(b.stats.radius);
        let outer = units(spec.maximum)+units(b.stats.radius);
        square >= inner*inner && square <= outer*outer
    }
    pub(super) fn dash_combat(&mut self, i: usize, grid: &[Vec<usize>]) -> bool {
        let Some(spec) = self.entities[i].stats.dash.clone() else { return false; };
        let Some(mut state) = self.entities[i].dash.take() else { return false; };
        let mut active = false;
        if state.consumed {
            state.consumed = false; active = true;
        } else if state.phase == "travel" {
            active = true;
        } else if state.phase == "charging" {
            let target = self.target(i,grid).and_then(|id| self.index(id));
            if let Some(j) = target { self.entities[i].target = Some(self.entities[j].id); }
            if let Some(j) = target.filter(|&j| self.dash_band(i,j,&spec)) {
                state.target = Some(self.entities[j].id);
                self.entities[i].target = state.target;
                state.timer += self.entities[i].attack_work() as f64;
                if state.timer+1e-9 >= spec.windup {
                    let a = &self.entities[i]; let b = &self.entities[j];
                    let (dx,dy) = (units(b.x)-units(a.x),units(b.y)-units(a.y));
                    let distance = isqrt(dx*dx+dy*dy);
                    let length = (distance-units(a.stats.range+b.stats.radius)).max(0);
                    let (mx,my) = norm(dx,dy,length);
                    state.destination = Some(((units(a.x)+mx) as f64/1000.0,(units(a.y)+my) as f64/1000.0));
                    let duration = (isqrt(mx*mx+my*my) as f64 / spec.speed.max(1) as f64 * 50.0).max(1.0);
                    state.immunity = (self.tick as f64 * 50.0+duration) as i64;
                    state.timer = 0.0; state.phase = "travel".into();
                }
            } else {
                state.phase = "idle".into(); state.timer = 0.0;
                state.target = None;
            }
            active = true;
        } else if self.entities[i].stun <= 0.0 {
            if let Some(j) = self.entities[i].target.and_then(|id| self.index(id))
                .filter(|&j| self.entities[j].alive && self.dash_band(i,j,&spec)) {
                state.phase = "charging".into(); state.timer = 0.0;
                state.target = Some(self.entities[j].id); active = true;
            }
        }
        self.entities[i].dash = Some(state);
        active
    }
    pub(super) fn dash_movement(&mut self, i: usize, external: (i64,i64)) -> bool {
        let Some(spec) = self.entities[i].stats.dash.clone() else { return false; };
        let Some(mut state) = self.entities[i].dash.take() else { return false; };
        if state.phase == "idle" && !state.consumed {
            self.entities[i].dash = Some(state); return false;
        }
        self.entities[i].moving = false;
        if state.phase == "travel" {
            if let Some((x,y)) = state.destination {
                let e = &mut self.entities[i];
                let (dx,dy) = (units(x-e.x),units(y-e.y));
                let distance = isqrt(dx*dx+dy*dy);
                let (mx,my) = if distance <= spec.speed {(dx,dy)} else {norm(dx,dy,spec.speed)};
                e.x = (units(e.x)+mx) as f64/1000.0; e.y = (units(e.y)+my) as f64/1000.0;
                state.timer += 50.0;
                if distance <= spec.speed {
                    if let Some(j) = state.target.and_then(|id| self.index(id)).filter(|&j| self.entities[j].alive) {
                        self.entities[i].dash = Some(state.clone());
                        self.damage(j,spec.damage);
                        self.character_hit_buff(i,j);
                        let e = &mut self.entities[i];
                        if e.stats.ordinary && e.clock_projection_ms()!=e.stats.interval {
                            e.clock_reseed=Some(e.stats.interval);
                        }
                        e.cooldown = e.stats.interval as f64/1000.0;
                    }
                    state.phase = "idle".into(); state.timer = 0.0;
                    state.destination = None; state.target = None;
                    state.immunity = self.tick*50+spec.tail;
                }
            } else { state.phase = "idle".into(); }
        }
        state.consumed = false;
        self.entities[i].dash = Some(state);
        self.apply_external(i,external);
        true
    }
}
