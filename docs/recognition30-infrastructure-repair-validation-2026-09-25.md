# Recognition30 standalone infrastructure-repair validation

## Disposition

`PASS — INFRASTRUCTURE VALIDITY ONLY`

This standalone validation establishes that the previously observed provider
structured-output / `max_output_tokens` infrastructure-failure class was not
reproduced across the five targeted cases under the repaired current
configuration. It is not an official Recognition30 baseline, replacement
baseline, reconciliation run, or recognition-accuracy measurement.

## Immutable execution evidence

- Source SHA: `caea7c351c5b3e0d2414c48be1f9e519e67c7432`.
- Dataset fingerprint (`recognition30-dataset-fingerprint-v1`):
  `5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`.
- Private standalone run directory:
  `C:\Projects\recognition30-runs\recognition30-v1-infrastructure-repair-validation-20260925-001`.
- Cases: `CA-R30-009`, `CA-R30-017`, `CA-R30-022`, `CA-R30-026`, and
  `CA-R30-029`.
- Provider/model: `openai-responses-grounded-observation` / `gpt-5.6-terra`.
- Execution: low reasoning effort, 2,000 maximum output tokens, 120-second
  timeout, SDK retries disabled, and non-adaptive full-face plus rim views.

## Provider and terminal-record results

- Confirmed provider observations: 20 attempted / 20 successful.
- Malformed structured outputs: 0; `max_output_tokens` truncations/failures: 0;
  timeouts: 0; provider failures: 0.
- Infrastructure-valid terminal records: 5 / 5.
- Input tokens: 191,544. Output tokens: 8,319. Cost is unavailable because
  the retained provider reports contain token counts but no pricing data.

Every case ended in `ABSTAIN`; decision correctness and recognition accuracy
were explicitly outside this validation.

| Case | Terminal outcome | Reason |
| --- | --- | --- |
| CA-R30-009 | `ABSTAIN` | `no_candidates` |
| CA-R30-017 | `ABSTAIN` | `none_verified` |
| CA-R30-022 | `ABSTAIN` | `none_verified` |
| CA-R30-026 | `ABSTAIN` | conflicting evidence cannot be sent to catalogue retrieval |
| CA-R30-029 | `ABSTAIN` | `no_candidates` |

## Accounting and boundary

One earlier interrupted `CA-R30-017` in-flight attempt remains unknown and
unaccounted environmental work. It is excluded from confirmed provider success
and failure accounting. The five durable records above are the evidence for
this disposition.

Checkpoint joining is expected to reject this run because the existing join
invariant requires all 30 Recognition30 case IDs; this was deliberately a
five-case standalone validation, not a 30-case Recognition30 run.

**SUPPORTED:** the previously observed provider structured-output /
`max_output_tokens` infrastructure-failure class is not reproduced across the
five targeted cases under the repaired current configuration.

**NOT SUPPORTED:** treating these five records as replacements in the
historical official baseline; deriving a reconciled 30-case accuracy result;
claiming current Recognition30 accuracy; or claiming the historical and
current recognition semantics are identical.

The historical official baseline remains immutable historical evidence.
