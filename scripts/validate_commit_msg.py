#!/usr/bin/env python3
"""Pre-commit local hook to validate commit messages follow Conventional Commits."""
from __future__ import annotations

import sys
import re

CC_RE = re.compile(r'^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\([^)]+\))?: .+')


def main():
    if len(sys.argv) < 2:
        print("No commit message file provided to hook.", file=sys.stderr)
        sys.exit(1)
    msg_path = sys.argv[1]
    try:
        with open(msg_path, 'r', encoding='utf-8') as f:
            # Use first non-empty line as subject
            lines = f.read().splitlines()
    except OSError:
        print("Could not read commit message.", file=sys.stderr)
        sys.exit(1)
    subject = ''
    for line in lines:
        if line.strip():
            subject = line.strip()
            break
    if not subject:
        print("Empty commit message; conventional commit required.", file=sys.stderr)
        sys.exit(1)
    if not CC_RE.match(subject):
        print("Commit message must follow Conventional Commits (type(scope)?: subject)", file=sys.stderr)
        print("Got:  '" + subject + "'", file=sys.stderr)
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
