# SC1 spell-chip / spell-hold option value: RESULTS (exploration)

Owner: cycle-model owner, for the BOT LEAD. Live trigger: s78-m14, where the search cast Zap on pure tower chip (36
damage, no enemy units), beating WAIT by 0.0009; an enemy Wizard arrived ~2 s later.

## Measurement (no new games; BN1 clean res-wint, 200 L16 games vs K4CW-r16 + R3a; job dir bot-cycle/sc1/measure.py)

**Rule:** "tower-only" = our Zap/Fireball with no enemy troop or building within 2.5 tiles of its target at the last
poll before execution, aimed within 4 tiles of an enemy tower.

**Per game:**
- **Casts:** Zap 5.19, Fireball 1.54.
- **Tower-only:** **1.01** (Zap 0.80, Fireball 0.22); K4CW 1.08, R3a 0.94. 123/200 games have at least one; cast-tick
  quartiles 1292 / 2902 / 3837.
- **Empty:** a further 0.42 per game hit no unit and aren't near a tower.
- **What follows:** after ~75% of tower-only casts, an enemy troop is played within 5 s while the spell is out of hand.
- **Margins:** not logged in sim rows; live s78-m14: 0.0009 over WAIT.
- **Descriptive only:** games with tower-only casts win 0.81, without 0.68 (confounded: the bot chips when ahead).

Systematic by the BOT LEAD's bar (≥ 0.5 per game), so the A/B follows.

## A/B SC1-AB: pre-registration (written 2026-10-17T20:20:49Z, before any game)

**Term** (bot/search/spellhold.py, token `sh<N>`, λ = N/1000, default OFF):
- Every root play of a spell (a card with no Troop/Building body in R.config) pays λ × cost(card), whatever it targets.
  This is a spell-in-hand option value; a wait keeps it.
- It composes with `res` in core.reserve. There are no per-card or target rules.
- Fireball (4) holds twice Zap's (2) value by construction. That is noted in advance and not tuned after results.

**λ values** (fixed now, the BOT LEAD's anchor to -res's 0.015 per elixir): **0.005** (`sh5`) and **0.015** (`sh15`).

**Bank:** SC1 base 153589845884221 (os.urandom, drawn 2026-10-17T20:20:49Z).
- 100 cases each vs LIVE-K4CW-r16-fp and R3a = 200 paired per arm.
- Pool v3 decks per live-diag's driver option (non-PEKKA strata allowed), L16, RoyaleSim.

**Arms:** `res-wint` (control), `res-sh5-wint`, `res-sh15-wint`.

**Default-off parity first:** 10 cases, new tree vs the previous tree, `res-wint`, identical command_sha256.

**Readout:**
- **Primary:** each sh arm − control, paired, normal 95% CI.
- **Also:** tower-only casts per game per arm (measure.py), reaction p50/p90, undefended share, elixir at the enemy's
  cross (l16_report).
- **Decision:** report as measured. A λ is a ship candidate only if its Δ > 0 with CI lower bound > −0.03 and
  tower-only casts drop. The final call is the BOT LEAD's.
