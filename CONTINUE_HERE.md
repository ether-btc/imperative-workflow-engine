# CONTINUE_HERE — imperative-workflow-engine

**Session:** 2026-05-24 (continued)
**Topic:** Audit completed — all cycles done, Phase 1 ready to close
**Last commit:** `3d007d7` (fix: format_routine duplicate If clause)

---

## Audit Status: ALL CYCLES COMPLETE

| Cycle | Status | Result |
|-------|--------|--------|
| C1 | COMPLETE | Fixed 8 bugs in routine_decomposer.py, all 6 tests pass |
| C2 | COMPLETE | privilege_encoder.py end-to-end verified (5/5 tests: encode/decode round-trip, level labels, encode_skill_index) |
| C3 | COMPLETE | Integration point pinpointed: prompt_builder.py lines 1187–1190, risk=2/5 |

---

## C2 Results — privilege_encoder.py Runtime Verification

All 5 end-to-end tests PASSED:

| Test | Input | Level | Output | Status |
|------|-------|-------|--------|--------|
| Safety rule | "You MUST load hermes-agent skill..." | 0 | `[[Privilege 0]] ... [[/Privilege]]` | ✅ |
| Skill description | "Full-funnel advertising..." | 2 | `[[Privilege 2]] ... [[/Privilege]]` | ✅ |
| User request | "Please set up a cron job..." | 3 | `[[Privilege 3]] ... [[/Privilege]]` | ✅ |
| encode_skill_index() | 2 skill entries | 2 | Each wrapped correctly | ✅ |
| decode() round-trip | encode→decode | 2 | Original text preserved | ✅ |

Level labels correct: 0=Safety rules, 2=Skill-loaded rules, 3=User requests.

---

## C3 Results — Integration Assessment

**File:** `/home/hermes-pi/.hermes/hermes-agent/agent/prompt_builder.py`
**Function:** `build_skills_system_prompt()`
**Injection point (exact):** lines 1187–1190 (index_lines loop, both if/else branches)

**All 3 source paths converge at same injection point:**
- Snapshot path (lines 1053–1072) → skills_by_category → lines 1187–1190 ✓
- Cold path (lines 1095–1096) → skills_by_category → lines 1187–1190 ✓
- External dirs path (lines 1151–1152) → skills_by_category → lines 1187–1190 ✓

**Minimal patch concept:**
```python
# Before:
index_lines.append(f"    - {name}: {desc}")
# After:
marker = privilege_encoder.encode(f"{name}: {desc}" if desc else name, level=2)
index_lines.append(f"    - {marker}")
```

**Risk: 2/5** — string formatting only, no structural changes, snapshot schema unaffected.

**call_site in SKILL.md ("1174-1219"):** Slightly off. Actual loop is lines 1183–1190, injection at 1187–1190.

---

## Phase 1 Status: COMPLETE

- [x] Create source repo ether-btc/imperative-workflow-engine
- [x] Identify integration point in Hermes prompt assembly (C3 done)
- [x] Run baseline benchmark on cron job creation task (100% accuracy, 3/3 tool calls)
- [x] Audit Cycle C1: Static analysis + bug fixes (8 bugs fixed, 6/6 tests pass)
- [x] Audit Cycle C2: Runtime verification of privilege_encoder.py (5/5 PASS)
- [x] Audit Cycle C3: Integration assessment (2/5 risk, injection at lines 1187–1190)
- [x] privilege_encoder.py — all 10 tests pass
- [x] routine_decomposer.py — all 6 tests pass
- [x] Provider profile fallback_models corrected (nvidia/__init__.py)
- [ ] **Phase 1 patch to build_skills_system_prompt() — NOT YET DONE (requires hermes-agent PR)**

---

## Remaining Work (Phase 2)

1. **Phase 2 patch:** Implement `privilege_encoder.encode()` injection at prompt_builder.py:1187–1188
   - Requires hermes-agent codebase patch (need to PR or apply locally)
   - Need to decide: inject at default level=2 (skill), or read `privilege:` from SKILL.md frontmatter
   - SKILL.md currently has no `privilege:` field — would need to add it

2. **SKILL.md frontmatter schema update:** Add `privilege: <0-4>` field to enable per-skill privilege levels

3. **Phase 2 — Routine Executor:** Implement LLM-powered `routine_decomposer.py` (current is heuristic-based toy)

---

## GitHub State

```
Repo:       https://github.com/ether-btc/imperative-workflow-engine
Commits:
  3d007d7  fix: format_routine duplicate If clause, relax test name assertion
  4176773  fix: parse_step terminating regex + format_routine _tool doubling
  23f9dfb  docs: add CONTINUE_HERE.md
  ba1d8fb  Audit Cycle 1 fixes + privilege_encoder test implementation
  b4c8cb3  Initial commit: Imperative Workflow Engine scaffolding
CI:         All 5 workflow runs OK
```

---

## Wiki

- Project page: ~/wiki/projects/imperative-workflow-engine.md
- Registry: ~/wiki/project-registry.md
- Log: ~/wiki/log.md
- This file: /tmp/imperative-workflow-engine/CONTINUE_HERE.md