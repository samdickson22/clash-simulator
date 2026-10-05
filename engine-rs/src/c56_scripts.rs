//! Literal C56 public scoring. Champion abilities remain masked by contract.
use super::*;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(super) struct SpellMeta {
    radius: f64,
    damage: f64,
    crown_damage: f64,
    building_damage: Option<f64>,
    duration: f64,
    projectile_range: f64,
    hits_air: bool,
    ignore_buildings: bool,
}

impl NativeScripts {
    pub(super) fn c56_choice(&self, b: &BattleState, seat: usize, style: &str) -> usize {
        self.c56_ranked(b, seat, style, false)[0].0
    }
    pub(super) fn c56_ranked(
        &self, b: &BattleState, seat: usize, style: &str, all_plays: bool,
    ) -> Vec<(usize, f64)> {
        if b.game_over {
            return vec![(2304, 0.0)];
        }
        let v = self.view(b, seat);
        let mask = self.mask(b, seat, &v);
        let incoming: Vec<_> = v
            .bodies
            .iter()
            .filter(|e| e.enemy && !e.crown && e.y < 17.0)
            .collect();
        let reserve = match style {
            "pressure" => 4.0,
            "balanced" => 7.0,
            _ => 9.0,
        };
        let mut best = (
            if incoming.is_empty() && v.elixir < reserve {
                2.8
            } else {
                -0.5
            },
            2304,
        );
        let mut ranked = Vec::new();
        if all_plays {
            ranked.push((best.1, best.0));
        }
        for (slot, name) in b.players[seat].hand.iter().take(4).enumerate() {
            let Some(name) = name else {
                continue;
            };
            let m = &self.meta.cards[name];
            let threat = incoming
                .iter()
                .copied()
                .filter(|e| !e.air || m.can_air)
                .min_by(|a, b| a.y.total_cmp(&b.y));
            let pressure = name == "Miner" || name == "GoblinBarrel";
            let mut crown_target = v
                .bodies
                .iter()
                .filter(|e| e.enemy && e.crown && e.y < 28.0)
                .min_by(|a, b| a.hp.total_cmp(&b.hp));
            if crown_target.is_none() {
                crown_target = v
                    .bodies
                    .iter()
                    .filter(|e| e.enemy && e.crown)
                    .min_by(|a, b| a.hp.total_cmp(&b.hp));
            }
            let mut targets: Vec<_> = v.bodies.iter().collect();
            if name == "Lightning" {
                targets.sort_by(|a, b| b.hp.total_cmp(&a.hp));
            }
            for tile in 0..576 {
                let action = slot * 576 + tile;
                if !mask[action] {
                    continue;
                }
                let (x, y) = ((tile % 18) as f64 + 0.5, (tile / 18) as f64 + 0.5);
                let score = if pressure {
                    crown_target.map_or(-1e6, |t| {
                        let distance = ((x - t.x).powi(2) + (y - t.y).powi(2)).sqrt();
                        6.0 * (-(distance - 1.8).abs()).exp() - 0.3 * m.cost
                    })
                } else if let Some(spell) = &m.c56_spell {
                    let (mut value, mut lethal, mut hits) = (0.0, false, 0);
                    for body in &targets {
                        if !body.enemy
                            || (body.air && !spell.hits_air)
                            || (body.building && spell.ignore_buildings)
                        {
                            continue;
                        }
                        let radius = spell.radius + body.radius;
                        let mut overlap =
                            (x - body.x).powi(2) + (y - body.y).powi(2) < radius * radius;
                        if name == "Log" || name == "BarbLog" {
                            overlap = (x - body.x).abs() < radius
                                && body.y >= y - 3.0
                                && body.y < y - 3.0 + spell.projectile_range;
                        }
                        if name == "Lightning" {
                            overlap = overlap && hits < 3;
                            hits += usize::from(overlap);
                        }
                        if name == "Tornado" {
                            if overlap && !body.crown && body.y < 19.0 {
                                value += body.cost
                                    * (-((x - 9.0).powi(2) + (y - 10.5).powi(2)) / 18.0).exp();
                            }
                            continue;
                        }
                        let horizon = if name == "Poison" || name == "Earthquake" {
                            spell.duration.min(3.0)
                        } else {
                            1.0
                        };
                        let mut damage = spell.damage * horizon;
                        if body.building && !body.crown {
                            damage = spell.building_damage.unwrap_or(damage) * horizon;
                        }
                        if body.crown {
                            lethal |=
                                overlap && body.hp > 0.0 && body.hp <= spell.crown_damage + 1e-3;
                        } else if overlap && body.spell_credit {
                            value += body.cost * damage.min(body.hp) / body.maximum.max(1.0);
                        }
                    }
                    if lethal {
                        100.0 + value
                    } else if value >= 0.6 * m.cost {
                        4.0 + value - m.cost
                    } else {
                        -1e6
                    }
                } else if let Some(t) = threat {
                    let tx = if m.building {
                        if t.x < 9.0 {
                            7.5
                        } else {
                            10.5
                        }
                    } else {
                        t.x
                    };
                    let ty = if m.building {
                        10.5
                    } else {
                        (t.y - m.range.max(1.0)).clamp(3.5, 13.5)
                    };
                    let fit = (-((x - tx).powi(2) + (y - ty).powi(2)) / 8.0).exp();
                    let mut score = 7.0 * fit - 0.28 * m.cost
                        + if m.building && t.only_buildings {
                            2.0 * fit
                        } else {
                            0.0
                        };
                    if m.only_buildings {
                        score -= 3.0;
                    }
                    score
                } else {
                    let mut desired = if m.only_buildings || style == "pressure" {
                        13.5
                    } else {
                        6.5
                    };
                    if name == "Xbow" {
                        desired = 14.5;
                    }
                    if name == "GoblinHut" {
                        desired = 12.5;
                    }
                    if m.building && name != "Xbow" && name != "GoblinHut" {
                        desired = 10.5;
                    }
                    let lane = (x - 3.5).abs().min((x - 14.5).abs());
                    let mut score = 4.2 * (-(y - desired).abs() / 3.0).exp() - lane - 0.32 * m.cost;
                    if m.only_buildings {
                        score += 1.5;
                    }
                    if !incoming.is_empty() && !m.can_air {
                        score -= 4.0;
                    }
                    score
                };
                if all_plays {
                    ranked.push((action, score));
                }
                if score > best.0 || (score == best.0 && action < best.1) {
                    best = (score, action);
                }
            }
        }
        if all_plays {
            ranked.sort_by(|a, b| b.1.total_cmp(&a.1).then(a.0.cmp(&b.0)));
        } else {
            ranked.push((best.1, best.0));
        }
        ranked
    }
}
