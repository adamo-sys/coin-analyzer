# Stage 10 Reliability Gate

## Purpose

The first Stage 10 two-candidate experiment is intentionally bounded. Merging the runtime slice is not, by itself, evidence that Coin Analyzer should gain broader swarm-like behavior.

This gate defines the evidence required before any architecture work that would increase candidate count, introduce real concurrency, allow specialized parallel roles, or otherwise broaden Stage 10 authority.

## Evidence required

The repository should demonstrate that the two-candidate experiment:

- produces the same aggregate decision from identical structured inputs;
- preserves the same decision when only the caller-supplied experiment identifier changes;
- invokes each authorized candidate no more than once;
- never retries or replaces a failed candidate automatically;
- isolates candidate-local failures so they do not corrupt the other candidate's evidence;
- snapshots both candidates' invariant evidence before either candidate executes;
- rejects out-of-scope changes only for the affected candidate;
- rejects missing/failed validation or invariant evidence only for the affected candidate;
- preserves zero/one/multiple viable-candidate outcomes deterministically;
- never synthesizes or combines candidate code;
- never promotes a preferred candidate automatically;
- requires human review whenever one or more candidates are viable;
- preserves human authority when deterministic comparison cannot distinguish a winner.

## Current evidence slice

`test_parallel_experiment_reliability.py` provides focused deterministic and adversarial coverage for these properties without changing Stage 10 runtime behavior.

## Broader Stage 10 entry condition

Any future expansion beyond the fixed two-candidate experiment requires all of the following:

1. this reliability evidence is merged;
2. focused tests are green;
3. full repository regression is green;
4. blocking CI, security, and quality checks are green;
5. no unresolved review finding contradicts the Stage 10 contract;
6. a separate architecture decision explicitly defines the proposed broader authority.

Passing this gate does not authorize additional agents, concurrency, retries, dynamic spawning, autonomous target discovery, candidate-code composition, or promotion authority. It only establishes that the fixed experiment is stable enough to consider a separately reviewed expansion.

## Still prohibited

Even after this gate passes, the following remain prohibited unless a later architecture decision explicitly changes them:

- open-ended swarms;
- unbounded agent group chat;
- recursive delegation;
- dynamic agent creation;
- automatic retries or replacement candidates;
- autonomous target selection;
- automatic candidate synthesis or code merging;
- collection, model, prompt, configuration, or policy mutation outside explicit reviewable scope;
- merge, deploy, release, or promotion authority.

Human repository-owner selection and normal repository CI remain mandatory.