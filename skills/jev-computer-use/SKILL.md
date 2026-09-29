---
name: jev-computer-use
description: Delegate sustained computer interaction to fast System One Jev using accessible UI or task-specific observations and actions; keep reasoning, new text and final verification with the calling agent. For multi-step UI work or repeated reactive controls, not single actions or reasoning-heavy tasks. Default native execution requires macOS and running Codex desktop with Computer Use installed.
---

# Jev Computer Use

You are System Two; Jev handles stretches of recognizable UI choices. Delegate
navigation, known-value forms and repeated reactive controls. Handle single
operations, ranking alternatives, calculation and open-ended synthesis yourself.
Matching supplied constraints and checking or correcting field values (including
date/time formats) are routine interaction, not a reasoning handoff. For mixed
work, delegate the interaction with an explicit stopping boundary before the
comparison or judgment (for example, display the options and stop before choosing).
Do not delegate the full comparison/selection instruction and rely on a generic
reasoning rule to stop Jev. Resolve reasoning yourself, including on resume: give
Jev a specific conclusion, never an instruction to perform the comparison.
Resume when a useful interaction stretch remains. No predicted UI plan needed.

## Choose observation and actions

Keep the same two modes: `step` for sequential work, `realtime` for a changing
interface. Choose observation and action sources independently of mode:

- Default: full accessible UI and built-in Computer Use actions; no adapter needed.
- Extend: add task-specific observations or executable actions to the defaults.
- Replace: use custom observations or actions instead of the defaults, for example
  game state and plant-at-cell actions. Either side can be replaced independently.

Observation means what Jev sees, not the literal field values in `input_texts`.
Replacing it preserves the goal, guidance, concise history with outcomes, warnings
and host control. You prepare adapters and questions; Jev selects actions, never
writes executable code. For custom work read [adapters](references/adapters.md).
The current `delegate_task`/CLI accepts only the default path; custom work needs
an agent-authored worker, not invented tool parameters.

## Delegate with default Computer Use

If `delegate_task` is not registered, read [setup](references/tasks.md) and use
the CLI route. Otherwise call it through its **registered tool interface**; do not
invent a `functions.exec` wrapper alias. Use a new private `state_dir` per task.
Supply only:

- `task`: the whole delegated interaction goal and **task-specific** constraints,
  briefly. For mixed tasks, explicitly stop at the boundary before host reasoning. Code already
  supplies generic interaction, input, authorization and stopping rules to Jev;
  do not restate them as a list of prohibitions or generate a UI script.
- `mode`: `step` for sequential work; `realtime` for an interface changing on its
  own clock. Its cycle is observe → Jev → execute; optional `period_ms` controls
  minimum spacing, not guaranteed latency. It is not a navigation speed boost.
- `input_texts`: **include every already-known field value on the first call**, as
  `{"id":{"text":"literal value","purpose":"what this value is for"}}`.
  Prepare known names, search criteria and destinations from the task without
  waiting to see the fields. Unknown widget types do not make known values unknown.
  Each entry can be copied verbatim or appended to a field’s observed text with a space. The runner also retains
  dates read from the UI, with their source labels, for later date-field entry;
  Jev selects the matching source. It does not invent missing values. A combined
  query is appropriate only when that whole phrase
  is intended for one field. The purpose describes meaning, not a predicted UI ID.
  For “fill name Lin and city Paris”, supply two entries: Lin/name and Paris/city,
  even before seeing their field labels. These are values to enter, **not labels
  of buttons or checkboxes to click**. Use `{}` for click-only work. Do not pre-resolve facts the user asks Jev to find
  in the UI. Leave genuinely
  unknown authored text for a later handoff; missing text does not make a field optional.

Omit other options unless this task needs them. `guidance` carries your specific
conclusion or an unusual work boundary, not generic reasoning instructions.
The runner supplies the current accessibility tree in bounded, navigable pages,
every concise step, input texts and warnings to Jev. Accumulated UI date values
are also paged, with recent sources first; caller-supplied values stay visible. Raw observations remain
complete in the task log and final handoff. Jev selects the operation and compatible
target together, then chooses a prepared value, reconsiders an incorrect input
target, or hands back genuinely missing text. Choice selectors can open their options without authored text.
Completion and reasoning handoff are choices in the same operation decision,
not a separate stop vote. It uses no screenshots or nested LLM.

## Manage the handoff

Wait for the worker to yield before operating the UI. Read the **current interface
already in its response**; continue through `takeover.js_binding` in the same MCP
native session. Follow `takeover.before_native_ui` only if native actions remain.
Do not rebind, reopen, or read that screen from logs. After your
own UI action, obtain a fresh observation using the supplied native documentation.

- Missing text: supply `input_texts`. Reasoning needed: decide yourself, then act
  or supply the specific conclusion in `guidance`.
- Completion proposed: verify the whole result; a Jev proposal is not proof.
- Uncertainty, capacity, budget or error: inspect the supplied state and reason;
  resolve the cause before resuming. An uncertain operation needs a fresh
  observation before retry; an oversized unchanged screen needs host handling.

Resume the same `state_dir`, omit `task`, choose `mode`, and supply only changes.
Previous inputs/history persist; revised text needs a new ID. Finish a small
remainder directly. Use `read_task_history` only for earlier screens/diagnostics,
preferably batching `observation_ids`. No extra navigation to reconstruct answers.

For setup, CLI execution, progress/stop and optional settings, read
[the reference](references/tasks.md) **only when needed**. Progress includes all
concise steps; full observations stay in private logs. Never run two UI controllers
concurrently. Jev can misjudge stopping or obscured controls; delegation adds no
authorization, and model confidence is not a safety guarantee.
