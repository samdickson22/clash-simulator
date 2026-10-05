//! Exact defense-v2 potential, including CPython 3.12 float-sum ordering.
use super::*;

pub(crate) fn py_sum(values: impl Iterator<Item = f64>) -> f64 {
    let (mut hi, mut lo) = (0.0_f64, 0.0_f64);
    for x in values {
        let t = hi + x;
        lo += if hi.abs() >= x.abs() {
            (hi - t) + x
        } else {
            (x - t) + hi
        };
        hi = t;
    }
    if lo != 0.0 && lo.is_finite() {
        hi + lo
    } else {
        hi
    }
}
fn crown(e: &Entity) -> bool {
    e.class == "Building" && (e.king || e.stats.name == "Tower")
}
fn body(e: &Entity) -> bool {
    e.alive && !crown(e) && (e.class == "Troop" || e.class == "Building")
}

impl scripts::NativeScripts {
    fn remaining_value(&self, e: &Entity) -> f64 {
        let max_hp = e.stats.max_hp.max(1.0);
        let fraction = (e.hp / max_hp).clamp(0.0, 1.0);
        let mut share = if self.meta.c56 {
            e.stats.leaf_elixir_share.expect("C56 leaf metadata is required")
        } else {
            let m = &self.meta.bodies[&e.stats.name];
            m.cost.max(0.0) / m.count.max(1.0)
        };
        let dps = e.stats.damage.max(0.0) / ((e.stats.interval as f64) / 1000.0).max(0.25);
        let intrinsic = 0.25
            + 0.80 * (max_hp / 1000.0).sqrt().clamp(0.25, 2.0)
            + 0.35 * (dps / 180.0).clamp(0.0, 2.0);
        if share <= 0.0 {
            share = intrinsic;
        }
        (0.75 * share + 0.25 * intrinsic) * fraction
    }
    pub(crate) fn leaf_parts(&self, b: &BattleState) -> Vec<f64> {
        let towers: [Vec<&Entity>; 2] = [0, 1].map(|owner| {
            b.entities
                .iter()
                .filter(|e| e.alive && e.owner == owner && crown(e) && e.hp > 0.0)
                .collect()
        });
        let mut hp = [[0.0; 3]; 2];
        let mut active = [false; 2];
        for owner in 0..2 {
            for e in &towers[owner] {
                hp[owner][if e.king {
                    2
                } else if e.x < 9.0 {
                    0
                } else {
                    1
                }] = e.hp;
                if e.king {
                    active[owner] = e.active;
                }
            }
        }
        let max_princess = self.meta.bodies["Tower"].hp;
        let max_king = self.meta.bodies["KingTower"].hp;
        let princess = [0, 1].map(|o| {
            ((hp[o][0] / max_princess).clamp(0.0, 1.0) + (hp[o][1] / max_princess).clamp(0.0, 1.0))
                / 2.0
        });
        let king = [0, 1].map(|o| (hp[o][2] / max_king).clamp(0.0, 1.0));
        let alive = [0, 1].map(|o| (hp[o][0] > 0.0) as i32 + (hp[o][1] > 0.0) as i32);
        let weight = [0, 1].map(|o| {
            if alive[o] == 2 {
                if active[o] {
                    0.05
                } else {
                    0.0
                }
            } else if alive[o] == 1 {
                0.25
            } else {
                0.60
            }
        });
        let crowns = (alive[0] - alive[1]) as f64 / 3.0;
        let princess_pressure = (1.0 - princess[1]) - (1.0 - princess[0]);
        let king_pressure = weight[1] * (1.0 - king[1]) - weight[0] * (1.0 - king[0]);
        let min_hp = [0, 1].map(|o| {
            hp[o]
                .iter()
                .copied()
                .filter(|&x| x > 0.0)
                .reduce(f64::min)
                .unwrap_or(0.0)
        });
        let tiebreak = (units(min_hp[0]) - units(min_hp[1])) as f64
            / (max_princess.max(max_king).max(1.0) * 1000.0);
        let early = (if alive[1] == 2 { 1.0 - king[1] } else { 0.0 })
            - (if alive[0] == 2 { 1.0 - king[0] } else { 0.0 });
        let values = [0, 1].map(|owner| {
            py_sum(
                b.entities
                    .iter()
                    .filter(|e| body(e) && e.owner == owner)
                    .map(|e| self.remaining_value(e)),
            )
        });
        let board = ((values[0] - values[1]) / 16.0).clamp(-1.0, 1.0);
        let danger = [0, 1].map(|owner| {
            py_sum(
                b.entities
                    .iter()
                    .filter(|e| body(e) && e.owner != owner as i32)
                    .map(|e| {
                        let Some(tower) = towers[owner]
                            .iter()
                            .min_by(|x, y| distance(e, x).total_cmp(&distance(e, y)))
                        else {
                            return 0.0;
                        };
                        let reach = (distance(e, tower) - e.stats.range.max(0.0)).max(0.0);
                        let eta = if e.class == "Troop" {
                            let base = e.public_speed_base.unwrap_or(if e.charge >= 10000 {
                                e.stats.charge_speed as f64
                            } else {
                                e.stats.speed as f64
                            });
                            let mut factor: f64 = if e.slow_ms > 0 { 0.7 } else { 1.0 };
                            if self.meta.c56 {
                                factor = factor.min(e.move_mode.max(0.0));
                                for slow in &e.area_slows { factor = factor.min(slow.1); }
                            }
                            let speed = (base * factor * e.haste_percent(1) as f64 / 100.0).max(0.0)
                                / 1000.0
                                / 0.05;
                            if speed <= 1e-9 && reach > 0.0 {
                                return 0.0;
                            }
                            reach / speed.max(1e-9)
                        } else {
                            if reach > 0.0 {
                                return 0.0;
                            }
                            0.0
                        };
                        let proximity = (-eta.min(30.0) / 4.0).exp();
                        let vulnerability = 0.60
                            + 0.40
                                * (1.0 - (tower.hp / tower.stats.max_hp.max(1.0)).clamp(0.0, 1.0));
                        self.remaining_value(e) * proximity * vulnerability
                    }),
            )
        });
        vec![
            crowns,
            princess_pressure,
            king_pressure,
            tiebreak,
            early,
            board,
            ((danger[1] - danger[0]) / 8.0).clamp(-1.0, 1.0),
        ]
    }
    pub(crate) fn phi(&self, b: &BattleState, seat: usize, elixir_weight: f64) -> f64 {
        if b.game_over {
            return match b.winner {
                None => 0.0,
                Some(w) if w == seat as i32 => 2.0,
                _ => -2.0,
            };
        }
        let p = self.leaf_parts(b);
        let objective = 0.55 * p[0] + 0.25 * p[1] + 0.10 * p[2] + 0.10 * p[3] - 0.20 * p[4];
        let potential = (objective + 0.08 * p[5] + 0.12 * p[6]).clamp(-1.5, 1.5);
        let phi =
            potential + elixir_weight * 0.08 * (b.players[0].elixir - b.players[1].elixir) / 16.0;
        if seat == 0 {
            phi
        } else {
            -phi
        }
    }
}
