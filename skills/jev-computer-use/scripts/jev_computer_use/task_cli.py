"""Delegate sustained System One computer use; the calling agent owns reasoning."""

import argparse
import json
import os
from pathlib import Path

from .computer import Computer
from .doctor import doctor
from .models import JevClient
from .runtime import NativeCUA
from .stage_state import read_status, request_stop
from .tasks import TaskRunner, complete_task, host_handoff


TOOL = {
    "name": "delegate_task",
    "description": "Delegate sustained text-accessible UI interaction to Jev. Keep comparison, ranking, calculation and final verification yourself: end the delegated task explicitly before that decision, then provide your concrete conclusion if further interaction remains. Handoff includes the current UI, history and takeover.js_binding in the same native session. Resume the same state_dir. Use this registered tool directly, not an invented wrapper alias.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "state_dir": {"type": "string", "description": "Private persistent task directory outside repositories; new directory for a new task"},
            "task": {"type": "string", "description": "Delegated interaction goal and task-specific constraints; omit on resume. If the user goal requires comparison/ranking/calculation, explicitly stop when its inputs/options are visible, before making that decision. Do not pass the whole reasoning task to Jev or predict a UI route."},
            "mode": {"type": "string", "enum": ["step", "realtime"], "description": "step for sequential work; realtime for interfaces changing on their own clock."},
            "period_ms": {"type": "integer", "minimum": 100, "maximum": 30000},
            "recheck_target": {"type": "boolean"},
            "input_texts": {"type": "object", "description": "Provide ALL known literal values required by the task as separate entries on the FIRST delegation. Prepare task-specified form/search criteria before seeing the fields, even if widget types are unknown. Each entry is copied verbatim or appended to observed field text with a space; native date/time formatting preserves its value; the runner additionally retains dates read from UI with source labels for date-field entry. Do not pre-resolve a fact the user asks Jev to find. These are values to enter, not button/checkbox labels to click; use {} for click-only work or no new known text. Revised text needs a new ID.", "additionalProperties": {
                "type": "object", "properties": {"text": {"type": "string", "description": "Exact literal value to insert in one field, without splitting or rewriting"}, "purpose": {"type": "string", "description": "What this entire literal value is for; not instructions to transform it"}},
                "required": ["text", "purpose"], "additionalProperties": False,
            }},
            "guidance": {"type": "string", "description": "Your concrete reasoning conclusion or task-specific interaction boundary, added to history. Resolve comparisons yourself before resuming; do not ask Jev to rank or calculate. Omit generic interaction instructions."},
            "max_steps": {"type": "integer", "minimum": 1},
            "max_seconds": {"type": "number", "exclusiveMinimum": 0},
            "min_continue_probability": {"type": "number", "minimum": 0, "maximum": 1, "description": "Default 0.5; lower continuation scores yield. Usually omit; not a calibrated guarantee."},
            "max_context_bytes": {"type": "integer", "minimum": 1, "description": "Default 100000 request bytes; overflow yields the full UI. Usually omit."},
            "pricing": {"type": "object", "description": "Optional verified USD rates per million Jev tokens; omit for unknown cost", "properties": {"input_tokens": {"type": "number", "minimum": 0}, "output_tokens": {"type": "number", "minimum": 0}}, "required": ["input_tokens", "output_tokens"], "additionalProperties": False},
        },
        "required": ["state_dir", "mode", "input_texts"], "additionalProperties": False,
    },
}

READ_TOOL = {
    "name": "read_task_history",
    "description": "Read earlier screens or diagnostics; the current UI is already in the handoff. Batch observation_ids; step selects one latest screen. With no selectors returns an index. Follow next_offset if truncated.",
    "inputSchema": {"type": "object", "properties": {
        "state_dir": {"type": "string"},
        "step": {"type": "integer", "minimum": 1},
        "observation_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1, "description": "Exact saved-screen IDs from handoff.observations or history results. Batch IDs to read several sources in one call. Do not combine with step."},
        "kind": {"type": "string", "enum": ["observation", "decision", "all"]},
        "offset": {"type": "integer", "minimum": 0},
        "max_chars": {"type": "integer", "minimum": 500, "maximum": 20000},
        "contains": {"type": "array", "items": {"type": "string", "minLength": 1}, "minItems": 1, "description": "Host-selected literal text to find in retained UI. Choose a step when known to avoid searching every screen."},
        "context_lines": {"type": "integer", "minimum": 0, "maximum": 40},
    }, "required": ["state_dir"], "additionalProperties": False},
    "annotations": {"readOnlyHint": True, "destructiveHint": False},
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--key-file", type=Path, default=os.environ.get("TYPESAFE_API_KEY_FILE"))
    parser.add_argument("--runtime-config")
    parser.add_argument("--doctor", action="store_true")
    operation = parser.add_mutually_exclusive_group()
    operation.add_argument("--status", action="store_true")
    operation.add_argument("--stop", action="store_true")
    operation.add_argument("--complete", action="store_true")
    parser.add_argument("--answer-file", type=Path)
    parser.add_argument("--wait", type=float, default=0)
    args = parser.parse_args(argv)
    if args.doctor:
        return doctor(args.runtime_config, "codex", "external", args.key_file)
    if not args.state_dir:
        parser.error("--state-dir is required")
    if args.status:
        value = read_status(args.state_dir, args.wait)
    elif args.stop:
        value = request_stop(args.state_dir)
    elif args.complete:
        if not args.answer_file:
            parser.error("--complete requires --answer-file with the outer agent's verified answer")
        value = complete_task(args.state_dir, args.answer_file.read_text())
    else:
        if not args.request_file:
            parser.error("--request-file is required")
        request = json.loads(args.request_file.read_text())
        if "mode" not in request:
            parser.error("The outer agent must choose mode=step or realtime")
        key = args.key_file.read_text().strip() if args.key_file else os.environ.get("TYPESAFE_API_KEY")
        if not key:
            parser.error("Configure TYPESAFE_API_KEY or --key-file")
        with NativeCUA(args.runtime_config) as native:
            value = TaskRunner(Computer(native), JevClient(key), args.state_dir).run(**request)
    print(json.dumps(host_handoff(value), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
