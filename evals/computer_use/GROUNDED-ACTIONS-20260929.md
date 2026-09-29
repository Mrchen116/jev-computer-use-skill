# Field grounding and month-grid semantics, 2026-09-29

Latest acceptance: the final MiniWoB matrix passed 9/9 first episodes, three fresh
Google Flights runs passed without host intervention, and Doubao sent the greeting
and received a reply. See the final validation sections below for the host
reasoning/text boundaries and retained failed attempts. These bounded samples do
not establish universal reliability.

This follows the unsuccessful [branch-rejection-only repair](RESELECTION-20260929.md).
The previous repair stopped the false missing-text request but still handed all
three calendars to the host. Those failures remain recorded; they are not counted
as successes of the new candidate.

## Engineering diagnosis and change

The old menu presented input fields before establishing whether any supplied
value belonged in them. Its technical compatibility check excluded a field's
identical current value while leaving other supplied values as possible inputs.
After rejecting origin, the replacement branch had only destination left. That
conditional head's probability of 1 meant only one offered target, not evidence
that the destination needed changing.

Input rejection now triggers one batched field-grounding request. Jev classifies
all offered input fields against the task/current values: satisfied, unrelated,
a supplied value, or genuinely missing text. The next operation decision sees
these statuses and only the corresponding input branches. This preserves genuine
missing-text handoff and can correct a wrong value; it does not simply ban all
fields that already contain text. Grounding runs only after an input rejection.

A second problem was the calendar action representation. Native AX supplied day
links named only `1`, `19`, etc., and a separate month heading. The click menu
repeated link URLs but did not attach the month to each day or the resulting
month to navigation. It also offered reopening the already-open read-only field
and clicking its adjacent static label.

The new native-description helper recognizes conventional English month grids
from an unambiguous month/year heading and all seven weekday headers. It augments
existing links with their full dates and previous/next-month links with the
resulting month/year. A focused read-only field with the recognized grid open,
and its adjacent label, no longer offer redundant reopening clicks. Ambiguous
or unrecognized tables are left alone. This does not claim arbitrary calendar
coverage. Raw AX observations and native target IDs remain unchanged.

There are no MiniWoB URLs, task names, fixed dates, city names, or scripted
month/day sequences in the runtime. Jev still chooses every click. The helper
supplies widget meaning, not the task answer or the shortest flight.

## Saved-state experiments

All three real API field-grounding probes marked the already-correct city fields
satisfied. Grounding alone stopped city replacement but did not reliably select
the calendar action. Adding observed month-grid semantics and removing redundant
reopening targets gave the correct next actions in all three retained states.

Replay through the actual revised runtime selected:

- Seed 11: previous month, December → November.
- Seed 22: December 1, the requested date in the displayed month.
- Seed 66: previous month, December → November (October requires another step).

Seeds 11 and 66 selected the correct click directly; seed 22 used input rejection
and the batched field-grounding repair. These are saved-state decisions, not live
completion evidence. They support the representation/decision-order diagnosis;
they do not identify a unique internal neural cause.

## Live development batch

The first native batch completed all three calendars without host UI operations:
seed 11 moved to November and chose 19; seed 22 chose December 1; seed 66 moved
back twice and chose October 22. However, all three then submitted unconfirmed
city queries and remained on the search form. The host confirmed autocomplete
options and completed booking. Official reward was 1 in each first episode,
but this batch is **not** accepted as autonomous navigation to flight results.
The earlier progress statement that seed 11 handed off only for ranking was
premature and was corrected after reading the actual post-Search observation.

[Development measurements](miniwob-grounded-development-20260929.json):
99.766, 124.680, 160.271 seconds; 25 outer UI calls in total.

The shared operation/target rule now explicitly distinguishes a typed query from
a confirmed autocomplete option and selects a matching visible suggestion before
leaving the field. Saved-state API replays of all six origin/destination states
selected the correct suggestions. This is a generic form interaction rule, not
an airport-code lookup or a prescribed task sequence.

## Retained boundary failure

The next batch reached flight results autonomously for seed 11, then failed the
first episode (raw reward -1) because Jev attempted ranking/booking itself. The
outer delegation still asked it to book the shortest flight without an explicit
stop-at-options boundary. A generic instruction assigning ranking to the host
was insufficient. Subsequent clicks on the completed page also exposed the
existing imperfect terminal/occlusion handling; the worker eventually yielded
`repeated_no_effect`. This failure is not relabelled as a success.

That batch was stopped: one failed book-flight episode, one interrupted checkbox
episode with no score, and seven unrun trials. See the
[retained failed/aborted batch](miniwob-grounded-boundary-failure-20260929.json).

A saved-state replay changed to completion review when the delegated task
explicitly stopped at matching options; strengthening the generic reasoning
criterion alone still chose a click. The Skill now requires an explicit
interaction boundary before host comparison/judgment and a concrete host
conclusion on resume. This is a generic delegation contract, not a per-case
benchmark prompt or runtime purchase-selection rule.

## Complete boundary-contract batch

The [complete 3-type × 3-seed batch](miniwob-grounded-boundary-20260929.json)
scored raw reward 1 in all nine first episodes (688.341 seconds total).
Only five completed without host UI actions. This is not nine autonomous Jev
passes: seed 22 required host guidance to confirm city suggestions; seed 66
required host UI repair of those suggestions. Seed 11 reached flight results
autonomously. All three date selections were completed by Jev.

The multi-layouts seed 11 handoff was also defective: the host omitted the genre
input, grounding correctly classified its field as missing, but the runtime
re-offered unrelated prepared values and ended in uncertain_action. The host
filled and submitted the form. Other checkbox/layout trials needed no host UI.

## Further generic fixes and current validation boundary

Native `内容列表` now maps to list. A static-text descendant of an observed
list/listbox that matches the focused editable field's nonempty query is exposed
as `select_option`, distinct from ordinary clicks. Execution still uses the same
native click and target ID. Matching text outside the list is not promoted.
This gives the operation head the meaning of the pending interaction instead of
hiding confirmation among generic labels. Saved-state real API replay through
the actual runtime selected both previously skipped seed 22 suggestions.

When grounding identifies a genuinely missing required input, the runner now
returns the existing field-specific help_input handoff directly instead of
discarding that finding and offering unrelated values again. Real API replay of
the retained multi-layouts failure now returns help_input for the genre field.

The [next live batch](miniwob-options-interrupted-20260929.json) completed seed 11
with first raw reward 1 in 89.737 seconds. Jev confirmed both city suggestions,
navigated the calendar and reached four flight options without host UI repair.
The host ranked options and ultimately clicked the booking button. A Jev resume
with the ranking conclusion instead returned review_completion; that resume is
not counted as successful autonomous booking.

Before seed 22 setup, the installed Computer Use executable became unavailable
and its application bundle disappeared from disk. The process exited with an
infrastructure error. Seeds 22 and 66 were not started. The missing-input fix was
applied afterward; its evidence is saved-state API replay and offline tests only.
Latest-code Flights/Doubao regressions and the remaining live checks are pending
restoration of the native runtime. Older native results in the preceding reports
are not relabelled as verification of this revision.

Current offline checks: 165 runner tests, 22 evaluator tests, clean diff whitespace,
fresh self-contained Skill install, and publication scans. These checks do not
establish the outstanding native acceptance or universal reliability.


## Restored runtime and retained follow-up failures

After the application bundle was restored, the new native plugin version was
26.924.51851. LaunchServices had registered both installed Chrome and its recovery
backup under one bundle ID. Unregistering only the backup restored unambiguous
selection; its files were preserved. The first setup-only attempt had no evaluated
UI actions and is not counted as a task result.

The [next complete matrix](miniwob-restored-development-20260929.json) finished
7/9 first episodes successfully. All three booking searches confirmed cities and
selected dates without host repair. However, seed 22's host delegated the ranking
instruction itself, and Jev chose the wrong flight. The tool's task description
still requested the "whole goal", contradicting the Skill's explicit boundary.
The tool and guidance descriptions now match the Skill: stop interaction before
comparison/ranking/calculation, then receive the host's concrete conclusion.

Multi-layouts seed 66 filled year and director but omitted genre before Submit.
Detailed inspection corrected the initial hypothesis that grounding had not run:
it did run, but classified the unnamed genre field as unrelated. Adjacent labels
were present in click descriptions yet absent from target objects used by the
conditional input/value and grounding questions. The same preserved state chose
Submit with the old target representation, and chose the genre field after adding
its observed adjacent label. Both focused and unfocused target paths now preserve
those labels. No new submit classifier or extra per-click checking loop was added.

One validation launch was interrupted before any evaluated UI action when a new
assertion found the focused-target path was still missing its label. That path
was corrected and all 165 tests passed before the next complete matrix. The
interrupted episode had no score and is not counted as a pass or a task failure.

Further retained runs exposed two additional protocol defects. Grounding could
choose the correct exact input with high confidence, then a repeated value
question would reject that same value without any intervening observation. The
revised input branch now consumes the grounded exact value directly. Grounding
itself now receives the task, prepared values and current field snapshots, not
prior operation choices or the complete action menu. Field labels and the exact
native displayed text stay available. Saved-state probes were mixed while that
context contract was being refined; one successful probe was not treated as
native acceptance.

A separate missing-text handoff spun for 30 rounds because every fresh observation
contained a different countdown. The handoff now reconsiders only if its field,
focus, app/window, or newly selectable controls change. An unrelated timer change
no longer prevents yielding. Tests cover both timer changes and genuinely new
input suggestions. A development API probe also caught a missing model envelope
field in the scoped request; it was fixed before live validation and is covered
by a request-contract assertion.

[Partial development batches](miniwob-restored-partial-20260929.json) preserve
interruptions, helper takeovers, unrun episodes and any official rewards already
observed. These are not folded into a claimed uninterrupted success rate.

## Final complete native MiniWoB matrix

The [final frozen-runtime matrix](miniwob-scoped-final-20260929.json) passed all
nine first episodes with official raw reward 1. Runtime code, Skill entrypoint
and tool schema were unchanged throughout this matrix; only the explanatory
reference was updated while it ran. The report retains the starting source hashes.

| Task | Seed 11 | Seed 22 | Seed 66 |
| --- | ---: | ---: | ---: |
| book-flight | 58.902 s | 43.608 s | 75.214 s |
| click-checkboxes-large | 35.330 s | 58.944 s | 50.562 s |
| multi-layouts | 49.800 s | 41.493 s | 41.200 s |

All three booking searches autonomously confirmed both cities, selected the date
and reached four flight options before their first handoff. The host compared
durations and made the final booking click: exactly one host UI action per booking
run, with no form/calendar/navigation repair. In seed 11, a host resume with its
ranking conclusion returned completion review without booking; the host then
completed that one remaining click. Autonomous resumed booking is not claimed.

All six checkbox/layout episodes required no host UI actions. Multi-layouts seed
11 correctly requested its omitted genre text, accepted the host's added input,
and completed the form itself. The layout cases yielded help_reasoning after
successful submission; their observed rewards and single-episode counters
confirmed success without host repair. Thus 9/9 official passes means hybrid
completion; it does not mean zero host reasoning or zero text handoffs.

The total helper wall time was 455.053 seconds, including host work. These reused
nine cases are acceptance evidence, not a statistical guarantee of universal
stability. Earlier failed and interrupted attempts remain linked above.

## Final Flights and Doubao regression

[Native measurements and final source hashes](scoped-native-20260929.json):

- Google Flights: three consecutive fresh runs passed in 37.121, 37.576 and
  35.618 seconds. Each showed 21 announced/selectable results for Zürich → London,
  October 20, 2026, one way, one adult, economy. Jev selected Chrome, opened a
  new tab, entered the URL and completed the form without host resumption or
  task UI actions. Chrome was already running; cold app launch was not tested.
- Doubao: passed in 17.391 seconds. The final native observation contained the
  sent `你好`, the reply `你好呀😊，有什么可以帮你的吗？`, and an empty compose editor.
  The host supplied the known message initially; no host resumption or task UI
  actions were used. A stale input target was detected and reselected before
  typing, rather than entered into the stale control.

An earlier Flights batch had one successful result-page run followed by
`Sky Computer Use native pipe closed before response`; its third trial did not
start. The failed transport attempt remains in the measurements. A fresh native
connection inspected the current state before starting the final three-run batch;
no uncertain operation was blindly replayed. The earlier first run contained
21 selectable flights but still included loading text in AX; the final three
explicitly announced 21 results. No claim of a flawless aggregate run history is
made by reporting the final successful batch.

Final validation: 167 runner tests, 22 evaluator tests, Skill format validation,
fresh copied-Skill installation, publication scans and clean diff whitespace.
Measurements preceded publication; no deployment was performed, and unrelated
game/content changes were left untouched. The bounded requested acceptance is complete; wider unseen-task
reliability remains outside what these samples establish.
