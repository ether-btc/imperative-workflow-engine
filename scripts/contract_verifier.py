#!/usr/bin/env python3
"""
contract_verifier.py — Runtime Verification of Execution Contracts

Treats LLM tool outputs as contracts and verifies them before accepting.
Per the Routine framework (arXiv:2507.14447), each step has a expected
outcome that must be validated. On violation: halt and surface the error.

Usage:
    python3 scripts/contract_verifier.py verify --input contract.json
    python3 scripts/contract_verifier.py --test
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any

VERSION = "0.1.0"


class ViolationSeverity(Enum):
    """How critical a contract violation is."""

    WARNING = "warning"  # Minor deviation, log and continue
    ERROR = "error"  # Significant deviation, halt
    CRITICAL = "critical"  # Safety boundary breached, halt immediately


@dataclass
class ContractViolation:
    """A single contract violation."""

    step_number: int
    step_name: str
    expected: str
    actual: str
    severity: ViolationSeverity
    message: str


@dataclass
class VerificationResult:
    """Result of verifying a contract against actual output."""

    passed: bool
    violations: list[ContractViolation] = field(default_factory=list)
    warnings: list[ContractViolation] = field(default_factory=list)


@dataclass
class ContractStep:
    """A single step in an execution contract."""

    number: int
    name: str
    description: str
    tool: Optional[str] = None
    condition: Optional[str] = None
    terminates: bool = False
    expected_outcome: Optional[str] = None
    output_schema: Optional[dict] = None


@dataclass
class ExecutionContract:
    """A complete execution contract with steps and metadata."""

    steps: list[ContractStep] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


# ── Validation patterns ───────────────────────────────────────────────────


def validate_tool_called(tool_name: str, expected_tool: str) -> bool:
    """Check that the expected tool was called."""
    if not expected_tool:
        return True
    # Strip _tool suffix for flexible matching
    expected = expected_tool.replace("_tool", "")
    return expected in tool_name.replace("_tool", "")


def validate_schema(data: Any, schema: dict) -> tuple[bool, str]:
    """
    Validate data against a simple output schema.

    Schema keys:
        type: required type name ("str", "int", "float", "bool", "list", "dict")
        pattern: regex pattern (for strings)
        min_length: minimum length (for strings/lists)
        max_length: maximum length (for strings/lists)
        enum: list of allowed values
        keys: sub-schema for dicts (key -> schema dict)
        items: sub-schema for lists (item schema)
    """
    schema_type = schema.get("type", "any")

    if schema_type == "str":
        if not isinstance(data, str):
            return False, f"expected string, got {type(data).__name__}"
        if "pattern" in schema:
            if not re.search(schema["pattern"], data):
                return (
                    False,
                    f"string {data!r} does not match pattern {schema['pattern']}",
                )
        if "min_length" in schema and len(data) < schema["min_length"]:
            return False, f"string length {len(data)} < min {schema['min_length']}"
        if "max_length" in schema and len(data) > schema["max_length"]:
            return False, f"string length {len(data)} > max {schema['max_length']}"
        if "enum" in schema and data not in schema["enum"]:
            return False, f"{data!r} not in allowed values {schema['enum']}"

    elif schema_type == "int":
        if not isinstance(data, int) or isinstance(data, bool):
            return False, f"expected int, got {type(data).__name__}"

    elif schema_type == "float":
        if not isinstance(data, (int, float)) or isinstance(data, bool):
            return False, f"expected float, got {type(data).__name__}"

    elif schema_type == "bool":
        if not isinstance(data, bool):
            return False, f"expected bool, got {type(data).__name__}"

    elif schema_type == "list":
        if not isinstance(data, list):
            return False, f"expected list, got {type(data).__name__}"
        if "min_length" in schema and len(data) < schema["min_length"]:
            return False, f"list length {len(data)} < min {schema['min_length']}"
        if "max_length" in schema and len(data) > schema["max_length"]:
            return False, f"list length {len(data)} > max {schema['max_length']}"
        if "items" in schema and data:
            for i, item in enumerate(data):
                ok, msg = validate_schema(item, schema["items"])
                if not ok:
                    return False, f"list[{i}]: {msg}"

    elif schema_type == "dict":
        if not isinstance(data, dict):
            return False, f"expected dict, got {type(data).__name__}"
        if "keys" in schema:
            for key, val_schema in schema["keys"].items():
                if key not in data:
                    return False, f"required key {key!r} missing"
                ok, msg = validate_schema(data[key], val_schema)
                if not ok:
                    return False, f"key {key!r}: {msg}"

    return True, ""


def validate_step_output(
    step: ContractStep,
    actual_output: Any,
) -> list[ContractViolation]:
    """
    Validate actual output against step's expected outcome and schema.
    Returns list of violations (empty = passed).
    """
    violations = []

    # 1. Tool was called check
    tool_called = actual_output.get("tool_called") or actual_output.get("tool_name") or ""
    if step.tool and tool_called:
        if not validate_tool_called(actual_output["tool_called"], step.tool):
            violations.append(
                ContractViolation(
                    step_number=step.number,
                    step_name=step.name,
                    expected=step.tool,
                    actual=actual_output["tool_called"],
                    severity=ViolationSeverity.ERROR,
                    message=f"Wrong tool called: expected {step.tool}, got {tool_called}",
                )
            )

    # 2. Schema validation
    if step.output_schema:
        ok, msg = validate_schema(actual_output.get("result"), step.output_schema)
        if not ok:
            violations.append(
                ContractViolation(
                    step_number=step.number,
                    step_name=step.name,
                    expected=f"schema: {step.output_schema}",
                    actual=str(actual_output.get("result")),
                    severity=ViolationSeverity.ERROR,
                    message=f"Output schema violation at Step {step.number}: {msg}",
                )
            )

    # 3. Expected outcome text check (substring match)
    if step.expected_outcome:
        result_str = str(actual_output.get("result", ""))
        if step.expected_outcome.lower() not in result_str.lower():
            violations.append(
                ContractViolation(
                    step_number=step.number,
                    step_name=step.name,
                    expected=step.expected_outcome,
                    actual=result_str,
                    severity=ViolationSeverity.WARNING,
                    message="Expected outcome substring not found in output",
                )
            )

    return violations


def verify_contract(
    contract: ExecutionContract,
    step_outputs: list[dict],
) -> VerificationResult:
    """
    Verify a full execution contract against actual step outputs.

    Args:
        contract: The execution contract with expected steps
        step_outputs: List of actual outputs, one per step (in order)

    Returns:
        VerificationResult with passed status and any violations
    """
    violations: list[ContractViolation] = []
    warnings: list[ContractViolation] = []

    # Check step count matches
    if len(step_outputs) != len(contract.steps):
        violations.append(
            ContractViolation(
                step_number=0,
                step_name="contract",
                expected=f"{len(contract.steps)} steps",
                actual=f"{len(step_outputs)} outputs",
                severity=ViolationSeverity.ERROR,
                message=f"Step count mismatch: contract has {len(contract.steps)} steps, got {len(step_outputs)} outputs",
            )
        )
        return VerificationResult(
            passed=False, violations=violations, warnings=warnings
        )

    # Verify each step
    for i, (step, output) in enumerate(zip(contract.steps, step_outputs)):
        step_violations = validate_step_output(step, output)
        for v in step_violations:
            if v.severity == ViolationSeverity.WARNING:
                warnings.append(v)
            else:
                violations.append(v)

    # Check termination
    if contract.steps and contract.steps[-1].terminates:
        last_output = step_outputs[-1] if step_outputs else {}
        if not last_output.get("workflow_ended"):
            violations.append(
                ContractViolation(
                    step_number=contract.steps[-1].number,
                    step_name=contract.steps[-1].name,
                    expected="workflow ended",
                    actual="workflow continued",
                    severity=ViolationSeverity.ERROR,
                    message="Final step expected to terminate workflow but it did not",
                )
            )

    passed = len(violations) == 0
    return VerificationResult(passed=passed, violations=violations, warnings=warnings)


def load_contract(path: str) -> ExecutionContract:
    """Load an execution contract from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)

    steps = []
    for s in data.get("steps", []):
        steps.append(
            ContractStep(
                number=s.get("number", 0),
                name=s.get("name", ""),
                description=s.get("description", ""),
                tool=s.get("tool"),
                condition=s.get("condition"),
                terminates=s.get("terminates", False),
                expected_outcome=s.get("expected_outcome"),
                output_schema=s.get("output_schema"),
            )
        )

    return ExecutionContract(steps=steps, metadata=data.get("metadata", {}))


def load_outputs(path: str) -> list[dict]:
    """Load step outputs from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("outputs", [])


# ── CLI ───────────────────────────────────────────────────────────────────


def run_tests() -> int:
    tests_passed = 0

    # Test 1: Tool validation — correct tool
    ok = validate_tool_called("terminal", "terminal_tool")
    assert ok, "Expected pass"
    tests_passed += 1

    # Test 2: Tool validation — wrong tool
    ok = validate_tool_called("read_file", "terminal_tool")
    assert not ok
    tests_passed += 1

    # Test 3: Schema validation — string pattern
    ok, msg = validate_schema("abc123", {"type": "str", "pattern": r"^\w+$"})
    assert ok, f"Expected pass, got {msg}"
    tests_passed += 1

    # Test 4: Schema validation — string pattern fail
    ok, msg = validate_schema("abc-123", {"type": "str", "pattern": r"^\w+$"})
    assert not ok
    tests_passed += 1

    # Test 5: Schema validation — string enum
    ok, msg = validate_schema("error", {"type": "str", "enum": ["ok", "error", "warn"]})
    assert ok
    tests_passed += 1

    # Test 6: Schema validation — list with items
    ok, msg = validate_schema([1, 2, 3], {"type": "list", "items": {"type": "int"}})
    assert ok, f"Expected pass, got {msg}"
    tests_passed += 1

    # Test 7: Schema validation — list item type fail
    ok, msg = validate_schema([1, "x", 3], {"type": "list", "items": {"type": "int"}})
    assert not ok
    tests_passed += 1

    # Test 8: Schema validation — dict with keys
    ok, msg = validate_schema(
        {"name": "test", "count": 5},
        {
            "type": "dict",
            "keys": {
                "name": {"type": "str"},
                "count": {"type": "int"},
            },
        },
    )
    assert ok, f"Expected pass, got {msg}"
    tests_passed += 1

    # Test 9: Verify contract — all steps pass
    contract = ExecutionContract(
        steps=[
            ContractStep(
                1,
                "Test",
                "Do the thing",
                "terminal",
                None,
                False,
                output_schema={"type": "str", "min_length": 1},
            ),
        ]
    )
    outputs = [{"tool_called": "terminal_tool", "result": "success"}]
    result = verify_contract(contract, outputs)
    assert result.passed, f"Expected pass, got violations: {result.violations}"
    tests_passed += 1

    # Test 10: Verify contract — wrong tool (ERROR)
    contract = ExecutionContract(
        steps=[
            ContractStep(1, "Test", "Do the thing", "read_file"),
        ]
    )
    outputs = [{"tool_called": "terminal_tool", "result": "ok"}]
    result = verify_contract(contract, outputs)
    assert not result.passed
    assert any(v.severity == ViolationSeverity.ERROR for v in result.violations)
    tests_passed += 1

    # Test 11: Verify contract — step count mismatch
    contract = ExecutionContract(
        steps=[
            ContractStep(1, "Step1", "Do thing A"),
            ContractStep(2, "Step2", "Do thing B"),
        ]
    )
    outputs = [{"tool_called": "terminal_tool", "result": "ok"}]
    result = verify_contract(contract, outputs)
    assert not result.passed
    tests_passed += 1

    # Test 12: Verify contract — termination check
    contract = ExecutionContract(
        steps=[
            ContractStep(1, "Final", "End here", "terminal", None, True),
        ]
    )
    outputs = [
        {"tool_called": "terminal_tool", "result": "done", "workflow_ended": "true"}
    ]
    result = verify_contract(contract, outputs)
    assert result.passed
    tests_passed += 1

    print(f"PASS: {tests_passed}/{tests_passed} tests passed")
    print("PASS", flush=True)
    return 0


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        return run_tests()

    parser = argparse.ArgumentParser(
        description="Contract Verifier — runtime verification of execution contracts",
        prog="contract_verifier.py",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    verify_parser = subparsers.add_parser("verify", help="Verify a contract")
    verify_parser.add_argument(
        "--contract", required=True, help="Path to contract JSON"
    )
    verify_parser.add_argument(
        "--outputs", required=True, help="Path to step outputs JSON"
    )
    verify_parser.add_argument("--json", action="store_true", help="JSON output")

    subparsers.add_parser("test", help="Run self-tests")

    args = parser.parse_args()

    if args.command == "test":
        return run_tests()
    elif args.command == "verify":
        try:
            contract = load_contract(args.contract)
            outputs = load_outputs(args.outputs)
            result = verify_contract(contract, outputs)

            if args.json:
                print(
                    json.dumps(
                        {
                            "passed": result.passed,
                            "violation_count": len(result.violations),
                            "warnings": len(result.warnings),
                            "violations": [
                                {
                                    "step": v.step_number,
                                    "name": v.step_name,
                                    "expected": v.expected,
                                    "actual": v.actual,
                                    "severity": v.severity.value,
                                    "message": v.message,
                                }
                                for v in result.violations
                            ],
                        },
                        indent=2,
                    )
                )
            else:
                if result.passed:
                    print(f"PASS — contract verified ({len(result.warnings)} warnings)")
                else:
                    print(f"FAIL — {len(result.violations)} violation(s):")
                    for v in result.violations:
                        print(
                            f"  Step {v.step_number} [{v.severity.value}]: {v.message}"
                        )
                        print(f"    Expected: {v.expected}")
                        print(f"    Actual:   {v.actual}")
                    for v in result.warnings:
                        print(f"  Step {v.step_number} [warning]: {v.message}")
            return 0 if result.passed else 1
        except FileNotFoundError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
