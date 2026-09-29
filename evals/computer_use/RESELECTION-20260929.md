# Input-branch rejection follow-up, 2026-09-29

The input-value decision can now reject a wrongly selected field and reconsider
its operation once before any UI mutation. This fixes the false missing-text
handoff observed in the preceding MiniWoB batch. It does **not** make the
MiniWoB calendar autonomous: all three live book-flight runs still needed host
UI takeover, now explicitly reported as `uncertain_action`.

## Decision contract

`reselect_action` means the chosen field/operation is inappropriate or its value
already satisfies the task. The runner removes that field's input branches for
this decision, rebuilds the operation/target choices and their shared capability
state, and includes the rejected operation/field as feedback. It does not remove
the field from later observations or execute a guessed replacement action.
A second rejected input selection yields uncertainty without entering text.
`help_input` means a genuinely required new field value is unavailable from both
the supplied inputs and current UI. Existing missing-value handoff remains tested.

There are no calendar labels, dates, app names or benchmark-specific routes in
this change. Choice-selector opening and genuine missing-text resumption remain
available. Exact requests and rejection feedback are retained in private traces.

## Evidence and remaining failure

Real Jev API replays of all three previous failed input decisions changed from
`help_input` to `reselect_action` (selected probability 0.98 in each). This is
saved-state evidence, not a native completion test.

The subsequent frozen native batch used the same pinned upstream revision,
original reward functions, general Skill protocol, Sol/medium outer agent, and
300-second deadline as the [preceding report](GENERALIZATION-20260929.md).

| book-flight seed | Whole-agent seconds | Official first raw reward | Episodes | Handoff | Outer UI calls |
|---|---:|---:|---:|---|---:|
| 11 | 103.519 | 1 | 1 | uncertain_action | 9 |
| 22 | 111.270 | 1 | 1 | uncertain_action | 9 |
| 66 | 151.442 | 1 | 1 | uncertain_action | 12 |

All three filled the cities and opened the picker, rejected changing the already
filled origin, then selected and rejected changing the already filled destination.
The bounded rejection path handed control back without corrupting either city.
The outer agent finished all three, so official success is 3/3 but autonomous
calendar completion remains 0/3. No reduction in takeover or latency is claimed.
See [sanitized measurements](miniwob-reselection-20260929.json).

Read-only experiments added UI deltas, shortened instructions, separated static
text from interactive controls, narrowed to newly revealed controls, and moved
capabilities into operation criteria. These did not produce a consistently
correct calendar choice and were not added to the runtime. A separate constraint
question correctly selected the pending date; adding that answer to the action
state still selected a city field. This localizes an unresolved decision problem,
but does not establish a unique root cause or a model capability limit.

## Regression validation

Flights again passed three consecutive end-to-end native trials: **42.285,
39.598, 43.867 seconds**, all with zero host task UI actions/resumption. Each
started on about:blank in running Chrome; Jev opened a new tab, entered the URL
and searched the requested Zurich–London one-way itinerary for 2026-10-20,
one adult, economy. All three final observations contained 21 flight links.
Cold application launch was not tested.

Doubao passed the end-to-end send task in **19.309 seconds**, with zero host
intervention: new tab, URL entry, message entry and submission. The final capture
shows the sent “你好” message with a timestamp and an empty editor. An assistant
reply was not yet present in that capture; this regression only claims sending,
which is the task's completion condition.

[Sanitized native measurements and runtime hashes](reselection-native-20260929.json).
Offline: 158 runner tests and the existing 22 evaluator tests. The added tests
verify returning to action selection without typing, removal of rejected input
branches and matching shared targets, and bounded repeated rejection as
uncertainty rather than missing user text.
