**CHANGES REQUESTED at exact HEAD `efaf99842cbc8260f12332fff8efb00ca5105901`. Stage/launch approval withheld.**

All eight supplied SHA-256s match; all507 engine-manifest entries and all11 implementation-packet bindings verify, and Rust/Cargo/build inputs remain unchanged versus5c8.

Concrete blockers:

- **P1 — Canonical projectiles remain stationary.** `fair_player.py:142` installs `entity(shot)`, whose `stats.speed` is0; `live_snapshot.py:160` supplies the required native speed, and native movement consumes `stats.speed`. The strengthened probe still accepts template/root agreement at0 while independently checking only `projectile_speed=1000`. Require canonical and reconstructed `stats.speed=1000`, positive projected native movement after launch delay for all three ranks/both seats, and a rejected zero-speed control.
- **P2 — Supplemental provenance is rebaselined without verification.** `stage_public.sh:45–47` copies the old supplemental probe and hashes whatever was copied; the checked OLD tools manifest excludes that file. Copy the committed reviewed probe, or first verify its approved SHA-256 `93e4881f3fe0fd5a157d4b683dfdff6ac83c8473318f02e3e0182aea78cc9011`.
- **P2 — Input verification remains incomplete.** Launchers check the hash of `gate-inputs-expected.sha256`, but do not verify its17 targets before/after gate; staging verifies them once. Add explicit boundary checks. Public receipts should also assert and record the **actually imported native module’s** resolved path/hash, rather than only checking the intended binary on disk.

The other preflight07 corrections are substantive: reconstructed fields, actual ordinary shots, Mirror pulses, fuse completion/removal, damage controls and released children are exercised. Archive write bounds, owned package binding, group draining and resource controls are acceptable by static inspection; stdlib preparation alone is execution-safe, without clearing staging or launch.

After repair, bind replacement source/probe/procedure hashes and obtain review before execution; verify actual04 identities/liveness immediately before staging/launch, then require fresh16/94/4/39/public14+owner16/577+600 evidence. No edits, imports, scripts, tests, SSH or jobs were performed; no readiness or deployment approval is given.
