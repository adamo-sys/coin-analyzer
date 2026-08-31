# Coin Analyzer — Commit Prompt

```text
MODE: COMMIT

Verify:
- expected branch
- expected HEAD/base state
- release gate passed
- working tree contains only intended changes

Run:
git diff --check
git status --short
git diff --stat

If clean and scoped correctly:

git add [ONLY INTENDED FILES]

git commit -m "[MESSAGE]"

Then return:

BRANCH:
HEAD:
COMMIT:
FILES:
STAT:
WORKING TREE:
```
