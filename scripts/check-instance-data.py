#!/usr/bin/env python3
"""Refuse instance data in a repository of the platform.

The repositories publish the platform's design, never its instance: no
hostnames, addresses, tokens or hardware identifiers (ADR-006). A commit can
carry them into history in four places, and this script checks all four: the
lines it adds, the names of its files, its message, and its author's address.

    check-instance-data.py --staged         the staged changes (pre-commit hook)
    check-instance-data.py --message FILE   a commit message (commit-msg hook)
    check-instance-data.py --history        every commit on every branch
    check-instance-data.py --stdin          lines from standard input, to test

Instance data is recognised in two ways:

- by its shape: an address in a private or tailnet range, a tailnet name, a
  token, a hardware identifier, a recovery key;
- by your instance's own values, one per line in
  ~/.config/research-platform/instance-values.txt, outside every repository.

Public values that only look like instance data, such as a vendor's key
fingerprint, are listed in instance-data-allow.txt, beside this script.

A finding names the place and the rule, never the value, so that a CI log does
not publish it again; in CI, a finding in a file's name does not print the
name either. Exit status: 0 nothing found, 1 something found, 2 a usage or git
error.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

# The shapes of instance data: (rule, regular expression, case-sensitive).
# None of these expressions matches its own text, so this file passes its own
# check.
SHAPES = [
    ("private-ipv4",
     r"(?<![0-9])(?<![0-9]\.)"
     r"(?:10\.[0-9]{1,3}|172\.(?:1[6-9]|2[0-9]|3[01])|192\.168)"
     r"\.[0-9]{1,3}\.[0-9]{1,3}(?![0-9])(?!\.[0-9])", False),
    ("tailnet-ipv4",
     r"(?<![0-9])(?<![0-9]\.)100\.(?:6[4-9]|[7-9][0-9]|1[01][0-9]|12[0-7])"
     r"\.[0-9]{1,3}\.[0-9]{1,3}(?![0-9])(?!\.[0-9])", False),
    ("tailnet-ipv6", r"fd7a:115c:a1e0[:]", False),
    ("tailnet-name", r"[a-z0-9-]+\.ts\.net(?![a-z0-9-])", False),
    ("mac-address",
     r"(?<![0-9a-f:-])(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}(?![0-9a-f:-])", False),
    ("email-address", r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)*\.[a-z]{2,}",
     False),
    ("ssh-host-fingerprint", r"SHA256:[A-Za-z0-9+/]{43}", True),
    ("ssh-public-key", r"AAAA[0-9A-Za-z+/]{60,}", True),
    ("gpu-uuid", r"GPU-[0-9a-f]{8}-", False),
    ("nvme-eui", r"nvme-eui\.[0-9a-f]{16}", False),
    ("uuid",
     r"(?<![0-9a-f])[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}"
     r"-[0-9a-f]{12}(?![0-9a-f])", False),
    ("long-hex-string", r"(?<![0-9a-f])[0-9a-f]{32,}(?![0-9a-f])", False),
    ("healthchecks-ping-url", r"hc-ping\.com/[0-9a-z_-]{8,}", False),
    # A topic on the public server, not a page under docs.ntfy.sh.
    ("ntfy-topic-url", r"(?<![a-z0-9.-])ntfy\.sh/[a-z0-9_-]+", False),
    ("bitlocker-recovery-key", r"[0-9]{6}(?:-[0-9]{6}){7}", False),
    ("tailscale-key", r"tskey-[a-z]+-[A-Za-z0-9]+", True),
    ("github-token",
     r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}",
     True),
]
SHAPES = [(rule, re.compile(rx, 0 if case_sensitive else re.IGNORECASE))
          for rule, rx, case_sensitive in SHAPES]

HUNK = re.compile(r"^@@ -[0-9]+(?:,[0-9]+)? \+([0-9]+)(?:,[0-9]+)? @@")
NOREPLY_DOMAIN = "@users.noreply.github.com"
GITHUB_NOREPLY = "noreply@" + "github.com"
ALLOW_FILE = Path(__file__).resolve().parent / "instance-data-allow.txt"
GUIDE = "docs/guides/set-up-the-instance-data-guard.md"
IN_CI = os.environ.get("CI") == "true"


def note(message):
    print(f"instance-data guard: {message}", file=sys.stderr)


def values_file():
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "research-platform" / "instance-values.txt"


def read_list(path):
    """The non-empty lines of a list that are not # comments, numbered."""
    items = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if line and not line.startswith("#"):
            items.append((number, line))
    return items


def git(*args):
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        note(f"git {args[0]} failed: {result.stderr.strip()}")
        sys.exit(2)
    return result.stdout


class Checker:
    def __init__(self):
        self.findings = 0
        allowed = [value for _, value in read_list(ALLOW_FILE)]
        self.allowed = (re.compile("|".join(map(re.escape, allowed)),
                                   re.IGNORECASE) if allowed else None)
        self.values = []
        path = values_file()
        if not path.exists():
            if not IN_CI:
                note(f"no list of instance values at {path}; only shapes are "
                     f"checked ({GUIDE}, section 3)")
            return
        for number, value in read_list(path):
            if len(value) < 4:
                note(f"line {number} of your list is shorter than 4 "
                     f"characters and is skipped")
            else:
                self.values.append((number, value.lower()))

    def check(self, place, text):
        if self.allowed:
            text = self.allowed.sub(" ", text)
        rules = [rule for rule, rx in SHAPES if rx.search(text)]
        lowered = text.lower()
        rules += [f"instance value (line {number} of your list)"
                  for number, value in self.values if value in lowered]
        for rule in rules:
            self.findings += 1
            print(f"{place}: {rule}")

    def check_address(self, place, address):
        address = address.strip().lower()
        if not (address.endswith(NOREPLY_DOMAIN) or address == GITHUB_NOREPLY):
            self.findings += 1
            print(f"{place}: not a GitHub noreply address")


def check_lines(checker, diff):
    """Check the added lines of a diff made with -U0.

    A line "commit <hash>", which --history puts before each commit's diff,
    labels the findings that follow it. Diff lines that carry content start
    with "+", "-" or "\\", so that line cannot be mistaken for content.
    """
    label, path, number, in_hunk = "", None, 0, False
    for line in diff.splitlines():
        if line.startswith("commit "):
            label, in_hunk = f"commit {line.split()[1][:12]}: ", False
        elif line.startswith("diff --git "):
            in_hunk = False
        elif line.startswith("@@"):
            match = HUNK.match(line)
            if match:
                number, in_hunk = int(match.group(1)), True
        elif not in_hunk:
            if line.startswith("+++ "):
                target = line[4:]
                path = None if target == "/dev/null" else target[2:]
        elif line.startswith("+"):
            checker.check(f"{label}{path}:{number}", line[1:])
            number += 1


def check_names(checker, listing):
    """Check the file names of a --name-only listing."""
    label = ""
    for line in listing.splitlines():
        if line.startswith("commit "):
            label = f"commit {line.split()[1][:12]}: "
        elif line:
            name = "a file name" if IN_CI else f"{line} (its name)"
            checker.check(f"{label}{name}", line)


def staged(checker):
    options = ["--cached", "--no-renames", "--diff-filter=ACMR"]
    check_names(checker, git("diff", *options, "--name-only"))
    check_lines(checker, git("diff", *options, "--no-color", "--no-ext-diff",
                             "-U0"))
    for line in git("diff", *options, "--numstat").splitlines():
        if line.startswith("-\t-\t"):
            note(f"binary file not checked, look at it yourself: {line[4:]}")
    for who in ("author", "committer"):
        ident = git("var", f"GIT_{who.upper()}_IDENT")
        address = ident[ident.find("<") + 1:ident.find(">")]
        checker.check_address(f"your {who} address", address)


def message(checker, path):
    lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()
    for number, line in enumerate(lines, 1):
        if not line.startswith("#"):
            checker.check(f"commit message, line {number}", line)


def history(checker):
    records = git("log", "--all", "--format=%H%x1f%ae%x1f%ce%x1f%B%x1e")
    for record in records.split("\x1e"):
        record = record.strip("\n")
        if not record:
            continue
        commit, author, committer, body = record.split("\x1f", 3)
        label = f"commit {commit[:12]}"
        checker.check_address(f"{label}: author address", author)
        checker.check_address(f"{label}: committer address", committer)
        for number, line in enumerate(body.splitlines(), 1):
            checker.check(f"{label}: message, line {number}", line)
    options = ["--all", "--no-renames", "--diff-filter=ACMR",
               "--format=commit %H"]
    check_names(checker, git("log", *options, "--name-only"))
    check_lines(checker, git("log", *options, "-p", "--no-color",
                             "--no-ext-diff", "-U0"))


def from_stdin(checker):
    for number, line in enumerate(sys.stdin.read().splitlines(), 1):
        checker.check(f"stdin:{number}", line)


def main(argv):
    if len(argv) == 2 and argv[0] == "--message":
        mode = "--message"
    elif len(argv) == 1 and argv[0] in ("--staged", "--history", "--stdin"):
        mode = argv[0]
    else:
        print(__doc__, file=sys.stderr)
        return 2
    checker = Checker()
    if mode == "--staged":
        staged(checker)
    elif mode == "--message":
        message(checker, argv[1])
    elif mode == "--history":
        history(checker)
    else:
        from_stdin(checker)
    if checker.findings:
        refused = (" Nothing was committed." if mode in ("--staged", "--message")
                   else "")
        note(f"{checker.findings} finding(s).{refused} See {GUIDE}.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
