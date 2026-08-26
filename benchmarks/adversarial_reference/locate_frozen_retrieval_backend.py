#!/usr/bin/env python3
"""Locate the exact pre-freeze reference-retrieval backend without scoring.

The 25-case benchmark contract requires the first frozen run to reuse the
existing pilot implementation unchanged. This diagnostic searches the local
worktree, refs, reflogs, and dangling commits for likely ORB/HSV retrieval code
and reports candidates. It never opens benchmark images and never performs
retrieval scoring.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent.parent
OUTPUT = ROOT / "retrieval_backend_archaeology.json"

TERMS = (
    "ORB_create",
    "cv2.ORB",
    "BFMatcher",
    "NORM_HAMMING",
    "knnMatch",
    "compareHist",
    "calcHist",
    "reference retrieval",
    "reference_retrieval",
    "Recall@5",
    "Top-1",
)
MESSAGE_TERMS = ("retrieval", "reference", "pilot", "orb", "hsv", "benchmark", "similarity")
TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ps1"}


def git(*args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=REPO, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check,
    )


def current_tree_hits() -> list[dict]:
    hits: list[dict] = []
    for path in REPO.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if any(part in {".git", ".venv", "venv", "node_modules"} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        matched = [term for term in TERMS if term.lower() in text.lower()]
        if matched:
            hits.append({"path": path.relative_to(REPO).as_posix(), "terms": matched})
    return hits


def pick_lines(text: str, limit: int = 80) -> list[str]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[:limit]


def main() -> int:
    print("Frozen retrieval backend archaeology probe")
    print("Scoring blind: no benchmark images will be opened.\n")

    worktree = current_tree_hits()
    print(f"Current-tree candidate files: {len(worktree)}")
    for row in worktree[:40]:
        print(f"  - {row['path']} | {', '.join(row['terms'])}")

    pickaxe: dict[str, list[str]] = {}
    for term in TERMS[:7]:
        proc = git("log", "--all", "--oneline", f"-S{term}", "--", "*.py")
        rows = pick_lines(proc.stdout, 30)
        if rows:
            pickaxe[term] = rows
    print(f"Git pickaxe terms with hits: {len(pickaxe)}")
    for term, rows in pickaxe.items():
        print(f"  {term}: {len(rows)} hit(s)")
        for row in rows[:8]:
            print(f"    {row}")

    messages: list[str] = []
    for term in MESSAGE_TERMS:
        proc = git("log", "--all", "--oneline", "--regexp-ignore-case", f"--grep={term}")
        messages.extend(pick_lines(proc.stdout, 40))
    messages = list(dict.fromkeys(messages))
    print(f"Relevant commit-message hits: {len(messages)}")
    for row in messages[:40]:
        print(f"  {row}")

    reflog_proc = git("reflog", "show", "--all", "--oneline")
    reflog_lines = pick_lines(reflog_proc.stdout, 500)
    reflog_hits = [
        line for line in reflog_lines
        if any(term in line.lower() for term in MESSAGE_TERMS)
    ]
    print(f"Relevant reflog hits: {len(reflog_hits)}")
    for row in reflog_hits[:40]:
        print(f"  {row}")

    fsck = git("fsck", "--no-reflogs", "--unreachable", "--no-progress")
    dangling_commits = []
    for line in fsck.stdout.splitlines():
        m = re.match(r"unreachable commit ([0-9a-f]{40})$", line.strip())
        if m:
            dangling_commits.append(m.group(1))
    dangling_hits: list[dict] = []
    for sha in dangling_commits[:250]:
        subject = git("show", "-s", "--format=%s", sha).stdout.strip()
        if any(term in subject.lower() for term in MESSAGE_TERMS):
            dangling_hits.append({"sha": sha, "subject": subject})
            continue
        # Search the commit tree directly for strong implementation signatures.
        grep = git("grep", "-I", "-n", "-E", "ORB_create|BFMatcher|NORM_HAMMING|knnMatch|compareHist", sha, "--", "*.py")
        if grep.returncode == 0 and grep.stdout.strip():
            dangling_hits.append({"sha": sha, "subject": subject, "grep": pick_lines(grep.stdout, 20)})
    print(f"Unreachable commits inspected: {min(len(dangling_commits), 250)}")
    print(f"Potential unreachable backend commits: {len(dangling_hits)}")
    for row in dangling_hits[:30]:
        print(f"  {row['sha'][:12]} {row.get('subject','')}")
        for hit in row.get("grep", [])[:5]:
            print(f"    {hit}")

    artifact = {
        "schema": "coin-analyzer-retrieval-backend-archaeology-v1",
        "retrieval_scoring_run": False,
        "benchmark_images_opened": False,
        "current_tree_hits": worktree,
        "pickaxe_hits": pickaxe,
        "commit_message_hits": messages,
        "reflog_hits": reflog_hits,
        "unreachable_commits_seen": len(dangling_commits),
        "unreachable_candidate_hits": dangling_hits,
    }
    OUTPUT.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(f"\nWrote archaeology report: {OUTPUT}")
    print("Retrieval scoring was NOT run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
