# Evaluations

The harness runs real native Computer Use with Jev and an outer Codex Sol/medium
agent. Offline tests validate code contracts; they are not task-success evidence.

## Start here

- [Latest measured results and limitations](computer_use/MINIWOB-RUNTIME.md):
  three MiniWoB task types × three seeds, plus four real websites and a realtime game.
- [Five-case public-web/realtime protocol](computer_use/PROTOCOL.md).
- [MiniWoB setup and reproduction](computer_use/MINIWOB.md): original pages and
  rewards, deliberately relaxed 300-second deadlines, not leaderboard scores.
- [Real invoice form](forms/zoho.md): Jev field/value choices on Zoho, verified
  amounts and a full normal-speed recording.
- [Game adapter experiment](games/README.md): live third-party tower defense,
  custom observations/actions and unaccelerated recording.
- [Native desktop generalization follow-up](../docs/desktop-generalization.md):
  shared field/menu fixes, two motivating cases, and a failed cross-year variant.
- [Current verification scope](../docs/testing.md).

## Evidence layout

`computer_use/` contains executable harnesses, offline tests and sanitized JSON
reports. Reports name their source hashes, models, token counts and limitations.
`*-followup.json` records subsequent trials; `*-comparison.json` compares them.
Development runs, unknown costs and failed attempts remain visible. The latest
report links the relevant files so users need not navigate every experiment.

[STATUS.md](computer_use/STATUS.md) is the chronological research log.
[RESULTS.md](computer_use/RESULTS.md) measures the older stage implementation;
it must not be used to advertise the current general-task executor.

Raw screen/model journals, credentials and pinned-source archives are private local
artifacts, not included in this repository. Their machine-local `/tmp` paths in
reports identify original runs, not downloadable evidence. The upstream revision,
commands and sanitized results are provided for reproduction.

Costs are API-equivalent estimates from recorded tokens and frozen rates, including
the outer LLM and Jev. They are not subscription deductions. Small reused samples
and historical CLI-version drift do not establish universal reliability or causal
speed/cost superiority. Never rerun a personal-desktop benchmark unattended against
real messages, purchases or personal documents.

- [2026-09-29 native generalization repair](computer_use/GENERALIZATION-20260929.md): end-to-end Flights/Doubao and the three-type, three-seed MiniWoB++ follow-up.

- [Input-branch rejection follow-up](computer_use/RESELECTION-20260929.md): false missing-text handoff repaired; native calendar autonomy remains unresolved.

- [Field grounding and widget semantics](computer_use/GROUNDED-ACTIONS-20260929.md): final nine-run MiniWoB acceptance with autonomous booking navigation, explicit host reasoning/text boundaries, and retained development failures.
