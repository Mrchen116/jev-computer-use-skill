# Setup and optional controls

`SKILL_ROOT` is this Skill's directory. Requires Python 3.9+, macOS, and running
Codex desktop with Computer Use installed and normal permissions; no pip packages.
Check with `python3 SKILL_ROOT/scripts/run.py --doctor`. Keep credentials and task
logs outside Git; use a private key file or `TYPESAFE_API_KEY[_FILE]` environment variable.

## Optional MCP

Start the server with:

```sh
python3 SKILL_ROOT/scripts/mcp_server.py --hybrid \
  --key-file /private/typesafe-key --journal /private/jev-native.jsonl
```

For a Codex server named `jev`, merge these settings, preserving other namespaces:

```toml
[features.code_mode]
direct_only_tool_namespaces = ["mcp__jev"]
[mcp_servers.jev.tools.delegate_task]
output_token_limit = 60000
```

Use your registered server name. This exposes `delegate_task`, `read_task_history`
and native `js`/`js_reset` sharing one session; handoff returns its existing app
binding and complete current UI. The output budget avoids premature truncation;
host context limits still apply.

## CLI and progress

Without MCP, save a request JSON and start it using a long-running shell tool:

```json
{"task":"Find 王明 and open the conversation for review.","mode":"step","input_texts":{"contact":{"text":"王明","purpose":"Contact name to search for"}}}
```

```sh
python3 SKILL_ROOT/scripts/run.py task --request-file /private/request.json \
  --state-dir /private/jev-task --key-file /private/typesafe-key
python3 SKILL_ROOT/scripts/run.py task --state-dir /private/jev-task --status
python3 SKILL_ROOT/scripts/run.py task --state-dir /private/jev-task --stop
python3 SKILL_ROOT/scripts/run.py task --state-dir /private/jev-task \
  --complete --answer-file /private/verified-answer.txt
```

Use an interactive terminal for CLI runs that may request native app access.
The CLI remembers an explicitly approved, identical empty app-access form only
within that process; other forms and new processes still require approval.
Prompts go to stderr so stdout remains machine-readable JSON.

Status includes all concise history, usage, warnings and `history_location`;
`--status --wait 20` waits for progress without model/UI calls. Stop is cooperative:
wait for exit before takeover. `--complete` records your verified verdict only.
Resume with the same directory and a JSON containing `mode` plus new guidance or
inputs. Unlike MCP, CLI cannot transfer JS bindings between processes: bind the
already-open app once only if further native actions are needed.

## Optional request fields

| Field | Default / meaning |
|---|---|
| `period_ms` | 1000; 100–30000, realtime minimum cycle spacing; overruns warn, do not queue. |
| `recheck_target` | true; changed window/target/focus or new choices at a focused input trigger a fresh decision. Other text changes only warn. |
| `max_steps`, `max_seconds` | 100, 300 per invocation; history and usage persist. |
| `min_continue_probability` | 0.5; low continuation score yields before acting. Not a calibrated guarantee. |
| `max_context_bytes` | 100000; the UI is paged first; oversized history or an individual page still hands back the full UI before calling Jev. Usually omit. |
| `pricing` | Optional verified USD/M Jev `input_tokens` and `output_tokens` rates. Missing cost is unknown. |

For older screens, `read_task_history(state_dir, observation_ids=[...])` reads saved
observations; optional `contains` filters literal lines for your read, not Jev's
context. Follow `next_offset` if truncated. `kind=decision` exposes diagnostics.
All current UI and concise history remain available to Jev; this reference does
not require the outer agent to generate rules, questions or action menus.

The runner asks for an operation type and conditional compatible targets in one
Jev request. Shared state includes the available targets for every operation,
because the operation head must know which controls each operation can actually
use. Only the chosen operation's target is consumed. For input, a second
Jev choice selects an exact prepared value, rejects an incorrectly selected field,
or asks for genuinely missing task-required text. On input rejection, Jev grounds
all currently offered input fields against the task and supplied values in one
batched question: already satisfied, unrelated, a specific required value, or
missing text. A missing required value immediately returns a field-specific
`help_input`; it is not re-offered unrelated prepared values. Satisfied/unrelated
fields leave this decision's input menu; other fields keep only the selected value. The revised
operation decision receives these field statuses and matching capabilities.
A revised input operation uses the exact value already selected by grounding;
it does not ask the same value question again without a new observation. There is no
text-generation model. Very large target/value lists
use lossless groups. Operation selection retains the full concise history. The
field-grounding subquestion receives the task, supplied values and observed field
snapshots only, so prior action choices do not stand in for current field state.
Every actual request/response is logged. Field/value combinations remain internal
to execution.
Observed adjacent field labels are carried in the target object as well as the
click description, so conditional field/value and grounding questions retain
that context even for unnamed inputs.

Completion review and reasoning handoff are operations in the same choice as UI
actions; there is no independent stop head that can contradict the chosen action.
The continuation threshold applies to the summed probability of nonterminal
operations. The minimum selected
operation/target/value score below 0.5 receives one factored decision review.
A reviewed mutation still below 0.3 yields `uncertain_action` without execution.
These conditional scores are not a joint probability or correctness guarantee.

The model sees current web content before browser chrome, with lossless pages for
large trees. Repeated table rows are paged while nearby dialog controls remain
visible. Raw observations stay complete in logs and the handoff. Input actions
focus an unfocused field and re-observe its identity before entering text, because
focus may open a replacement editor. A uniquely matching editor can be filled;
otherwise only the focus change is recorded and Jev sees the new state before
choosing text. Focused single-line replacement uses explicit plain-text paste;
multiline editors use native setValue, and caret insertion uses typeText.
Post-input verification reads the displayed
value; asynchronous suggestions receive a bounded settling interval. Repeated
unchanged waits and two-state action cycles yield instead of consuming the budget.
History records attempted operations and observed effects, not proof that a button
achieved the outcome described by its label. Current constraints take precedence.

Conventional English month grids are recognized from a month/year heading and
all seven weekday headers. Numbered day links retain their native IDs but gain the
observed full date; previous/next-month links gain their resulting month/year.
Ambiguous or unrecognized tables remain unchanged. An already-open grid's focused
read-only field and adjacent label do not offer redundant reopening clicks. This
is an AX description adapter, not a prescribed navigation sequence; Jev still
chooses every month/day action, and native execution/fresh-target checks remain.

Operation and conditional-target questions both distinguish typed autocomplete
queries from confirmed values: select the matching visible suggestion before
leaving the field. Literal input verification alone does not establish selection.
Matching static-text descendants of an observed list/listbox are exposed as
`select_option` when an editable field has a focused nonempty query. They execute
the existing native click; matching text outside a list remains an ordinary click.
