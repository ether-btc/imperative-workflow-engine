#!/usr/bin/env python3
"""
privilege_encoder.py — Privilege-Level Prompt Encoding

Encodes instruction sources with explicit [[Privilege N]] priority markers
per the ManyIH framework (arXiv:2604.09443v3).

Usage:
    python3 scripts/privilege_encoder.py encode "instruction text" --level 2
    python3 scripts/privilege_encoder.py --test
    python3 scripts/privilege_encoder.py batch --file instructions.txt
"""

import argparse
import os
import sys
import json
from dataclasses import dataclass
from typing import Optional

VERSION = "0.1.0"

# Privilege levels (lower ordinal = higher priority)
PRIV_SAFETY = 0   # [[Privilege 0]] — Safety rules (MUST NEVER deviate)
PRIV_SYSTEM = 1   # [[Privilege 1]] — System imperatives
PRIV_SKILL  = 2   # [[Privilege 2]] — Skill-loaded rules
PRIV_USER   = 3   # [[Privilege 3]] — User requests (default)
PRIV_TOOL   = 4   # [[Privilege 4]] — Tool outputs

PRIV_LABELS = {
    0: "Safety rules",
    1: "System imperatives",
    2: "Skill-loaded rules",
    3: "User requests",
    4: "Tool outputs",
}

DEFAULT_LEVEL = PRIV_USER  # 3


@dataclass
class EncodedInstruction:
    original: str
    encoded: str
    privilege_level: int
    format: str  # "ordinal" or "scalar"


def encode_ordinal(text: str, level: int) -> str:
    """Encode with [[Privilege N]] ... [[/Privilege]] format."""
    level = max(0, min(4, level))  # clamp to 0-4
    return f"[[Privilege {level}]] {text} [[/Privilege]]"


def encode_scalar(text: str, level: int) -> str:
    """Encode with [[z=N]] ... [[/z]] format (higher N = higher priority)."""
    level = max(0, min(4, level))
    return f"[[z={level}]] {text} [[/z]]"


def encode(text: str, level: int = DEFAULT_LEVEL, format: str = "ordinal") -> EncodedInstruction:
    """
    Encode instruction text with privilege marker.
    
    Args:
        text: The instruction text to encode
        level: Privilege level (0-4)
        format: "ordinal" (default) or "scalar"
    
    Returns:
        EncodedInstruction with original, encoded text, level, and format
    """
    if format == "scalar":
        encoded = encode_scalar(text, level)
    else:
        encoded = encode_ordinal(text, level)
    
    # Clamp for storage in the dataclass (mirrors what we put in the encoded string)
    clamped_level = max(0, min(4, level))
    return EncodedInstruction(
        original=text,
        encoded=encoded,
        privilege_level=clamped_level,
        format=format,
    )


def decode(encoded: str) -> Optional[EncodedInstruction]:
    """
    Decode a privilege-encoded string back to its components.
    Supports both ordinal and scalar formats.
    Returns None if the string is not properly encoded.
    """
    import re
    # Ordinal: [[Privilege N]] text [[/Privilege]]
    m = re.match(r'^\[\[Privilege (\d+)\]\]\s*(.+?)\s*\[\[/Privilege\]\]$', encoded, re.DOTALL)
    if m:
        level = int(m.group(1))
        return EncodedInstruction(original=m.group(2), encoded=encoded, 
                                  privilege_level=level, format="ordinal")
    
    # Scalar: [[z=N]] text [[/z]]
    m = re.match(r'^\[\[z=(\d+)\]\]\s*(.+?)\s*\[\[/z\]\]$', encoded, re.DOTALL)
    if m:
        level = int(m.group(1))
        return EncodedInstruction(original=m.group(2), encoded=encoded,
                                  privilege_level=level, format="scalar")
    
    return None


def encode_skill_index(skills: list[dict], default_level: int = PRIV_SKILL) -> str:
    """
    Encode a skill index with privilege markers for the Hermes system prompt.
    """
    lines = []
    for skill in skills:
        name = skill.get("name", "unknown")
        desc = skill.get("description", "")
        privilege = skill.get("privilege", default_level)
        entry = f"  - {name}: {desc}"
        encoded = encode(entry, privilege)
        lines.append(encoded.encoded)
    return "\n".join(lines)


def encode_source(contents: str, source_type: str = "skill") -> str:
    """Encode a complete instruction source with privilege markers."""
    level_map = {
        "safety": PRIV_SAFETY,
        "system": PRIV_SYSTEM,
        "skill": PRIV_SKILL,
        "user": PRIV_USER,
        "tool": PRIV_TOOL,
    }
    level = level_map.get(source_type.lower(), DEFAULT_LEVEL)
    return encode(contents, level).encoded


# ── CLI ──────────────────────────────────────────────────────────────

def run_tests() -> int:
    """Run self-tests. Returns 0 on success."""
    tests_passed = 0
    tests_failed = 0
    
    # Test 1: Ordinal encoding level 2
    result = encode("Test instruction", level=2, format="ordinal")
    assert result.encoded == "[[Privilege 2]] Test instruction [[/Privilege]]", f"Got: {result.encoded}"
    assert result.privilege_level == 2
    tests_passed += 1
    
    # Test 2: Ordinal encoding level 0 (safety)
    result = encode("MUST NEVER do this", level=0, format="ordinal")
    assert result.encoded == "[[Privilege 0]] MUST NEVER do this [[/Privilege]]", f"Got: {result.encoded}"
    tests_passed += 1
    
    # Test 3: Scalar encoding
    result = encode("Scalar test", level=3, format="scalar")
    assert result.encoded == "[[z=3]] Scalar test [[/z]]", f"Got: {result.encoded}"
    tests_passed += 1
    
    # Test 4: Decode ordinal
    decoded = decode("[[Privilege 1]] System imperative [[/Privilege]]")
    assert decoded is not None
    assert decoded.privilege_level == 1
    assert decoded.original == "System imperative"
    assert decoded.format == "ordinal"
    tests_passed += 1
    
    # Test 5: Decode scalar
    decoded = decode("[[z=4]] Tool output [[/z]]")
    assert decoded is not None
    assert decoded.privilege_level == 4
    assert decoded.original == "Tool output"
    assert decoded.format == "scalar"
    tests_passed += 1
    
    # Test 6: Level clamping (5 → 4)
    result = encode("Clamp test", level=5)
    assert result.privilege_level == 4
    tests_passed += 1
    
    # Test 7: Level clamping (negative → 0)
    result = encode("Clamp test", level=-1)
    assert result.privilege_level == 0
    tests_passed += 1
    
    # Test 8: Invalid decode returns None
    decoded = decode("Plain text without markers")
    assert decoded is None
    tests_passed += 1
    
    # Test 9: encode_skill_index
    skills = [{"name": "test-skill", "description": "A test skill", "category": "general"}]
    output = encode_skill_index(skills, default_level=PRIV_SKILL)
    assert "[[Privilege 2]]" in output
    assert "test-skill" in output
    tests_passed += 1
    
    # Test 10: encode_source
    output = encode_source("Skill body content here", source_type="skill")
    assert output == "[[Privilege 2]] Skill body content here [[/Privilege]]"
    tests_passed += 1
    
    print(f"PASS: {tests_passed}/{tests_passed + tests_failed} tests passed")
    print("PASS", flush=True)
    return 0


def main() -> int:
    # Handle --test BEFORE argparse processing
    if len(sys.argv) >= 2 and sys.argv[1] == "--test":
        return run_tests()
    
    parser = argparse.ArgumentParser(
        description="Privilege-Level Prompt Encoding Tool",
        prog="privilege_encoder.py",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # encode subcommand
    encode_parser = subparsers.add_parser("encode", help="Encode an instruction")
    encode_parser.add_argument("text", help="Instruction text to encode")
    encode_parser.add_argument("--level", type=int, default=DEFAULT_LEVEL,
                              choices=[0, 1, 2, 3, 4],
                              help=f"Privilege level (0-4, default: {DEFAULT_LEVEL})")
    encode_parser.add_argument("--format", choices=["ordinal", "scalar"], default="ordinal",
                              help="Encoding format")
    encode_parser.add_argument("--json", action="store_true", help="JSON output")
    
    # decode subcommand
    decode_parser = subparsers.add_parser("decode", help="Decode an encoded instruction")
    decode_parser.add_argument("encoded", help="Encoded instruction string")
    decode_parser.add_argument("--json", action="store_true", help="JSON output")
    
    # test subcommand
    subparsers.add_parser("test", help="Run self-tests")
    
    args = parser.parse_args()
    
    if args.command == "test":
        return run_tests()
    elif args.command == "encode":
        result = encode(args.text, level=args.level, format=args.format)
        if args.json:
            print(json.dumps({
                "original": result.original,
                "encoded": result.encoded,
                "privilege_level": result.privilege_level,
                "format": result.format,
                "label": PRIV_LABELS.get(result.privilege_level, "unknown"),
            }, indent=2))
        else:
            print(result.encoded)
        return 0
    elif args.command == "decode":
        result = decode(args.encoded)
        if result is None:
            print(f"ERROR: Not a valid encoded instruction", file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps({
                "original": result.original,
                "encoded": result.encoded,
                "privilege_level": result.privilege_level,
                "format": result.format,
                "label": PRIV_LABELS.get(result.privilege_level, "unknown"),
            }, indent=2))
        else:
            print(f"Level {result.privilege_level} ({PRIV_LABELS.get(result.privilege_level)}): {result.original}")
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
