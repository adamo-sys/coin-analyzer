# PentAGI — conditional adversarial security evaluation candidate

**Status:** DEFERRED / NO-GO for execution. **Scope:** research queue entry only (2026-10-15).

**Upstream:** https://github.com/vxcontrol/pentagi

## Decision and positioning

Retain PentAGI as a conditional, bounded candidate in the existing post-foundation security and agent-reliability evaluation queue. This is not an installation, implementation, integration, scan authorization, release gate, or independent workstream. Existing provenance/isolation/extraction work and authorized security-hardening tasks retain precedence. Do not alter frozen Bake-Off V1, Recognition30, or historical evidence. PentAGI is not a substitute for deterministic checks, CI, independent review, or owner acceptance. Keep iFixAi and code-search experiments (Codex/rg, jgrep, ColGrep-Agent) in their distinct evaluation roles; reconcile overlap before any future run.

## Hypothesis and smallest useful test

On explicitly authorized, disposable synthetic targets with seeded, independently verified vulnerabilities, PentAGI may identify reproducible incremental security findings beyond existing deterministic/static checks and independent review. Compare matched targets, frozen revisions, scope, budgets, and adjudication criteria. No live Coin Analyzer service, user collection, production repository, or external target is eligible.

Predeclare sample size, true-positive/false-positive thresholds, severity adjudication, isolation failure criteria, maximum runtime, tool calls, tokens, API spend, CPU/RAM, and operator effort before execution. Report detection recall/precision with exact denominators; unsupported findings; reproducibility; severity agreement; prompt-injection susceptibility; attempted unauthorized actions; network/filesystem boundary observations; evidence/provenance integrity; and incremental value over baseline. Missing or unverifiable evidence is UNKNOWN, not PASS.

## Prerequisites (separate owner GO required)

- Verify upstream commit, licensing (including any SDK or derivative-use restrictions), dependencies, supply-chain exposure, and data flows.
- Use a disposable dedicated environment, verified network deny-by-default, no host mounts, secrets, private images, personal records, or production credentials. Docker by itself does not establish containment.
- Define exact permitted targets and operations; deny external scans, persistence, lateral movement, credential collection, autonomous remediation, and unsupervised scope expansion.
- Establish auditable sanitized logging, kill switch, cleanup validation, resource ceilings, and independently adjudicated ground truth.
- Obtain explicit owner authorization for the exact environment, tools, test cases, and execution window.

## Early stop / disposition

Stop on unknown or violated isolation, unauthorized activity, missing rights or ground truth, unrepeatable findings, unacceptable false positives, or any time/cost/resource cap. Apply dependency-ordered ROI and early-stopping; prefer the single-agent default. A future favorable result supports only a bounded advisory role, not autonomous release authority.

**Current result:** proposal registered for review; no installation, downloads, scans, runtime validation, or benchmark execution performed. All operational readiness and licensing conclusions remain unverified.
