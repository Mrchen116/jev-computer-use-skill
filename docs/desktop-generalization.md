# Native desktop generalization follow-up — 2026-09-29

The motivating tasks were sending a greeting in Doubao and finding a named solar term in Calendar before creating a timed event. No app name, URL, holiday lookup table, fixed UI index, or per-task click sequence was added to the executor or policy.

## Shared capability changes

- Editable capabilities survive unfamiliar/localized AX roles; field context includes values and adjacent labels. Unfocused fields can be addressed directly.
- Prepared literal pieces can be appended to existing text. Dates observed in the UI retain their source labels and can be reused without the caller resolving the holiday.
- Native date/time input and verification preserve the requested value across display formats. Verification handles AX index changes after a form rerenders.
- Large UI trees and accumulated observed dates are navigable in pages. Large action sets are grouped by operation/field instead of arbitrary positional chunks.
- Form-value matching stays with Jev; ranking, calculation and open-ended synthesis still yield. The default continuation cutoff is 0.5 instead of 0.9; explicit pause/help decisions and target/input checks remain.
- Ineffective text clicks are suppressed on the same observed screen. Loading transitions can settle before yielding for low confidence.
- The CLI reuses only an explicitly approved identical empty app-access form within one process and emits prompts on stderr.

## Real integration evidence

These are development acceptance runs, not an independent benchmark or a reliability estimate. Jev used the native Computer Use transport and `jev-latest` (reported `jev-1.13.0`). The host prepared known task literals, approved requested app access, reset test fixtures between attempts and verified the returned UI. Successful runs had no host UI action or reasoning guidance in the middle. Calendar received no resolved holiday date.

- `doubao8`: from a blank Chrome tab, navigate to Doubao and send the supplied greeting. Passed: the conversation contained the sent text and the composer was empty. 12.307 seconds of active runner time, 9 history records including host inputs and final review.
- `calendar8`: from Today, find 2026 立冬 in Calendar and create 回家, 05:00–06:00. Passed: UI source showed November 7, 2026; the created event showed that date, 5:00 AM–6:00 AM, all-day off. 47.505 seconds, 16 history records. The host subsequently checked the native fields. One requested event is retained.

Earlier attempts are not counted as passes: missing editable roles, excessive model requests, omitted focus, stale field indices, repeated title/date replacement, invalid native time syntax and positional action grouping caused handoffs. `calendar7` reached the right fields but began with development state; `calendar8` was the clean restart.

A stronger variant changed the term, year, title and times (2027 小雪, 07:30–08:15). It navigated to the UI date but hit accumulated-input capacity. After pagination it still yielded while selecting inputs and toggled all-day incorrectly. **This variant did not pass.** The temporary incorrect event was removed. Input pagination has offline coverage, not a successful long-horizon live acceptance claim. Long histories can still exceed the request budget, and Jev can choose the wrong action or handoff. The two passed cases do not establish reliable arbitrary desktop autonomy.

Raw native/model journals remain private outside the repository, under `/tmp/jev-general-acceptance-j0wkjf8g`. Final-version retest and validation results are recorded below.

- Final-version `doubao9` repeated the blank-tab test with the default 100,000-byte request limit. Passed in 13.822 seconds, 8 history records; sent greeting visible and composer empty. No host intervention during the run.

The subsequent `calendar9` clean retest failed: after setting 5:00 AM, the UI already showed 6:00 AM as the end and all-day off. Jev chose the all-day checkbox anyway (action probability 0.20, reported confidence 0.19), while its separate continuation probability was 0.95. Only continuation was gated, so the wrong low-confidence click executed. Neither the user task nor the start/end inputs were missing. This falsifies a claim of stable Calendar success from the previous passing runs.

The runner now reviews a diffuse action choice once against a small candidate set, independently of continuation. A still-diffuse mutation returns `uncertain_action` without execution. Checkbox choices describe check/uncheck transitions, and typed date fields exclude non-date literals. A score threshold cannot catch confidently wrong actions; real regression results follow.

`calendar10` initially yielded on a reviewed navigation choice (0.49 for the date label, 0.31 for Search), without mutation. The review trigger remains 0.5; after narrowing candidates, the stop cutoff is 0.3. These are heuristic ambiguity bounds, not calibrated reliability thresholds. The initial yield is retained as a failed uninterrupted run.

Final fixed-version `calendar11` ran from Today without mid-run host UI or reasoning intervention and reached the correct requested event fields in 56.076 seconds: November 7, 2026, 5:00–6:00 AM, all-day off. It then selected Tab at 0.26; candidate review selected the all-day checkbox at 0.26 (completion 0.24). The runner returned `uncertain_action` and **did not execute that checkbox change**. The host verified the correct result from the handoff and native UI. This is a completed task result with host final verification, **not evidence that Jev reliably recognizes completion itself**. The wrong-choice tendency persists; the guard preserves the result in this run.

Validation: 133 project tests, 22 evaluator tests, Skill schema validation, `git diff --check`, and the publication scan. Synthetic tests include unrelated field names, date/time values, checkbox labels, AX renumbering and high-continuation/low-action decisions. They test protocol contracts, not model generalization.

Final `doubao10`, including the action-review change, passed from a blank tab in 15.376 seconds (10 history records). The greeting appeared in the conversation, the composer was empty, and Jev yielded for final review. No host UI action or guidance occurred during execution.
