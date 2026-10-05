# Clasher strategy council

Astra and Fable approved the same strategy at Max reasoning effort. [consensus.json](consensus.json) records both endorsements and the SHA-256 of [strategy.md](strategy.md). The strategy's pre-approval heading is preserved because changing it would change the signed bytes. [max-settings-verified.json](max-settings-verified.json) records the subsequent live settings check.

The user requested implementation after agreement. M0 engineering is active, with no gameplay fitting or fresh acceptance collected. The prospective entry protocol remains draft until real development studies and stable source pins are available.

Implementation evidence is organized under `m0/`:

- [Public contract](m0/contract/README.md) and [cross-pipeline integration](m0/integration/README.md).
- [Simulator levels](m0/levels/README.md) and [recurrent PPO checks](m0/ppo-audit/README.md).
- [Data plumbing](m0/data/README.md). Use the corrected `m0/data/roles_v2/` manifests.
- [Readiness evaluator](m0/readiness/README.md). Its synthetic tests do not establish native admission.
- [Root-bank declarations](m0/root-bank/README.md), with no fresh captures or outcomes yet.
- [Actual-model local benchmark](m0/benchmark/README.md), with unchanged weights and two completed games.
- [Live adapter](m0/live-adapter/README.md) and [human-data inventory](m0/human-audit/README.md), including their remaining observation limitations.
- [Mac mini sizing](m0/benchmark/macmini-tuning.md), [native refill repair](m0/native-public-v4/refill-repair.md), and [local staging package](m0/training-package/README.md).

The combined integration suite passes 319 tests. Its log is `m0/integration/broad-pytest-final.log`. Full council matches now include tick 6001 so the final tiebreaker produces a terminal result.

Full episode prefix reconstruction is the production recurrence reference. A finite suffix started from zero can alter behavior at collection boundaries, so it remains an explicitly approximate diagnostic rather than the training default.

Sam answered the compute-account question: use the Mac mini for now. Local execution and a suitably sized local benchmark replace the immediate remote-machine dependency. The larger-machine plan remains a later scaling option, and no cloud resources will be launched under this direction. See [execution-direction.md](execution-direction.md).
