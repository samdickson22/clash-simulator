# Default-off parity and switch behaviour: cycle-model package (fleet only; nothing ran on the Mac)

The trees are exactly their manifests (sha-verified, no extra files):
- pkg-trees/base-W = MANIFEST-fullpool-wint.json 7322efaa…;
- base-P = MANIFEST-fullpool.json e855d300…;
- cyc-W / cyc-P = this package's manifests.

## 1. Archived live battles, fixed timing

**Method** (05; tests/archived_parity.py + archpar.sh):
- **Battles:** s72-m04…m09, six full-pool -res live battles. Each is replayed through the tree's own LiveTranslator +
  LiveSession (the translator owner's shadow method).
- **Player:** at every poll, the deterministic twin K4L-R-gs-rw-fc-t2-mk1a1-res decides on the view. It has no wall
  deadline and fixed seeds, uses the full-pool belief, and runs in the deployed fullpool env.
- **Hash:** the sha256 of the per-poll (tick, can_act, action, wait_ticks) list.

    ARCHIVED (s72-m04..m09 live battles replayed through the tree translator + deterministic K4L-R-gs-rw-fc-t2-mk1a1-res; 05)
      s72-m04: base-W ea95b60ef60d rep ea95b60ef60d cyc-W off ea95b60ef60d soft b05ab1b12a4d | base-P ea95b60ef60d cyc-P off ea95b60ef60d | polls 632 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 8 soft-belief 8 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      s72-m05: base-W e80b04e6e798 rep e80b04e6e798 cyc-W off e80b04e6e798 soft 7641cd782025 | base-P e80b04e6e798 cyc-P off e80b04e6e798 | polls 648 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 4 soft-belief 4 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      s72-m06: base-W 61b7df5fe742 rep 61b7df5fe742 cyc-W off 61b7df5fe742 soft df4db17e4c8f | base-P 61b7df5fe742 cyc-P off 61b7df5fe742 | polls 418 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 3 soft-belief 3 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      s72-m07: base-W e85f71437f64 rep e85f71437f64 cyc-W off e85f71437f64 soft 9aca4c050fee | base-P e85f71437f64 cyc-P off e85f71437f64 | polls 383 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 6 soft-belief 6 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      s72-m08: base-W 1a170dda4c8d rep 1a170dda4c8d cyc-W off 1a170dda4c8d soft d2b61aaee689 | base-P 1a170dda4c8d cyc-P off 1a170dda4c8d | polls 619 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 6 soft-belief 6 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      s72-m09: base-W 53a1bbd3f24c rep 53a1bbd3f24c cyc-W off 53a1bbd3f24c soft 0eef69bab0ed | base-P 53a1bbd3f24c cyc-P off 53a1bbd3f24c | polls 680 errs [0, 0, 0, 0, 0, 0] conflicts(dropped:1) 3 soft-belief 3 tag ['cycle_model:soft:preal_sha256:f9096e223b61d285']
      SUMMARY: cyc-W off == base-W 6/6; base-W repeat == base-W 6/6; cyc-P off == base-P 6/6; cyc-W soft differs 6/6

- **Default-off parity:** identical action hashes on 6/6 battles for cyc-W (switch unset) vs the deployed wint tree, and
  6/6 for cyc-P vs the deployed plain tree.
- **Determinism:** a repeat of the deployed tree reproduces its hashes 6/6.
- **Soft is active:** switch on (BOT_CYCLE_MODEL=soft + BOT_CYCLE_PREAL): decisions change on 6/6 battles. Every dropped
  opponent conflict reaches the belief as a soft play (3–8 per battle), and each battle's translator stats carry
  cycle_model:soft:preal_sha256:f9096e223b61d285.
- **Errors:** 0 player errors in all 36 replays. The 55 replay errors on s72-m04 are the replay harness's own and the
  same in every arm.

## 2. Sim, deterministic twins

**Method** (08; tests/parity_tree.py + parity_tree.sh): LIVE-AB1 cases 0–9 vs R3a, command_sha256.

    SIM (LIVE-AB1 cases 0-9 vs R3a; deterministic twins; 08)
      cyc-W vs base-W K4L-R-gs-mk1a1-res: off==base 10/10  soft(clean obs)==base 10/10  soft conflicts 0  soft belief [('FullPoolBelief', 'CycleBelief')]  imports-from ['cyc-W']
      cyc-W vs base-W K4L-R-gs-rw-fc-t2-mk1a1-res: off==base 10/10  soft(clean obs)==base 10/10  soft conflicts 0  soft belief [('FullPoolBelief', 'CycleBelief')]  imports-from ['cyc-W']
      cyc-P vs base-P K4L-R-gs-mk1a1-res: off==base 10/10  soft(clean obs)==base 10/10  soft conflicts 0  soft belief [('FullPoolBelief', 'CycleBelief')]  imports-from ['cyc-P']
      cyc-P vs base-P K4L-R-gs-rw-fc-t2-mk1a1-res: off==base 10/10  soft(clean obs)==base 10/10  soft conflicts 0  soft belief [('FullPoolBelief', 'CycleBelief')]  imports-from ['cyc-P']
    

## 3. Session start (tests/start_check.py on cyc-W, deployed fullpool env)

| env | result |
|---|---|
| unset | starts; no tag; nothing printed |
| soft + valid preal-v1.json | starts; stderr `cycle-model: mode=soft preal=… sha256=f9096e22…`; tr_stats tag cycle_model:soft:preal_sha256:f9096e223b61d285 |
| soft, BOT_CYCLE_PREAL unset | RuntimeError at LiveTranslator construction: refuses to start |
| soft, BOT_CYCLE_PREAL missing | RuntimeError: refuses to start |
| bad spec (soft:bogus=1) | ValueError: refuses to start |

In drive.py the translator is built in build_bot(), after the manifest check and before the first frame or tap. A
refusal therefore exits the driver before battle 1.

## 4. Per-decision cost

- With the switch off, the code path is the frozen one (parity above).
- With it on, a decision without a new conflict does no extra work. The first conflict of a battle costs ≤ ~120 ms on
  loaded fleet hosts at ~100k prior rows (5.3–7 ms max in the translator owner's Mac-env shadow). Later conflicts take
  ~1 ms.

## 5. Translator-only replay on the current trees (the translator owner, 11:09Z)

**Setup:**
- 80 recorded live battles s41–s60, through each tree's own `drive.make_session` (the inline SyncSession) with logged
  actions, deployed fp env, only the tree on PYTHONPATH.
- Origins were checked: every module comes from the tree or the frozen runtime.
- Tree shas: cyc translate 014b7fd9, preal.py 2cbdb5a9, belief.py 5352b6c0, preal-v1.json f9096e22; base translate
  c10b997b.
- Files (05): live-multibody-20261015/guardfix/pkgreplay/CMP-W.json and CMP-P.json.

| check | cyc-W | cyc-P |
|---|---|---|
| default-off: accepted opponent plays / own plays / drops, base vs cyc | identical (1,350 plays), 0 errors | identical |
| soft vs off: guarded D1 stream (public_events, drops) | identical, 0 errors | identical |
| seat-1 cycle drops → `card?` | 439 → 438 soft + 1 ninth (exact) | same |
| `card?` with the switch off | 0 | 0 |
| P(real) over the 438 | mean 0.715; 262 at ≥ 0.85, 66 below 0.15 | same |
| tr_stats tag | cycle_model:soft:preal_sha256:f9096e223b61d285 | same |
| switch on, PREAL unset | RuntimeError (refuses to start) | same |

**drop_features on the deployed tree:**
- It is self-consistent on all 439 drops.
- Against the main-era labelled features, 9/422 shared drops differ, all because the deployed board-only translator
  accepted slightly different upstream plays. The feature code is not the cause.

## 6. End-to-end install dry run (05; zsh 5.9; tests/installdry/)

The INSTALL.md block was extracted verbatim and run with zsh 5.9 against a fake `B` tree. The only substitutions were
`B`, `WRAP_SHA` (a stub wrapper exiting 0 or 1 stands in for run-fpbench-mac.sh) and `PRESTOP_SHA`.

| case | result |
|---|---|
| pass | INSTALL-OK; NEW tree = the manifest's 225 code entries exactly; manifest and launcher shas exact; launcher executable; base dir byte-identical |
| pre-start check exits 1 | `STOP: pre-start check failed (rc=1)`; launcher left NON-executable; base intact |
| NEW already exists | `STOP: fullpool-r1-wint-cyc exists`; nothing copied |
| package file tampered | `STOP: package integrity (wint)`; nothing copied |
| PRESTOP_SHA left unset | `STOP: PRESTOP_SHA not set` |
| PRESTOP_SHA wrong | `STOP: fp_prestop_check.py sha` |
| symlink inside the base tree | `STOP: symlink inside fullpool-r1-wint …`, before any copy |
| launcher sha mismatch after copy (injected) | `STOP: sha loop/run-fullpool-wint-cyc.sh`; the launcher is NOT executable (it ships with mode 0644) |

Each payload file is also `chmod a-x`'d right after its copy. Tested with an executable package launcher: a launcher-sha
failure or a failed pre-start check still leaves the installed launcher NOT executable (tests/installdry/xmode*.out.txt).

The real run used the round-3 version of the block: Sol r3 findings fixed, with the launcher shipped 0644, base symlinks
refused, and symlink destinations refused.

**Real checker on the installed dry tree:** live-diag's fp_prestop_check.py (95d8336a…), deployed fullpool env, `--players
LIVE-K4L-R-gs-rw-fc-w200-t4-p4-mk1a1-res-wint`.
- The lines file was MANIFEST-LINES minus the 37 `../../../` Mac data files, which don't exist on the fleet; it keeps
  the installed manifest and launcher.
- Result: **exit 0**. 227/227 files match; the player constructs with all token checks true (type, wint, deadline,
  samples, reserve, name); all five origin-checked modules import from the new dir.
