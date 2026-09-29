import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from jev_computer_use.computer import action_menu, describe_window
from jev_computer_use.observations import compact_ui, observation_id
from jev_computer_use.stage_state import read_status, request_stop
from jev_computer_use.task_cli import main
from jev_computer_use.tasks import TaskRunner, complete_task, read_task_history, host_handoff


class ComputerDouble:
    def __init__(self):
        self.application = None
        self.focus = None
        self.value = ""
        self.result = "not submitted"
        self.calls = []
        self.notice = ""
        self.fail = False
        self.window = "Task"

    def observe(self):
        raw = (f'Window: "{self.window}", App: Test\n'
               f'0 standard window Task\n  1 text field (settable) Message, Value: {self.value}\n'
               f'  2 button Apply\n  3 text Result: {self.result}\n  4 text {self.notice}\n')
        if self.focus:
            raw += f'The focused UI element is {self.focus}\n'
        return describe_window(raw if self.application else "Desktop inventory", self.application,
                               [{"id": "test", "name": "Test"}, {"id": "mail", "name": "Mail"}])

    def execute(self, action):
        self.calls.append(action)
        if self.fail:
            raise RuntimeError("Uncertain mutation")
        kind = action["type"]
        if kind == "switch_app":
            self.application = action["application"]
        elif kind == "click":
            self.focus = action["target"]["id"]
        elif kind == "replace":
            self.value = action["text"]
        elif kind == "insert":
            self.value += action["text"]
        elif kind == "key" and action["key"] == "Return":
            self.result = self.value


class JevDouble:
    def __init__(self, choices, callback=None):
        self.choices = iter(choices)
        self.requests = []
        self.usage = {"input_tokens": 0, "output_tokens": 0}
        self.callback = callback

    def ask(self, payload):
        self.requests.append(copy.deepcopy(payload))
        questions = payload["questions"]
        choice = getattr(self, "pending", None) or next(self.choices)
        self.pending = None
        def answer(key):
            return {"choice": key, "confidence": .9, "probabilities": {key: .9}}
        answers = {key: answer(next(iter(q["criteria"]))) for key, q in questions.items()}
        if "operation" in questions:
            kinds = {"app": "switch_app", "view": "view_page", "inputs": "input_page"}
            kind = choice if choice in ("help_input", "help_reasoning", "review_completion", "wait") else kinds.get(choice.split("_")[0], choice.split("_")[0])
            self.assert_choice(kind, questions["operation"])
            answers["operation"] = answer(kind)
            head = "target_" + kind
            if head in questions:
                target = choice
                if kind in ("replace", "insert", "append"):
                    text_id = next(k for k in sorted(payload["state"]["input_texts"], key=len, reverse=True) if choice.endswith("_" + k))
                    field = choice[len(kind) + 1:-(len(text_id) + 1)]
                    field = field or payload["state"]["observation"]["focused_element"]
                    target = "field_" + str(field)
                    self.pending = choice
                if target not in questions[head]["criteria"]:
                    target = next(k for k, v in questions[head]["criteria"].items() if isinstance(v, dict) and target in v)
                    self.pending = choice
                self.assert_choice(target, questions[head])
                answers[head] = answer(target)
        else:
            head = next(iter(questions))
            self.assert_choice(choice, questions[head])
            answers[head] = answer(choice)
        self.usage["input_tokens"] += 100
        if self.callback:
            self.callback()
        return {"answers": answers}, .01

    @staticmethod
    def assert_choice(choice, question):
        if choice not in question["criteria"]:
            raise AssertionError("Not in menu: " + choice)


class TaskTests(unittest.TestCase):
    def test_unrelated_timer_change_does_not_starve_missing_text_handoff(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application, computer.focus = 'test', '1'
            computer.notice = 'Time left: 98'
            jev = JevDouble(['help_input'], lambda: setattr(computer, 'notice', 'Time left: 97'))
            result = TaskRunner(computer, jev, root).run(task='Write the requested message')
            self.assertEqual(result['reason'], 'help_input')
            self.assertEqual(len(jev.requests), 1)
            self.assertEqual(computer.calls, [])

    def test_new_input_choice_is_seen_before_missing_text_handoff(self):
        class Suggestions(ComputerDouble):
            show = False
            def observe(self):
                value = super().observe()
                if self.show:
                    value['ui_tree'] += '\n  5 button Suggested value'
                    value['controls']['5'] = {'id': '5', 'role': 'button', 'name': 'Suggested value', 'value': '', 'settable': False}
                return value
        with tempfile.TemporaryDirectory() as root:
            computer = Suggestions()
            computer.application, computer.focus = 'test', '1'
            jev = JevDouble(['help_input', 'click_5', 'review_completion'], lambda: setattr(computer, 'show', True))
            result = TaskRunner(computer, jev, root).run(task='Choose the suggested value')
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(len(computer.calls), 1)
            self.assertEqual(computer.calls[0]['target']['id'], '5')

    def test_step_reuses_post_action_state_but_realtime_observes_each_cycle(self):
        for mode in ("step", "realtime"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                computer = ComputerDouble()
                computer.application = "test"
                ticks = []
                def tick():
                    ticks.append(1)
                    computer.notice = "cycle " + str(len(ticks))
                    return False
                jev = JevDouble(["click_2", "review_completion"])
                with patch("jev_computer_use.tasks.Cycle.wait", side_effect=tick):
                    result = TaskRunner(computer, jev, root).run(task="Click Apply then stop", mode=mode)
                self.assertEqual(result["reason"], "review_completion")
                self.assertEqual(len(computer.calls), 1)
                next_ui = jev.requests[1]["state"]["observation"]["ui_tree"]
                self.assertIn("cycle 1" if mode == "step" else "cycle 2", next_ui)

    def test_reasoning_operation_ignores_conditional_click_target(self):
        class NeedsReasoning(JevDouble):
            def ask(self, payload):
                response, seconds = super().ask(payload)
                response["answers"]["operation"] = {
                    "choice": "help_reasoning", "confidence": .98,
                    "probabilities": {"click": .01, "review_completion": .01, "help_reasoning": .98}}
                return response, seconds
        for mode in ("step", "realtime"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                computer = ComputerDouble()
                computer.application = "test"
                jev = NeedsReasoning(["click_2"])
                result = TaskRunner(computer, jev, root).run(task="Choose the shortest option", mode=mode)
                self.assertIn("help_reasoning", jev.requests[0]["questions"]["operation"]["criteria"])
                self.assertEqual(result["reason"], "help_reasoning")
                self.assertEqual(computer.calls, [])
                self.assertEqual(result["history"][-1]["action"]["type"], "help_reasoning")
                self.assertIn("Result:", host_handoff(result)["current_observation"]["ui_tree"])

    def test_high_continuation_does_not_authorize_a_diffuse_action(self):
        class Diffuse(JevDouble):
            def ask(self, payload):
                response, seconds = super().ask(payload)
                if len(self.requests) == 1:
                    response['answers']['operation'] = {'choice': 'click', 'confidence': .19,
                        'probabilities': {'click': .2, 'replace': .15, 'review_completion': .1}}
                return response, seconds
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application = 'test'
            jev = Diffuse(['click_2', 'review_completion'])
            result = TaskRunner(computer, jev, root).run(task='Form is already correct')
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(computer.calls, [])
            self.assertEqual(len(jev.requests), 2)
            self.assertNotIn('next_action', jev.requests[1]['questions'])

    def test_still_diffuse_review_yields_without_mutation(self):
        class Diffuse(JevDouble):
            def ask(self, payload):
                response, seconds = super().ask(payload)
                response['answers']['operation']['probabilities'] = {'click': .2}
                return response, seconds
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application = 'test'
            result = TaskRunner(computer, Diffuse(['click_2', 'click_2']), root).run(task='Continue')
            self.assertEqual(result['reason'], 'uncertain_action')
            self.assertEqual(computer.calls, [])

    def test_uncertain_continuation_blocks_a_high_confidence_click_in_same_call(self):
        class Uncertain(JevDouble):
            def ask(self, payload):
                response, seconds = super().ask(payload)
                response["answers"]["operation"] = {"choice": "click", "confidence": .65, "probabilities": {"click": .65, "review_completion": .35}}
                return response, seconds
        for threshold in (.9, .6):
            with self.subTest(threshold=threshold), tempfile.TemporaryDirectory() as root:
                computer = ComputerDouble()
                computer.application = "test"
                jev = Uncertain(["click_1"])
                result = TaskRunner(computer, jev, root).run(task="Continue", min_continue_probability=threshold, max_steps=1)
                self.assertEqual(len(jev.requests), 1)
                self.assertEqual(len(computer.calls), 0 if threshold == .9 else 1)
                self.assertEqual(result["reason"], "uncertain_continuation" if threshold == .9 else "step_budget")

    def test_date_field_renumbering_does_not_verify_neighboring_time_field(self):
        class RenumberedDates(ComputerDouble):
            def observe(self):
                raw = ('0 standard window Form\n 1 日期时间区域 (settable, date) Value: 4/12/27\nThe focused UI element is 1' if not self.value else
                       f'0 standard window Form\n 1 日期时间区域 (settable, date) Value: 8:00 AM\n 9 日期时间区域 (settable, date) Value: {self.value}\nThe focused UI element is 9')
                return describe_window(raw, 'test', [])
        with tempfile.TemporaryDirectory() as root:
            computer = RenumberedDates()
            computer.application = 'test'
            result = TaskRunner(computer, JevDouble(['replace_date', 'review_completion']), root).run(
                task='Change date', input_texts={'date': {'text': '8/19/27', 'purpose': 'date'}})
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(result['history'][1]['result']['observed_value'], '8/19/27')

    def test_placeholder_field_keeps_identity_after_native_value_appears(self):
        class PlaceholderComputer(ComputerDouble):
            def observe(self):
                label = "From:" if not self.value else f"Value: {self.value}, Placeholder: From:"
                return describe_window(
                    f'Window: "Task", App: Test\n0 standard window Task\n 1 text field (settable) {label}\n 2 button Search\nThe focused UI element is 1 text field',
                    "test", [{"id": "test", "name": "Test"}])
        with tempfile.TemporaryDirectory() as root:
            computer = PlaceholderComputer()
            computer.application = "test"
            result = TaskRunner(computer, JevDouble(["replace_city", "review_completion"]), root).run(
                task="Fill the city", input_texts={"city": {"text": "Emmonak, AK", "purpose": "From city"}})
            self.assertEqual(result["reason"], "review_completion")
            effect = next(e["result"] for e in result["history"] if e.get("action", {}).get("type") == "replace")
            self.assertEqual(effect["verification"], "exact_value")

    def test_input_verification_follows_renumbered_editable_focus(self):
        class Renumbered(ComputerDouble):
            def observe(self):
                ref = '7' if self.value else '1'
                label = self.value or 'Compose'
                return describe_window(f'0 standard window Form\n {ref} 文本输入区 (settable) {label}\n 9 button Send\nThe focused UI element is {ref}', 'test', [])
        with tempfile.TemporaryDirectory() as root:
            computer = Renumbered()
            computer.application = 'test'
            result = TaskRunner(computer, JevDouble(['replace_message', 'review_completion']), root).run(
                task='Fill the message', input_texts={'message': {'text': 'Different message', 'purpose': 'message'}})
            self.assertEqual(result['reason'], 'review_completion')
            self.assertEqual(result['history'][-2]['result']['verification'], 'displayed_text')

    def test_plain_text_input_is_not_verified_using_date_normalization(self):
        class Reformatter(ComputerDouble):
            def execute(self, action):
                super().execute(action)
                if action['type'] == 'replace':
                    self.value = '7:30 AM'
        with tempfile.TemporaryDirectory() as root:
            computer = Reformatter()
            computer.application, computer.focus = 'test', '1'
            result = TaskRunner(computer, JevDouble(['replace_message']), root).run(
                task='Fill literal text', input_texts={'message': {'text': '07:30', 'purpose': 'literal message'}})
            self.assertEqual(result['reason'], 'input_unverified')

    def test_native_text_targets_and_unlabelled_fields_are_executable(self):
        obs = describe_window('0 standard window Test\n 1 text Begin\n 2 text field (settable)\n 3 text Airport option', "test", [])
        menu = action_menu(obs, {})
        self.assertEqual(menu["click_1"]["target"]["name"], "Begin")
        self.assertEqual(menu["click_2"]["target"]["role"], "textbox")
        self.assertEqual(menu["click_3"]["target"]["name"], "Airport option")

    def test_readonly_picker_remains_clickable_without_direct_input_options(self):
        obs = describe_window('0 standard window Test\n 1 text field\n 2 button Calendar\nThe focused UI element is 1 text field', "test", [])
        menu = action_menu(obs, {"date": {"text": "2026-09-22", "purpose": "Date"}})
        self.assertNotIn("replace_date", menu)
        self.assertNotIn("insert_date", menu)
        self.assertNotIn("help_input", menu)
        obs["focused_element"] = "2"
        self.assertIn("click_1", action_menu(obs, {}))

    def test_changed_inline_input_text_is_verified_but_unchanged_label_is_not(self):
        class InlineComputer(ComputerDouble):
            def observe(self):
                label = self.value or self.notice
                return describe_window(
                    f'Window: "Task", App: Test\n0 standard window Task\n 1 text field (settable) {label}\n 2 button Search\nThe focused UI element is 1 text field',
                    "test", [{"id": "test", "name": "Test"}])
        for existing_label in ("", "drama"):
            with self.subTest(existing_label=existing_label), tempfile.TemporaryDirectory() as root:
                computer = InlineComputer()
                computer.application, computer.notice = "test", existing_label
                result = TaskRunner(computer, JevDouble(["replace_genre", "review_completion"]), root).run(
                    task="Fill the genre", input_texts={"genre": {"text": "drama", "purpose": "Genre"}})
                expected = "input_unverified" if existing_label else "review_completion"
                self.assertEqual(result["reason"], expected)
                effect = next(e["result"] for e in result["history"] if e.get("action", {}).get("type") == "replace")
                self.assertEqual(effect["verification"], "unverified" if existing_label else "displayed_text")

    def test_repeated_no_effect_yields_in_step_but_only_warns_in_realtime(self):
        for mode in ("step", "realtime"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                computer = ComputerDouble()
                computer.application = "test"
                jev = JevDouble(["key_space"] * 4 + ["review_completion"])
                result = TaskRunner(computer, jev, root).run(task="Continue", mode=mode, period_ms=100)
                self.assertIn("repeated_no_effect", [w["code"] for w in result["warnings"]])
                self.assertEqual(result["reason"], "repeated_no_effect" if mode == "step" else "review_completion")
                self.assertEqual(len(computer.calls), 3 if mode == "step" else 4)

    def test_full_task_navigation_input_and_host_completion(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            jev = JevDouble(["app_test", "click_1", "replace_message", "key_Return", "review_completion"])
            result = TaskRunner(computer, jev, root).run(
                task="Write hello then apply it", input_texts={"message": {"text": "hello", "purpose": "Message to apply"}},
                pricing={"input_tokens": 1, "output_tokens": 2})
            self.assertEqual(result["reason"], "review_completion")
            self.assertFalse(result["global_completion"])
            self.assertEqual(computer.result, "hello")
            self.assertEqual([a["type"] for a in computer.calls], ["switch_app", "click", "replace", "key"])
            self.assertEqual(len(jev.requests), 6)
            self.assertTrue(all("next_action" not in p["questions"] for p in jev.requests))
            self.assertIn("field_1", jev.requests[1]["questions"]["target_replace"]["criteria"])
            self.assertIn("click_1", jev.requests[1]["questions"]["target_click"]["criteria"])
            self.assertNotIn("click_1", jev.requests[2]["questions"]["target_click"]["criteria"])
            self.assertIn("help_input", jev.requests[2]["questions"]["operation"]["criteria"])
            self.assertEqual(jev.requests[3]["state"]["selected_target"]["id"], "1")
            self.assertIn("replace_message", jev.requests[3]["questions"]["input_value"]["criteria"])
            status = read_status(root)
            self.assertEqual(status["history"], result["history"])
            self.assertNotIn("context", status)
            self.assertEqual(status["usage"]["jev"]["input_tokens"], 600)
            self.assertEqual(status["usage"]["jev_cost_usd"], .0006)
            records = [json.loads(line) for line in Path(status["history_location"]).read_text().splitlines()]
            self.assertEqual(sum(r["kind"] == "decision" for r in records), 6)
            self.assertEqual(Path(status["history_location"]).stat().st_mode & 0o777, 0o600)
            self.assertTrue(complete_task(root, "Verified: hello")["global_completion"])

    def test_window_change_during_value_choice_prevents_input(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application = "test"
            jev = JevDouble(["replace_1_message", "review_completion"])
            def change_window():
                if len(jev.requests) == 2:
                    computer.window = "Another form"
            jev.callback = change_window
            result = TaskRunner(computer, jev, root).run(
                task="Fill Message", input_texts={"message": {"text": "hello", "purpose": "Message"}})
            self.assertEqual(computer.calls, [])
            self.assertEqual(result["reason"], "review_completion")
            self.assertTrue(any(e["result"].get("reason") == "target_changed" for e in result["history"]))

    def test_wait_and_completion_use_one_operation_choice(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application = "test"
            jev = JevDouble(["wait", "review_completion"])
            result = TaskRunner(computer, jev, root).run(task="Wait for the result", period_ms=100)
            self.assertEqual(result["reason"], "review_completion")
            self.assertEqual(result["history"][0]["action"]["type"], "wait")
            self.assertNotIn("pause_now", jev.requests[0]["questions"])
            self.assertEqual(len(jev.requests), 2)

    def test_host_input_and_reasoning_resume_preserve_whole_history(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            first = TaskRunner(computer, JevDouble(["app_test", "click_1", "help_input"]), root).run(task="Complete this task")
            second_jev = JevDouble(["replace_answer", "app_mail", "review_completion"])
            second = TaskRunner(computer, second_jev, root).run(
                guidance="I checked the source: use the exact prepared answer, then continue in Mail.",
                input_texts={"answer": {"text": "hello", "purpose": "The message requested by the task"}})
            self.assertEqual(second["history"][:3], first["history"])
            context = second_jev.requests[0]["state"]
            self.assertEqual(context["task"], "Complete this task")
            self.assertEqual(context["history"][-1]["actor"], "agent")
            self.assertEqual(second["usage"]["jev"]["input_tokens"], 700)
            self.assertEqual(second["current_application"], "mail")

    def test_history_is_not_last_five_and_ui_is_not_keyword_filtered(self):
        class ChangingComputer(ComputerDouble):
            def execute(self, action):
                super().execute(action)
                self.result += "."
        with tempfile.TemporaryDirectory() as root:
            computer = ChangingComputer()
            computer.notice = "Unrelated but observable text stays in context"
            jev = JevDouble(["app_test"] + ["key_Down"] * 7 + ["review_completion"])
            TaskRunner(computer, jev, root).run(task="General task")
            self.assertEqual(len(jev.requests[-1]["state"]["history"]), 8)
            self.assertIn(computer.notice, jev.requests[-1]["state"]["observation"]["ui_tree"])

    def test_stop_during_decision_does_not_execute_returned_action(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            jev = JevDouble(["app_test"], lambda: request_stop(root))
            result = TaskRunner(computer, jev, root).run(task="Test")
            self.assertEqual(result["status"], "stopped")
            self.assertEqual(result["usage"]["jev"]["input_tokens"], 100)
            self.assertEqual(computer.calls, [])

    def test_text_change_warns_without_discarding_stable_target(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            jev = JevDouble(["app_test", "click_1", "review_completion"], lambda: setattr(computer, "notice", computer.notice + " tick"))
            result = TaskRunner(computer, jev, root).run(task="Test")
            self.assertEqual(result["reason"], "review_completion")
            self.assertEqual(computer.focus, "1")
            self.assertIn("ui_changed_during_decision", [w["code"] for w in result["warnings"]])

    def test_changed_focus_blocks_typing_only_when_recheck_enabled(self):
        for recheck in (True, False):
            with self.subTest(recheck=recheck), tempfile.TemporaryDirectory() as root:
                computer = ComputerDouble()
                def change():
                    if len(jev.requests) == 3:
                        computer.focus = None
                jev = JevDouble(["app_test", "click_1", "replace_x", "review_completion"], change)
                result = TaskRunner(computer, jev, root).run(task="Test", recheck_target=recheck,
                    input_texts={"x": {"text": "x", "purpose": "Test message"}})
                self.assertEqual(result["reason"], "review_completion")
                if recheck:
                    self.assertIn("target_changed", [w["code"] for w in result["warnings"]])
                self.assertEqual(computer.value, "" if recheck else "x")

    def test_uncertain_mutation_is_retained_and_not_replayed(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.fail = True
            result = TaskRunner(computer, JevDouble(["app_test"]), root).run(task="Test")
            self.assertEqual(result["reason"], "execution_error")
            self.assertEqual(result["history"][-1]["result"]["status"], "uncertain")
            self.assertEqual(len(computer.calls), 1)

    def test_same_control_in_a_different_window_is_not_clicked(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            def change_window():
                if len(jev.requests) == 2:
                    computer.window = "Another window"
            jev = JevDouble(["app_test", "click_1", "review_completion"], change_window)
            result = TaskRunner(computer, jev, root).run(task="Test")
            self.assertEqual(result["reason"], "review_completion")
            self.assertIn("target_changed", [w["code"] for w in result["warnings"]])
            self.assertIsNone(computer.focus)

    def test_slow_realtime_decision_warns_without_being_discarded(self):
        class SlowJev(JevDouble):
            def ask(self, payload):
                response, _ = super().ask(payload)
                return response, .2
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            result = TaskRunner(computer, SlowJev(["app_test", "review_completion"]), root).run(task="Test", mode="realtime", period_ms=100)
            self.assertEqual(result["reason"], "review_completion")
            self.assertEqual(computer.application, "test")
            self.assertIn("decision_exceeded_period", [w["code"] for w in result["warnings"]])

    def test_capacity_yields_without_truncation_or_model_call(self):
        with tempfile.TemporaryDirectory() as root:
            jev = JevDouble([])
            result = TaskRunner(ComputerDouble(), jev, root).run(task="Keep all context", max_context_bytes=1)
            self.assertEqual(result["reason"], "context_capacity")
            self.assertEqual(jev.requests, [])
            self.assertEqual(result["context"]["task"], "Keep all context")

    def test_large_current_ui_is_delivered_without_another_read_or_model_call(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.application = 'test'
            computer.notice = 'Complete large interface text\n' * 5000
            jev = JevDouble([])
            with patch.object(computer, 'observe', wraps=computer.observe) as observe:
                result = TaskRunner(computer, jev, root).run(task='Inspect this interface', max_context_bytes=1)
                reads = observe.call_count
                handoff = host_handoff(result)
                self.assertEqual(observe.call_count, reads)
            self.assertEqual(result['reason'], 'context_capacity')
            self.assertEqual(jev.requests, [])
            self.assertIn(computer.notice, handoff['current_observation']['ui_tree'])
            self.assertNotIn('current_observation', read_status(root))

    def test_failed_execution_marks_last_observation_as_needing_refresh(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.fail = True
            result = TaskRunner(computer, JevDouble(['app_test']), root).run(task='Test')
            handoff = host_handoff(result)
            self.assertTrue(handoff['observation_needs_refresh'])
            self.assertEqual(handoff['current_observation']['ui_tree'],
                             result['context']['observation']['ui_tree'])

    def test_realtime_uses_same_payload_and_host_selected_period(self):
        with tempfile.TemporaryDirectory() as root:
            jev = JevDouble(["app_test", "review_completion"])
            result = TaskRunner(ComputerDouble(), jev, root).run(task="Test", mode="realtime", period_ms=100, recheck_target=False)
            self.assertEqual(result["period_ms"], 100)
            self.assertGreaterEqual(result["elapsed_seconds"], .1)
            self.assertIn("operation", jev.requests[-1]["questions"])

    def test_status_cli_is_read_only_and_includes_history(self):
        with tempfile.TemporaryDirectory() as root:
            TaskRunner(ComputerDouble(), JevDouble(["help_reasoning"]), root).run(task="Test")
            stream = io.StringIO()
            with patch("jev_computer_use.task_cli.NativeCUA", side_effect=AssertionError("No UI calls")), contextlib.redirect_stdout(stream):
                main(["--state-dir", root, "--status"])
            self.assertEqual(len(json.loads(stream.getvalue())["history"]), 1)

    def test_outer_agent_can_expand_logged_observations_and_decisions(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.notice = "A long retained observation. " * 50
            TaskRunner(computer, JevDouble(["app_test", "review_completion"]), root).run(task="Test")
            index = read_task_history(root)
            self.assertTrue(index["observations"])
            first = read_task_history(root, step=1, max_chars=500)
            second = read_task_history(root, step=1, offset=first["next_offset"], max_chars=500)
            self.assertNotEqual(first["text"], second["text"])
            decision = read_task_history(root, step=1, kind="decision", max_chars=20000)
            self.assertIn('"choice": "app_test"', decision["text"])
            expanded = read_task_history(root, step=1, max_chars=20000)
            self.assertEqual(len(expanded["sources"]), 1)
            self.assertIn("Result: not submitted", expanded["text"])

    def test_large_menu_keeps_every_action_and_executes_only_exact_choice(self):
        class WideComputer(ComputerDouble):
            def observe(self):
                obs = super().observe()
                raw = obs["ui_tree"] + "\n" + "\n".join(f"  {i} button Item {i}" for i in range(1000, 1300))
                return describe_window(raw, self.application, obs["applications"])
        with tempfile.TemporaryDirectory() as root:
            computer = WideComputer()
            computer.application = "test"
            jev = JevDouble(["click_1299"])
            result = TaskRunner(computer, jev, root).run(task="Select Item 1299", max_steps=1)
            self.assertEqual(result["reason"], "step_budget")
            self.assertEqual(computer.focus, "1299")
            self.assertEqual(len(computer.calls), 1)
            grouped = jev.requests[0]["questions"]["target_click"]["criteria"]
            keys = [key for group in grouped.values() for key in group]
            self.assertEqual(len(keys), len(set(keys)))
            self.assertTrue(all(f"click_{i}" in keys for i in range(1000, 1300)))
            self.assertEqual(jev.requests[0]["state"], jev.requests[1]["state"])
            self.assertLessEqual(len(jev.requests[1]["questions"]["target_click"]["criteria"]), 255)

    def test_compact_history_and_handoff_keep_full_raw_observation_available(self):
        with tempfile.TemporaryDirectory() as root:
            value = TaskRunner(ComputerDouble(), JevDouble(["app_test", "review_completion"]), root).run(task="Test")
            handoff = host_handoff(value)
            self.assertNotIn("context", handoff)
            self.assertEqual(handoff["history"], value["history"])
            self.assertNotIn("observed_changes", handoff["history"][0]["result"])
            self.assertEqual(handoff["current_observation"]["ui_tree"], value["context"]["observation"]["ui_tree"])
            self.assertNotIn("controls", handoff["current_observation"])
            self.assertNotIn("applications", handoff["current_observation"])
            self.assertFalse(handoff["observation_needs_refresh"])
            self.assertNotIn("current_observation", read_status(root))
            expanded = read_task_history(root, observation_ids=[handoff["detail_observation_id"]], max_chars=20000)
            self.assertIn(value["context"]["observation"]["ui_tree"].rstrip(), expanded["text"])
            raw = [json.loads(line) for line in Path(value["history_location"]).read_text().splitlines()]
            self.assertTrue(any(e.get("observed_changes") for e in raw if e["kind"] == "execution_result"))

    def test_host_can_search_observed_text_without_ui_or_jev_calls(self):
        with tempfile.TemporaryDirectory() as root:
            computer = ComputerDouble()
            computer.notice = "Needle with exact source wording"
            jev = JevDouble(["app_test", "review_completion"])
            TaskRunner(computer, jev, root).run(task="Test")
            before = (len(jev.requests), len(computer.calls))
            result = read_task_history(root, step=2, contains=["needle"], context_lines=0, max_chars=20000)
            self.assertEqual(len(result["sources"]), 1)
            self.assertIn("  4 text Needle with exact source wording", result["text"])
            self.assertEqual((len(jev.requests), len(computer.calls)), before)
            missing = read_task_history(root, contains=["missing term"])
            self.assertEqual(missing["text"], "")
            self.assertEqual(missing["missing_terms"], ["missing term"])

    def test_benchmark_scope_removes_external_actions_without_hiding_ui(self):
        from jev_computer_use.computer import Computer
        from jev_computer_use.eval_boundary import EvaluationComputer
        raw = ('Window: "Docs", App: Google Chrome.\n0 web area Docs, URL: https://docs.pytest.org/en/stable/\n'
               '1 link Install, Value: docs.pytest.org/en/stable/getting-started.html\n'
               '2 link PyPI, Value: pypi.org/project/pytest/\n')
        original = describe_window(raw, "com.google.Chrome", [])
        with patch.object(Computer, "observe", return_value=original):
            observed = EvaluationComputer(None, ["https://docs.pytest.org/en/stable/"]).observe()
        menu = action_menu(observed, {})
        self.assertIn("click_1", menu)
        self.assertNotIn("click_2", menu)
        self.assertEqual(observed["ui_tree"], raw)

    def test_benchmark_scope_preserves_scheme_elided_local_links(self):
        from jev_computer_use.computer import Computer
        from jev_computer_use.eval_boundary import EvaluationComputer
        raw = ('0 web area Test, URL: 127.0.0.1:1234/episode/form.html\n'
               '1 link 19, Value: 127.0.0.1:1234/episode/form.html#\n'
               '2 link Other task, Value: 127.0.0.1:1234/unrelated/\n'
               '3 link Other scheme, Value: https://127.0.0.1:1234/episode/form.html\n')
        with patch.object(Computer, "observe", return_value=describe_window(raw, "com.google.Chrome", [])):
            observed = EvaluationComputer(None, ["http://127.0.0.1:1234/episode"]).observe()
        menu = action_menu(observed, {})
        self.assertIn("click_1", menu)
        self.assertNotIn("click_2", menu)
        self.assertNotIn("click_3", menu)
        self.assertEqual(observed["ui_tree"], raw)

    def test_delayed_input_choices_are_seen_before_leaving_field_when_recheck_enabled(self):
        class InputComputer(ComputerDouble):
            show_choices = False
            def observe(self):
                value = super().observe()
                if self.show_choices:
                    value["ui_tree"] += "\n  5 button Suggested value"
                    value["controls"]["5"] = {"id": "5", "role": "button", "name": "Suggested value", "value": "", "settable": False}
                return value
        for recheck in (True, False):
            with self.subTest(recheck=recheck), tempfile.TemporaryDirectory() as root:
                computer = InputComputer()
                computer.application, computer.focus = "test", "1"
                choices = ["click_2", "click_5", "review_completion"] if recheck else ["click_2", "review_completion"]
                jev = JevDouble(choices, lambda: setattr(computer, "show_choices", True))
                result = TaskRunner(computer, jev, root).run(task="Accept the matching input then continue", recheck_target=recheck)
                self.assertEqual(computer.calls[0]["target"]["id"], "5" if recheck else "2")
                self.assertEqual(len(computer.calls), 1)
                self.assertEqual("input_choices_changed" in [w["code"] for w in result["warnings"]], recheck)

    def test_scope_waits_for_navigation_without_replaying_any_action(self):
        from jev_computer_use.computer import Computer
        from jev_computer_use.eval_boundary import EvaluationComputer
        pending = describe_window('Window: Loading\n', "com.google.Chrome", [])
        loaded = describe_window('Window: Docs\n0 web area Docs, URL: https://docs.example/\n', "com.google.Chrome", [])
        with patch.object(Computer, "observe", side_effect=[pending] * 5 + [loaded]) as observe, patch('jev_computer_use.eval_boundary.time.sleep'), patch.object(Computer, 'execute') as execute:
            self.assertEqual(EvaluationComputer(None, ['https://docs.example/']).observe(), loaded)
            self.assertEqual(observe.call_count, 6)
            execute.assert_not_called()

    def test_scope_wait_is_bounded_and_rejects_explicit_outside_url_immediately(self):
        from jev_computer_use.computer import Computer
        from jev_computer_use.eval_boundary import EvaluationComputer
        pending = describe_window('Window: Loading\n', "com.google.Chrome", [])
        outside = describe_window('Window: Outside\n0 web area Other, URL: https://outside.example/\n', "com.google.Chrome", [])
        with patch.object(Computer, 'observe', return_value=pending), patch('jev_computer_use.eval_boundary.time.monotonic', side_effect=[0, 31]):
            with self.assertRaisesRegex(RuntimeError, 'Cannot verify'):
                EvaluationComputer(None, ['https://docs.example/']).observe()
        with patch.object(Computer, 'observe', return_value=outside) as observe, patch('jev_computer_use.eval_boundary.time.sleep') as sleep:
            with self.assertRaisesRegex(RuntimeError, 'outside.example'):
                EvaluationComputer(None, ['https://docs.example/']).observe()
            self.assertEqual(observe.call_count, 1)
            sleep.assert_not_called()

    def test_all_tabs_controls_and_multiline_text_remain_visible(self):
        raw = '0 standard window Test\n  1 tab Other tab\n  2 text Body\n  continuation\n'
        raw += "\n".join(f"  {n} button B{n}" for n in range(3, 150))
        obs = describe_window(raw, "app", [])
        menu = action_menu(obs, {})
        self.assertIn("click_149", menu)
        self.assertIn("click_1", menu)
        self.assertEqual(obs["ui_tree"], raw)
        self.assertNotIn("more_controls", menu)

    def test_compact_view_keeps_content_nesting_disabled_and_unknown_controls(self):
        raw = ('Window: "Mail"\n0 window Mail\n\t1 container Alice\n'
               '\t\t2 text 第一行\n  literal continuation\n\t\t3 文本 第二行\n'
               '\t\t4 button (disabled) Send\n\t\t5 custom widget Value: x\n'
               '\t6 container\n\t\t7 text unrelated but retained\n')
        self.assertEqual(compact_ui(raw),
            'Window: "Mail"\n0 window Mail\n group Alice\n  第一行\n'
            '  literal continuation\n  第二行\n  4 button (disabled) Send\n'
            '  5 custom widget Value: x\n group\n  unrelated but retained\n')
        self.assertEqual(compact_ui('  1 text space-indented fallback'),
                         '  1 text space-indented fallback')
        self.assertEqual(compact_ui('\t9 text field (settable) Recipient, Value: Alice'),
                         ' 9 text field (settable) Recipient, Value: Alice')
        self.assertEqual(compact_ui('\t10 text area (settable) Body'),
                         ' 10 text area (settable) Body')

    def test_exact_saved_screen_batching_and_step_search_never_mix_snapshots(self):
        with tempfile.TemporaryDirectory() as root:
            first = describe_window('Window: A\n0 text Old value\n', 'app', [])
            second = describe_window('Window: B\n0 text New value\n', 'app', [])
            records = [
                {"kind": "observation", "next_step": 1, "observation": first},
                {"kind": "observation", "next_step": 2, "observation": second},
                {"kind": "observation", "next_step": 2, "observation": second},
            ]
            Path(root, 'history.jsonl').write_text('\n'.join(json.dumps(r) for r in records))
            read = read_task_history(root, step=1, contains=['value', 'absent'])
            self.assertIn('New value', read['text'])
            self.assertNotIn('Old value', read['text'])
            self.assertEqual(read['missing_terms'], ['absent'])
            ids = [observation_id(first), observation_id(second)]
            read = read_task_history(root, observation_ids=ids, contains=['value'])
            self.assertEqual(len(read['sources']), 2)
            self.assertEqual(read['text'].count('New value'), 1)
            self.assertIn('Old value', read['text'])
            with self.assertRaisesRegex(ValueError, 'Unknown observation'):
                read_task_history(root, observation_ids=['unseen'])


if __name__ == "__main__":
    unittest.main()
