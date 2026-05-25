#!/usr/bin/env python3
"""
examples/phase5_demo.py — End-to-end demonstration of Imperative Workflow Engine

This script exercises all 5 phases together in a single workflow:
1. Privilege encoding of a sample system prompt
2. Tool filtering for a multi-tool task
3. Routine decomposition into execution contract
4. Contract verification against simulated outputs
5. Variable memory scratchpad for long parameters

Requires: all scripts/ *.py modules in the same project.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Ensure scripts/ are importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from privilege_encoder import encode, decode  # noqa: E402
from privilege_hook import encode_skill_index, apply_privilege_encoding  # noqa: E402
from routine_decomposer import decompose, format_routine  # noqa: E402
from contract_verifier import (  # noqa: E402
    ExecutionContract, ContractStep,
    verify_contract,
)
from tool_filter import filter_tools, Tool  # noqa: E402
from variable_memory import set_var, get_var, resolve, clear_vars, ValueType  # noqa: E402
from typing import List  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DEFAULT_TOOLS = [
    {"name": "terminal", "description": "Execute shell commands on the system"},
    {"name": "web_search", "description": "Search the web for information"},
    {"name": "web_extract", "description": "Extract content from a web page URL"},
    {"name": "file_read", "description": "Read the contents of a file"},
    {"name": "file_write", "description": "Write content to a file"},
    {"name": "mnemosyne_remember", "description": "Save durable information to persistent memory"},
    {"name": "mnemosyne_recall", "description": "Search persistent memory"},
    {"name": "cronjob", "description": "Manage scheduled cron jobs"},
    {"name": "terminal_run", "description": "Run a command in the terminal tool"},
    {"name": "delegate_task", "description": "Spawn a subagent to work on a task"},
    {"name": "skill_view", "description": "Load a skill's full content"},
    {"name": "skills_list", "description": "List available skills"},
]

SAMPLE_SYSTEM_PROMPT = """You are a helpful assistant.

Available skills:
- hermes-agent: Configure, extend, or contribute to Hermes Agent.
- mnemosyne: Persistent memory system for durable facts.
- terminal: Execute shell commands on the system.
- cronjob: Manage scheduled cron jobs.

Tool outputs should be formatted as JSON."""


# ---------------------------------------------------------------------------
# Phase 1 — Privilege Encoding
# ---------------------------------------------------------------------------
def demo_privilege_encoding():
    print("=== Phase 1: Privilege-Level Prompt Encoding ===\n")

    # Encode individual instructions
    safety = encode("Do not disclose secrets.", level=0)
    skill_rule = encode("Always check skill-loaded rules before acting.", level=2)
    user_req = encode("Create a cron job.", level=3)

    print("Safety (P0):     ", safety)
    print("Skill rule (P2): ", skill_rule)
    print("User request (P3): ", user_req)
    print()

    # Encode a full Hermes skill index
    skills_text = """- hermes-agent: Configure Hermes Agent
- mnemosyne: Persistent memory
- terminal: Execute shell commands"""

    encoded = encode_skill_index(skills_text, default_level=2)
    print("Encoded skill index:")
    print(encoded)
    print()

    # Decode a block
    decoded = decode("[[Privilege 3]] Create a cron job. [[/Privilege]]")
    print("Decoded:", decoded)
    print()

    # Apply full adapter to a synthetic system prompt
    adapted = apply_privilege_encoding(SAMPLE_SYSTEM_PROMPT)
    print("Full prompt with privilege encoding applied (first 5 lines):")
    for line in adapted.splitlines()[:5]:
        print("  ", line)
    print()

    return encoded


# ---------------------------------------------------------------------------
# Phase 2 — Tool Filtering
# ---------------------------------------------------------------------------
# Convert dicts to Tool objects for filter_tools
TOOLS_LIST: List[Tool] = [Tool(**t) for t in DEFAULT_TOOLS]

def demo_tool_filtering():
    print("=== Phase 2: Semantic Tool Filtering ===\n")

    task1 = "I need to search the web and extract a page, then save the result to a file."
    task2 = "Schedule a cron job to run every hour."
    task3 = "Read system logs and search for errors."

    for task in [task1, task2, task3]:
        print(f"Task: {task}")
        result = filter_tools(task, TOOLS_LIST, threshold=0.5)
        print(f"  Relevant tools ({len(result.filtered_tools)}/{len(TOOLS_LIST)}):")
        for name, score in result.filtered_tools:
            print(f"    {name:20s} — {score:.3f}")
        print()

    return result


# ---------------------------------------------------------------------------
# Phase 3 — Routine Decomposition
# ---------------------------------------------------------------------------
def demo_routine_decomposition():
    print("=== Phase 3: Routine Execution Contracts ===\n")

    task = "Check disk usage, search for large files, and log results to memory."
    tool_names = [t["name"] for t in DEFAULT_TOOLS]
    routine = decompose(task, tool_names)

    print(f"Task: {task}")
    print(f"Steps: {len(routine.steps)}")
    for step in routine.steps:
        print(f"  Step {step.number}: {step.name}")
        print(f"    Description: {step.description}")
        print(f"    Tool: {step.tool}")
        print(f"    Terminates: {step.terminates}")
        print()

    # Format and re-parse
    formatted = format_routine(routine)
    print("Formatted routine:")
    print(formatted)
    print()

    return routine


# ---------------------------------------------------------------------------
# Phase 4 — Runtime Verification
# ---------------------------------------------------------------------------
def demo_contract_verification(routine):
    print("=== Phase 4: Runtime Verification ===\n")

    # Build a contract from the decomposed routine
    steps = routine.steps if hasattr(routine, "steps") else []
    contract = ExecutionContract(
        steps=[
            ContractStep(
                number=i + 1,
                name=s.name,
                description=s.description or s.name,
                tool=s.tool,
                expected_outcome="success",
                output_schema={"type": "dict"},
            )
            for i, s in enumerate(steps[:3])  # first 3 steps only
            if s.tool
        ],
        metadata={"name": "disk_check_contract"},
    )

    # Simulate outputs (some correct, one wrong)
    simulated_outputs = {
        "step_1": {"tool_called": steps[0].tool if steps else "terminal", "status": "ok"},
        "step_2": {"tool_called": steps[1].tool if len(steps) > 1 else "web_search", "status": "ok"},
        # Step 3 intentionally missing to simulate a violation
    }

    result = verify_contract(contract, simulated_outputs)

    print(f"Contract: {contract.metadata.get('name', 'unnamed')}")
    print(f"  Steps expected: {len(contract.steps)}")
    print(f"  Steps found: {len(simulated_outputs)}")
    print(f"  Violations: {len(result.violations)}")
    for v in result.violations:
        print(f"    ❌ {v}")
    print(f"  Is valid: {result.passed}")
    print(f"  Can terminate: {result.can_terminate if hasattr(result, 'can_terminate') else 'N/A'}")
    print()


# ---------------------------------------------------------------------------
# Phase 5 — Variable Memory
# ---------------------------------------------------------------------------
def demo_variable_memory():
    print("=== Phase 5: Variable Memory (Mnemosyne scratchpad) ===\n")

    # Store values
    set_var("task_name", "disk cleanup", vtype=ValueType.STRING)
    set_var("threshold_gb", 10, vtype=ValueType.INT)
    set_var("dry_run", True, vtype=ValueType.BOOL)

    # Retrieve
    print("Stored variables:")
    for key in ["task_name", "threshold_gb", "dry_run"]:
        val = get_var(key)
        print(f"  {key}: {val}")
    print()

    # Resolve tokens in a template
    template = "Task: {{task_name}}, threshold={{threshold_gb}}GB, dry_run={{dry_run}}"
    resolved = resolve(template)
    print(f"Template: {template}")
    print(f"Resolved: {resolved}")
    print()

    # Clear for next run
    clear_vars()
    print("Variables cleared.\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    print("=" * 70)
    print("Imperative Workflow Engine — End-to-End Demo")
    print("=" * 70)
    print()

    demo_privilege_encoding()
    demo_tool_filtering()
    routine = demo_routine_decomposition()
    demo_contract_verification(routine)
    demo_variable_memory()

    print("=" * 70)
    print("Demo complete — all 5 phases exercised.")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
