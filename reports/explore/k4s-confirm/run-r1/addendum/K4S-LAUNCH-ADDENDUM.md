# PREREG-K4S launch freeze addendum (run r1)

- Composed 2026-10-11T19:55:15Z (`date -u`) by the K4S runner r1 (Claude Opus 5.5, 127x05) for coordinator 0523ae6f. Machine-readable twin: `K4S-LAUNCH-ADDENDUM.json`.
- **No frozen byte changed** (freeze 391d2006, fill fab6e03f). Outcomes SEALED; nothing here reads a game outcome.

| Item | Binding |
|---|---|
| OA-1 hub copier (coordinator 18:00Z, 3badf70d; r4 19:07Z, r5 19:19Z) | `oa1/mirror_k4s.py` `47eb96d61bd094ffea300f6892844e63ede1c6127795e93a72781e9c1d7da5cd`; tests `c575fb9146900fb30b07bfe145e8118134c123723c6591a23651f238566e347f`; binding GPT-6.1-Sol review `reviews/SOL-REVIEW-OA1-B2-r7.md` **APPROVE_WITH_FIXES** (`280c80e6d491bfd1d33b1ad5ecfa1327d1f80510142c029d4a36d462e602b7d7`). Supersedes the r3 §4.4 "hub 01" wording for K4S. |
| B2 job manifest (3badf70d) | `oa1/FROZEN-K4S.json` **`416f6e51e32e1900faaf8ceaf329287475a6a621fb1dc2d1b6def50ebb528ed1`** (176 files = frozen k4s-confirm tree + PREREG r3 at 391d2006; Mac manifest pinned d89cab16); builder `47d6e8dc480c9b5090cb6bf62e962af430d36fc4987ea591ca225cdb7fce56fa` |
| B4 barrier prerequisites | 03/04: 391d2006 objects fetched by SHA into /mpac/sdicks02/repos/clasher (FETCH_HEAD only); PREREG r3 bytes 9650972d copied into each staged repo (frozen barrier prerequisites) |
| K4S Amendment 1 (45f32c0f) | amended Mac manifest 8bb20a75…; fleet reporting keeps d89cab16; END/Mac only from a separate amended tree naming 8bb20a75 |
| 03 idle service (18:22Z, d999d016) | PID 2180947, start_ticks 139691386, cmdline 16152ceb… (= T1's committed pin); flags only |
| Smoke freeze-SHA disclosure (18:48Z, f442b968) | frozen run.py stamps freeze_manifest_sha256 = sha256(FROZEN-K4S.json) whenever the job manifest exists, so excluded smoke games carry the manifest SHA; K4S-SPEC 5 says null in qualification and smoke; accepted, no frozen byte changed |
| STOP drill (f442b968) | `receipts/stop-drill.json` `2a92916ac6b569cc6b39b0315ad3be786f256d19434f5a15b1149c64d701a8b3`: owned STOP drained in ≈1.7 s / 2.7 s, 0 owned groups |
| Launch qualification | 03 `f985a32c436997ce7738fe360058f3272606b2c8c3bfcf3d4ab7e579aa14852d`, 04 `a11c978c7af5f36cfaecce01bb748a2a19130268d82540d97d78b3f7cf6ea0f0` (28/28 each) |
| Dispatch | smoke `5ff0b681c5011457342f20234e658c63eb8a335ca8ed69a62d8f2bbd60039b9e`; reporting `78335dc40094b404848088e55c287a536034e739c56789aa6f46af9a9b8af5b2` (3900 blocks, 33000 games) |
| END prep | K4-states.pkl a97b1fbf + corpora.json 3501e2ac (= git 81f2483e) copied read-only (0444, SHA-verified) from the 05 bundle into <job>/end-corpus on 03/04; END only in the coordinator-declared window from a separate amended tree |
| Health tool | `tools/k4s_health.py` `00ff7caf8e28a266feb1ceed45653add5d56990261e6a00bcd207c7c7f057ed8` (Sol-reviewed with OA-1) |
