# Current general task protocol

Latest follow-up: [field grounding, calendar/list semantics, and native acceptance](../evals/computer_use/GROUNDED-ACTIONS-20260929.md). The final MiniWoB matrix passed nine first episodes: booking navigation was autonomous, with host ranking/final booking and one legitimate missing-text handoff. Earlier failures and interrupted runs remain recorded.

Earlier: [input-branch rejection and unresolved calendar handoff](../evals/computer_use/RESELECTION-20260929.md).

Previous: [2026-09-29 native general-task repair and acceptance](../evals/computer_use/GENERALIZATION-20260929.md), including retained failures and end-to-end Flights/Doubao evidence.

See the [native desktop generalization follow-up](desktop-generalization.md) for Doubao/Calendar acceptance, shared capability changes, and an explicitly failed cross-year variant.

The default Skill/CLI/MCP route uses tasks.py, decisions.py and computer.py. Tests in tests/test_tasks.py cover full history and AX context, focused prepared inputs, separate submission, host input/reasoning resumption, cross-app state, progress/log detail, cooperative stop, optional target rechecking, capacity handoff and uncertain mutation without replay. These protocol tests do not establish Jev task success rates.

The factored decision protocol is covered by `tests/test_decisions.py`: separate
operation/target heads, only the selected branch consumed, per-field exact-value
selection with a missing-text option, pause/stop before a follow-up model call,
and native date/time compatibility. A 12-field/16-value fixture exposes 12 input
targets followed by 16 values plus handoff, instead of 192 concrete input choices.
The executor retains concrete actions internally for identity checks. The complete
30-step fixture history is preserved. Task-loop tests also cover target lists over
255 choices without silent truncation. This changes the decision protocol, not the
observation parser or history retention policy.

On 2026-09-29, four real Jev API probes over synthetic AX observations selected
the intended input field/value (two calls), Apply click, missing-text handoff and
completion review (one call each). In that earlier protocol, the missing-text probe action head chose
`help_input` while the pause head chose `help_reasoning`; the runner would honor
the latter and still return to the host without typing. The latest repair removes
that competing pause head; completion and handoff are now operation choices.
A real-Jev/ simulated-form loop filled `hello`, clicked Apply and proposed review
in four API calls. These checks used the actual request validation and task loop,
but did not operate native Doubao or Calendar.

Retained failure: an earlier loop using the existing unit-test computer requested
Return submission, but Jev clicked its Apply button and then waited to the eight-
step budget (nine API calls). That test double only implements Return submission,
so Apply never produced a result. The later form implements its displayed Apply
button and uses a click-Apply task. No runtime fix was made for this separate
instruction-following/waiting failure; neither this failure nor the later success
establishes native app reliability. Private requests and responses remain outside
Git. Validation at that earlier snapshot: 139 runner tests and 22 evaluator tests passed;
the latest report records 156 runner tests and 22 evaluator tests.

Two real Jev + native CUA checks passed on an isolated local fixture: prepared text through final review (15.35 s), and missing-text handoff → caller supplies text → separate CLI process resumes with complete history → realtime mode → host completion (18.84 s active time). The first setup attempt correctly handed back from the wrong foreground window; the harness was fixed before the passing runs. See [sanitized evidence](general-task-verification.json). These are integration checks, not the requested representative benchmark or evidence of a cost advantage. Current validation is recorded in the follow-up below. The subsequent real general-protocol run completed all 8 answer checks, but was slower and more expensive than the reused baseline; two requests lacked billing data and one navigation left its granted public-site prefixes. See [development comparison](../evals/computer_use/general-development-comparison.json). It does not establish savings.

Current handoff regression tests exercise the real MCP/task runner with the
external native runtime and Jev replaced by doubles. They verify one live native
session through delegation, host takeover and resumption; an existing app binding;
documentation replay after an explicit reset; inline full UI without a duplicate
JSON copy; capacity handoff without another observation/model call; and a refresh
flag after uncertain execution. An offline replay of the retained pathlib page
preserved all 120,537 characters (127,114 UTF-8 bytes) in one content block. These
checks did not operate Chrome. They are now supplemented by the real Chrome
handoff follow-up below; offline checks alone did not expose the host wrapper's
output truncation.

## Runtime and real-web follow-up, 2026-09-23

R15 completed 9/9 MiniWoB trials with complete billing: $1.048699 / 374.28 s,
versus historical native $2.216530 / 608.30 s (52.7% cheaper, 38.5% faster).
CLI version drift prevents strict matched-runtime acceptance. R13/R14 intermediate
batches, the same-request transport probe and source archives are retained.
The separate R14 four-site batch passed 4/4 but was only 7.9% cheaper and 12.3%
slower; one issue lookup used host screenshots. Realtime scored 12/12 with
1.21–1.52 s reactions. No native control was rerun and no game saving is inferred.
See [measurements and limitations](../evals/computer_use/MINIWOB-RUNTIME.md).

Regression coverage includes real local HTTP/1.1 reuse without automatic POST
retry, step/realtime observation cadence, delayed input options, deferred native
documentation at completion, and strict comparison of the unchanged native MCP
path. Validation at R15: 113 project tests + 22 evaluator tests.

## Skill simplification follow-up, 2026-09-22

The shorter Skill completed 9/9 real MiniWoB trials. First-response Sol input and
output tokens fell 13.1% and 28.7% versus R07. Two Jev transport failures required
host recovery and left total billing unknown; elapsed time increased. The complete
batch, partial development failures, source verification and retained limitations
are in [the follow-up report](../evals/computer_use/MINIWOB-SLIM-SKILL.md).
Validation at that milestone: 107 project tests and 20 evaluator tests, plus Skill validation.

## R07 MiniWoB++ multi-step follow-up, 2026-09-22

The routing-repaired general Skill and native Sol/medium each completed 9/9
trials across `click-checkboxes-large`, `multi-layouts` and `book-flight`.
Native total: 608.30 seconds / $2.216530. Skill total: 548.90 seconds / $1.658808
($1.642125 Sol and $0.016683 Jev): **25.2% lower cost and 9.8% less total time**.
The 50% cost-reduction target remains unmet.

All six checkbox/form trials used exactly two outer LLM requests and no
intermediate LLM/UI intervention. That subset was 25.7% cheaper with only 2.1%
less time. Native batching can complete a visible form in one action call; Jev
still makes serial per-step decisions. The Skill routing fix removed the two
previous failed wrapper calls, but flight takeover cost increased in the fresh
run. Both results are retained; improvement is not assumed from a code change.

This uses original benchmark pages/rewards with a **300-second deadline**, not
the standard 20–30-second protocol. Source archives, generated queries, model
usage and native traces were verified. See the
[matched comparison and cost breakdown](../evals/computer_use/MINIWOB-COMPARISON.md).
Earlier failures and a real high-confidence terminal-state misjudgment remain in
[the development results](../evals/computer_use/MINIWOB-RESULTS.md). The small,
reused-seed sample does not establish universal desktop reliability.

## Real handoff follow-up, 2026-09-22

Four development iterations ran the same two public tasks with real Sol/medium,
Jev and native Chrome, reusing the existing native baseline. The final candidate
completed both tasks. All five handoff trees matched the model-visible output
verbatim; current-screen history rereads, output truncations, native rebinds and
native execution errors were all zero. Research read one earlier pytest page
from history, which avoided returning to that page.

The final document task took 142.15 s / $0.384037; research took 131.69 s /
$0.568515. Total $0.952551 / 273.83 s versus the historical baseline's $0.841692 /
223.68 s means **13.2% more cost and 22.4% more time**. Handoff continuity is
verified; the cost target is not met. Costs include the complete outer LLM usage
and Jev input at the frozen comparison rates. See the
[token-level report and handoff audit](../evals/computer_use/handoff-live-comparison.json).

Failures are retained: [first run](../evals/computer_use/handoff-development.json)
had wrapper truncation and an unauthorized New Tab click followed by recovery;
[prompt-only follow-up](../evals/computer_use/handoff-prompt-followup.json) still
truncated the UI; [direct-tool follow-up](../evals/computer_use/handoff-direct-followup.json)
delivered the whole UI but still reread it once. The final candidate uses direct
MCP exposure with a configured output budget and places handoff instructions
after the complete tree. Remaining measured waste includes late preparation of
known input strings and extra fine-grained source-link verification.

## Historical measurements

Everything below describes the older stage/discovery implementation. Its cost and completion figures do not measure the current general task loop. The benchmark runner explicitly selects --legacy-stages for reproduction.

# Verification scope

## Native comparison suite

The [five-case protocol](../evals/computer_use/PROTOCOL.md) defines resettable
public website tasks plus a synthetic real-time game, independent judges, native Codex Sol/medium and Jev treatment,
paired seeds, real token pricing, and the intended 50% aggregate cost target.
Development runs are not the frozen evaluation. Native journals and auth material
remain outside the repository; only sanitized measurements may be published.
The [frozen results](../evals/computer_use/RESULTS.md) report 8/8 success in each
web arm, 58.2% aggregate API-equivalent cost savings and 4.9% less total time.
Two final hybrid-only realtime games both achieved 12/12 with no misses or wrong
tools, and 1.50–2.27 s reactions. The historical failed native realtime attempt
was not rerun; no paired game cost advantage is inferred.
The [development status](../evals/computer_use/STATUS.md) retains earlier missed
targets, the issue-lookup cost regression and infrastructure failures.

Additional offline checks cover stage URL boundaries, evidence retrieval without
reopening UI, correct treatment of repeated controls on new pages, no replay after
uncertain execution, private archive permissions, independent fixture judges and
cached/reasoning-token cost arithmetic. Native URL-elision checks recognize the
unfocused browser address without making browser chrome or page-owned address
fields actionable. Mode tests cover host-controlled cycle spacing, no queued catch-up, changed-state
and slow-decision warnings without discarding valid actions, optional target reads,
progress during pending inference, cooperative stop without late clicks, no-op
waiting and retained evidence across a host-selected mode switch.
Text-view tests require complete multilingual character coverage within the byte
budget and collection from a later view without UI actions. Input-option tests
cover sequential alternatives, explicit submission, value verification, ambiguous
fields, cancellation and uncertain submission without replay.
Multi-site tests cover strict scope membership, benchmark grants covering every
requested prefix, collection across observed links and supplied destinations,
rejection before UI access, and no replay after uncertain navigation.

## Offline checks

```sh
python -m pip install .
python -m unittest discover -s tests -v
python scripts/check_release.py
```

These cover native AX parsing, source evidence retention, tab/control paging, factual history, metadata-only reports, model response validation, text-helper budgets and key exclusion, temporary response cleanup, runtime manifest discovery, and a synthetic end-to-end policy loop. The uncertain-action case verifies that a failed mutation is not replayed or declared complete.

Host handoff tests run a live worker thread through input and completion requests, supply replies through the real file interface, and make constructing a Codex text helper fail. They also reject stale IDs/wrong types, check private file permissions, cancellation, timeout and bounded help. They do not simulate host reasoning quality.

Offline tests use fake model responses/desktop state. They do not establish compatibility with a live Codex installation or Jev service. The release scan checks tracked files for common credential formats, developer home paths and private runtime artifacts; it is not a comprehensive secret detector.

## Native smoke, zero model calls

```sh
python -m jev_computer_use.smoke
```

This operates real Chrome through native CUA, opens a new tab with the packaged synthetic fixture, fills a field with mixed English/Chinese text, clicks a local button, and independently checks the output. It leaves the tab open. No Jev or text-LLM call is made. The printed JSON contains counts and a synthetic outcome, not the user's application inventory.

Use this on macOS with Codex desktop open and normal permissions available. `--doctor` does not replace this check.

## Paid task run

```sh
jev-computer-use 'Open the demo page, fill Test message with native test, click Apply locally, and report the result' --helper codex --local-demo --max-steps 18 --max-llm-calls 8
```

The fixture's URL is a supplied fact; the agent still begins from the app inventory and chooses its own actions. The command requires valid credentials and may invoke the text helper. Only the local fixture is synthetic: the surrounding browser is the real user's application.

For the primary Skill path, run its `scripts/run.py` with `--exchange-dir` and `--local-demo`, then service handoffs exactly as described in [SKILL.md](../skills/jev-computer-use/SKILL.md). No internal text helper should be launched. Do not count waiting for the host as model inference time or turn handoff count into a token-cost estimate.

## Development evidence

[navigation-and-context-verification.json](navigation-and-context-verification.json)
records six real native navigations and a real Jev request against saved public
document text. The subsequent [host follow-up](../evals/computer_use/paging-navigation-followup.json)
passed research, issue lookup and the realtime game. These isolated repairs and
hybrid-only runs do not establish paired cost savings. Frozen comparisons and
their failed targets remain in the [evaluation status](../evals/computer_use/STATUS.md).

[input-options-verification.json](input-options-verification.json) records a real
seven-candidate search through native Chrome: six nonmatching candidates followed
by a matching seventh, without an outer-model handoff between inputs. The earlier
premature-help probe is retained. The next whole-task comparison failed one issue
attempt during outer-agent screenshot/drag recovery and is preserved in
[input-options-frozen.json](../evals/computer_use/input-options-frozen.json), with
unknown aggregate cost instead of excluding that failure.

[control-verification.json](control-verification.json) records the sequential-loop
Skill pilot with real Sol/medium, Jev and native CUA. A real CLI control smoke also
reads aggregated warnings during inference, requests stop without executing the
pending action, then switches to step while retaining evidence. Earlier designs
and failures are kept separately. These are functional checks, not a frozen paired
cost benchmark or a claim of universal realtime performance.


[skill-verification.json](skill-verification.json) records the 0.2.0 host-handoff test from a copied, self-contained skill outside the repository, without pip installation. Codex acted as the external host and answered the real runner's requests. The synthetic form task used 8 decision rounds, 14 Jev requests, 4 host handoffs and 20 CUA calls; no standalone Codex text helper was used. One stale decision was discarded. Host waiting includes time spent editing documentation during the run, so its wall time is not a latency benchmark. Other host agents have not been individually tested.

[development-samples.json](development-samples.json) contains sanitized counts from the pre-packaging prototype. Original private traces stay outside the repository.

| Sample | Outcome | Decision rounds | Jev calls, including risk | LLM calls | Wall time |
| --- | --- | ---: | ---: | ---: | ---: |
| Public input-method project lookup | Completed | 8 | 14 | 3 | 71.54 s |
| Synthetic Chinese field + local button | Completed | 8 | 14 | 6 | 105.61 s |

Environment: macOS, installed `unified-computer-use` plugin `26.915.31945`, Jev API, configured Codex CLI helper. The main helper model was not pinned. These cases were run during development, not randomized repetitions on the packaged release. The first run encountered stale/frameless actions before additional execution checks were added; the second passed after native field replacement was adopted.

An isolated input probe found dropped characters with `typeText`; three direct `setValue` attempts, including Chinese, matched the requested value. The backend now checks the observed field value after every fill. This does not imply every app implements AX value assignment identically.

See [release-verification.json](release-verification.json) for the historical 0.1.0 package checks; current packaging checks are recorded in [release-0.3.0.json](release-0.3.0.json). No comparison here establishes general task success rate, all-app support, or cost/speed superiority over another agent.
