"""Add a tick-abortable rollout to a fresh private engine; frozen methods untouched."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def stage(source, dest):
    if dest.exists():
        raise FileExistsError(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns('target', '*.so', '__pycache__'))
    text = (source/'src/wait_screen8.rs').read_text().split('\nimpl NativeScripts {\n    #[allow')[0]
    text = text.replace('wait_reserved_choice', 'e1_reserved_choice').replace('wait_command_simulation', 'e1_command_simulation')
    text = text.replace('continue_own: bool, endpoint: bool, trace: bool,',
                        'continue_own: bool, endpoint: bool, trace: bool, deadline: Option<std::time::Instant>,')
    check = '''if deadline.is_some_and(|end| std::time::Instant::now() >= end) {
            return Err(pyo3::exceptions::PyTimeoutError::new_err("E1 wall deadline"));
        }'''
    text = text.replace('let mut sim = battle.clone();', check+'\n        let mut sim = battle.clone();')
    text = text.replace('for tick in 0..=horizon {', 'for tick in 0..=horizon {\n            '+check)
    text = text.replace('Ok((sim, events))', check+'\n        Ok((sim, events))')
    (dest/'src/e1_commands.rs').write_text(text)
    p = dest/'src/scripts.rs'; text = p.read_text()
    text = text.replace('mod wait_screen8;', 'mod wait_screen8;\n#[path = "e1_commands.rs"]\nmod e1_commands;')
    assert 'mod e1_commands;' in text
    marker = '    #[getter]\n    fn mask_version'
    method = '''    #[pyo3(name = "rollout_e1", signature=(battle, seat, action, opponent, delay, opponent_delay, horizon, interval, elixir_weight, remaining_seconds))]
    #[allow(clippy::too_many_arguments)]
    fn rollout_e1_detached(&self, py: Python<'_>, battle: &BattleState,
        seat: usize, action: usize, opponent: &str, delay: i64,
        opponent_delay: i64, horizon: usize, interval: usize,
        elixir_weight: f64, remaining_seconds: f64) -> PyResult<f64> {
        if !remaining_seconds.is_finite() || remaining_seconds < 0.0 {
            return Err(PyValueError::new_err("invalid E1 wall budget"));
        }
        let deadline = std::time::Instant::now().checked_add(std::time::Duration::from_secs_f64(remaining_seconds))
            .ok_or_else(|| PyValueError::new_err("invalid E1 deadline"))?;
        native_call(py, || {
            let (sim, _) = self.e1_command_simulation(battle, seat, action, vec![], opponent,
                delay, opponent_delay, 1, 1, horizon, interval, interval, true, false, false, Some(deadline))?;
            let value = self.phi(&sim, seat, elixir_weight);
            if std::time::Instant::now() >= deadline {
                return Err(pyo3::exceptions::PyTimeoutError::new_err("E1 late value"));
            }
            Ok(value)
        })
    }

'''
    assert marker in text; p.write_text(text.replace(marker, method+marker))
    manifest = {str(p.relative_to(dest)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(dest.rglob('*')) if p.is_file()}
    (dest/'e1-source-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('source', type=Path); ap.add_argument('dest', type=Path)
    a = ap.parse_args(); stage(a.source, a.dest)
