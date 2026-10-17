# fp_mac_bench r8b (r7 audit + Sol r7 items 1-4 + loop owner's r8b decision on belief rebuilds): every except site on the bench's decision path, and how a swallowed failure is observed

Scope: the code the bench drives = live/loop/drive.py `make_session` (SyncSession + GuardedPlayer) -> bot/live/translate.py
LiveSession / LiveTranslator -> [bot/search/interrupt.Interruptible] -> bot/live/player.LivePlayer (fast tier
bot/exit/student.StudentPlayer; search tier bot/search/lopp_fast.WallLearnedPlayer(_FastMixin, player.WallCandidatePlayer)
-> R3a gate / belief / candidates -> lopp_fast reduce + LearnedPool workers). Files as deployed (sha256 prefix):
player.py 02252a3d, lopp_fast.py 42778eca (package), lopp.py e7df1711, interrupt.py ef68c4c9, translate.py c10b997b,
drive.py 650a87da, bot/players/search.py e130eb2e; candidates.py / bot/search/players.py / student.py / base.py have none.

Class-level design (r7): observation AT THE SOURCE, independent of how the deployed code reports it.
- O1 `fast_exc`: the bench wraps `live.fast.act` in a proxy that records ANY exception and re-raises it unchanged.
- O2 `search_exc`: same for `live.search.act` (on- and off-cadence; everything below it propagates up to here unless a
  site inside swallows it -- those are rows 5-11).
- O3 `lopp.FAILURES`: the process-wide note_failure counter, snapshotted before / after each run (every lopp / lopp_fast
  give-up path calls note_failure in the parent process).
- O4 classifier `decision_problems(stats)`: error, source other than search/fast (default-* cutoff fallback, fast-error,
  stall-fast), native_failure, native_failures, search_failures, fallback, student_default.
- O5 counters: the LivePlayer's fast_errors / errors / panics, max over every step.
- O6 (r8) cutoffs: ANY cutoff -- hit, preparation_cutoff or a default-* source, including a completed search that hit the
  cutoff with a usable choice (lopp_fast.py:619 hit=True, fallback=False, source 'search') -- is an error (also flagged by
  the classifier). This also covers the late-failure paths that only occur under a cutoff: the stale-generation chunk
  discard (lopp_fast.py:331) and abandoned native futures (:534).
- O7 (r8b) belief rebuilds: REPORTED, not invalidating (loop owner, 2026-10-17: they occur in every live battle, 1-4 in all
  63 of s68-s73, and are part of the latency being measured). Per player: belief_rebuilds (the belief's own counter, max over
  every step) and belief_rebuilt_at (per run: the decision n, its step_ms, searched or not). A rebuild that pushes a decision
  past the deadline becomes a cutoff, which O6 invalidates.
Any of O1-O6 -> error -> run invalid (exit 2); O7 (belief rebuilds) is report-only. Behaviour of the deployed code is
unchanged (proxies re-raise).

| # | site | swallows / does | observation | test (r7 suite) | mutation check |
|---|---|---|---|---|---|
| 1 | player.py:290 `self.fast.act` except BaseException | any fast-tier exception -> fast_errors += 1, WAIT substituted, search continues | O1 (+O5 fast_errors) | M1 FAST_RAISE=5 -> rc 2, kind fast_exc | M1m MUTATE=fast_exc,counters -> rc 0 |
| 2 | player.py:311 `self.search.act` except BaseException | any search exception; OFF-CADENCE / blocked polls return WAIT stats=None BEFORE errors += 1 (Sol r6) | O2 (+O5 errors on cadence only) | M2 SEARCH_RAISE=3 (off-cadence, raised after the poll ran) -> rc 2, kind search_exc only | M2m MUTATE=search_exc -> rc 0 (nothing else sees it: Sol's scenario exactly). Debug run (tests/r7/fptest7m.debug.log): an exception raised BEFORE the poll runs skips the R3a 5-tick gate, which then fails on cadence ('standalone gate must run once per 250 ms' -> fast-error, player.errors, fast-disabled): caught by O4/O5 even without O2 |
| 3 | player.py:126 / :151 (WallCandidatePlayer.act) except TimeoutError | belief.update / belief.sample past the cutoff -> fallback action, preparation_cutoff -> source default-* | O4 (source default-*, fallback, preparation_cutoff) + O6 | M3 BELIEF_TIMEOUT=2 -> rc 2, kind 'source default' | M3m MUTATE=classifier,cutoffs -> rc 0 |
| 4 | player.py:218 LiveBelief.update except ValueError | 'no train deck' -> rebuild the C56 prior (other ValueErrors re-raised) | O7 reported (C56 belief only; the full-pool names use row 18's class); a slow one -> O6 | as row 18 | as row 18 |
| 5 | lopp.py:344 serial score_candidates except BaseException | reduce failure -> note_failure('serial'), fail_decision, native_failure='serial' | O3 + O4 (native_failure; source default-*) | serial path not used by the fc/p4 live names; O3/O4 proven by M4 | as M4 |
| 6 | lopp_fast.py:499 rollout_e1 except TimeoutError; :619 completed-but-hit; :331 stale-generation discard; :534 abandoned futures | a native rollout past its budget / a search that ran past the cutoff (with or without a usable choice) | O6 (cutoffs) + O4 (hit / preparation_cutoff / default-*) | H FP_TEST_HIT=3 (source 'search', hit=True, fallback=False) -> rc 2; INFO A17 | Ha MUTATE=cutoffs -> 2 (classifier); Hb MUTATE=classifier -> 2 (cutoffs); Hm both -> 0 |
| 7 | lopp_fast.py:501 / :523 / :564 / :567 / :579 | native panic in a thread, dead pool at ship / collect, pool.errors (native_pool), serial batch panic -> failed[] -> note_failure + fail_decision + native_failure | O3 + O4 (+ O6: the give-up is a cutoff default) | M4 POOL_ERR=2 -> rc 2. NOTE: M4 injects into the PARENT-side pool.errors right after collect; it does not exercise worker transport (pipes) or LearnedPool's own process start; those paths end in the same pool.errors / pool_dead -> failed[] branch, and any late failure under a cutoff is covered by O6 | M4a MUTATE=failures -> 2; M4b MUTATE=classifier -> 2; M4m MUTATE=failures,classifier,cutoffs -> 0 |
| 8 | lopp_fast.py:194 / :211 (pool worker process) | root parse / batch_rollouts panic in a worker -> err sent to the parent -> pool.errors | row 7 path (native_pool) | M4 injects exactly pool.errors at collect | as M4 |
| 9 | lopp_fast.py:173 / :305 / :323 | worker recv EOF (worker exits), parent send / recv OSError -> pool.broken + errors / raise | row 7 path (pool_dead) | covered by M4's path (pool.errors -> failed) | as M4 |
| 10 | lopp_fast.py:134 config_need except ValueError | the fc cut config cannot be parsed -> None -> the full (uncut) config is shipped | not a failure: identical values (the fc cut is exact by construction / parity), only latency, which the bench measures | -- | -- |
| 11 | lopp_fast.py:346 LearnedPool.close except BrokenPipe/OSError | teardown of a dead pool after the run | not on the decision path (run already scored) | -- | -- |
| 12 | translate.py:648 _consistent except ValueError (OwnCycle) | the deployed stream guard drops an own play its own-cycle tracker rejects | designed translator behaviour (not a search-tier failure, does not invalidate); REPORTED per player: own_cycle_dropped (+ translator_stats), so a K2 arm cannot hide a difference there | R8 check: fields present per player | -- |
| 13 | translate.py:1043 LiveSession._poll except ValueError | HUD disagreement -> no tap (submit_refused) | designed (the live tap guard; does not invalidate); REPORTED per player: submit_refused (+ translator_stats) | R8 check: fields present per player | -- |
| 14 | drive.py:759 board_hook except Exception | installed only if LL_UNITS_BOT=1 is exported (neither run-fullpool.sh's env nor the bench sets it); its except replaces a logging row (tr.board_last) and returns the assignment unchanged | no decision effect (logging only) | -- | -- |
| 15 | sess.step itself (any exception the session does not catch) | -- | the bench records it as an error (n=...: Exc) | A11 (close error), earlier T4 | -- |
| 16 | bot/search/interrupt.py | no except sites | -- | -- | -- |
| 17 | drive.py SyncSession / GuardedPlayer (849-918), handsync | no except sites (stall mode = a substitution on a can-act WAIT with stats, visible as source stall-fast -> O4) | O4 | U1 (stall-fast case) | -- |

drive.py's other except sites (69..1501) are in its capture / navigation / main loop, which the bench does not run (it
calls make_session(...).step directly).
| 18 | bot/fullpool/belief.py:58 (3d1e62a2) FullPoolBelief.update except ValueError | 'no train deck' -> rebuild the full-pool prior from the revealed cards and retry (the class BOT_BELIEF_PRIOR selects; happens in every live battle) | O7 REPORTED (count + where), not invalidating; a rebuild that blows the deadline -> O6 cutoff -> invalid | R FP_TEST_BELIEF_REBUILD=2 -> rc 0 with belief_rebuilds >= 1 reported; RC same + FP_TEST_BELIEF_REBUILD_SLEEP_MS=2500 (w2000 deadline) -> rc 2 (cutoff) | RCm MUTATE=cutoffs,classifier -> rc 0, rebuild still reported |

