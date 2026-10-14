# IL_Replay: license check and usage ruling (2026-10-14)

**Checked:** 2026-10-14, the Hugging Face dataset `VanguardX101/IL_Replay`.

| Field | Finding |
|---|---|
| API metadata | `license: None`, `gated: False`, `private: False`, `lastModified` 2026-09-06, sha `059d43a0…` |
| Card | No license field or text. Tags: reinforcement-learning, imitation-learning, game-replays, anonymized |
| Card description | "An anonymized battle replay dataset for imitation learning and offline AI research"; 252,238 replays, 17,836,160 actions |
| Restrictions | None stated: no research-only, non-commercial, no-redistribution or no-training terms |
| Source | Not stated. The schema label `royaleapi-replay-parquet.v1` suggests RoyaleAPI-format replays (inference) |
| Local copy | 03:`/mpac/sdicks02/repos/clasher-local-data/il_replay` (`hf_manifest.json`: api, dataset, files, revision; no license field) |

**Conclusion:** no license is granted and no use is explicitly forbidden. All rights are therefore reserved by default.

**Coordinator ruling:** **internal evaluation only.**
- Never commit or publish the data, any derived dataset, or the `rext-bc`/`rext-bcppo` weights.
- Keep them in fleet `/mpac` job dirs only.
- Reports may give opponent scores, with this data source disclosed.

Note: our own v1 human prior was trained from this corpus earlier; this ruling doesn't change that.
