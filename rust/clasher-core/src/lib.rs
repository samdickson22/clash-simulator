use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::VecDeque;

const FNV_OFFSET_BASIS: u64 = 0xcbf29ce484222325;
const FNV_PRIME: u64 = 0x100000001b3;

fn fnv1a(payload: &[u8]) -> u64 {
    payload.iter().fold(FNV_OFFSET_BASIS, |hash, byte| {
        (hash ^ u64::from(*byte)).wrapping_mul(FNV_PRIME)
    })
}

#[pyfunction]
fn noop_ticks(ticks: u32) -> u32 {
    ticks
}

#[pyfunction]
fn consume_state_bytes(payload: &[u8]) -> (usize, u64) {
    (payload.len(), fnv1a(payload))
}

fn sha256_hex(payload: &[u8]) -> String {
    format!("{:x}", Sha256::digest(payload))
}

fn validate_checkpoint(payload: &[u8]) -> PyResult<u64> {
    let root: Value = serde_json::from_slice(payload)
        .map_err(|error| PyValueError::new_err(format!("invalid battle checkpoint: {error}")))?;
    let schema_version = root
        .get("schema_version")
        .and_then(Value::as_u64)
        .ok_or_else(|| PyValueError::new_err("battle checkpoint has no integer schema_version"))?;
    if schema_version != 1 {
        return Err(PyValueError::new_err(format!(
            "unsupported battle checkpoint schema {schema_version}; expected 1"
        )));
    }
    Ok(schema_version)
}

type PlayerInit = (
    i64,
    f64,
    f64,
    i64,
    Vec<Option<String>>,
    Vec<String>,
    f64,
    f64,
    f64,
);
type PlayerStateTuple = PlayerInit;
type TowerInit = (i64, i64, String, f64, i64, bool, bool, f64);
type TowerStateTuple = TowerInit;

struct ResidentPlayer {
    player_id: i64,
    elixir: f64,
    max_elixir: f64,
    next_card_refill_cooldown_ms: i64,
    hand: Vec<Option<String>>,
    cycle_queue: VecDeque<String>,
    king_tower_hp: f64,
    left_tower_hp: f64,
    right_tower_hp: f64,
}

impl ResidentPlayer {
    fn from_init(value: PlayerInit) -> PyResult<Self> {
        let (
            player_id,
            elixir,
            max_elixir,
            cooldown_ms,
            hand,
            cycle_queue,
            king_tower_hp,
            left_tower_hp,
            right_tower_hp,
        ) = value;
        if !elixir.is_finite()
            || !max_elixir.is_finite()
            || !king_tower_hp.is_finite()
            || !left_tower_hp.is_finite()
            || !right_tower_hp.is_finite()
        {
            return Err(PyValueError::new_err(
                "player elixir and tower hitpoints must be finite",
            ));
        }
        Ok(Self {
            player_id,
            elixir,
            max_elixir,
            next_card_refill_cooldown_ms: cooldown_ms,
            hand,
            cycle_queue: cycle_queue.into(),
            king_tower_hp,
            left_tower_hp,
            right_tower_hp,
        })
    }

    fn state_tuple(&self) -> PlayerStateTuple {
        (
            self.player_id,
            self.elixir,
            self.max_elixir,
            self.next_card_refill_cooldown_ms,
            self.hand.clone(),
            self.cycle_queue.iter().cloned().collect(),
            self.king_tower_hp,
            self.left_tower_hp,
            self.right_tower_hp,
        )
    }

    fn advance(&mut self, dt: f64, base_regen_time: f64, refill_ms: i64, tick_ms: i64) {
        if self.elixir < self.max_elixir {
            let elixir_per_second = 1.0 / base_regen_time;
            self.elixir = self.max_elixir.min(self.elixir + elixir_per_second * dt);
        }

        if self.next_card_refill_cooldown_ms > 0 {
            self.next_card_refill_cooldown_ms = 0.max(self.next_card_refill_cooldown_ms - tick_ms);
        }
        if self.next_card_refill_cooldown_ms != 0 || self.cycle_queue.is_empty() {
            return;
        }
        let Some(slot) = self.hand.iter().position(Option::is_none) else {
            return;
        };
        self.hand[slot] = self.cycle_queue.pop_front();
        self.next_card_refill_cooldown_ms = refill_ms;
    }

    fn append_hash_payload(&self, payload: &mut Vec<u8>) {
        payload.extend_from_slice(&self.player_id.to_le_bytes());
        payload.extend_from_slice(&self.elixir.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.max_elixir.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.next_card_refill_cooldown_ms.to_le_bytes());
        payload.extend_from_slice(&(self.hand.len() as u64).to_le_bytes());
        for card in &self.hand {
            match card {
                None => payload.push(0),
                Some(name) => {
                    payload.push(1);
                    append_string(payload, name);
                }
            }
        }
        payload.extend_from_slice(&(self.cycle_queue.len() as u64).to_le_bytes());
        for card in &self.cycle_queue {
            append_string(payload, card);
        }
        payload.extend_from_slice(&self.king_tower_hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.left_tower_hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.right_tower_hp.to_bits().to_le_bytes());
    }

    fn towers_lost(&self) -> i64 {
        if self.king_tower_hp <= 0.0 {
            return 3;
        }
        i64::from(self.left_tower_hp <= 0.0) + i64::from(self.right_tower_hp <= 0.0)
    }

    fn lowest_tower_hp_milli(&self, towers: &[ResidentTower]) -> i64 {
        towers
            .iter()
            .filter(|tower| tower.player_id == self.player_id && tower.hp > 0.0)
            .map(|tower| tower.hp_milli)
            .min()
            .unwrap_or(0)
    }
}

struct ResidentTower {
    id: i64,
    player_id: i64,
    slot: String,
    hp: f64,
    hp_milli: i64,
    is_alive: bool,
    is_active: bool,
    last_attack_time: f64,
}

impl ResidentTower {
    fn from_init(value: TowerInit) -> PyResult<Self> {
        let (id, player_id, slot, hp, hp_milli, is_alive, is_active, last_attack_time) = value;
        if !matches!(slot.as_str(), "left" | "right" | "king") {
            return Err(PyValueError::new_err(format!(
                "unsupported Crown Tower slot {slot:?}"
            )));
        }
        if !hp.is_finite() || !last_attack_time.is_finite() {
            return Err(PyValueError::new_err(
                "tower hitpoints and last_attack_time must be finite",
            ));
        }
        Ok(Self {
            id,
            player_id,
            slot,
            hp,
            hp_milli,
            is_alive,
            is_active,
            last_attack_time,
        })
    }

    fn state_tuple(&self) -> TowerStateTuple {
        (
            self.id,
            self.player_id,
            self.slot.clone(),
            self.hp,
            self.hp_milli,
            self.is_alive,
            self.is_active,
            self.last_attack_time,
        )
    }

    fn append_hash_payload(&self, payload: &mut Vec<u8>) {
        payload.extend_from_slice(&self.id.to_le_bytes());
        payload.extend_from_slice(&self.player_id.to_le_bytes());
        append_string(payload, &self.slot);
        payload.extend_from_slice(&self.hp.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.hp_milli.to_le_bytes());
        payload.push(u8::from(self.is_alive));
        payload.push(u8::from(self.is_active));
        payload.extend_from_slice(&self.last_attack_time.to_bits().to_le_bytes());
    }
}

fn append_string(payload: &mut Vec<u8>, value: &str) {
    payload.extend_from_slice(&(value.len() as u64).to_le_bytes());
    payload.extend_from_slice(value.as_bytes());
}

/// Long-lived native battle allocation.
///
/// Initialization and explicit checkpoint replacement may cross the FFI as a
/// complete canonical payload. Ordinary phase/tick methods mutate the fields
/// below directly and never serialize or reparse that payload.
#[pyclass(module = "_clasher_rust")]
struct ResidentBattle {
    checkpoint: Vec<u8>,
    checkpoint_sha256: String,
    schema_version: u64,
    checkpoint_generation: u64,
    tick: i64,
    time: f64,
    dt: f64,
    double_elixir: bool,
    triple_elixir: bool,
    overtime: bool,
    game_over: bool,
    double_elixir_start_time: f64,
    overtime_start_time: f64,
    triple_elixir_start_time: f64,
    player_tick_ms: i64,
    refill_schedule: Vec<(f64, i64)>,
    players: Vec<ResidentPlayer>,
    towers: Vec<ResidentTower>,
    idle_eligible: bool,
    sparse_idle_win_checks: bool,
    sudden_death: bool,
    sudden_death_crowns: (i64, i64),
    tiebreaker_time: f64,
    winner: Option<i64>,
}

#[pymethods]
impl ResidentBattle {
    #[new]
    #[pyo3(signature = (
        checkpoint,
        *,
        tick,
        time,
        dt,
        double_elixir,
        triple_elixir,
        overtime,
        game_over,
        double_elixir_start_time,
        overtime_start_time,
        triple_elixir_start_time,
        player_tick_ms,
        refill_schedule,
        players,
        towers,
        idle_eligible,
        sparse_idle_win_checks,
        sudden_death,
        sudden_death_crowns,
        tiebreaker_time,
        winner
    ))]
    #[allow(clippy::too_many_arguments)]
    fn new(
        checkpoint: &[u8],
        tick: i64,
        time: f64,
        dt: f64,
        double_elixir: bool,
        triple_elixir: bool,
        overtime: bool,
        game_over: bool,
        double_elixir_start_time: f64,
        overtime_start_time: f64,
        triple_elixir_start_time: f64,
        player_tick_ms: i64,
        refill_schedule: Vec<(f64, i64)>,
        players: Vec<PlayerInit>,
        towers: Vec<TowerInit>,
        idle_eligible: bool,
        sparse_idle_win_checks: bool,
        sudden_death: bool,
        sudden_death_crowns: (i64, i64),
        tiebreaker_time: f64,
        winner: Option<i64>,
    ) -> PyResult<Self> {
        if !time.is_finite() || !dt.is_finite() || dt < 0.0 {
            return Err(PyValueError::new_err(
                "battle time and non-negative dt must be finite",
            ));
        }
        let schema_version = validate_checkpoint(checkpoint)?;
        if refill_schedule.is_empty() {
            return Err(PyValueError::new_err("refill schedule cannot be empty"));
        }
        let players = players
            .into_iter()
            .map(ResidentPlayer::from_init)
            .collect::<PyResult<Vec<_>>>()?;
        let towers = towers
            .into_iter()
            .map(ResidentTower::from_init)
            .collect::<PyResult<Vec<_>>>()?;
        Ok(Self {
            checkpoint: checkpoint.to_vec(),
            checkpoint_sha256: sha256_hex(checkpoint),
            schema_version,
            checkpoint_generation: 0,
            tick,
            time,
            dt,
            double_elixir,
            triple_elixir,
            overtime,
            game_over,
            double_elixir_start_time,
            overtime_start_time,
            triple_elixir_start_time,
            player_tick_ms,
            refill_schedule,
            players,
            towers,
            idle_eligible,
            sparse_idle_win_checks,
            sudden_death,
            sudden_death_crowns,
            tiebreaker_time,
            winner,
        })
    }

    /// Advance only the resident clock/timer phase of one native logic tick.
    /// Later milestones will append the remaining phases before complete-tick
    /// capability can be enabled.
    fn advance_clock_phase(&mut self) -> bool {
        if self.game_over {
            return false;
        }
        self.time += self.dt;
        self.tick += 1;
        if self.time >= self.double_elixir_start_time {
            self.double_elixir = true;
        }
        if self.time >= self.overtime_start_time {
            self.overtime = true;
        }
        if self.time >= self.triple_elixir_start_time {
            self.triple_elixir = true;
        }
        true
    }

    fn clock_state(&self) -> (i64, f64, f64, bool, bool, bool, bool) {
        (
            self.tick,
            self.time,
            self.dt,
            self.double_elixir,
            self.triple_elixir,
            self.overtime,
            self.game_over,
        )
    }

    fn clock_sha256(&self) -> String {
        let mut payload = Vec::with_capacity(28);
        payload.extend_from_slice(&self.tick.to_le_bytes());
        payload.extend_from_slice(&self.time.to_bits().to_le_bytes());
        payload.extend_from_slice(&self.dt.to_bits().to_le_bytes());
        payload.extend_from_slice(&[
            u8::from(self.double_elixir),
            u8::from(self.triple_elixir),
            u8::from(self.overtime),
            u8::from(self.game_over),
        ]);
        sha256_hex(&payload)
    }

    /// Advance the resident player phase after the clock phase of this tick.
    fn advance_player_phase(&mut self) {
        self.advance_players();
    }

    fn advance_players(&mut self) {
        let base_regen_time = if self.triple_elixir {
            0.93
        } else if self.double_elixir {
            1.4
        } else {
            2.8
        };
        let refill_ms = self
            .refill_schedule
            .iter()
            .find(|(segment_end, _)| self.time < *segment_end - 1e-9)
            .map(|(_, cooldown_ms)| *cooldown_ms)
            .unwrap_or_else(|| self.refill_schedule.last().expect("nonempty schedule").1);
        for player in &mut self.players {
            player.advance(self.dt, base_regen_time, refill_ms, self.player_tick_ms);
        }
    }

    fn player_states(&self) -> Vec<PlayerStateTuple> {
        self.players
            .iter()
            .map(ResidentPlayer::state_tuple)
            .collect()
    }

    fn player_sha256(&self) -> String {
        let mut payload = Vec::new();
        payload.extend_from_slice(&(self.players.len() as u64).to_le_bytes());
        for player in &self.players {
            player.append_hash_payload(&mut payload);
        }
        sha256_hex(&payload)
    }

    fn supports_idle_ticks(&self) -> bool {
        self.idle_eligible
    }

    fn advance_idle_ticks(&mut self, ticks: i64) -> PyResult<i64> {
        if ticks <= 0 {
            return Ok(0);
        }
        if !self.idle_eligible {
            return Err(PyRuntimeError::new_err(
                "resident battle did not pass the Python idle preflight",
            ));
        }
        let mut advanced = 0;
        for _ in 0..ticks {
            if self.game_over {
                break;
            }
            self.advance_clock_phase();
            self.advance_players();
            for tower in &mut self.towers {
                if tower.is_alive && tower.is_active {
                    tower.last_attack_time += self.dt;
                }
            }
            advanced += 1;
            if !self.sparse_idle_win_checks
                || (!self.sudden_death && self.time >= self.overtime_start_time)
                || (self.sudden_death && self.time >= self.tiebreaker_time)
            {
                self.check_win_conditions();
            }
            if self.game_over {
                break;
            }
        }
        Ok(advanced)
    }

    fn check_win_conditions(&mut self) {
        let king_alive = (
            self.players[0].king_tower_hp > 0.0,
            self.players[1].king_tower_hp > 0.0,
        );
        if !king_alive.0 || !king_alive.1 {
            self.game_over = true;
            self.winner = match king_alive {
                (false, false) => None,
                (true, false) => Some(0),
                (false, true) => Some(1),
                (true, true) => unreachable!(),
            };
            return;
        }
        let player0_crowns = self.players[1].towers_lost();
        let player1_crowns = self.players[0].towers_lost();
        if self.time >= self.overtime_start_time && !self.sudden_death {
            if player0_crowns != player1_crowns {
                self.game_over = true;
                self.winner = Some(if player0_crowns > player1_crowns {
                    0
                } else {
                    1
                });
                return;
            }
            self.sudden_death = true;
            self.sudden_death_crowns = (player0_crowns, player1_crowns);
        }
        if self.sudden_death {
            if player0_crowns != player1_crowns {
                self.game_over = true;
                self.winner = Some(if player0_crowns > player1_crowns {
                    0
                } else {
                    1
                });
                return;
            }
            if self.time >= self.tiebreaker_time {
                let player0_lowest = self.players[0].lowest_tower_hp_milli(&self.towers);
                let player1_lowest = self.players[1].lowest_tower_hp_milli(&self.towers);
                self.winner = if player0_lowest > player1_lowest {
                    Some(0)
                } else if player1_lowest > player0_lowest {
                    Some(1)
                } else {
                    None
                };
                self.game_over = true;
            }
        }
    }

    fn tower_states(&self) -> Vec<TowerStateTuple> {
        self.towers.iter().map(ResidentTower::state_tuple).collect()
    }

    fn outcome_state(&self) -> (bool, bool, Option<i64>, (i64, i64)) {
        (
            self.sudden_death,
            self.game_over,
            self.winner,
            self.sudden_death_crowns,
        )
    }

    fn idle_sha256(&self) -> String {
        let mut payload = Vec::new();
        payload.extend_from_slice(&self.tick.to_le_bytes());
        payload.extend_from_slice(&self.time.to_bits().to_le_bytes());
        payload.push(u8::from(self.double_elixir));
        payload.push(u8::from(self.triple_elixir));
        payload.push(u8::from(self.overtime));
        payload.push(u8::from(self.sudden_death));
        payload.push(u8::from(self.game_over));
        match self.winner {
            None => payload.push(0),
            Some(winner) => {
                payload.push(1);
                payload.extend_from_slice(&winner.to_le_bytes());
            }
        }
        payload.extend_from_slice(&self.sudden_death_crowns.0.to_le_bytes());
        payload.extend_from_slice(&self.sudden_death_crowns.1.to_le_bytes());
        payload.extend_from_slice(&(self.players.len() as u64).to_le_bytes());
        for player in &self.players {
            player.append_hash_payload(&mut payload);
        }
        payload.extend_from_slice(&(self.towers.len() as u64).to_le_bytes());
        for tower in &self.towers {
            tower.append_hash_payload(&mut payload);
        }
        sha256_hex(&payload)
    }

    fn checkpoint_bytes(&self) -> Vec<u8> {
        self.checkpoint.clone()
    }

    fn checkpoint_sha256(&self) -> &str {
        &self.checkpoint_sha256
    }

    fn checkpoint_size(&self) -> usize {
        self.checkpoint.len()
    }

    fn checkpoint_generation(&self) -> u64 {
        self.checkpoint_generation
    }

    fn schema_version(&self) -> u64 {
        self.schema_version
    }

    fn replace_checkpoint(&mut self, checkpoint: &[u8]) -> PyResult<()> {
        let schema_version = validate_checkpoint(checkpoint)?;
        self.checkpoint.clear();
        self.checkpoint.extend_from_slice(checkpoint);
        self.checkpoint_sha256 = sha256_hex(checkpoint);
        self.schema_version = schema_version;
        self.checkpoint_generation = self
            .checkpoint_generation
            .checked_add(1)
            .ok_or_else(|| PyRuntimeError::new_err("checkpoint generation overflow"))?;
        Ok(())
    }

    fn supports_complete_tick(&self) -> bool {
        false
    }
}

#[pymodule]
fn _clasher_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_function(wrap_pyfunction!(noop_ticks, module)?)?;
    module.add_function(wrap_pyfunction!(consume_state_bytes, module)?)?;
    module.add_class::<ResidentBattle>()?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fnv_is_stable() {
        assert_eq!(fnv1a(b""), 0xcbf29ce484222325);
        assert_eq!(fnv1a(b"clasher"), 0xf8c3eade13d5df8d);
    }

    #[test]
    fn sha256_is_stable() {
        assert_eq!(
            sha256_hex(b"clasher"),
            "2c69056d0b19b570ec219f88f78d9e3cb73ebb7c0496c1f50b59e3585f1f615d"
        );
    }
}
