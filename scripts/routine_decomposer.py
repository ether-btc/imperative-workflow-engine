#!/usr/bin/env python3
"""
routine_decomposer.py - Decompose tasks into Routine-style execution contracts.

Per the Routine framework (arXiv:2507.14447), each task is decomposed into
structured steps with:
  - Step number
  - Step name (concise imperative)
  - Step description (what, conditions, objectives)
  - Step tool (which function to call)
  - Termination condition

Usage:
    python3 scripts/routine_decomposer.py decompose "Create a cron job every hour"
    python3 scripts/routine_decomposer.py --test
"""

import argparse
import sys
import json
import re
from dataclasses import dataclass, field
from typing import Optional, List

VERSION = "0.1.0"


@dataclass
class RoutineStep:
    number: int
    name: str
    description: str
    tool: Optional[str] = None
    condition: Optional[str] = None
    terminates: bool = False


@dataclass
class Routine:
    steps: List[RoutineStep] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


def parse_step(line: str) -> Optional[RoutineStep]:
    """
    Parse a single step line in Routine format.
    Handles three patterns:
    1. Step N. Name: Description, using tool_name tool;
    2. Step N. Name: If condition, Description, using tool_name tool;
    3. Step N. Name: Description, using tool_name tool, and terminate workflow;
    """
    # Pattern: simple step - use [^,] for description to stop at first comma
    m = re.match(
        r"^Step\s+(\d+)\.\s+([^:]+):\s*([^,]+),\s*using\s+([a-zA-Z][a-zA-Z0-9_]*)\s*tool[;,]?\s*$",
        line.strip(),
    )
    if m:
        num = int(m.group(1))
        name = m.group(2).strip()
        desc = m.group(3).strip()
        tool = m.group(4).strip().rstrip("_")
        terminates = "terminate workflow" in line.lower()
        return RoutineStep(
            number=num, name=name, description=desc, tool=tool, terminates=terminates
        )

    # Pattern: conditional step
    m = re.match(
        r"^Step\s+(\d+)\.\s+([^:]+):\s*If\s+([^,]+),\s*([^,]+),\s*using\s+([a-zA-Z][a-zA-Z0-9_]*)\s*tool[;,]?\s*$",
        line.strip(),
    )
    if m:
        num = int(m.group(1))
        name = m.group(2).strip()
        condition = m.group(3).strip()
        desc = m.group(4).strip()
        tool = m.group(5).strip().rstrip("_")
        terminates = "terminate workflow" in line.lower()
        return RoutineStep(
            number=num,
            name=name,
            description=desc,
            tool=tool,
            condition=condition,
            terminates=terminates,
        )

    # Pattern: terminating step (simple + terminates flag)
    m = re.match(
        r"^Step\s+(\d+)\.\s+([^:]+):\s*([^,]+),\s*using\s+([a-zA-Z][a-zA-Z0-9_]*(?:_tool)?)\s*,\s*and\s+terminate\s+workflow\s*;?\s*$",
        line.strip(),
    )
    if m:
        num = int(m.group(1))
        name = m.group(2).strip()
        desc = m.group(3).strip()
        tool = m.group(4).strip()
        return RoutineStep(
            number=num, name=name, description=desc, tool=tool, terminates=True
        )

    return None


def decompose(task: str, available_tools: Optional[List[str]] = None) -> Routine:
    """
    Decompose a natural language task into Routine-style steps.
    Simplified heuristic version - production would use LLM.
    """
    tools = available_tools or [
        "terminal",
        "read_file",
        "write_file",
        "patch",
        "search_files",
        "cronjob",
        "delegate_task",
        "skill_view",
        "execute_code",
        "mnemosyne_remember",
    ]
    steps = []
    parts = re.split(
        r"\b(?:then|and then|next|after that)\b", task, flags=re.IGNORECASE
    )

    for i, part in enumerate(parts, 1):
        part = part.strip()
        if not part:
            continue
        tool = _heuristic_tool(part, tools)
        step = RoutineStep(
            number=i,
            name="Step {}".format(i),
            description=part,
            tool=tool,
            terminates=(i == len(parts)),
        )
        steps.append(step)

    return Routine(steps=steps, metadata={"original_task": task})


def _heuristic_tool(step_text: str, tools: List[str]) -> str:
    """Simple heuristic to guess which tool a step might use."""
    step_lower = step_text.lower()
    mappings = [
        (["create cron", "schedule", "cron"], "cronjob"),
        (["read file", "read"], "read_file"),
        (["write file", "create file", "write"], "write_file"),
        (["search", "find"], "search_files"),
        (["terminal", "bash", "run command"], "terminal"),
        (["delegate", "spawn", "subagent"], "delegate_task"),
        (["remember", "store", "memory"], "mnemosyne_remember"),
    ]
    for terms, tool in mappings:
        if any(t in step_lower for t in terms):
            return tool
    return "terminal"


def format_routine(routine: Routine) -> str:
    """Format a Routine as a string in Routine notation."""
    lines = []
    for step in routine.steps:
        base = "Step {}. {}: {}".format(step.number, step.name, step.description)
        if step.condition:
            base = "Step {}. {}: If {}, {}".format(
                step.number, step.name, step.condition, step.description
            )
        tool_str = ", using {}".format(step.tool) if step.tool else ""
        term_str = ", and terminate workflow" if step.terminates else ""
        lines.append(base + tool_str + term_str + ";")
    return "\n".join(lines)


# CLI


def run_tests() -> int:
    tests_passed = 0

    step = parse_step(
        "Step 1. Verify Permissions: Check user has admin role, using auth_tool;"
    )
    assert step is not None
    assert step.number == 1
    assert step.name == "Verify Permissions"
    assert "Check user" in step.description
    assert step.tool == "auth"
    assert not step.terminates
    tests_passed += 1

    step = parse_step(
        "Step 2. Fetch Data: If user is admin, retrieve records, using db_query_tool;"
    )
    assert step is not None
    assert step.number == 2
    assert step.condition == "user is admin"
    tests_passed += 1

    step = parse_step(
        "Step 3. Format Response: Return structured JSON, using formatter_tool, and terminate workflow;"
    )
    assert step is not None
    assert step.terminates
    tests_passed += 1

    step = parse_step("Not a valid step line")
    assert step is None
    tests_passed += 1

    routine = decompose("Read a file then write it back")
    assert len(routine.steps) == 2
    assert routine.steps[0].tool == "read_file"
    assert routine.steps[1].tool == "write_file"
    tests_passed += 1

    routine = Routine(
        steps=[
            RoutineStep(1, "Verify", "Check permissions", "auth_tool", None, False),
            RoutineStep(
                2,
                "Fetch",
                "If admin, retrieve records",
                "db_query_tool",
                "admin",
                False,
            ),
            RoutineStep(3, "Format", "Return JSON", "formatter_tool", None, True),
        ]
    )
    output = format_routine(routine)
    assert "Step 1. Verify:" in output
    assert "using auth_tool" in output
    assert "terminate workflow" in output
    tests_passed += 1

    print("PASS: {}/{} tests passed".format(tests_passed, tests_passed))
    print("PASS", flush=True)
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        return run_tests()

    parser = argparse.ArgumentParser(
        description="Routine Decomposer - task to execution contract",
        prog="routine_decomposer.py",
    )
    subparsers = parser.add_subparsers(dest="command")

    decomp_parser = subparsers.add_parser("decompose", help="Decompose a task")
    decomp_parser.add_argument("task", help="Task description")
    decomp_parser.add_argument("--tools", nargs="*", help="Available tool names")
    decomp_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("test", help="Run self-tests")

    store_parser = subparsers.add_parser("store", help="Store a routine in Mnemosyne")
    store_parser.add_argument("name", help="Routine name (key)")
    store_parser.add_argument(
        "--task", help="Task description (for decompose-then-store)"
    )
    store_parser.add_argument("--json", help="JSON serialized routine to store")

    load_parser = subparsers.add_parser("load", help="Load a routine from Mnemosyne")
    load_parser.add_argument("name", help="Routine name")
    load_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("clear", help="Clear all stored routines from Mnemosyne")

    args = parser.parse_args()

    if args.command == "test":
        return run_tests()
    elif args.command == "decompose":
        routine = decompose(args.task, args.tools)
        output = format_routine(routine)
        if args.json:
            print(
                json.dumps(
                    {
                        "original_task": args.task,
                        "steps": [
                            (
                                s.number,
                                s.name,
                                s.description,
                                s.tool,
                                s.condition,
                                s.terminates,
                            )
                            for s in routine.steps
                        ],
                        "formatted": output,
                    },
                    indent=2,
                )
            )
        else:
            print(output)
        return 0
    elif args.command == "store":
        import variable_memory as vm

        if args.json:
            import json

            routine_data = json.loads(args.json)
        elif args.task:
            # Decompose then store
            routine = decompose(args.task)
            routine_data = {
                "steps": [
                    (s.number, s.name, s.description, s.tool, s.condition, s.terminates)
                    for s in routine.steps
                ],
                "metadata": {"original_task": args.task},
            }
        else:
            print("ERROR: either --task or --json is required", file=sys.stderr)
            return 1
        import json

        # Serialize to JSON and store as variable
        key = f"routine:{args.name}"
        record = json.dumps(routine_data)
        # Use variable_memory's set_var via its internal mechanism
        # We bypass to use mnemosyne directly
        try:
            from hermes_tools import mnemosyne_scratchpad_write

            mnemosyne_scratchpad_write(key, record)
        except Exception:
            # fallback to variable_memory
            vm.set_var(key, record, vm.ValueType.STRING)
        print(f"Stored routine '{args.name}' ({len(record)} bytes)")
        return 0
    elif args.command == "load":
        import variable_memory as vm

        key = f"routine:{args.name}"
        result = vm.get_var(key)
        if result is None:
            print(f"ERROR: routine '{args.name}' not found", file=sys.stderr)
            return 1
        data, _ = result
        if args.json:
            import json

            print(json.dumps(json.loads(data), indent=2))
        else:
            # Reconstruct and format
            import json

            loaded = json.loads(data)
            steps = [
                RoutineStep(
                    number=s[0],
                    name=s[1],
                    description=s[2],
                    tool=s[3] if len(s) > 3 else None,
                    condition=s[4] if len(s) > 4 else None,
                    terminates=s[5] if len(s) > 5 else False,
                )
                for s in loaded.get("steps", [])
            ]
            routine = Routine(steps=steps, metadata=loaded.get("metadata", {}))
            print(format_routine(routine))
        return 0
    elif args.command == "clear":
        import variable_memory as vm

        # Clear all routines (keys starting with routine:)
        keys = vm.list_vars()
        count = 0
        for k in keys:
            if k.startswith("routine:"):
                vm.drop_var(k)
                count += 1
        print(f"Cleared {count} routine(s)")
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
