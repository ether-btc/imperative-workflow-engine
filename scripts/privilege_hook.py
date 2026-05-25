#!/usr/bin/env python3
"""
privilege_hook.py — Skill-level hook adapter for Hermes Agent

Wraps build_skills_system_prompt() output to inject [[Privilege N]] markers
without modifying Hermes core. Import this skill in your Hermes session and
call apply_privilege_encoding() after loading regular skills.
"""

from __future__ import annotations

import re
import sys
from typing import Optional

# ---------------------------------------------------------------------------
# Privilege levels
# ---------------------------------------------------------------------------

PRIVILEGE_LEVELS = {
    "system": 0,      # safety rules — MUST NEVER deviate
    "imperative": 1,  # system imperatives
    "skill": 2,       # skill-loaded rules  ← default for all skills
    "user": 3,        # user requests         ← default for user queries
    "tool": 4,        # tool outputs
}


# ---------------------------------------------------------------------------
# Encoding / decoding
# ---------------------------------------------------------------------------

def encode(text: str, level: int = 2, *, fmt: str = "ordinal") -> str:
    """Wrap *text* in a privilege block."""
    if fmt == "scalar":
        return f"[[z={level}]] {text} [[/z]]"
    return f"[[Privilege {level}]] {text} [[/Privilege]]"


def decode(encoded: str, *, fmt: str = "ordinal") -> Optional[tuple[str, int]]:
    """Return (text, level) for the *first* privilege block, or None."""
    if fmt == "scalar":
        m = re.search(r"\[\[z=(\d+)\]\]\s+(.*?)\s*\[\[/z\]\]", encoded)
    else:
        m = re.search(r"\[\[Privilege (\d+)\]\]\s+(.*?)\s*\[\[/Privilege\]\]", encoded)
    if not m:
        return None
    return m.group(2), int(m.group(1))


# ---------------------------------------------------------------------------
# Skill-index encoding (the actual hook)
# ---------------------------------------------------------------------------

def encode_skill_index(skills_prompt: str, default_level: int = 2) -> str:
    """
    Parse a standard Hermes skill-index prompt and wrap each skill
    description with [[Privilege N]].

    Input format expected (Hermes):
      - <skill_name>: <skill_description>
      - <skill_name>: <skill_description>
      ...

    Returns the same prompt with privilege markers injected.
    """
    lines = skills_prompt.splitlines()
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        # Match "- <name>: <desc>" or "<number>. <name>: <desc>"
        m = re.match(r"^(\s*[-\*]?\s*)([^:]+):\s*(.*)$", stripped)
        if m:
            prefix = m.group(1)
            name = m.group(2).strip()
            desc = m.group(3).strip()
            wrapped = encode(f"{name}: {desc}", level=default_level)
            out.append(f"{prefix}{wrapped}")
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Adapter: wrap an existing prompt string
# ---------------------------------------------------------------------------

def apply_privilege_encoding(
    raw_system_prompt: str,
    *,
    user_level: int = 3,
    tool_level: int = 4,
    default_skill_level: int = 2,
) -> str:
    """
    Heuristically classify sections of a Hermes system prompt and wrap
    them with the appropriate privilege level.

    This is the main entry-point for the skill adapter.
    """
    lines = raw_system_prompt.splitlines()
    out: list[str] = []
    current_section = "unknown"

    for line in lines:
        stripped = line.strip().lower()

        # Detect section boundaries heuristically
        if stripped.startswith("you are") or stripped.startswith("safety") or "must never" in stripped:
            current_section = "system"
        elif stripped.startswith("available skills") or stripped.startswith("skills:"):
            current_section = "skills"
        elif stripped.startswith("tool") and "output" in stripped:
            current_section = "tool"
        elif stripped.startswith("user:") or stripped.startswith("request:"):
            current_section = "user"

        # Determine level
        if current_section == "system":
            level = PRIVILEGE_LEVELS["system"]
        elif current_section == "skills":
            level = default_skill_level
        elif current_section == "tool":
            level = PRIVILEGE_LEVELS["tool"]
        elif current_section == "user":
            level = PRIVILEGE_LEVELS["user"]
        else:
            level = default_skill_level

        out.append(encode(line, level=level))

    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _test() -> None:
    import doctest

    print("Running doctests + unit tests ...")
    assert encode("test", 2) == "[[Privilege 2]] test [[/Privilege]]"
    assert decode("[[Privilege 2]] test [[/Privilege]]") == ("test", 2)
    assert decode("no match") is None

    # Skill index encoding
    sample = "- hermes-workflow: Manage workflows\n- mnemosyne: Memory system"
    result = encode_skill_index(sample)
    assert "[[Privilege 2]] hermes-workflow:" in result
    assert "[[Privilege 2]] mnemosyne:" in result

    # Apply adapter
    prompt = "You are a helpful assistant.\nAvailable skills:\n- skill1: does X\nTool output."
    adapted = apply_privilege_encoding(prompt)
    assert "[[Privilege" in adapted
    print("✅ All tests passed")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Privilege hook adapter")
    sub = parser.add_subparsers(dest="cmd")

    p_encode = sub.add_parser("encode", help="Encode a single text block")
    p_encode.add_argument("text", help="Text to encode")
    p_encode.add_argument("--level", type=int, default=2, help="Privilege level (default 2)")

    p_decode = sub.add_parser("decode", help="Decode a single text block")
    p_decode.add_argument("text", help="Text to decode")

    p_index = sub.add_parser("index", help="Encode a Hermes skill index prompt")
    p_index.add_argument("--file", help="File containing skill index (default: stdin)")
    p_index.add_argument("--default-level", type=int, default=2)

    p_adapt = sub.add_parser("adapt", help="Apply full privilege encoding to a system prompt")
    p_adapt.add_argument("--file", help="File containing system prompt (default: stdin)")

    p_test = sub.add_parser("test", help="Run tests")

    args = parser.parse_args()

    if args.cmd == "encode":
        print(encode(args.text, args.level))
    elif args.cmd == "decode":
        result = decode(args.text)
        if result:
            print(f"level={result[1]} text={result[0]}")
        else:
            print("No privilege block found")
    elif args.cmd == "index":
        source = sys.stdin.read() if args.file is None else open(args.file).read()
        print(encode_skill_index(source, default_level=args.default_level))
    elif args.cmd == "adapt":
        source = sys.stdin.read() if args.file is None else open(args.file).read()
        print(apply_privilege_encoding(source))
    elif args.cmd == "test":
        _test()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
