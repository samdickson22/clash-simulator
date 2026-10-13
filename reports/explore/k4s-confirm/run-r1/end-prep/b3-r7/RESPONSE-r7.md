# b3-r7 response: ruling IR-03 (proposed): 127x03 has no idle resident for K4S END

Sources: `end-prep/IDLE-03-RETIREMENT-PROPOSAL.md` (proposed ruling IR-03, change 2 and the S4 rows of its tables);
`b3-r6/README.md`, `b3-r6/RESPONSE-r6.md`. `b3-r7/` is a copy of `b3-r6/` (b3-r6 `SHA256SUMS` verified before and after
the copy; `b3-r6/` untouched). Line numbers are for the b3-r7 bytes in `SHA256SUMS`. S4 sha256 `2b8f5fb3b79b85103394e18c39330b772fbf2deb28d95fbd01d2d73273d7f016`.

## Change (smallest)

| What | Where (file:line) |
|---|---|
| `PRODUCTION_PINS["admissions"]["127x03"]` = `system-bus-admission.json` only (identity unchanged: dbus-daemon PID 2049 / start_ticks 1273). The r6 `idle-services.json` pin (PID 2180947) is deleted. | `assemble_fleet_reference.py:329-332`; source comment `:308-310` |
| `IR03_HOST`, `IR03_RETIRED` (the message) and `retired_idle(host, names, pins)`: true only for 127x03, when `idle-services.json` is named AND the active pins carry no idle pin for 127x03 (a future coordinator re-pin lifts it; 04 keeps its r6 refusals) | `:353-364` |
| `--committed-admission idle-services.json` for 127x03 refuses citing IR-03, in the pure step-0 binding check (no file touched) | `committed_bindings`, `:770` |
| a 127x03 request whose `guard.admissions` names `idle-services.json` refuses citing IR-03, before the generic set check and before any admission is read | `plan_bundle` step 6, `:1001-1002` |
| docstring (E3 note; production pins) and `--committed-admission` help | `:47-49`, `:59-60`, `:1171-1172` |
| **unchanged:** `:1005` (r6 `:989`): an idle admission only on a plan `idle_service_exception` host; the generic set check `:1003-1004`; the idle identity checks (`:1023-1029`, reachable only under a test-only re-pin); every other pin; `ADMISSIONS`; the canonical bootstrap r1 region; `safe_input.py`; B1 `members()`; `assembler_sha256` in the receipt and both summaries | — |

The refusal text (both paths): `<path> idle-services.json on 127x03 refused: ruling IR-03 (127x03 has no idle resident
for K4S END; 127x03 admissions are system-bus-admission.json only; the committed 127x03-idle-services.json is a retired
historical admission and is never placed in a guard job or bundle)`.

Every other pin is unchanged: `canonical_sha(PRODUCTION_PINS)` of b3-r7 = `95e3ec55f1fc7d8c5dfc20bde2f5cd86c3aa27c578a012156f883362bda04fd0` = the b3-r6 `PRODUCTION_PINS` with
only `admissions["127x03"]["idle-services.json"]` deleted (computed by importing both files; pinned in
`test_r7_every_other_pin_is_the_r6_value`). The bootstrap region SHA-256 is identical to b3-r6's (computed), and
`test_s4_r5_bootstrap.py` passes.

## Tests

- **Fixture:** `World(..., idle=False)` (`test_assemble_fleet_reference.py:130-134`, `:243`). Every synthetic world is now
  bus only, as production is. `idle=True` models a test-only coordinator re-pin of an idle service on 03 (synthetic
  pins), so the r6 idle checks stay covered.
- **Updated** (r6 expectations that encoded the 03 idle pin): `test_happy_path_bundle` (guard admissions = bus only),
  `test_f2_production_pins_are_the_verified_constants` (03 = bus only), `test_f2_idle_admission_required_on_03` →
  `..._when_repinned`, `test_f2_admission_content_checks` (idle rows on a re-pinned world),
  `test_r3_f1_hard_link_canary_refused_before_any_read[admission-idle-*]` (re-pinned world),
  `test_frozen_reporting_guard_init_accepts_bundle_and_job` (frozen guard admissions = FROZEN-T1 + bus),
  `test_frozen_reporting_guard_init_rejects_bad_jobs` (new row: a 03 job still carrying `idle-services.json` is refused
  by the frozen guard, "Every existing guard admission must be pinned"; the "idle absent" row now runs on a re-pin).
- **New** `test_s4_r7_ir03.py` (19 tests: 14 synthetic/pure, 2 frozen-guard, 3 real-request rows):
  - pins: `test_r7_production_admission_pins_are_bus_only_on_both_hosts`, `test_r7_every_other_pin_is_the_r6_value`,
    `test_r7_retired_idle_is_pin_driven_and_03_only`;
  - 03 bus only passes: `test_r7_03_bus_only_bundle`, `test_r7_bus_only_passes_under_the_production_admission_pins[127x03]`
    (the production admission pins verbatim), `test_r7_03_bus_only_ignores_the_retired_committed_idle_copy` (the copy
    is committed at its E3 path, as on A', and is never opened);
  - 03 with idle refuses: `test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it` (the idle copy is never
    opened; recorder control), `test_r7_03_committed_idle_binding_refuses_citing_ir03`,
    `test_r7_committed_bindings_refusal_is_pure`, `test_r7_03_idle_only_still_refuses_the_missing_bus`;
  - control: `test_r7_03_repinned_idle_is_accepted_test_only`;
  - 04 unchanged: `test_r7_bus_only_passes_under_the_production_admission_pins[127x04]`,
    `test_r7_04_idle_in_request_keeps_the_r6_refusal` (exact r6 messages, no IR-03), and the existing
    `test_host_04_has_no_idle_admission`, `test_f2_idle_admission_refused_on_04`;
  - kept `:1005`: `test_r7_plan_idle_host_check_unchanged`;
  - frozen guard (fleet_validity, frozen root): `test_r7_frozen_guard_accepts_03_bus_only_job`,
    `test_r7_frozen_guard_refuses_03_job_carrying_the_retired_idle_file`;
  - real requests (05 only, read-only): `test_r7_real_ir03_requests_drop_only_the_idle_admission[3]`.

## The three 127x03 requests (`requests-ir03/`)

Written by `make_requests_ir03.py` (O_EXCL, 0444; record in `requests-ir03/make_requests_ir03.out.json`). Each source
must hash to its `end-staging/requests/make_requests.out.json` value and be exactly the make_requests writer's bytes
(`json.dumps(indent=1, sort_keys=True) + "\n"`). The only change is deleting `guard.admissions["idle-services.json"]`
(checked by parse); `guard.job` and everything else are unchanged. The retired idle file itself was never opened.

| request | source sha256 (end-staging) | new sha256 (requests-ir03) | guard job (unchanged) |
|---|---|---|---|
| `request-127x03-pf00.json` | `85e9c3859ee311e29deb6ad4ab88e4f174d1fe1f30dd1150762e5a93cb6f35f6` | `6c913789c6832d89fdd8414a38fa246adba4f9a8d4232a395c1b5bf435093eae` | `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-pf00` |
| `request-127x03-rd00-a00.json` | `ed3a13018a8157ea1cb12e09fab8991f3bd484ba88782a754953923363ace4d0` | `c403446424d3ada6e915a90b88eb2bb5aaeb054780405ff838f749ba4bc096e5` | `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a00` |
| `request-127x03-rd00-a01.json` | `18d8411ca0434debbe3723820dcbc073986bee4f564ba57679b6a84592a6ea54` | `dd55582d2942e99dbb84c1095dec06a962a49db5a0bc1a9d313c147c3612dabb` | `/mpac/sdicks02/jobs/clasher/k4s-end-guard-r1-rd00-a01` |

## Production proof on 127x05 (six real requests)

Driver `proof_driver_r7.py` (b3-r6's driver plus the IR-03 request set and two negative controls): this directory's
S4 (`2b8f5fb3…`, equal to every receipt's `assembler_sha256`), the `e4v3-venv` interpreter `-I -B`, `env -i`
(PATH/HOME/LANG), cwd `/tmp`, `nice -n 19 taskset -c 8-15`, `--repository end-prep/repo-full` (receipt
`repository_head` = the S9 commit), committed admissions from the request records (03: the bus only), `--out` in a fresh
`mkdtemp` under `/dev/shm/b3r7-proof-*`. One at a time; each bundle deleted right after its SHAs were recorded; the
scratch directory then removed. Raw record: `PROOF-r7.json`. Every bundle: `runtime_files` 4307 entries, canonical
`fc3dbeb42a7737ab844f1f6033ff42b19cd1d514f9670631e36cc7f72a2008e7` (= S9 and b3-r6); guard admissions and bundle admission files = `system-bus-admission.json` only;
`production_pins` true, status CANDIDATE.

| request | request sha256 | result | tiers-pins.json sha256 | assembly-receipt.json sha256 | vs b3-r6 tiers-pins | runtime files | bundle bytes |
|---|---|---|---|---|---|---|---|
| `requests-ir03/request-127x03-pf00.json` | `6c913789c6832d89fdd8414a38fa246adba4f9a8d4232a395c1b5bf435093eae` | PASS (rc 0) | `5082e8b21f687c7e92af9e93ed5c1b0c21e9af858ad3ab90955ed49e07fd1b03` | `c0874a6f6a33dc17a166e2fde415b3a22947f849f00868ac582f82a73700535a` | differs from r6 (`ca4ce6ef`) | 4307 | 23475392007 |
| `requests-ir03/request-127x03-rd00-a00.json` | `c403446424d3ada6e915a90b88eb2bb5aaeb054780405ff838f749ba4bc096e5` | PASS (rc 0) | `39e3f2566a2dd528053101f982934898f24821ba58db6d960a92e4a0ca428070` | `49b96b98bc65a9f27adfa65c46b51620f27189fa1ac74c5432a4fba30f5ab857` | differs from r6 (`783db178`) | 4307 | 23475392015 |
| `requests-ir03/request-127x03-rd00-a01.json` | `dd55582d2942e99dbb84c1095dec06a962a49db5a0bc1a9d313c147c3612dabb` | PASS (rc 0) | `03b8f52e08447141cb436fcd683867376ca482bf7689eb1550d7d0380f825fc5` | `7e0814a7afb54e264135052aed3c6f3d277aab74cdc70cfed13004b954b1c173` | differs from r6 (`ab2be9d4`) | 4307 | 23475392015 |
| `/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-127x04-pf00.json` | `60895f3ad0c71958317297ca777dd316f56bc7926abf53a119b4ffc6d12a5c95` | PASS (rc 0) | `fd8c9ee5e8fc262f49f17961b62668b2daa156e1c49bfbc26be93754e00faa0f` | `9fc01c8053e958e637a34de44fed1123ae53b88aaec6aa5c4ea66fd7a3883729` | same as r6 | 4307 | 23475391999 |
| `/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-127x04-rd00-a00.json` | `43f2ca41f7256e6565bb681129442772322e9b486263f0b12415cc177478def9` | PASS (rc 0) | `2fb48c3e71ca4dbc6be3300cf557eba94d0f6eab36d994385ef1ac7d92f2fb6e` | `ce9d6c2a8ce75132bb1ef4cd0c536731cb1e3bec71d73ce7acda3473806a63d5` | same as r6 | 4307 | 23475392007 |
| `/mpac/sdicks02/k4s-runner/run-r1/end-staging/requests/request-127x04-rd00-a01.json` | `bd6f3dc3656b9811451405be60ba928ab1be36056946fee00a3f2b2cc9c1a91e` | PASS (rc 0) | `d1292b2eff22e2449237187d6bc8d8dc45e623d43f164bd639a920a549d2a458` | `f563d2c05e69e066f2c5d64e0ad451d1abe5b3619f55d5df024a7f133c9502ad` | same as r6 | 4307 | 23475392007 |

The three 127x04 manifests are byte-identical to b3-r6's (04 unchanged). The 127x03 manifests differ from b3-r6's only in the guard admission map and `files`, which no longer carry `guard-admissions/idle-services.json`.

**IR-03 negative controls** (the ORIGINAL r6-shape `end-staging/requests/request-127x03-pf00.json`, production pins,
`--dry-run`):

| control | --committed-admission | result | nothing written |
|---|---|---|---|
| argv bus + idle (b3-r6 shape) | `idle-services.json, system-bus-admission.json` | rc 2, REFUSED-IR03 | yes |
| argv bus only | `system-bus-admission.json` | rc 2, REFUSED-IR03 | yes |

  - argv bus + idle (b3-r6 shape): `ASSEMBLY REFUSED: --committed-admission idle-services.json on 127x03 refused: ruling IR-03 (127x03 has no idle resident for K4S END; 127x03 admissions are system-bus-admission.json only; the committed 127x03-idle-services.json is a retired historical admission and is never placed in a guard job or bundle)`
  - argv bus only: `ASSEMBLY REFUSED: guard.admissions idle-services.json on 127x03 refused: ruling IR-03 (127x03 has no idle resident for K4S END; 127x03 admissions are system-bus-admission.json only; the committed 127x03-idle-services.json is a retired historical admission and is never placed in a guard job or bundle)`

## Mutation (`mutate_s4_r7.py` → `MUTATION-RESULTS-r7.json`, k4s-freeze 3.12 `-O`, frozen root set)

**9/9 KILLED**: each mutant failed every one of its named tests AND the suite (`-x`). NULL controls:
NULL-0 SURVIVED, NULL-1 SURVIVED. The recorded assembler/test SHAs equal the final bytes.

| mutant | result | named killing tests (all failed) |
|---|---|---|
| IR-03 pin: the r6 03 idle-service pin restored | KILLED | `test_r7_production_admission_pins_are_bus_only_on_both_hosts`, `test_r7_every_other_pin_is_the_r6_value`, `test_r7_retired_idle_is_pin_driven_and_03_only`, `test_r7_bus_only_passes_under_the_production_admission_pins[127x03]`, `test_r7_03_bus_only_ignores_the_retired_committed_idle_copy`, `test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it`, `test_r7_committed_bindings_refusal_is_pure`, `test_f2_production_pins_are_the_verified_constants` |
| IR-03 --committed-admission check off | KILLED | `test_r7_03_committed_idle_binding_refuses_citing_ir03`, `test_r7_committed_bindings_refusal_is_pure` |
| IR-03 guard.admissions check off | KILLED | `test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it`, `test_r7_03_idle_only_still_refuses_the_missing_bus` |
| IR-03 both checks off (generic r6 messages only) | KILLED | `test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it`, `test_r7_03_committed_idle_binding_refuses_citing_ir03`, `test_r7_committed_bindings_refusal_is_pure`, `test_r7_03_idle_only_still_refuses_the_missing_bus` |
| IR-03 message does not cite the ruling | KILLED | `test_r7_03_request_naming_idle_refuses_citing_ir03_before_reading_it`, `test_r7_03_committed_idle_binding_refuses_citing_ir03`, `test_r7_committed_bindings_refusal_is_pure`, `test_r7_03_idle_only_still_refuses_the_missing_bus` |
| IR-03 on every host (04 loses its r6 refusal) | KILLED | `test_r7_retired_idle_is_pin_driven_and_03_only`, `test_r7_04_idle_in_request_keeps_the_r6_refusal`, `test_f2_idle_admission_refused_on_04` |
| IR-03 ignores the pins (a re-pin cannot lift it) | KILLED | `test_r7_retired_idle_is_pin_driven_and_03_only`, `test_r7_03_repinned_idle_is_accepted_test_only`, `test_f2_idle_admission_required_on_03_when_repinned` |
| IR-03 retires the bus admission too | KILLED | `test_r7_retired_idle_is_pin_driven_and_03_only`, `test_r7_03_bus_only_bundle`, `test_r7_bus_only_passes_under_the_production_admission_pins[127x03]`, `test_happy_path_bundle` |
| kept :989 plan idle-host check off | KILLED | `test_r7_plan_idle_host_check_unchanged` |

## Runner addendum (2026-10-13T08:46:35Z)

`test_s4_r7_ir03.py::test_r7_real_ir03_requests_drop_only_the_idle_admission` keyed the IR-03 request metadata by its absolute original path and failed in copied trees. The runner changed it to a basename lookup that requires exactly one row. Test-only; `assemble_fleet_reference.py` (2b8f5fb3…) is unchanged.
