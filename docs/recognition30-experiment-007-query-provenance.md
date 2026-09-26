# Recognition30 E7 query provenance attestation

Status: `OWNER_ATTESTED_QUERY_PROVENANCE_ONLY`

## Attestation

On 2026-09-26, the Recognition30 dataset owner stated that they personally
took all photographs used as Recognition30 query images.

This is an owner attestation about the origin/authorship of the query
photographs. It is recorded as provenance evidence for E7.

## What this establishes

- The Recognition30 query photographs were captured by the dataset owner.
- They are not merely unattributed images of unknown origin.
- E7 leakage review may cite this attestation as query-side provenance.

## What this does not establish

This attestation alone does **not** set any reference-side leakage declaration
to `false`.

In particular, it does not independently prove that:

- a Numista reference is not the same image as a Recognition30 query image;
- a Numista reference was not derived from a Recognition30 query image; or
- a Numista reference depicts a different physical specimen.

Those determinations still require the evidence defined by
`docs/recognition30-experiment-007-leakage-audit.md`. The physical-specimen
question remains especially distinct from photographic authorship.

## E7 boundary

No image download, image hashing, embedding inference, model acquisition,
production retriever change, or E7 execution authorization is granted by this
attestation.

The current leakage manifest remains fail-closed until its declarations are
updated from sufficient evidence.
