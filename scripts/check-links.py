#!/usr/bin/env python3
"""Check that every relative link in the repository's Markdown resolves.

    check-links.py

A link resolves when its target exists in the repository and, when it names
an anchor in a Markdown file, that file has a heading or an HTML id with that
anchor, made the way GitHub makes them. Links with a scheme, such as https:,
are not followed, so the check needs no network. Code blocks and code spans
are skipped. Exit status: 0 every link resolves, 1 a link is broken, 2 a git
error.
"""

import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from urllib.parse import unquote

FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
CODE_SPAN = re.compile(r"(`+).+?\1")
INLINE_LINK = re.compile(r"\]\(\s*<?([^)\s>]+)>?(?:\s+[\"'][^\"']*[\"'])?\s*\)")
DEFINITION = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s|$)")
HTML_ID = re.compile(r"""<a\s[^>]*\b(?:id|name)\s*=\s*["']([^"']+)["']""",
                     re.IGNORECASE)
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.IGNORECASE)


def prose(path):
    """The lines of a Markdown file outside code blocks, numbered."""
    fence = None
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        match = FENCE.match(line)
        if match:
            marker = match.group(1)
            if fence is None:
                fence = marker
            elif marker[0] == fence[0] and len(marker) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield number, line


def slug(heading, seen):
    """GitHub's anchor for a heading: its text, lowercased, with spaces as
    hyphens and without punctuation; a repeated anchor gets -1, -2..."""
    text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", heading)
    text = text.replace("`", "").replace("*", "")
    kept = [ch for ch in text.lower()
            if unicodedata.category(ch)[0] in "LMN"
            or unicodedata.category(ch) == "Pc" or ch in " -"]
    anchor = "".join(kept).replace(" ", "-")
    count = seen.get(anchor, 0)
    seen[anchor] = count + 1
    return anchor if count == 0 else f"{anchor}-{count}"


def anchors(path, cache={}):
    if path not in cache:
        seen, found = {}, set()
        for _, line in prose(path):
            match = HEADING.match(line)
            if match:
                found.add(slug(match.group(1), seen))
            found.update(HTML_ID.findall(line))
        cache[path] = found
    return cache[path]


def main():
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print("check-links: not in a git repository", file=sys.stderr)
        return 2
    root = Path(result.stdout.strip()).resolve()
    files = subprocess.run(["git", "-C", str(root), "ls-files", "-z", "*.md"],
                           capture_output=True, text=True).stdout.split("\0")
    checked, broken = 0, 0
    for name in filter(None, files):
        source = root / name
        for number, line in prose(source):
            line = CODE_SPAN.sub("", line)
            targets = INLINE_LINK.findall(line) + DEFINITION.findall(line)
            for target in targets:
                if SCHEME.match(target):
                    continue
                checked += 1
                part, _, anchor = target.partition("#")
                path = (source.parent / unquote(part)).resolve() if part else source
                inside = path == root or root in path.parents
                ok = inside and path.exists()
                if ok and anchor and path.suffix == ".md":
                    ok = unquote(anchor) in anchors(path)
                if not ok:
                    broken += 1
                    print(f"{name}:{number}: {target}")
    print(f"check-links: {checked} relative links, {broken} broken",
          file=sys.stderr)
    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main())
