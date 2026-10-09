//! W-only command simulation and balanced scan/top-eight refinement.
//! The existing command simulation and ordinary S6 rollout remain unchanged.
use super::*;

pub(super) type CommandInput = (i64, usize, String, f64);
pub(super) type CommandEvent = (String, i64, usize, usize, bool, String);
#[derive(Clone)]
struct Command { due: i64, action: usize, card: String, cost: f64 }

impl NativeScripts {
    fn wait_reserved_choice(&self, sim: &mut BattleState, actor: usize,
        style: &str, queue: &[Command]) -> PyResult<usize> {
        // Shadow only the acting player's exact reservations. Restore before
        // any physical step: execution performs the sole engine debit/cycle.
        let physical = sim.players[actor].clone();
        for c in queue {
            sim.players[actor].elixir -= c.cost;
            sim.players[actor].hand[c.action / 576] = None;
            sim.players[actor].cycle.push_back(c.card.clone());
        }
        let result = self.select_action(sim, actor, style);
        sim.players[actor] = physical;
        result
    }

    pub(super) fn wait_command_simulation(&self, battle: &BattleState, seat: usize,
        action: usize, own_pending: Vec<CommandInput>, opponent: &str,
        delay: i64, opponent_delay: i64, capacity: usize, opponent_capacity: usize,
        horizon: usize, own_interval: usize, opponent_interval: usize,
        continue_own: bool, endpoint: bool, trace: bool,
    ) -> PyResult<(BattleState, Vec<CommandEvent>)> {
        if seat > 1 || delay < 0 || opponent_delay < 0 || capacity == 0
            || opponent_capacity == 0 || own_interval == 0 || opponent_interval == 0
            || (action > 2304 && !(2400..=2402).contains(&action)) || !["balanced", "pressure", "defense"].contains(&opponent) {
            return Err(PyValueError::new_err("invalid delayed rollout configuration"));
        }
        let wait_ticks = match action { 2400 => 10, 2401 => 20, 2402 => 40, _ => 0 };
        let action = if wait_ticks > 0 { 2304 } else { action };
        let mut sim = battle.clone();
        let mut queues: [Vec<Command>; 2] = [vec![], vec![]];
        for (due, a, card, cost) in own_pending {
            if a >= 2304 || due < sim.tick || !cost.is_finite() || cost < 0.
                || queues[seat].iter().any(|c| c.action / 576 == a / 576)
                || sim.players[seat].hand[a / 576].as_ref() != Some(&card)
                || self.meta.cards.get(&card).is_none_or(|m| (m.cost-cost).abs() > 1e-9) {
                return Err(PyValueError::new_err("invalid own pending reservation"));
            }
            queues[seat].push(Command { due, action: a, card, cost });
        }
        if queues[seat].len() > capacity {
            return Err(PyValueError::new_err("pending capacity exceeded"));
        }
        let mut events = vec![];
        let origin = sim.tick;
        let submit = |s: &BattleState, actor: usize, a: usize, lead: i64,
            queue: &mut Vec<Command>, cap: usize, events: &mut Vec<CommandEvent>| -> PyResult<()> {
            if a == 2304 { return Ok(()); }
            if queue.len() >= cap || a >= 2304
                || queue.iter().any(|c| c.action / 576 == a / 576) {
                return Err(PyValueError::new_err("duplicate slot or full command channel"));
            }
            let card = s.players[actor].hand[a / 576].clone()
                .ok_or_else(|| PyValueError::new_err("empty submitted slot"))?;
            let cost = self.meta.cards[&card].cost;
            let reserved: f64 = queue.iter().map(|c| c.cost).sum();
            if cost > s.players[actor].elixir-reserved+1e-6 {
                return Err(PyValueError::new_err("unaffordable pending reservation"));
            }
            if trace { events.push(("submit".into(), s.tick, actor, a, true, card.clone())); }
            queue.push(Command { due: s.tick+lead, action: a, card, cost });
            Ok(())
        };
        submit(&sim, seat, action, delay, &mut queues[seat], capacity, &mut events)?;
        let other = self.wait_reserved_choice(&mut sim, 1-seat, opponent, &queues[1-seat])?;
        submit(&sim, 1-seat, other, opponent_delay, &mut queues[1-seat], opponent_capacity, &mut events)?;
        for tick in 0..=horizon {
            if tick == horizon && !endpoint { break; }
            if sim.game_over { break; }
            // Preserve S6's cadence-before-execution tie rule for own rollout.
            if tick > 0 && tick < horizon {
                for actor in [seat, 1-seat] {
                    let (interval, cap, lead, style) = if actor == seat {
                        (own_interval, capacity, delay, "balanced")
                    } else { (opponent_interval, opponent_capacity, opponent_delay, opponent) };
                    if (actor != seat || (continue_own && tick >= wait_ticks)) && tick % interval == 0 && queues[actor].len() < cap {
                        let a = self.wait_reserved_choice(&mut sim, actor, style, &queues[actor])?;
                        submit(&sim, actor, a, lead, &mut queues[actor], cap, &mut events)?;
                    }
                }
            }
            for actor in [seat, 1-seat] {
                let mut i = 0;
                while i < queues[actor].len() {
                    if queues[actor][i].due <= origin+tick as i64 {
                        let c = queues[actor].remove(i);
                        // Never execute a different card that later refilled this slot.
                        let accepted = sim.players[actor].hand[c.action / 576].as_ref() == Some(&c.card)
                            && self.apply_discrete(&mut sim, actor, c.action)?;
                        if trace { events.push(("execute".into(), sim.tick, actor, c.action, accepted, c.card)); }
                    } else { i += 1; }
                }
            }
            if tick < horizon { sim.tick_once(false); }
        }
        Ok((sim, events))
    }
}

impl NativeScripts {
    #[allow(clippy::too_many_arguments)]
    pub(super) fn wait_screen8_scores(&self, battle: &BattleState, seat: usize,
        candidates: Vec<usize>, elixir: f64, delay: i64, opponent_delay: i64,
        horizon: usize, interval: usize, elixir_weight: f64, budget_seconds: Option<f64>,
    ) -> PyResult<Vec<Option<f64>>> {
        use std::time::{Duration, Instant};
        if !elixir.is_finite() || !(0.0..=10.000001).contains(&elixir)
            || candidates.is_empty() || !candidates.contains(&2304)
            || candidates.iter().any(|&a| a > 2304 && !(2400..=2402).contains(&a))
            || candidates.iter().enumerate().any(|(i,a)| candidates[..i].contains(a))
            || budget_seconds.is_some_and(|v| !v.is_finite() || v < 0.0) {
            return Err(PyValueError::new_err("invalid W-screen8 inputs"));
        }
        let start = Instant::now();
        let budget = budget_seconds.map(Duration::from_secs_f64);
        let expired = || budget.is_some_and(|v| start.elapsed() >= v);
        let value = |a: usize, style: &str| -> PyResult<f64> {
            let (sim, _) = self.wait_command_simulation(battle, seat, a, vec![], style,
                delay, opponent_delay, 1, 1, horizon, interval, interval, true, false, false)?;
            Ok(self.phi(&sim, seat, elixir_weight))
        };
        let mut scores = vec![None; candidates.len()];
        let mut coarse = vec![0.0; candidates.len()];
        let mut plays = vec![];
        // No partially scanned list is eligible for refinement.
        for (i, &a) in candidates.iter().enumerate() {
            if a < 2304 {
                if expired() { return Ok(scores); }
                coarse[i] = value(a, "balanced")?;
                if expired() { return Ok(scores); }
                plays.push(i);
            }
        }
        plays.sort_by(|&i, &j| coarse[j].partial_cmp(&coarse[i]).unwrap_or(std::cmp::Ordering::Equal).then(i.cmp(&j)));
        plays.truncate(8);
        let wait_index = candidates.iter().position(|&a| a == 2304).unwrap();
        for (i, &a) in candidates.iter().enumerate() {
            if a == 2400 || (a < 2304 && !plays.contains(&i)) { continue; }
            let mut score = if a < 2304 { coarse[i] / 3.0 } else { 0.0 };
            let styles: &[&str] = if a < 2304 { &["pressure", "defense"] }
                else { &["balanced", "pressure", "defense"] };
            let mut complete = true;
            for style in styles {
                if expired() { complete = false; break; }
                score += value(a, style)? / 3.0;
                if expired() { complete = false; break; }
            }
            if complete { scores[i] = Some(score); }
            else { break; }
        }
        if let Some(i) = candidates.iter().position(|&a| a == 2400) {
            scores[i] = scores[wait_index];
        }
        // Copy the raw WAIT score before applying each duration's prior.
        for (i, &a) in candidates.iter().enumerate() {
            let ticks: f64 = match a { 2304 | 2400 => 10.0, 2401 => 20.0, 2402 => 40.0, _ => 0.0 };
            if let Some(score) = scores[i].as_mut() {
                if ticks > 0.0 && score.abs() < 2.0 {
                    *score += 0.01 * (ticks / 20.0).sqrt() * (1.0 - elixir / 10.0).max(0.0);
                }
            }
        }
        Ok(scores)
    }
}
