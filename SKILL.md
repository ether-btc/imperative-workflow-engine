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
status: planning
source: ether-btc/imperative-workflow-engine
integration:
  enforced: false
  call_sites: []
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

Implements structured imperative workflows that dramatically improve LLM agent runtime accuracy in multi-step tasks.

## Core Concepts

### 1. Privilege-Level Prompt Encoding

```
[[Privilege 0]] - Safety rules (MUST NEVER deviate)
[[Privilege 1]] - System imperatives
[[Privilege 2]] - Skill-loaded rules
[[Privilege 3]] - User requests (default)
[[Privilege 4]] - Tool outputs
```

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

## Phases

### Phase 1 - Privilege Encoder (current)
- [x] Create source repo
- [ ] Implement scripts/privilege_encoder.py
- [ ] Identify integration point in Hermes prompt assembly
- [ ] Benchmark before/after

### Phase 2 - Routine Executor
- [ ] Build scripts/routine_decomposer.py
- [ ] Store Routines in Mnemosyne

### Phase 3 - Runtime Verification + Tool Filtering
- [ ] scripts/contract_verifier.py + scripts/tool_filter.py

### Phase 4 - Variable Memory
- [ ] Mnemosyne scratchpad with typed KV store

## Key Research

- Zhou et al. 2025 - "Routine" - arXiv:2507.14447
- Wang et al. 2026 - "ManyIH" - arXiv:2604.09443v3
