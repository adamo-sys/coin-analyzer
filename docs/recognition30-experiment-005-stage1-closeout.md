# Recognition30 Experiment 5 Stage 1 closeout

## Disposition

`EXPERIMENT_5_STAGE1_EXPAND_NOT_SUPPORTED`

Stage 1 is closed.  No Experiment 5 expansion is approved, active, or
required by this record.  The result is evidence about the bounded observation
contract comparison only; it does not authorize a recognition, verifier, or
provider behavior change.

## Immutable execution evidence

- Canonical main at execution: `15f6d8955c1886bb5bec5ace883e7cd048b43603`.
- Frozen dataset fingerprint (`recognition30-dataset-fingerprint-v1`):
  `5ce59a80db35b58950358eb3441cdd78b350f5bcecf0326678202366ab737a20`.
- Control prompt SHA-256:
  `24b80fc6ac26d4f94cb7380a2102c5f423bd7b2763d9a5e8c940235d5f136b17`.
- Treatment prompt SHA-256:
  `c3a18771d8103e55ffad72f19e98da572c08d71749732dd1cd8cba7682972a60`.
- Run directory (private, immutable, and intentionally outside Git):
  `C:\Projects\recognition30-runs\recognition30-v1-experiment-005-stage1-pilot-execution-001`.
- `request_manifest.json` SHA-256:
  `68073DF1C2DF7A88D45E097B9E2B645F1AC2A9DEA3DC34634B096EDF49328ADF`.
- `observation_records.jsonl` SHA-256:
  `5309AD8D98103F51F6F2D597D954117626E0607052C6C3AFEAA83FD7298696FD`.
- `evaluation.json` SHA-256:
  `17E84D7EFE51871DFA97DD8CE9FCB7D88D1BD4BA97053E9AB162CCC05F5A2298`.

The pilot preflight planned 16 requests with zero provider calls.  Execution
made 16 attempts: 16 successful observations, zero malformed/contract
failures, zero timeout/connection/status failures, and 16 durable terminal
records (unique sequences 1–16).  No retries occurred and no attempt exceeded
the authorized 16.  Ground truth was used only by the offline evaluator, never
in a provider request.  The frozen dataset and official baseline were not
modified.

## Findings

- **CA-R30-030:** Control preserved visible `SIXPENCE` but did not emit a
  `denomination_mark`, and emitted incorrect `date_like=1967`.  Treatment
  preserved visible `SIXPENCE` but emitted neither a denomination mark nor a
  date.  It therefore did not improve correct literal structured denomination
  or date capture.
- **CA-R30-011:** Both arms preserved the legitimate
  `denomination_mark=10 ÖRE`; neither emitted a date.  Treatment did not
  damage the denomination evidence.
- There was no treatment-only wrong structured evidence.  The evaluator's raw
  `10 ÖRE`/`10 ore` mismatch is a canonical-format difference recognized by the
  current deterministic downstream normalization.
- The offline CA-R30-030 replay found that control retrieved CA-R30-029 and
  CA-R30-030, ranked the correct candidate second, and conflicted on the wrong
  year before abstaining.  Treatment retrieved only CA-R30-030 and removed the
  year conflict, but supplied only visible-text support—not strong
  denomination/date support—so verification and the final two-side gate still
  abstained.

Treatment's avoidance of the false control date is insufficient to justify a
larger paid comparison because it produced no material correct structured
denomination/date capture on the target cases.
