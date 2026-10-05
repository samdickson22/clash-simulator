//! P16 public-script inputs. Float32 boundaries are part of the Python contract.
use super::*;
#[path = "c56_scripts.rs"]
mod c56;

#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct CardMeta {
    #[serde(default)]
    air: bool,
    #[serde(default)]
    can_air: bool,
    #[serde(default)]
    unrestricted: bool,
    #[serde(default)]
    c56_spell: Option<c56::SpellMeta>,
    #[serde(default)]
    efficiency: f64,
    #[serde(default)]
    tower_pressure: f64,
    token: i64,
    radius: f64,
    blocker_radius: f64,
    pub(crate) cost: f64,
    pub(crate) count: f64,
    pub(crate) hp: f64,
    damage: f64,
    range: f64,
    shield: bool,
    building: bool,
    spell: bool,
    margin: i32,
    only_buildings: bool,
}
#[derive(Clone, Debug, Deserialize, Serialize)]
pub(crate) struct Metadata {
    #[serde(default)]
    pub(crate) c56: bool,
    cards: BTreeMap<String, CardMeta>,
    pub(crate) bodies: BTreeMap<String, CardMeta>,
}
#[pyclass(module = "clasher_core")]
#[derive(Clone)]
pub struct NativeScripts {
    pub(crate) meta: Metadata,
}

#[derive(Clone, Debug, Serialize)]
struct Body {
    #[serde(skip)]
    air: bool,
    token: i64,
    x: f64,
    y: f64,
    enemy: bool,
    building: bool,
    hp: f64,
    maximum: f64,
    radius: f64,
    blocker_radius: f64,
    cost: f64,
    only_buildings: bool,
    crown: bool,
    spell_credit: bool,
}
#[derive(Serialize)]
struct View {
    bodies: Vec<Body>,
    hand: Vec<i64>,
    elixir: f64,
    towers: Vec<f64>,
}
fn f32clip(x: f64) -> f64 {
    x.clamp(0.0, 1.0) as f32 as f64
}
fn crown(e: &Entity) -> bool {
    e.class == "Building" && (e.king || e.stats.name == "Tower")
}
fn occupied(
    x: f64,
    y: f64,
    radius: f64,
    half: Option<f64>,
    bodies: &[Body],
    crowns: bool,
    v5: bool,
) -> bool {
    bodies
        .iter()
        .filter(|b| b.building && (!crowns || b.crown))
        .any(|b| {
            let r = b.blocker_radius;
            let diameter = r.max(0.0) * 2.0;
            let diameter = if v5 {
                (diameter * 10000.0).round_ties_even() / 10000.0
            } else {
                diameter
            };
            let bh = (diameter.ceil() + 1.0).max(1.0) / 2.0 + 0.5;
            let bx = if v5 {
                (b.x * 1000.0).round_ties_even() / 1000.0
            } else {
                b.x
            };
            let by = if v5 {
                (b.y * 1000.0).round_ties_even() / 1000.0
            } else {
                b.y
            };
            let dx = (x - bx).abs();
            let dy = (y - by).abs();
            if let Some(h) = half {
                dx < h + bh && dy < h + bh
            } else {
                dx * dx + dy * dy < (radius + r.max(0.5)).powi(2) || (dx < bh && dy < bh)
            }
        })
}
impl NativeScripts {
    fn anchored_building_occupied(&self, b: &BattleState, seat: usize, name: &str,
        x: f64, y: f64, half: f64, bodies: &[Body]) -> bool {
        let body_half = |body: &Body| {
            let diameter = (body.blocker_radius.max(0.0)*2.0*10000.0).round_ties_even()/10000.0;
            (diameter.ceil()+1.0).max(1.0)/2.0+0.5
        };
        // contract_v5.py:529-550 checks requested crown tiles, then the
        // even footprint's world-space anchor with localization padding removed.
        if bodies.iter().filter(|e| e.crown).any(|e| {
            let h=body_half(e)-0.5+1e-9;
            (x-(e.x*1000.0).round_ties_even()/1000.0).abs()<=h
                && (y-(e.y*1000.0).round_ties_even()/1000.0).abs()<=h
        }) { return true; }
        let (wx,wy)=if seat==1 {(18.0-x,32.0-y)} else {(x,y)};
        let card=&b.config.cards[name];
        let offset=if card.footprint%2==1 {0.5} else {0.0};
        let requested=(wx.floor()+offset,wy.floor()+offset);
        let anchor=if card.anchors.contains(&requested) { requested } else {
            *card.anchors.iter().min_by(|a,c| {
                ((a.0-wx).powi(2)+(a.1-wy).powi(2)).total_cmp(&((c.0-wx).powi(2)+(c.1-wy).powi(2)))
                    .then(c.0.total_cmp(&a.0)).then(c.1.total_cmp(&a.1))
            }).unwrap()
        };
        let (ax,ay)=if seat==1 {(18.0-anchor.0,32.0-anchor.1)} else {anchor};
        bodies.iter().filter(|e| e.building).any(|e| {
            let h=half+body_half(e)-0.5;
            (ax-(e.x*1000.0).round_ties_even()/1000.0).abs()<h
                && (ay-(e.y*1000.0).round_ties_even()/1000.0).abs()<h
        })
    }
    fn view(&self, b: &BattleState, seat: usize) -> View {
        let mut bodies = Vec::new();
        for e in &b.entities {
            if !e.alive || e.spirit || !(e.class == "Troop" || e.class == "Building") {
                continue;
            }
            if self.meta.c56
                && e.owner != seat as i32
                && (e.underground || e.stealth_until > b.tick * 50)
            {
                continue;
            }
            let m = &self.meta.bodies[&e.stats.name];
            let maximum = if self.meta.c56 && !crown(e) && !e.is_clone {
                e.stats.max_hp
            } else {
                m.hp
            };
            let (x, y) = if seat == 0 {
                (e.x, e.y)
            } else {
                (18.0 - e.x, 32.0 - e.y)
            };
            bodies.push(Body {
                air: m.air,
                token: m.token,
                x: f32clip(x / 18.0) * 18.0,
                y: f32clip(y / 32.0) * 32.0,
                enemy: e.owner != seat as i32,
                building: e.class == "Building",
                hp: if e.spirit {
                    0.0
                } else {
                    f32clip(e.hp / e.stats.max_hp.max(1.0)) * maximum
                },
                maximum,
                radius: m.radius,
                blocker_radius: m.blocker_radius,
                cost: m.cost / m.count.max(1.0),
                only_buildings: m.only_buildings,
                crown: crown(e),
                spell_credit: !m.shield,
            });
        }
        bodies.sort_by(|a, b| {
            a.building
                .cmp(&b.building)
                .then(a.enemy.cmp(&b.enemy))
                .then(a.token.cmp(&b.token))
                .then(
                    ((a.y / 32.0 * 1e5).round_ties_even())
                        .total_cmp(&(b.y / 32.0 * 1e5).round_ties_even()),
                )
                .then(
                    ((a.x / 18.0 * 1e5).round_ties_even())
                        .total_cmp(&(b.x / 18.0 * 1e5).round_ties_even()),
                )
        });
        let mut towers = Vec::new();
        for owner in [seat, 1 - seat] {
            for slot in 0..3 {
                let e = b.entities.iter().find(|e| {
                    e.alive
                        && e.owner == owner as i32
                        && crown(e)
                        && if slot == 2 {
                            e.king
                        } else {
                            !e.king && ((e.x < 9.0) != (seat == 1)) == (slot == 0)
                        }
                });
                towers.push(e.map_or(0.0, |e| f32clip(e.hp / e.stats.max_hp.max(1.0))));
            }
        }
        View {
            bodies,
            towers,
            hand: b.players[seat]
                .hand
                .iter()
                .take(4)
                .map(|s| s.as_ref().map_or(0, |s| self.meta.cards[s].token))
                .collect(),
            elixir: f32clip(b.players[seat].elixir / 10.0) * 10.0,
        }
    }
    fn mask(&self, b: &BattleState, seat: usize, v: &View) -> Vec<bool> {
        let mut out = vec![false; 2306];
        out[2304] = true;
        if b.game_over {
            return out;
        }
        let zone: Vec<bool> = (0..576)
            .map(|i| {
                let x = (i % 18) as f64 + 0.5;
                let y = (i / 18) as f64 + 0.5;
                let in_zone = (y >= 1.0 && y < 15.0)
                    || (x >= 6.0 && x < 12.0 && y < 6.0)
                    || (v.towers[3] <= 1e-4
                        && ((x < 9.0 && y >= 17.0 && y < 21.0)
                            || (x >= 2.0 && x < 5.0 && y >= 15.0 && y < 17.0)))
                    || (v.towers[4] <= 1e-4
                        && ((x >= 9.0 && y >= 17.0 && y < 21.0)
                            || (x >= 13.0 && x < 16.0 && y >= 15.0 && y < 17.0)));
                let wx = if seat == 1 { 18.0 - x } else { x };
                in_zone
                    && (!(15.0..17.0).contains(&y)
                        || (2.5..4.5).contains(&wx)
                        || (13.5..15.5).contains(&wx))
            })
            .collect();
        for (slot, name) in b.players[seat].hand.iter().take(4).enumerate() {
            let Some(name) = name else {
                continue;
            };
            let m = &self.meta.cards[name];
            if m.cost > v.elixir + 1e-6 {
                continue;
            }
            let unrestricted = if self.meta.c56 {
                m.unrestricted
            } else {
                m.spell && name != "Log"
            };
            let half = if m.building {
                let diameter = m.radius.max(0.0) * 2.0;
                let diameter = if self.meta.c56 {
                    (diameter * 10000.0).round_ties_even() / 10000.0
                } else {
                    diameter
                };
                Some((diameter.ceil() + 1.0).max(1.0) / 2.0)
            } else {
                None
            };
            for i in 0..576 {
                if b.config.blocked_tiles[i] || (!unrestricted && !zone[i]) {
                    continue;
                }
                let x = (i % 18) as f64 + 0.5;
                let y = (i / 18) as f64 + 0.5;
                if x < m.margin as f64 || x >= 18.0 - m.margin as f64 {
                    continue;
                }
                let blocked=if self.meta.c56 && m.building && m.unrestricted {
                    self.anchored_building_occupied(b,seat,name,x,y,half.unwrap(),&v.bodies)
                } else { occupied(x,y,m.radius,half,&v.bodies,false,self.meta.c56) };
                if !m.spell && blocked {
                    if m.building
                        || (self.meta.c56 && m.air)
                        || occupied(x, y, m.radius, None, &v.bodies, true, self.meta.c56)
                    {
                        continue;
                    }
                    // The Python ring search only exposes whether any candidate exists.
                    // Every deployment-zone tile is within 30 rings of any other zone tile.
                    if !(0..576).any(|j| {
                        (zone[j] || (self.meta.c56 && unrestricted))
                            && !b.config.blocked_tiles[j]
                            && b.config.walkable[j]
                            && !occupied(
                                (j % 18) as f64 + 0.5,
                                (j / 18) as f64 + 0.5,
                                m.radius,
                                None,
                                &v.bodies,
                                false,
                                self.meta.c56,
                            )
                    }) {
                        continue;
                    }
                }
                out[slot * 576 + i] = true;
            }
        }
        out
    }
}
impl NativeScripts {
    fn public_choice(&self, b: &BattleState, seat: usize, style: &str) -> usize {
        if b.game_over {
            return 2304;
        }
        let v = self.view(b, seat);
        let mask = self.mask(b, seat, &v);
        let threat = v
            .bodies
            .iter()
            .filter(|e| e.enemy && !e.crown && e.y < 17.0)
            .min_by(|a, b| a.y.total_cmp(&b.y));
        let reserve = match style {
            "pressure" => 4.0,
            "defense" => 9.0,
            _ => 7.0,
        };
        let mut best = (
            if threat.is_none() && v.elixir < reserve {
                2.8
            } else {
                -0.5
            },
            2304,
        );
        for (slot, name) in b.players[seat].hand.iter().take(4).enumerate() {
            let Some(name) = name else {
                continue;
            };
            let m = &self.meta.cards[name];
            for i in 0..576 {
                let action = slot * 576 + i;
                if !mask[action] {
                    continue;
                }
                let x = (i % 18) as f64 + 0.5;
                let y = (i / 18) as f64 + 0.5;
                let score = if m.spell {
                    let sp = b.config.cards[name].spell.as_ref().unwrap();
                    let mut value = 0.0;
                    let mut lethal = false;
                    for e in v.bodies.iter().filter(|e| e.enemy) {
                        let overlap = if name == "Log" {
                            (x - e.x).abs() < sp.radius + e.radius
                                && e.y >= y - 3.0
                                && e.y < y - 3.0 + sp.projectile_range
                        } else {
                            (x - e.x).powi(2) + (y - e.y).powi(2) < (sp.radius + e.radius).powi(2)
                        };
                        if e.crown {
                            lethal |= overlap
                                && e.hp > 0.0
                                && e.hp <= sp.crown_tower_damage.unwrap() + 1e-3;
                        } else if e.spell_credit {
                            value += (overlap as u8 as f64) * e.cost * sp.damage.min(e.hp)
                                / e.maximum.max(1.0);
                        }
                    }
                    if lethal {
                        100.0 + value
                    } else if value >= 0.8 * m.cost {
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
                    let efficiency = ((m.hp / 700.0).sqrt() + m.damage / 300.0) / m.cost.max(1.0);
                    let mut score = 6.0 * fit + efficiency - 0.28 * m.cost;
                    if m.building && t.only_buildings {
                        score += 2.0 * fit;
                    }
                    if m.only_buildings {
                        score -= 3.0;
                    }
                    score
                } else {
                    let lane = (x - 3.5).abs().min((x - 14.5).abs());
                    let desired = if m.only_buildings || style == "pressure" {
                        13.5
                    } else {
                        6.5
                    };
                    let mut score = 4.2 * (-(y - desired).abs() / 3.0).exp() - lane - 0.32 * m.cost;
                    if m.only_buildings {
                        score += 1.5;
                    }
                    if m.building {
                        score -= 3.0;
                    }
                    score
                };
                if score > best.0 || (score == best.0 && action < best.1) {
                    best = (score, action);
                }
            }
        }
        best.1
    }
    fn balanced_choice(&self, b: &BattleState, seat: usize) -> usize {
        let v = self.view(b, seat);
        let mask = self.mask(b, seat, &v);
        let mut incoming = Vec::new();
        let mut enemies = Vec::new();
        for e in b.entities.iter().filter(|e| {
            e.alive
                && e.owner != seat as i32
                && !crown(e)
                && (e.class == "Troop" || e.class == "Building")
        }) {
            let hp = e.stats.max_hp.max(1.0);
            let dps = e.stats.damage.max(0.0) * 1000.0 / (e.stats.interval as f64).max(250.0);
            let strength = (0.6 + e.hp.max(0.0) / hp) * (0.5 + (hp / 900.0).sqrt() + dps / 180.0);
            let (x, y) = if seat == 0 {
                (e.x, e.y)
            } else {
                (18.0 - e.x, 32.0 - e.y)
            };
            enemies.push((x, y, strength));
            if y < 16.5 {
                incoming.push((x, y, strength * (-(y - 5.5).max(0.0) / 6.0).exp()));
            }
        }
        let total: f64 = incoming.iter().map(|v| v.2).sum();
        let (ix, iy) = if incoming.is_empty() {
            (9.0, 10.0)
        } else {
            (
                incoming.iter().map(|v| v.0 * v.2).sum::<f64>() / total.max(1e-9),
                incoming.iter().map(|v| v.1 * v.2).sum::<f64>() / total.max(1e-9),
            )
        };
        let weight = enemies.iter().map(|v| v.2).sum::<f64>().max(1e-9);
        let (cx, cy) = if enemies.is_empty() {
            (9.0, 23.5)
        } else {
            (
                enemies.iter().map(|v| v.0 * v.2).sum::<f64>() / weight,
                enemies.iter().map(|v| v.1 * v.2).sum::<f64>() / weight,
            )
        };
        let threat = (total / 1.5).min(1.0);
        let mut best = (
            if total <= 0.08 && b.players[seat].elixir < 7.0 {
                2.8
            } else {
                -0.5
            },
            2304,
        );
        for (slot, name) in b.players[seat].hand.iter().take(4).enumerate() {
            let Some(name) = name else {
                continue;
            };
            let m = &self.meta.cards[name];
            for i in 0..576 {
                let action = slot * 576 + i;
                if !mask[action] {
                    continue;
                }
                let x = (i % 18) as f64 + 0.5;
                let y = (i / 18) as f64 + 0.5;
                let defense_fit = (-((x - ix).powi(2) + (y - (iy + 1.5).min(14.0)).powi(2))
                    / (2.0 * 3.5 * 3.5))
                    .exp();
                let cluster_fit =
                    (-((x - cx).powi(2) + (y - cy).powi(2)) / (2.0 * 3.0 * 3.0)).exp();
                let defense = 5.0 * defense_fit + if m.building { 1.2 } else { 0.0 };
                let offense = 3.5 * (-(y - 13.0).abs() / 3.5).exp()
                    + 0.5 * m.efficiency
                    + 2.0 * m.tower_pressure;
                let score = threat * defense
                    + (1.0 - threat) * offense
                    + if m.spell { 2.5 * cluster_fit } else { 0.0 }
                    - 0.32 * m.cost;
                if score > best.0 || (score == best.0 && action < best.1) {
                    best = (score, action);
                }
            }
        }
        best.1
    }
}

#[pymethods]
impl NativeScripts {
    #[new]
    fn new(metadata: &str) -> PyResult<Self> {
        Ok(Self {
            meta: serde_json::from_str(metadata)
                .map_err(|e| PyValueError::new_err(e.to_string()))?,
        })
    }
    /// All public-legal C56 heuristic placements, including the wait action.
    fn ranked_actions(&self, battle: &BattleState, seat: usize, style: &str) -> PyResult<Vec<(usize, f64)>> {
        if !self.meta.c56 || seat > 1 || !matches!(style, "balanced" | "pressure" | "defense") {
            return Err(PyValueError::new_err("ranked actions require C56 metadata and a valid seat/style"));
        }
        Ok(self.c56_ranked(battle, seat, style, true))
    }
    fn evaluate(&self, battle: &BattleState, seat: usize, elixir_weight: f64) -> PyResult<f64> {
        if seat > 1 {
            return Err(PyValueError::new_err("invalid seat"));
        }
        Ok(self.phi(battle, seat, elixir_weight))
    }
    fn evaluation_parts(&self, battle: &BattleState) -> Vec<f64> {
        self.leaf_parts(battle)
    }
    #[pyo3(signature=(battle, seat, action, other_action, style, opponent, horizon, interval, elixir_weight, trace=false, full_rng=false))]
    fn rollout(
        &self,
        battle: &BattleState,
        seat: usize,
        action: usize,
        other_action: usize,
        style: &str,
        opponent: &str,
        horizon: usize,
        interval: usize,
        elixir_weight: f64,
        trace: bool,
        full_rng: bool,
    ) -> PyResult<(
        f64,
        usize,
        usize,
        usize,
        Vec<(i64, usize, usize, String)>,
        String,
    )> {
        Ok(self.rollout_until(battle, seat, action, other_action, style, opponent,
            horizon, interval, elixir_weight, trace, full_rng, None)?.unwrap())
    }
    /// Priority-ordered work queue; reduction always follows candidate index.
    /// Only candidates with all three rollouts completed before the cutoff count.
    #[pyo3(signature=(battle, seat, candidates, horizon, interval, elixir_weight, threads=2, remaining_seconds=None, trace=false))]
    fn search_candidates(&self, py: Python<'_>, battle: &BattleState, seat: usize,
        candidates: Vec<usize>, horizon: usize, interval: usize, elixir_weight: f64,
        threads: usize, remaining_seconds: Option<f64>, trace: bool,
    ) -> PyResult<Vec<Option<Vec<RolloutResult>>>> {
        if seat > 1 || interval == 0 || threads == 0 || threads > 64
            || candidates.is_empty() || candidates.iter().any(|&a| a > 2305)
            || remaining_seconds.is_some_and(|s| !s.is_finite() || s < 0.0) {
            return Err(PyValueError::new_err("invalid candidate search configuration"));
        }
        let deadline = remaining_seconds.map(|s| {
            Instant::now().checked_add(Duration::from_secs_f64(s.min(1e9))).unwrap()
        });
        py.allow_threads(|| {
            let mut root = battle.clone();
            let styles = ["balanced", "pressure", "defense"];
            let mut others = [2304; 3];
            for (i, style) in styles.iter().enumerate() {
                if expired(deadline) { return Ok(vec![None; candidates.len()]); }
                others[i] = self.select_action(&mut root, 1 - seat, style)?;
            }
            let next = AtomicUsize::new(0);
            std::thread::scope(|scope| {
                let mut handles = Vec::new();
                for _ in 0..threads.min(candidates.len()) {
                    let root = &root;
                    let next = &next;
                    let candidates = &candidates;
                    handles.push(scope.spawn(move || -> PyResult<Vec<(usize, Option<Vec<RolloutResult>>)>> {
                        let mut rows = Vec::new();
                        loop {
                            if expired(deadline) { break; }
                            let i = next.fetch_add(1, Ordering::Relaxed);
                            if i >= candidates.len() { break; }
                            let mut results = Vec::new();
                            for j in 0..3 {
                                match self.rollout_until(root, seat, candidates[i], others[j],
                                    "balanced", styles[j], horizon, interval, elixir_weight,
                                    trace, trace, deadline)? {
                                    Some(result) => results.push(result),
                                    None => break,
                                }
                            }
                            let complete = results.len() == 3 && !expired(deadline);
                            rows.push((i, if complete { Some(results) } else { None }));
                        }
                        Ok(rows)
                    }));
                }
                let mut ordered = vec![None; candidates.len()];
                // Join every worker, including on error, before returning to Python.
                for handle in handles {
                    let rows = handle.join().map_err(|_| PyValueError::new_err("candidate worker panicked"))??;
                    for (i, result) in rows { ordered[i] = result; }
                }
                Ok(ordered)
            })
        })
    }
    fn select_action(&self, battle: &mut BattleState, seat: usize, style: &str) -> PyResult<usize> {
        if seat > 1 {
            return Err(PyValueError::new_err("invalid seat"));
        }
        if self.meta.c56 {
            // Python's public champion HUD lookup refreshes ownership even
            // when its controller masks the ability action.
            battle.champion_can_activate(seat);
        }
        match style {
            "balanced" | "pressure" | "defense" => Ok(if self.meta.c56 {
                self.c56_choice(battle, seat, style)
            } else {
                self.public_choice(battle, seat, style)
            }),
            "sb-balanced" if !self.meta.c56 => Ok(self.balanced_choice(battle, seat)),
            _ => Err(PyValueError::new_err("unsupported script style")),
        }
    }
    fn apply_discrete(
        &self,
        battle: &mut BattleState,
        seat: usize,
        action: usize,
    ) -> PyResult<bool> {
        if seat > 1 || action > if self.meta.c56 { 2305 } else { 2304 } {
            return Err(PyValueError::new_err("invalid action/seat"));
        }
        if action == 2304 {
            return Ok(false);
        }
        if action == 2305 {
            return Ok(battle.champion_activate(seat));
        }
        let Some(name) = battle.players[seat].hand[action / 576].clone() else {
            return Ok(false);
        };
        let tile = action % 576;
        let (x, y) = ((tile % 18) as f64 + 0.5, (tile / 18) as f64 + 0.5);
        let (x, y) = if seat == 0 {
            (x, y)
        } else {
            (18.0 - x, 32.0 - y)
        };
        battle.apply_action(seat, &name, x, y)
    }
    fn public_view(&self, battle: &mut BattleState, seat: usize) -> PyResult<String> {
        if seat > 1 {
            return Err(PyValueError::new_err("invalid seat"));
        }
        if self.meta.c56 {
            // Python's public champion HUD lookup refreshes ownership even
            // when its controller masks the ability action.
            battle.champion_can_activate(seat);
        }
        Ok(serde_json::to_string(&self.view(battle, seat)).unwrap())
    }
    fn public_mask(&self, battle: &mut BattleState, seat: usize) -> PyResult<Vec<bool>> {
        if seat > 1 {
            return Err(PyValueError::new_err("invalid seat"));
        }
        if self.meta.c56 {
            // Python's public champion HUD lookup refreshes ownership even
            // when its controller masks the ability action.
            battle.champion_can_activate(seat);
        }
        Ok(self.mask(battle, seat, &self.view(battle, seat)))
    }
}

use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::{Duration, Instant};

type RolloutResult = (f64, usize, usize, usize, Vec<(i64, usize, usize, String)>, String);

fn expired(deadline: Option<Instant>) -> bool {
    deadline.is_some_and(|end| Instant::now() >= end)
}

impl NativeScripts {
    #[allow(clippy::too_many_arguments)]
    fn rollout_until(&self, battle: &BattleState, seat: usize, action: usize,
        other_action: usize, style: &str, opponent: &str, horizon: usize,
        interval: usize, elixir_weight: f64, trace: bool, full_rng: bool,
        deadline: Option<Instant>) -> PyResult<Option<RolloutResult>> {
        if seat > 1 || interval == 0 {
            return Err(PyValueError::new_err("invalid rollout seat/interval"));
        }
        if expired(deadline) { return Ok(None); }
        let mut sim = battle.clone();
        let digest = |b: &BattleState| {
            let mut value = b.hex_digest();
            if full_rng {
                let mut hash = Sha256::new();
                for word in &b.rng.state { hash.update(word.to_le_bytes()); }
                hash.update((b.rng.index as u32).to_le_bytes());
                value.push_str(&format!(":{:x}", hash.finalize()));
            }
            value
        };
        self.apply_discrete(&mut sim, seat, action)?;
        self.apply_discrete(&mut sim, 1 - seat, other_action)?;
        let (mut ticks, mut calls, mut skips) = (0, 0, 0);
        let mut events = Vec::new();
        while ticks < horizon && !sim.game_over {
            for _ in 0..interval {
                if sim.game_over {
                    break;
                }
                if expired(deadline) { return Ok(None); }
                sim.tick_once(false);
                ticks += 1;
            }
            if ticks < horizon && !sim.game_over {
                for actor in [seat, 1 - seat] {
                    if expired(deadline) { return Ok(None); }
                    calls += 1;
                    let controller = if actor == seat || opponent.is_empty() {
                        style
                    } else {
                        opponent
                    };
                    let elixir = f32clip(sim.players[actor].elixir / 10.0) * 10.0;
                    let wait = !self.meta.c56 && controller != "sb-balanced"
                        && sim.players[actor].hand.iter().take(4).all(|n| {
                            n.as_ref()
                                .is_none_or(|n| self.meta.cards[n].cost > elixir + 1e-6)
                        });
                    let move_id = if wait {
                        skips += 1;
                        2304
                    } else {
                        self.select_action(&mut sim, actor, controller)?
                    };
                    if trace {
                        events.push((sim.tick, actor, move_id, digest(&sim)));
                    }
                    if move_id != 2304 {
                        self.apply_discrete(&mut sim, actor, move_id)?;
                    }
                }
            }
        }
        if expired(deadline) { return Ok(None); }
        Ok(Some((
            self.phi(&sim, seat, elixir_weight),
            ticks,
            calls,
            skips,
            events,
            if trace {
                digest(&sim)
            } else {
                String::new()
            },
        )))
    }
}
