# Agent Workflow Changelog

## 2026-09-03 — Guarded architecture-first workflow

The repository agent instructions were reconciled with the current AI-assisted development process.

Key changes:

- replaced the artificial "one tiny unit per prompt" rule with bounded vertical work packages;
- retained architecture-first requirements for production behavior changes;
- made GitHub Actions the authoritative automated verification gate;
- documented the primary implementer / independent reviewer separation;
- clarified scoped authorization for branches, commits, pushes, pull requests, and merges;
- retained user merge authority by default and prohibited inference of indefinite authority;
- added current blocking/advisory CI distinctions;
- preserved privacy, provenance, recognition-confidence, and local-only image boundaries;
- removed the stale hard-coded repository-wide test count in favor of current CI evidence;
- standardized final reporting around changed files, tests, risks, review findings, and deferred work.

This change is process documentation only. It does not modify production behavior, benchmark state, recognition semantics, collection data, or evidence authorization.
