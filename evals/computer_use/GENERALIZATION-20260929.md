# Native general-task repair and acceptance, 2026-09-29

The final runtime completed three consecutive Google Flights end-to-end trials
and one end-to-end Doubao send without intermediate host guidance, resumption or
host UI actions. This is a small repeated acceptance sample, not a universal
reliability or speed claim. The code contains no Flights/Doubao URL, label,
selector, or prescribed button sequence.

## What changed

- Completion review and reasoning handoff are operations in the same decision
  as UI actions. Removed the competing independent stop head and its wait override.
  The optional continuation threshold sums nonterminal operation probabilities.
- Every question receives the executable targets for each operation in shared
  state. In a retained MiniWoB decision, extra wording alone still selected a
  replacement in the wrong field; shared target capabilities selected the
  read-only date picker instead. The later live run confirmed this first error
  disappeared, but the opened picker still required host intervention.
- Operation and conditional-target questions prioritize current values and unmet
  task constraints. History records attempts, not proof of a button label's effect.
  A retained failure-state API comparison changed `wait` to `click` when operation
  instructions changed, but still selected Search; the matching target instruction
  then selected the incorrect-mode control. This was a read-only decision probe.
- Native AX comboboxes can be editable inputs or choice selectors. A value choice
  can open the existing options control instead of demanding missing authored text.
- Filling an unfocused field first observes its focus transition and uses the
  uniquely matching current editor. A different editor is returned to Jev with
  `input_deferred`; no fill is claimed. This handles fields replaced by popups.
- Focused single-line replacement uses explicit plain-text paste to avoid inline
  autocomplete suffixes. Multiline editors retain native addressed `setValue`;
  caret insertion uses `typeText`. A real multiline paste trial inserted old
  clipboard text; verification stopped before submission. Addressed `setValue`
  was independently checked, then verified in a fresh full Doubao run.
- Full raw observations remain private and complete. Model views prioritize web
  content, keep picker commit controls alongside paged table rows, preserve
  selected state, and expose aggregate option menus through keyboard semantics.
  Async input settling and post-input verification support rebuilt fields.
  Uncertain decisions re-observe changed state before yielding. Unchanged waits
  and two-state action cycles are bounded.

## Google Flights

The final three runs started on a neutral about:blank page in a running Chrome
window. Fixture setup reset our test tab to that neutral page; it did not open
Flights or fill any conditions. Earlier three-run batches selected an existing
unrelated tab instead. Jev selected Chrome,
created a new tab, entered the URL, chose cities and one-way mode, entered the date,
searched and handed back visible flight options. Chrome was already running;
cold application launch was not tested.

Whole task: open Chrome, create a new tab, visit Google Flights, find Zurich to
London flights on 2026-10-20, one-way, one adult, economy; stop at matching options
without selecting or booking. Prepared literals: URL, Zurich, London, ISO date, 1.
No UI plan or mid-run guidance was supplied. The live `jev-latest` endpoint
reported model `jev-1.13.0` in these runs.

| Final trial | Runner seconds | Actual Jev API calls | Visible options | Host intervention |
|---|---:|---:|---:|---:|
| 1 | 36.065 | 24 | 21 | 0 |
| 2 | 34.910 | 22 | 21 | 0 |
| 3 | 46.869 | 34 | 21 | 0 |

All final handoffs show the requested route/date, One way, Economy, “1 adult”,
and actual flight links with departure/arrival details. Trial 3 recovered a temporary site error using the visible Reload control and
returned actual options. It also retained a
Loading results indicator, but already contained 21 flight links; acceptance is
visible matching options, not disappearance of all loading UI. Earlier complete
three-run batches also passed, but used intermediate input-transport revisions.
These times include Jev's navigation, inference, native execution and waiting;
exclude outer fixture setup and independent final verification. They are not
comparable to a demo that starts after page navigation.

## Doubao

Final trial: 18.354 seconds, 11 Jev API calls, zero host resumption/guidance/UI
intervention. Starting on an unrelated tab, Jev opened a new tab, entered the URL,
waited for the page, filled “你好”, submitted, and handed back the new message plus
“你好呀！有什么可以帮你的吗？” and an empty message editor. An earlier passing end-to-end run also rejected and re-observed a changed target
during page loading before typing.

Earlier runs are retained: URL autocomplete mismatch; uncertain action during
page load; a send from an already-open page (not a navigation pass); and multiline
clipboard text mismatch stopped before submission. A prior guest-quota/login
block from an earlier revision does not describe the later successful live state.

## MiniWoB++

The first full batch passed 9/9 official scores, with 6/9 completed without outer
UI actions. All three book-flight cases required host intervention. This batch is
retained in [development measurements](miniwob-generalization-development-20260929.json).
After the shared-target repair, the final full batch also passed 9/9 against pinned Farama source
`33c3b4ddef8c6eb67c57a29663d844b1eda7e614`, using the existing general Skill arm
(native AX, real Jev, outer gpt-5.6-sol/medium), cases `click-checkboxes-large`,
`multi-layouts`, `book-flight`, and seeds 11, 22, 66. The deadline is 300 seconds,
not the standard 20–30-second leaderboard protocol. Pass requires the official
first episode raw reward of 1, exactly one episode, and the harness scope checks.

[Final measurements](miniwob-generalization-final-20260929.json):

| Task | Seed 11 seconds | Seed 22 seconds | Seed 66 seconds | Official passes | Runs without outer UI actions |
|---|---:|---:|---:|---:|---:|
| click-checkboxes-large | 65.738 | 65.067 | 65.084 | 3/3 | 3/3 |
| multi-layouts | 79.767 | 53.786 | 60.904 | 3/3 | 3/3 |
| book-flight | 129.393 | 105.771 | 118.351 | 3/3 | 0/3 |

All nine used exactly one episode, received official raw reward 1, and passed
scope and telemetry audits. Times are whole evaluated-agent runs, excluding
fixture setup; they include outer planning and verification, so they are not
Jev-only inference times. There were 54 executed Jev operations and 28 outer UI
tool calls; a tool call can contain multiple actions, so these are not comparable
units for an action-share percentage.

The remaining limitation is explicit: all three book-flight runs correctly
filled the cities and opened the read-only date picker, then requested input
help instead of navigating the calendar. The host performed 9, 8, and 11 UI tool
calls respectively to finish those runs. Choosing the shortest itinerary also
requires host reasoning under this Skill protocol, but the earlier calendar
handoff is unnecessary and remains unresolved. The shared-target repair removed
the previously observed date-into-city-field error; it did not improve the
number of runs completed without outer UI actions.

The other six runs had no outer UI actions, but still used outer planning,
prepared inputs and final verification. In particular, multi-layouts seed 11
needed a second delegation after an input-help handoff. Thus neither 9/9 official
success nor 6/9 without outer UI actions means nine or six fully independent,
uninterrupted Jev runs. The runtime was unchanged throughout the final batch.

The first initialization attempt failed before an evaluated agent started:
Chrome's new-tab page exposed more than one text field. Setup now selects the
actual focused field after Cmd+L rather than requiring one input in the entire
window. This changes fixture initialization only, not Jev or benchmark pages.

## Retained evidence and validation

[Sanitized per-run measurements](generalization-20260929.json) retain development
failures, existing-result short-circuits (excluded from navigation acceptance),
intermediate passes and the final acceptance runs. Full native/model traces and
credentials remain outside Git. No failed trial was discarded or relabelled as a
pass because a subsequent run worked.

Validation: 156 runner tests, 22 evaluator tests, Skill validation, publication
scan and whitespace checks. A fresh copied Skill installation was also checked.
