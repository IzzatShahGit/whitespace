"""Check translation files against the English source: same keys, same {placeholders}.

Usage: python3 scripts/check-i18n.py [code ...]   (default: every messages/*.json)
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "src" / "lib" / "i18n"


def english() -> dict[str, str]:
    """Flatten en.ts's object literal ("a.b.c" -> text). A small parser for that file only:
    `key: {` opens a group, `key: "text",` is a string (possibly on the next line)."""
    source = (ROOT / "en.ts").read_text()
    body = source[source.index("export const en = {") :]
    body = body[: body.index("\n};") + 3]
    out: dict[str, str] = {}
    stack: list[str] = []
    pending: str | None = None
    for line in body.splitlines()[1:]:
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        if m := re.match(r"^(\w+): \{$", s):
            stack.append(m.group(1))
        elif s.startswith("}"):
            if stack:
                stack.pop()
        elif m := re.match(r'^(\w+):\s*"(.*)",?$', s):
            out[".".join([*stack, m.group(1)])] = m.group(2)
        elif m := re.match(r"^(\w+):$", s):
            pending = m.group(1)
        elif pending and (m := re.match(r'^"(.*)",?$', s)):
            out[".".join([*stack, pending])] = m.group(1)
            pending = None
    return out


def flat(obj: object, prefix: str = "") -> dict[str, str]:
    if isinstance(obj, dict):
        result: dict[str, str] = {}
        for k, v in obj.items():
            result.update(flat(v, f"{prefix}{k}."))
        return result
    return {prefix[:-1]: str(obj)}


def holes(text: str) -> set[str]:
    return set(re.findall(r"\{(\w+)\}", text))


def main() -> int:
    source = english()
    codes = sys.argv[1:] or [p.stem for p in sorted((ROOT / "messages").glob("*.json"))]
    bad = 0
    for code in codes:
        path = ROOT / "messages" / f"{code}.json"
        try:
            data = flat(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            print(f"{code}: cannot read: {exc}")
            bad += 1
            continue
        problems = {
            "missing": sorted(set(source) - set(data)),
            "extra": sorted(set(data) - set(source)),
            "placeholders": [k for k in source if k in data and holes(source[k]) != holes(data[k])],
            "empty": [k for k, v in data.items() if not v.strip()],
        }
        found = {name: keys for name, keys in problems.items() if keys}
        if found:
            bad += 1
            for name, keys in found.items():
                print(f"{code}: {name}: {', '.join(keys[:20])}")
        else:
            print(f"{code}: ok ({len(data)} strings)")
    print(f"source: {len(source)} strings")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
