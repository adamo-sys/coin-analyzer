# Recognition30 Experiment 6 closeout

## Disposition

`EXPERIMENT_6_LEXICAL_RETRIEVAL_ENRICHMENT_NOT_SUPPORTED`

Experiment 6 is closed. The bounded lexical-reference treatment did not improve
correct-candidate retrieval recall over the control. This record does not
authorize a production retriever, verifier, identity-gate, or provider behavior
change.

## Execution evidence

- Execution date: 2026-09-26.
- Frozen dataset: `recognition30_v1`.
- Frozen dataset fingerprint (`recognition30-dataset-fingerprint-v1`):
  `5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`.
- Input observation report:
  `C:\Projects\recognition30-runs\recognition30-current-baseline-20260926\report.json`.
- E6 result artifact:
  `C:\Projects\recognition30-runs\recognition30-current-baseline-20260926\e6-retrieval.json`.
- Evaluator schema:
  `coin-analyzer-recognition30-e6-retrieval-replay-v1`.
- Cases: 30.
- Provider/model calls: 0.
- Production changes: none.

The experiment replayed the already-recorded grounded observations. The control
used the current sparse deterministic catalogue representation. The treatment
added only deterministic lexical reference material from existing country
aliases and type-design metadata; it did not derive reference terms from the
evaluated observations.

## Results

| Metric | Control | Treatment |
| --- | ---: | ---: |
| Correct candidate retrieved @10 | 11/30 | 11/30 |
| Recall@10 | 36.7% | 36.7% |
| Delta | — | 0/30 |

Two cases, CA-R30-017 and CA-R30-026, failed closed before retrieval because
their grounded evidence was conflicting.

The treatment changed some candidate sets and rankings, so it was not
behaviorally inert, but it rescued zero additional correct candidates. The
bounded hypothesis that simple deterministic lexical-reference enrichment would
materially improve Recognition30 retrieval is therefore not supported.

## Interpretation boundary

The 36.7% figure is a retrieval diagnostic under the frozen Recognition30
benchmark catalogue and observations. It is not production recognition
accuracy and does not replace an official baseline.

This result supports evaluating a distinct visual-reference retrieval hypothesis
next, while preserving the current conservative downstream verification and
identity gate. Any Coin-CLIP or other embedding/reference-corpus experiment
requires its own bounded design and authorization.
