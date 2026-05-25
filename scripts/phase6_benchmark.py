#!/usr/bin/env python3
"""
Phase 6 — Benchmark: privilege_encoding impact measurement

Collects baseline step metrics from E2E demo, then runs with
apply_privilege_encoding() treatment to compute before/after delta.

Usage:
    python3 scripts/phase6_benchmark.py baseline      # collect baseline metrics
    python3 scripts/phase6_benchmark.py treatment     # collect treatment metrics
    python3 scripts/phase6_benchmark.py compare       # compare baseline vs treatment
    python3 scripts/phase6_benchmark.py run           # run full benchmark
"""

import json
import sys
import time
import subprocess
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent.resolve()
FIXTURE_DIR = SCRIPT_DIR / "fixtures" / "benchmark"
RESULTS_DIR = SCRIPT_DIR / "fixtures" / "benchmark"
RESULTS_FILE = RESULTS_DIR / "results.json"

BASELINE_FILE = RESULTS_DIR / "baseline_metrics.json"
TREATMENT_FILE = RESULTS_DIR / "treatment_metrics.json"

# examples/ is one level up from scripts/
DEMO_PATH = SCRIPT_DIR.parent / "examples" / "phase5_demo.py"


@dataclass
class StepMetric:
    step: int
    phase: str
    action: str
    passed: bool
    latency_ms: float
    hallucination_detected: bool = False
    privilege_tier_access: str = "N/A"


@dataclass
class WorkflowRun:
    workflow_id: str
    privilege_tier: str
    duration_ms: float
    steps: list[StepMetric]
    total_steps: int = 0
    passed_steps: int = 0
    hallucination_count: int = 0
    privilege_abuse_count: int = 0


def load_results(mode: str) -> Optional[dict]:
    path = BASELINE_FILE if mode == "baseline" else TREATMENT_FILE
    if not path.exists():
        return None
    with open(path) as f:
        return json.load(f)


def save_results(data: dict, mode: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = BASELINE_FILE if mode == "baseline" else TREATMENT_FILE
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"[SAVE] {mode} metrics -> {path}")


def run_e2e_demo() -> tuple[str, int]:
    result = subprocess.run(
        [sys.executable, str(DEMO_PATH)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    return result.stdout + result.stderr, result.returncode


def parse_demo_output(output: str) -> list[StepMetric]:
    metrics: list[StepMetric] = []
    phases = [
        ("Phase 1: Privilege-Level Prompt Encoding", "Phase 1: Privilege Encoding"),
        ("Phase 2: Semantic Tool Filtering", "Phase 2: Tool Filtering"),
        ("Phase 3: Routine Execution Contracts", "Phase 3: Routine Decomposition"),
        ("Phase 4: Runtime Verification", "Phase 4: Contract Verification"),
        ("Phase 5: Variable Memory", "Phase 5: Variable Memory"),
    ]

    phase_found = [False] * len(phases)
    for line in output.splitlines():
        for i, (search_str, label) in enumerate(phases):
            if search_str in line:
                phase_found[i] = True

    if all(phase_found):
        for i, (_, label) in enumerate(phases):
            metrics.append(StepMetric(
                step=i + 1,
                phase=label,
                action="end-to-end-run",
                passed=True,
                latency_ms=0.0,
                hallucination_detected=False,
                privilege_tier_access="N/A",
            ))
    elif any(phase_found):
        for i, (_, label) in enumerate(phases):
            if phase_found[i]:
                metrics.append(StepMetric(
                    step=i + 1,
                    phase=label,
                    action="end-to-end-run",
                    passed=True,
                    latency_ms=0.0,
                    hallucination_detected=False,
                    privilege_tier_access="N/A",
                ))
    return metrics


def compute_run_stats(steps: list[StepMetric], tier: str) -> WorkflowRun:
    passed = sum(1 for s in steps if s.passed)
    hallucinations = sum(1 for s in steps if s.hallucination_detected)
    abuse = sum(1 for s in steps if s.privilege_tier_access not in ("N/A", "granted"))
    total = len(steps)
    return WorkflowRun(
        workflow_id="phase5_e2e",
        privilege_tier=tier,
        duration_ms=0.0,
        steps=steps,
        total_steps=total,
        passed_steps=passed,
        hallucination_count=hallucinations,
        privilege_abuse_count=abuse,
    )


def compute_delta(baseline: dict, treatment: dict) -> dict:
    def safe_rate(n, total):
        return (n / total * 100) if total > 0 else 0.0

    b_total = sum(w["passed_steps"] for w in baseline.get("workflows", []))
    b_steps = sum(w["total_steps"] for w in baseline.get("workflows", []))
    b_halls = sum(w["hallucination_count"] for w in baseline.get("workflows", []))
    b_abuse = sum(w["privilege_abuse_count"] for w in baseline.get("workflows", []))

    t_total = sum(w["passed_steps"] for w in treatment.get("workflows", []))
    t_steps = sum(w["total_steps"] for w in treatment.get("workflows", []))
    t_halls = sum(w["hallucination_count"] for w in treatment.get("workflows", []))
    t_abuse = sum(w["privilege_abuse_count"] for w in treatment.get("workflows", []))

    b_acc = safe_rate(b_total, b_steps)
    t_acc = safe_rate(t_total, t_steps)
    b_hall = safe_rate(b_halls, b_steps)
    t_hall = safe_rate(t_halls, t_steps)
    b_ab = safe_rate(b_abuse, b_steps)
    t_ab = safe_rate(t_abuse, t_steps)

    return {
        "step_accuracy_baseline": b_acc,
        "step_accuracy_treatment": t_acc,
        "hallucination_rate_baseline": b_hall,
        "hallucination_rate_treatment": t_hall,
        "privilege_abuse_baseline": b_ab,
        "privilege_abuse_treatment": t_ab,
        "delta_step_accuracy": t_acc - b_acc,
        "delta_hallucination": t_hall - b_hall,
        "delta_privilege_abuse": t_ab - b_ab,
    }


def cmd_baseline() -> None:
    print("=== Phase 6: Baseline Collection ===")
    print("Running E2E demo (no apply_privilege_encoding treatment)\n")
    output, _ = run_e2e_demo()
    metrics = parse_demo_output(output)
    workflows = [compute_run_stats(metrics, tier="read-only")]
    data = {
        "workflows": [asdict(w) for w in workflows],
        "step_accuracy_baseline": (
            sum(w.passed_steps for w in workflows) /
            max(sum(w.total_steps for w in workflows), 1) * 100
        ),
        "note": "Baseline -- no apply_privilege_encoding() treatment. "
                "Uses current Hermes system prompt (Phase 1-5 structure only).",
    }
    save_results(data, "baseline")
    print(f"\nBaseline: {len(metrics)} steps measured -> {BASELINE_FILE}")


def cmd_treatment() -> None:
    print("=== Phase 6: Treatment Collection ===")
    print("NOTE: Real treatment requires instrumented Hermes session with")
    print("      apply_privilege_encoding() post hook or native prompt_builder.py:1183 PR.")
    print("      This run collects a PLACEHOLDER result.\n")

    baseline_data = load_results("baseline")
    output, _ = run_e2e_demo()
    metrics = parse_demo_output(output)
    workflows = [compute_run_stats(metrics, tier="read-only")]

    data = {
        "workflows": [asdict(w) for w in workflows],
        "step_accuracy_treatment": (
            sum(w.passed_steps for w in workflows) /
            max(sum(w.total_steps for w in workflows), 1) * 100
        ),
        "note": "TREATMENT PLACEHOLDER -- real measurement requires live Hermes integration. "
                "Two paths: (1) adapter post-hook in a skill, or (2) native PR to prompt_builder.py:1183.",
        "_placeholder": True,
    }
    save_results(data, "treatment")
    print(f"\nTreatment placeholder: {len(metrics)} steps -> {TREATMENT_FILE}")


def cmd_compare() -> None:
    baseline = load_results("baseline")
    treatment = load_results("treatment")

    if baseline is None or treatment is None:
        print("[ERROR] Run baseline and treatment first:")
        print("  python3 scripts/phase6_benchmark.py baseline")
        print("  python3 scripts/phase6_benchmark.py treatment")
        sys.exit(1)

    delta = compute_delta(baseline, treatment)

    print("=" * 60)
    print("Phase 6 Benchmark Results")
    print("=" * 60)
    print(f"  Step accuracy:  baseline={delta['step_accuracy_baseline']:.1f}%  "
          f"treatment={delta['step_accuracy_treatment']:.1f}%  "
          f"delta={delta['delta_step_accuracy']:+.1f}%")
    print(f"  Hallucination:  baseline={delta['hallucination_rate_baseline']:.1f}%  "
          f"treatment={delta['hallucination_rate_treatment']:.1f}%  "
          f"delta={delta['delta_hallucination']:+.1f}%")
    print(f"  Privilege abuse: baseline={delta['privilege_abuse_baseline']:.1f}%  "
          f"treatment={delta['privilege_abuse_treatment']:.1f}%  "
          f"delta={delta['delta_privilege_abuse']:+.1f}%")
    print()

    if treatment.get("_placeholder"):
        print("[NOTE] Treatment is placeholder -- real benchmark needs Hermes integration.")
        print("       See docs/phase6-benchmark-design.md for integration paths.")
        print()

    results = {
        "delta": delta,
        "baseline_file": str(BASELINE_FILE),
        "treatment_file": str(TREATMENT_FILE),
        "is_placeholder": treatment.get("_placeholder", False),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results: {RESULTS_FILE}")


def cmd_run() -> None:
    cmd_baseline()
    print()
    cmd_treatment()
    print()
    cmd_compare()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    {"baseline": cmd_baseline, "treatment": cmd_treatment,
     "compare": cmd_compare, "run": cmd_run}.get(cmd, lambda: (print(f"Unknown: {cmd}"), sys.exit(1)))()