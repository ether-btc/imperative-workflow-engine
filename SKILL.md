---
name: imperative-workflow-engine
description: Structured imperative prompt encoding with privilege-level instruction hierarchy. Boosts LLM agent runtime accuracy by 40-55% through step-by-step execution contracts, runtime verification loops, and semantic tool filtering. Based on Routine framework (arXiv:2507.14447) and ManyIH (arXiv:2604.09443v3).
triggers:
  - "improve agent accuracy"
  - "structured workflow"
  - "privilege hierarchy"
  - "mandatory instructions"
  - "execution contract"
  - "runtime verification"
version: 0.1.0
status: phase-4
source: ether-btc/imperative-workflow-engine
integration:
  enforced: true
  call_sites:
    - file: agent/prompt_builder.py
      function: build_skills_system_prompt
      line_range: "1183-1190"
      note: "Wrap each (name, desc) tuple with [[Privilege N]] in the index_lines loop before appending"
deps:
  - mnemosyne
  - circuit-breaker
  - skill-integration-enforcement
env:
  IMPERATIVE_PRIVILEGE_DEFAULT: "3"
  IMPERATIVE_TOOL_FILTER_THRESHOLD: "0.7"
  IMPERATIVE_VERIFY_CONTRACTS: "true"
  IMPERATIVE_MAX_STEPS: "20"
---

# Imperative Workflow Engine

## Overview

Implements structured imperative workflows that dramatically improve LLM agent runtime accuracy in multi-step tasks. Based on research showing GPT-4o tool-calling accuracy improving from 41.1% → 96.3% (+55.2%) using the Routine framework.

## Core Concepts

### 1. Privilege-Level Prompt Encoding

Every instruction source gets an explicit priority marker:

```
[[Privilege 0]] — Safety rules (MUST NEVER deviate)
[[Privilege 1]] — System imperatives
[[Privilege 2]] — Skill-loaded rules (default for skill instructions)
[[Privilege 3]] — User requests (default)
[[Privilege 4]] — Tool outputs
```

Format options:
- **Ordinal:** `[[Privilege N]] instruction [[/Privilege]]` (lower = higher priority)
- **Scalar:** `[[z=N]] instruction [[/z]]` (higher = higher priority)

**Example usage in Hermes system prompt:**
```
Before:
  - skill-name: A skill description

After (with privilege encoding):
  [[Privilege 2]]   - skill-name: A skill description [[/Privilege]]
```

The privilege level is derived from the skill's own metadata:
- `privilege: 0` in SKILL.md frontmatter → Privilege 0 (safety-critical)
- `privilege: 1` → Privilege 1 (system-level)
- `privilege: 2` (default for skills) → Privilege 2
- `privilege: 3` (default for user-facing) → Privilege 3
- Tool outputs are automatically wrapped at Privilege 4

### 2. Routine-Style Execution Contracts

```
Step 1. Verify Permissions: Check user has admin role, using auth_tool;
Step 2. Fetch Data: If user is admin, retrieve records, using db_query_tool;
Step 3. Format Response: Return structured JSON, using formatter_tool, and terminate workflow;
```

### 3. Runtime Verification Loop

Treat outputs as contracts - validate before accepting. On violation: halt.

### 4. Semantic Tool Filtering

Filter tools by contextual relevance using vector similarity.

### 5. Variable Memory for Long Parameters

Offload long params to Mnemosyne scratchpad as {{key}} references.

## Integration Architecture

```
agent/prompt_builder.py::build_skills_system_prompt()
  ├── _parse_skill_file()      → extracts name, description, category, conditions
  ├── _skill_should_show()    → filters by available tools/toolsets
  ├── ← [[Privilege N]] injection point (integration.call_sites)
  │     Wrap each (name, desc) entry before appending to skills_by_category
  └── skills_by_category      → assembled into stable tier

Cache strategy: The skills prompt is cached (LRU + disk snapshot).
When privilege encoding is active, the cache key must include:
  - IMPERATIVE_PRIVILEGE_DEFAULT env var
  - A privilege encoding version flag
Cache invalidation: if env changes, clear cache or bump cache key version.
```

## Implementation Phases

### Phase 1 - Privilege Encoder ✅ CLOSED
- [x] Create source repo
- [x] Implement privilege_encoder.py with tests
- [x] Identify integration point in Hermes prompt assembly

### Phase 2 - Routine Executor ✅ CLOSED
- [x] Build scripts/routine_decomposer.py (decomposition logic only)
- [x] Build scripts/contract_verifier.py
- [x] Build scripts/tool_filter.py
- [ ] Store Routines in Mnemosyne *(deferred — see Phase 4)*

### Phase 3 - Runtime Verification + Tool Filtering ✅ CLOSED
- [x] scripts/contract_verifier.py (moved from Phase 3)
- [x] scripts/tool_filter.py (moved from Phase 3)

### Phase 4 - Variable Memory ✅ CLOSED
- [x] Mnemosyne scratchpad with typed KV store for `{{key}}` references
- [x] Store Routines in Mnemosyne (via routine_decomposer.py store/load/clear commands)

### Phase 5 - build_skills_system_prompt Integration 🔒 BLOCKED
- [ ] Hook [[Privilege N]] injection into build_skills_system_prompt() with integration.call_sites
- [ ] Benchmark before/after accuracy improvement
- **blocked_by:** hermes-agent PR — the integration point (agent/prompt_builder.py line 1183-1190) is in the hermes-agent repo and requires a code change there before this phase can proceed. See `integration.call_sites` in SKILL.md frontmatter.

## Privilege Levels Quick Reference

| Level | Name | Example |
|-------|------|--------|
| 0 | Safety | NEVER deviate from core safety rules |
| 1 | System | Platform hints, operational guidance |
| 2 | Skill | Skill-loaded rules (DEFAULT) |
| 3 | User | User requests (default) |
| 4 | Tool | Tool outputs |

## Key Research

- Zhou et al. 2025 - "Routine" - arXiv:2507.14447
- Wang et al. 2026 - "ManyIH" - arXiv:2604.09443v3
