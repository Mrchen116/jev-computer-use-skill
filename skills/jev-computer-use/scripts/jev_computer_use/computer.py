"""Full native observations and concrete actions for the general task loop."""

from datetime import datetime
import json
import re
import time

from .desktop import nodes
from .calendar_view import annotate_month_grids


def editable(control):
    """Native settable text/date capabilities also work for unfamiliar role names."""
    return control.get("settable", False) and control["role"] in ("textbox", "combobox", "datefield", "other") and not re.search(r"\b(?:boolean|float|integer)\b", control.get("attributes", ""))


def equivalent_value(expected, actual):
    """Compare native date/time formatting without treating another date as success."""
    if expected == actual:
        return True
    def parsed(value):
        value = (value or "").replace("\u202f", " ").replace("\xa0", " ").strip()
        for fmt in ("%H:%M", "%I:%M %p", "%Y-%m-%d", "%Y/%m/%d", "%m/%d/%y", "%m/%d/%Y", "%Y年%m月%d日"):
            try:
                result = datetime.strptime(value, fmt)
                return ("time", result.hour, result.minute) if "%M" in fmt else ("date", result.year, result.month, result.day)
            except ValueError:
                pass
        return None
    left, right = parsed(expected), parsed(actual)
    return left is not None and left == right


def observed_dates(raw):
    """Expose literal dates from UI text, with source labels; never resolve a holiday."""
    result = {}
    for line in raw.splitlines():
        for match in re.finditer(r"(?<!\d)(\d{4})(?:年|[-/])(\d{1,2})(?:月|[-/])(\d{1,2})(?:日|\b)", line):
            year, month, day = map(int, match.groups())
            try:
                value = datetime(year, month, day)
            except ValueError:
                continue
            key = "observed_date_" + value.strftime("%Y%m%d")
            source = line.strip()
            item = result.setdefault(key, {"text": f"{month}/{day}/{str(year)[2:]}", "purpose": "Date observed in UI: "})
            if source not in item["purpose"]:
                item["purpose"] += source + "; "
    return result


def describe_window(raw, application, applications):
    """Preserve the complete AX text; parse only what execution needs."""
    focus = re.search(r"The focused UI element is (\d+)\b", raw)
    focused = focus[1] if focus else None
    controls = {}
    parsed = nodes(raw)
    ancestors = []
    for index, node in enumerate(parsed):
        while ancestors and ancestors[-1]["depth"] >= node["depth"]:
            ancestors.pop()
        in_listbox = any(n["role"] == "listbox" for n in ancestors)
        ancestors.append(node)
        if "(disabled)" in node["detail"]:
            continue
        label = re.sub(r"^(?:\([^)]*\)\s*)+", "", node["detail"])
        label = re.sub(r"^Description: ", "", label)
        name = re.split(r"(?:^|, )(?:Value|URL|Placeholder|Help|Secondary Actions|ID|Details):", label)[0]
        if not name:
            placeholder = re.search(r"(?:^|, )Placeholder: (.*?)(?=, (?:Value|URL|Help|Secondary Actions|ID|Details):|$)", label)
            name = placeholder[1] if placeholder else ""
        value = re.search(r"(?:^|, )Value: (.*?)(?=, (?:Placeholder|URL|Help|ID|Details|Secondary Actions):|$)", label, re.S)
        controls[node["ref"]] = {
            "id": node["ref"], "role": "combobox" if re.search(r"\b(?:combo box|组合框)\b", node["line"], re.I) else node["role"], "name": name,
            "value": value[1] if value else "",
            "attributes": node["detail"],
            "multiline": bool(re.search(r"(?:text area|textarea|文本输入区)", node["line"], re.I)),
            "settable": bool(re.search(r"\([^)]*\bsettable\b[^)]*\)", node["detail"])),
        }
        if in_listbox and node["ref"] == focused and node["role"] == "text":
            focused_line = next((line for line in raw.splitlines() if line.startswith("The focused UI element is ")), "")
            focus_nodes = nodes(focused_line.removeprefix("The focused UI element is "))
            selected_name = re.sub(r"^(?:\([^)]*\)\s*)+", "", focus_nodes[0]["detail"]) if focus_nodes else ""
            if selected_name and selected_name != name and selected_name in name:
                controls[node["ref"]].update(combined_options=True, selected_option=selected_name)
        controls[node["ref"]]["list_item"] = any(n["role"] in ("list", "listbox") for n in ancestors[:-1])
        controls[node["ref"]]["selected"] = any("(selected" in n["detail"] for n in ancestors)
        # AX often leaves a field unnamed while exposing its label as a sibling.
        # Quote that structural fact; do not invent a semantic label or UI route.
        previous = parsed[index - 1] if index else None
        if ((editable(controls[node["ref"]]) or node["role"] == "textbox") and previous
                and previous["role"] in ("text", "heading")
                and previous["depth"] == node["depth"]):
            controls[node["ref"]]["preceding_text"] = previous["detail"]
            if not name and not editable(controls[node["ref"]]) and previous["role"] == "text":
                controls[previous["ref"]]["label_for"] = node["ref"]
        following = parsed[index + 1] if index + 1 < len(parsed) else None
        if following and following["role"] in ("text", "heading") and following["depth"] == node["depth"]:
            controls[node["ref"]]["following_text"] = following["detail"]
    focused_control = controls.get(focused, {})
    query = focused_control.get("value", "").strip()
    if query and editable(focused_control):
        for control in controls.values():
            if control["role"] == "text" and control.get("list_item") and query.casefold() in control["name"].casefold():
                control["option_for"] = focused
    annotate_month_grids(parsed, controls)
    if focused in controls and controls[focused]["role"] == "textbox" and not editable(controls[focused]) and any(c.get("calendar_context") for c in controls.values()):
        controls[focused]["picker_open"] = True
    return {
        "application": application, "applications": applications,
        "window": raw.splitlines()[0] if raw else "",
        "focused_element": focused, "ui_tree": raw,
        "controls": controls,
    }


def action_menu(observation, input_texts):
    """Build executable options without predicting a task's UI route."""
    def context(control):
        context = "".join(f". Immediately {position} AX sibling text: {control[key]!r}"
                          for position, key in (("preceding", "preceding_text"), ("following", "following_text")) if control.get(key))
        return context + (". " + control["calendar_context"] if control.get("calendar_context") else "") + (f". Current value: {control['value']!r}" if control.get("value") else "")

    def compatible(control, text):
        if control["value"] == text:
            return False
        if control["role"] != "datefield":
            return True
        # Native date/time widgets accept their displayed component, not arbitrary
        # text. An all-day form may expose only dates until its toggle changes.
        time_only = bool(re.fullmatch(r"\d{1,2}:\d{2}(?:[\s\u202f]*(?:AM|PM))?", control["value"], re.I))
        input_time = bool(re.fullmatch(r"\d{1,2}:\d{2}(?:[\s\u202f]*(?:AM|PM))?", text, re.I))
        if time_only:
            return input_time
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%y", "%m/%d/%Y", "%Y年%m月%d日"):
            try:
                datetime.strptime(text, fmt)
                return True
            except ValueError:
                pass
        return False

    actions = {}
    for app in observation["applications"]:
        if app["id"] != observation["application"]:
            actions["app_" + app["id"]] = {
                "type": "switch_app", "application": app["id"],
                "label": "Switch to application: " + app["name"],
            }
    for ref, control in observation["controls"].items():
        # Conditional input/value questions receive this target independently
        # from click labels; preserve the observed label context there too.
        target = {k: control[k] for k in ("id", "role", "name", "value", "preceding_text", "following_text") if k in control}
        # Re-focusing the already focused field is not a next input operation.
        # Offering it caused Jev to loop instead of asking the host for text.
        needs_focus = (control["role"] == "combobox" or not editable(control) or ref != observation["focused_element"]) and not control.get("picker_open")
        # Native click can address text too. Custom buttons and autocomplete
        # options often expose only AX static text, without a button/link role.
        clickable = control["role"] in ("button", "link", "checkbox", "radio", "tab", "menuitem", "textbox", "combobox", "datefield", "event", "list") or editable(control) or (control["role"] == "text" and bool(control["name"]))
        if needs_focus and clickable and not control.get("combined_options") and not observation["controls"].get(control.get("label_for"), {}).get("picker_open"):
            verb = "Click"
            if control["role"] == "checkbox" and control["value"] in ("0", "1"):
                verb = "Check (currently unchecked)" if control["value"] == "0" else "Uncheck (currently checked)"
            actions["click_" + ref] = {
                "type": "click", "target": target,
                "label": f"{verb} {control['role']} {ref}: {control['name']}" + context(control),
                **({"semantic_operation": "select_option"} if control.get("option_for") else {}),
            }
        # setValue addresses a specific native field; it does not require AX to
        # report focus (some apps report only the selection instead).
        if editable(control) and ref != observation["focused_element"]:
            for text_id, item in input_texts.items():
                if not compatible(control, item["text"]):
                    continue
                actions[f"replace_{ref}_{text_id}"] = {
                    "type": "replace", "target": target, "text_id": text_id,
                    "text": item["text"],
                    "label": f"Set field {ref} ({control['name']})" + context(control) + f" to input_texts[{text_id!r}].text exactly. Does not submit.",
                }
        if control["role"] in ("scrollarea", "webarea"):
            for direction in ("up", "down", "left", "right"):
                actions[f"scroll_{ref}_{direction}"] = {
                    "type": "scroll", "target": target, "direction": direction,
                    "label": f"Scroll {direction} in {ref}: {control['name']}",
                }
    focused = observation["controls"].get(observation["focused_element"])
    if focused and editable(focused):
        target = {k: focused[k] for k in ("id", "role", "name", "value", "preceding_text", "following_text") if k in focused}
        for text_id, item in input_texts.items():
            if not compatible(focused, item["text"]):
                continue
            for mode in ("replace", "insert"):
                actions[f"{mode}_{text_id}"] = {
                    "type": mode, "target": target, "text_id": text_id,
                    "text": item["text"],
                    "label": f"{mode.title()} text in focused field {target['id']} ({target['name']})" + context(focused) + f" using input_texts[{text_id!r}].text exactly. Do not submit.",
                }
        # Concatenate known pieces without requiring the host to author a phrase.
        # Use the observed value, not the caret (which AX does not expose).
        if focused["value"] and focused["role"] != "datefield":
            for text_id, item in input_texts.items():
                if item["text"] and item["text"] not in focused["value"]:
                    combined = focused["value"].rstrip() + " " + item["text"]
                    actions[f"append_{text_id}"] = {
                        "type": "replace", "target": target, "text_id": text_id,
                        "text": combined,
                        "label": f"Append input_texts[{text_id!r}] after the existing field text, separated by a space; preserve its existing content. Result: {combined!r}. Does not submit.",
                    }
        actions["help_input"] = {
            "type": "help_input", "target": target,
            "label": f"Ask the outer agent for the exact text needed in focused field {target['id']}: {target['name']}" + context(focused),
        }
    choice_menu = next((c for c in observation["controls"].values() if c.get("combined_options")), None)
    if observation["application"]:
        for key in ("super+f", "super+n", "super+t", "Return", "Escape", "Tab", "Up", "Down", "Left", "Right", "space", "super+a"):
            label = f"Press {key} at the current focus"
            if choice_menu and key in ("Up", "Down", "Return", "Escape"):
                label += f" in the open option menu. Current selection: {choice_menu['selected_option']!r}. Option text: {choice_menu['name']!r}. Up/Down move selection; Return accepts it; Escape cancels."
            actions["key_" + key] = {"type": "key", "key": key, "label": label}
    actions.update({
        "wait": {"type": "wait", "label": "Wait for the next observation"},
        "help_reasoning": {"type": "help_reasoning", "label": "Ask the outer agent for reasoning, clarification or an operation not available in this menu"},
        "review_completion": {"type": "review_completion", "label": "Pause for outer review: the whole task has its result or a terminal outcome (success or failure). Do not retry or reset it yourself."},
    })
    return actions


class Computer:
    """Use the installed CUA transport without a browser-specific state model."""

    def __init__(self, native, application=None):
        self.native = native
        self.application = application
        self.bound = None
        self.pending_input = None
        self.current_observation = None

    def _json(self, expression):
        result = self.native.js('nodeRepl.write("JEV_FULL:"+JSON.stringify(' + expression + '));')
        return json.loads(result.rsplit("JEV_FULL:", 1)[1].strip())

    def observe(self):
        """Read a complete current AX observation and the actual app inventory."""
        if not self.application:
            apps = self._json("await cua.listApps({emit:false})")
            applications = [{"id": a["id"], "name": a["displayName"]} for a in apps]
            return describe_window("No application selected yet.", None, applications)
        if self.bound != self.application:
            self.native.js("var jevComputer = await cua.getApp(" + json.dumps(self.application) + ");")
            self.bound = self.application
        # Both reads belong to one observation; avoid a second MCP round trip.
        apps, raw = self._json("[await cua.listApps({emit:false}), await jevComputer.getAXState({emit:false,disableDiffing:true})]")
        if self.pending_input:
            # Typing can open a new picker after the first AX read. Observe a
            # bounded quiet interval before choosing another operation.
            is_combobox = self.pending_input == "combobox"
            self.pending_input = None
            started = stable = time.monotonic()
            def choices_visible():
                return any(n["role"] in ("listbox", "menuitem") for n in nodes(raw))
            while time.monotonic() - started < (3 if is_combobox else 1):
                if time.monotonic() - stable >= .3 and (not is_combobox or choices_visible()):
                    break
                time.sleep(.1)
                fresh = self._json("await jevComputer.getAXState({emit:false,disableDiffing:true})")
                if fresh != raw:
                    raw, stable = fresh, time.monotonic()
        applications = [{"id": a["id"], "name": a["displayName"]} for a in apps]
        self.current_observation = describe_window(raw, self.application, applications)
        return self.current_observation

    def execute(self, action):
        """Execute one selected action; never submit as a side effect of filling."""
        kind = action["type"]
        if kind == "switch_app":
            self.application = action["application"]
            return
        if kind == "wait":
            return
        ref = int(action["target"]["id"]) if "target" in action else None
        if kind == "click":
            code = f"await jevComputer.click({ref});"
        elif kind == "scroll":
            code = f"await jevComputer.scroll({ref}, {json.dumps(action['direction'])}, 1);"
        elif kind == "key":
            code = f"await jevComputer.pressKey({json.dumps(action['key'])});"
        elif kind == "replace":
            if self.current_observation and str(ref) != self.current_observation["focused_element"]:
                # Focus can replace a launcher field with a popup editor. Never
                # type through the stale native reference from before that click.
                self.native.js(f"await jevComputer.click({ref});")
                current = self.observe()
                field = current["controls"].get(current["focused_element"])
                target = action["target"]
                candidates = [c for c in current["controls"].values()
                              if editable(c) and c["role"] == target["role"]
                              and c["name"].strip() == target["name"].strip()]
                if len(candidates) == 1:
                    field = candidates[0]
                if not (field and editable(field) and field["role"] == target["role"]
                        and field["name"].strip() == target["name"].strip()):
                    return {"input_deferred": True, "detail": "Focus opened a different editor; no text entered. Choose the input from the new observation."}
                ref = int(field["id"])
            text = action["text"]
            if action["target"]["role"] == "datefield" and re.fullmatch(r"\d{1,2}:\d{2}", text):
                # The native date transport parses a 12-hour time string; the
                # verification layer still checks the caller's original instant.
                text = datetime.strptime(text, "%H:%M").strftime("%I:%M %p").lstrip("0")
            if (self.current_observation and str(ref) == self.current_observation["focused_element"]
                    and action["target"]["role"] in ("textbox", "combobox")
                    and not self.current_observation["controls"].get(str(ref), {}).get("multiline")):
                # Paste a complete replacement: keystroke typing can append an
                # inline autocomplete suffix that was never supplied by the caller.
                code = f'await jevComputer.pressKey("super+a"); await jevComputer.paste({json.dumps(text)}, {{format:"text"}});'
            else:
                code = f"await jevComputer.setValue({ref}, {json.dumps(text)});"
        elif kind == "insert":
            # Re-clicking would move the caret and invalidate the selected insertion.
            code = f"await jevComputer.typeText({json.dumps(action['text'])});"
        else:
            raise ValueError("Unsupported computer operation: " + kind)
        self.native.js(code)
        self.pending_input = action["target"]["role"] if kind in ("replace", "insert") else None
