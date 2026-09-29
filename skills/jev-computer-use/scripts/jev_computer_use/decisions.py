"""Factor operation, target and prepared text without exposing their product."""

import json

AUTOCOMPLETE_RULE = "A typed autocomplete query is not a confirmed option. When suggestions are visible, select the matching option before leaving the field."


class DecisionRejectedError(ValueError):
    """Input selection rejected both the initial and revised operation."""


class DecisionCapacityError(ValueError):
    """A decision cannot fit the configured provider/request limits."""


def operation(key, action):
    return action.get("semantic_operation") or ("append" if key.startswith("append_") else action["type"])


def action_space(actions):
    """Group concrete executor actions by operation and compatible target."""
    space = {}
    for key, action in actions.items():
        kind = operation(key, action)
        target = "field_" + action["target"]["id"] if "text_id" in action else key
        space.setdefault(kind, {}).setdefault(target, {})[key] = action
    return space


def target_choices(targets):
    choices = {}
    for target, candidates in targets.items():
        action = next(iter(candidates.values()))
        if "text_id" in action:
            # Context stays in the observed tree; do not repeat every field/value pair.
            choices[target] = action["target"]
        else:
            choices[target] = action["label"]
    return choices


def bounded_question(criteria, instructions):
    if len(criteria) > 255:
        pairs = list(criteria.items())
        criteria = {f"group_{i // 255}": dict(pairs[i:i + 255]) for i in range(0, len(pairs), 255)}
        instructions = [instructions, "Choose the group containing the required target; its exact target will be selected before execution."]
    if len(criteria) > 255:
        raise DecisionCapacityError("Target selection exceeds 255 groups")
    return {"type": "choice", "instructions": instructions, "criteria": criteria}


def decision_questions(actions, instructions):
    """Ask operation and conditional targets together; consume one target head."""
    space = action_space(actions)
    descriptions = {
        "select_option": "Select a matching item from the current input field's visible suggestions before leaving that field.",
        "click": "Click a visible control", "replace": "Replace a field with a prepared value",
        "insert": "Insert a prepared value at the current caret/selection",
        "append": "Append a prepared piece to the observed field value with a space",
        "key": "Press a key at the current focus", "scroll": "Scroll a visible region",
        "switch_app": "Switch to an application", "view_page": "Read another UI page",
        "input_page": "Read another page of retained UI values",
    }
    questions = {"operation": {
        "type": "choice", "instructions": [AUTOCOMPLETE_RULE, *(item for item in instructions if item != AUTOCOMPLETE_RULE)],
        "criteria": {kind: descriptions.get(kind, next(iter(next(iter(targets.values())).values()))["label"])
                     for kind, targets in space.items()},
    }}
    for kind, targets in space.items():
        if kind in descriptions:
            questions["target_" + kind] = bounded_question(target_choices(targets), [AUTOCOMPLETE_RULE,
                "Compare every requested constraint with CURRENT field values. Choose a control to correct a mismatch before submitting the form. Prior button labels describe actions, not their achieved effects.",
                f"Assuming the next operation is {kind}, which compatible target best advances state.task NOW? This is conditional; only the chosen operation's target will be used.",
                "Use the current observation, field labels, values and adjacent text. For input operations, only choose a field when an available prepared value matches its purpose. A combobox may be a choice selector: click it to choose an option rather than request authored text. Resolve an open picker before moving to unrelated controls. Input text is chosen only after its target is fixed; do not assume other questions' answers.",
            ])
    return questions


def ask_decision(jev, payload, actions, record, max_bytes, cancelled, *, reconsidered=False):
    """Resolve one concrete action; all requests and responses remain in the log."""
    seconds = 0

    def ask(request, phase):
        nonlocal seconds
        size = len(json.dumps(request, ensure_ascii=False).encode())
        if size > max_bytes:
            raise DecisionCapacityError(f"Decision requires {size} bytes, above {max_bytes}")
        response, elapsed = jev.ask(request)
        seconds += elapsed
        record(phase, request, response, elapsed)
        return response

    def score(answer):
        return answer.get("probabilities", {}).get(answer["choice"], answer.get("confidence", 0))

    response = ask(payload, "operation_target")
    answers = response["answers"]
    space = action_space(actions)
    kind = answers["operation"]["choice"]
    targets = space[kind]
    scores = [score(answers["operation"])]
    # Stopping is an operation, not a competing independent decision head.
    terminal = {"review_completion": "pause", "help_reasoning": "help_reasoning"}
    distribution = {"continue": 0.0, "pause": 0.0, "help_reasoning": 0.0}
    for option, probability in answers["operation"].get("probabilities", {}).items():
        distribution[terminal.get(option, "continue")] += probability
    pause = {"choice": terminal.get(kind, "continue"), "probabilities": distribution}
    target = next(iter(targets))
    head = "target_" + kind
    if head in payload["questions"]:
        answer = answers[head]
        scores.append(score(answer))
        target = answer["choice"]
        criteria = payload["questions"][head]["criteria"]
        if target not in targets:
            request = {**payload, "questions": {head: bounded_question(criteria[target], [f"Select the exact {kind} target in the chosen group."])}}
            # A pause/stop must not spend another call merely to finish an unused head.
            if pause["choice"] != "continue" or cancelled():
                return None, pause, {}, seconds
            answer = ask(request, "target_group")["answers"][head]
            scores.append(score(answer))
            target = answer["choice"]
    candidates = targets[target]
    selected = next(iter(candidates))
    if "text_id" in candidates[selected]:
        if pause["choice"] != "continue" or cancelled():
            return None, pause, {}, seconds
        grounded_field = payload["state"].get("input_field_status", {}).get("field_" + candidates[selected]["target"]["id"])
        if reconsidered and len(candidates) == 1 and grounded_field and grounded_field["status"] == "input_" + candidates[selected]["text_id"]:
            # Grounding already chose this exact value against this observation.
            # Asking again can contradict the decision without new evidence.
            return selected, pause, {selected: min(*scores, grounded_field["confidence"])}, seconds
        values = {key: {"text_id": action["text_id"], "result": action["text"],
                        "purpose": payload["state"]["input_texts"][action["text_id"]]["purpose"]}
                  for key, action in candidates.items()}
        # Even when supplied values exist, none may be appropriate for this field.
        values["reselect_action"] = "The selected field/operation is wrong or its required value is already satisfied. Return to action selection without entering text."
        values["help_input"] = "This field really needs a new value required by the task, but that value is absent from all supplied inputs and the UI. Ask the outer agent for that missing text."
        target_field = next(iter(candidates.values()))["target"]
        if target_field["role"] == "combobox":
            values["open_options"] = "This field selects from options, not authored text. Open its options to select the task-required value."
        request = {**payload, "state": {**payload["state"], "selected_operation": kind,
                                       "selected_target": next(iter(candidates.values()))["target"]},
                   "questions": {"input_value": bounded_question(values, [
                       "Choose the prepared value whose purpose matches the selected field and task. Check whether this field actually needs changing before choosing text. Choose reselect_action if the field already satisfies the task or another control must be used; absence of a matching candidate for a wrongly selected field is not missing user input. For a choice selector use open_options to reveal its choices. Choose help_input only if this field must change and its required text is genuinely unavailable. Do not author new text."])}}
        answer = ask(request, "input_value")["answers"]["input_value"]
        selected = answer["choice"]
        if selected not in values:
            # A very large supplied-value list uses the same lossless grouping.
            request = {**request, "questions": {"input_value": bounded_question(request["questions"]["input_value"]["criteria"][selected], ["Choose the exact prepared value or missing-text handoff."])}}
            if cancelled():
                return None, pause, {}, seconds
            answer = ask(request, "input_group")["answers"]["input_value"]
            selected = answer["choice"]
        scores.append(score(answer))
        if selected == "reselect_action":
            if reconsidered:
                raise DecisionRejectedError("Input selection rejected the revised field; no text was entered")
            if cancelled():
                return None, pause, {}, seconds
            # Resolve field/value meaning before offering another input operation.
            fields = {action["target"]["id"]: action["target"] for action in actions.values() if "text_id" in action}
            statuses = {}
            field_questions = {"field_" + ref: bounded_question({
                **{"input_" + key: value for key, value in payload["state"]["input_texts"].items()},
                "satisfied": "Current value already meets the task. Do not change it.",
                "unrelated": "No task requirement belongs in this field.",
                "missing": "The required text is genuinely unavailable."},
                {"task": payload["state"]["task"], "field": {**field, "displayed_text": field["value"] or field["name"]},
                 "question": "Which prepared value belongs to this field in the requested final result? Judge EVERY field against the whole task, independently of the next action or current focus. Required empty fields are not unrelated. The observed field label determines its meaning; an input purpose is a hint, not a restriction on task-specified text. Choose satisfied only when the current displayed value meets the task, unrelated only if no task requirement belongs here, or missing if no supplied value is suitable. Native editable fields may expose their current text as the AX name without a Value attribute; compare displayed_text before deciding to replace it."})
                for ref, field in fields.items()}
            # Field grounding is a rejection repair, not an extra call on every click.
            # Its input is a current field snapshot, not the prior action plan.
            grounding = {**payload, "state": {key: payload["state"][key] for key in ("task", "input_texts")},
                         "questions": field_questions}
            grounded = ask(grounding, "input_grounding")["answers"]
            for head, answer in grounded.items():
                choice = answer["choice"]
                if choice.startswith("group_"):
                    if cancelled():
                        return None, pause, {}, seconds
                    question = bounded_question(field_questions[head]["criteria"][choice],
                                                field_questions[head]["instructions"])
                    answer = ask({**grounding, "questions": {head: question}}, "input_grounding_group")["answers"][head]
                    choice = answer["choice"]
                    grounded[head] = answer
                statuses[head] = {"field": fields[head.removeprefix("field_")], "status": choice, "confidence": score(answer)}
            # Grounding already established a required input is unavailable.
            # Re-offering unrelated text would discard that decision and loop.
            missing = next((item["field"] for item in statuses.values() if item["status"] == "missing"), None)
            if missing is not None:
                actions["help_input"] = {"type": "help_input", "target": missing,
                                         "label": "Ask the outer agent for the required text for this field"}
                return "help_input", pause, {"help_input": score(grounded["field_" + missing["id"]])}, seconds
            revised_actions = {key: action for key, action in actions.items()
                               if "text_id" not in action or statuses["field_" + action["target"]["id"]]["status"] == "input_" + action["text_id"]}
            questions = decision_questions(revised_actions, payload["questions"]["operation"]["instructions"])
            state = {**payload["state"], "input_field_status": statuses, "rejected_input": {
                "operation": kind, "target": target_field,
                "reason": "The text-selection step rejected changing this field. Reassess the current task and UI; choose another operation."},
                "available_targets": {key.removeprefix("target_"): question["criteria"]
                                      for key, question in questions.items() if key.startswith("target_")}}
            chosen, continuation, revised_scores, elapsed = ask_decision(
                jev, {**payload, "state": state, "questions": questions}, revised_actions,
                record, max_bytes, cancelled, reconsidered=True)
            if chosen in revised_actions:
                actions[chosen] = revised_actions[chosen]
            return chosen, continuation, revised_scores, seconds + elapsed
        if selected == "open_options":
            selected = "click_" + target_field["id"]
        if selected == "help_input":
            # Carry the selected field to the existing handoff, including unfocused fields.
            actions[selected] = {"type": "help_input", "target": next(iter(candidates.values()))["target"],
                                 "label": "Ask the outer agent for text for the selected field"}
    # Scores from separate conditional heads are not a calibrated joint probability.
    # The minimum only retains the runner's existing conservative ambiguity gate.
    return selected, pause, {selected: min(scores)}, seconds
