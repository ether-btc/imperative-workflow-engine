# Imperative Workflow Engine

Structured imperative prompt encoding for LLM agent runtime accuracy improvement.

## Overview

Based on the Routine framework (arXiv:2507.14447), this project implements privilege-level instruction encoding that improves multi-step task accuracy from ~41% to ~96%.

## Components

| Script | Purpose | Status |
|--------|---------|--------|
| `scripts/privilege_encoder.py` | Encode instruction text with `[[Privilege N]]` markers | ✅ 10/10 |
| `scripts/routine_decomposer.py` | Decompose tasks into Routine-style execution contracts | ✅ 6/6 |
| `scripts/contract_verifier.py` | Runtime verification of execution contracts | ✅ 12/12 |
| `scripts/tool_filter.py` | Semantic tool filtering by contextual relevance | ✅ 11/11 |
| `scripts/variable_memory.py` | Mnemosyne-backed typed KV store for `{{key}}` refs | ✅ 13/13 |

Fixtures: `scripts/fixtures/sample_contract.json` + `sample_outputs.json`

## Privilege Levels

| Level | Label | Use |
|-------|-------|-----|
| 0 | Safety rules | MUST NEVER deviate |
| 1 | System imperatives | Core system directives |
| 2 | Skill-loaded rules | Default for skill instructions |
| 3 | User requests | Default for user requests |
| 4 | Tool outputs | Tool results |

## Usage

```bash
# Encode a skill instruction at Privilege 2 (skill level)
python3 scripts/privilege_encoder.py encode "Your instruction here" --level 2

# Decompose a task into execution contract
python3 scripts/routine_decomposer.py decompose "Create a cron job every hour"

# Store a routine in Mnemosyne
python3 scripts/routine_decomposer.py store my-routine --task "Create a cron job"

# Variable memory — set, get, resolve {{key}} references
python3 scripts/variable_memory.py set name "Alice" --type str
python3 scripts/variable_memory.py get name
python3 scripts/variable_memory.py resolve "Hello {{name}}!"

# Run tests
python3 scripts/privilege_encoder.py --test
python3 scripts/routine_decomposer.py --test
python3 scripts/contract_verifier.py --test
python3 scripts/tool_filter.py --test
python3 scripts/variable_memory.py --test

# End-to-end contract verification
python3 scripts/contract_verifier.py verify \
  --contract scripts/fixtures/sample_contract.json \
  --outputs scripts/fixtures/sample_outputs.json
```

## Integration

The privilege encoder integrates into `agent/prompt_builder.py::build_skills_system_prompt()` at lines 1183-1190.

See `SKILL.md` for full architecture documentation.

## Links

- Repo: https://github.com/ether-btc/imperative-workflow-engine
- Research: Zhou et al. 2025 — arXiv:2507.14447 (Routine framework)
- Research: Wang et al. 2026 — arXiv:2604.09443v3 (ManyIH)